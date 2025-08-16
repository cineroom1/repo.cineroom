import sys
import urllib.parse
import xbmcgui
import xbmcplugin
import urllib.request
import threading
import json
import xbmc
import xbmcvfs
import threading
import hashlib
import time # Adicionado para time.sleep
import urllib.error # Adicionado para urllib.error.HTTPError
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from resources.lib.utils import get_all_videos
from urllib.parse import urlencode, parse_qsl
from resources.action.favorites import load_favorites
from resources.action.video_listing import create_video_item
from resources.lib.utils import get_all_videos, VIDEO_CACHE
from resources.lib.utils_view import set_view_mode



HANDLE = int(sys.argv[1])
URL = sys.argv[0]

def get_url(**kwargs) -> str:
    params = {}
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            params[key] = json.dumps(value)
        else:
            params[key] = value
    return f"{URL}?{urlencode(params)}"

GENRES_SERIES = [
    {'name': 'Ação', 'key': 'Ação'},
    {'name': 'Animação', 'key': 'Animação'},
    {'name': 'Aventura', 'key': 'Aventura'}, 
    {'name': 'Cinema TV', 'key': 'Cinema TV'},
    {'name': 'Comédia', 'key': 'Comédia'},
    {'name': 'Crime', 'key': 'Crime'},
    {'name': 'Documentário', 'key': 'Documentário'},
    {'name': 'Drama', 'key': 'Drama'},
    {'name': 'Fantasia', 'key': 'Fantasia'}, 
    {'name': 'Faroeste', 'key': 'Faroeste'},
    {'name': 'Ficção Cientifica', 'key': 'Ficção Cientifica'},
    {'name': 'Família', 'key': 'Família'},
    {'name': 'Guerra', 'key': 'Guerra'},
    {'name': 'História', 'key': 'História'},
    {'name': 'Mistério', 'key': 'Mistério'}, 
    {'name': 'Música', 'key': 'Música'},
    {'name': 'Romance', 'key': 'Romance'},
    {'name': 'Terror', 'key': 'Horror'},
    {'name': 'Thriller', 'key': 'Thriller'}
    # Adicione mais gêneros conforme necessário
]

def list_series_genres():
    """
    Lista os gêneros de séries pré-definidos.
    """
    xbmcplugin.setPluginCategory(HANDLE, 'Gêneros de Séries')
    xbmcplugin.setContent(HANDLE, "genres")

    for genre in GENRES_SERIES:
        list_item = xbmcgui.ListItem(label=genre['name'])
        list_item.setInfo('video', {'title': genre['name']})
        
        # Gera a URL para listar séries do gênero específico
        url = get_url(action='list_series_by_genre', genre=genre['key'])
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
    

def list_series_by_genre(genre, page=1, items_per_page=70):
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 200))
        genre = urllib.parse.unquote(genre)
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def normalize_genre(g):
        return g.lower().strip().replace(" ", "").replace("-", "")

    genre_info = next((g for g in GENRES_SERIES 
                     if normalize_genre(g['name']) == normalize_genre(genre) or 
                     normalize_genre(g['key']) == normalize_genre(genre)), None)
    
    if not genre_info:
        xbmcgui.Dialog().ok("Erro", f"Gênero '{genre}' não encontrado.")
        return

    genre_name = genre_info['name']
    normalized_genre = normalize_genre(genre_name)
    
    def get_genre_series():
        cache_key = f"series_genre_{normalized_genre}_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_series = get_all_videos()
        filtered = [
            s for s in all_series
            if (s.get('type') == 'tvshow' and
                any(normalized_genre == normalize_genre(g)
                    for g in s.get('genres', [])))
        ]
        
        seen_titles = set()
        unique_series = []
        for serie in filtered:
            if serie.get('title') not in seen_titles:
                unique_series.append(serie)
                seen_titles.add(serie['title'])
        
        VIDEO_CACHE.set(cache_key, json.dumps(unique_series), expiry_hours=12)
        return unique_series

    try:
        series = get_genre_series()
        
        if not series:
            xbmcgui.Dialog().ok("Aviso", f"Nenhuma série encontrada no gênero {genre_name}.")
            return

        xbmcplugin.setPluginCategory(HANDLE, genre_name)
        xbmcplugin.setContent(HANDLE, 'tvshows')

        start = (page - 1) * items_per_page
        end = start + items_per_page
        for serie in series[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE,serie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        if end < len(series):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(
                action='list_series_by_genre', 
                genre=genre_name,
                page=page + 1, 
                items_per_page=items_per_page
            )
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)
            
        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_series_by_genre: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)
    
    
def list_series_studios():
    """
    Lista os estúdios de séries disponíveis (lista pré-definida).
    """
    xbmcplugin.setPluginCategory(HANDLE, 'Estúdios de Séries')
    xbmcplugin.setContent(HANDLE, "genres")

    # Lista de estúdios pré-definida
    STUDIOS = [
        "Netflix",
        "HBO",
        "HBO Max",
        "Amazon",
        "Disney+",
        "Apple TV+",
        "Paramount+",
        "Hulu",
        "Globoplay",
        "Crunchyroll",
        "Disney Channel",
        "Cartoon Network",
        "Outros"
    ]

    # Exibe os estúdios na interface
    for studio in STUDIOS:
        list_item = xbmcgui.ListItem(label=studio)
        list_item.setInfo('video', {'title': studio})
        
        # Gera a URL para listar séries do estúdio específico
        url = get_url(action='list_series_by_studio', studio=studio)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_series_by_studio(studio):
    """
    Lista as séries de um determinado estúdio usando create_video_item.
    """
    try:
        xbmcplugin.setPluginCategory(HANDLE, f'Séries - {studio}')
        xbmcplugin.setContent(HANDLE, 'tvshows')

        series = get_all_videos()
        if not series:
            xbmcgui.Dialog().ok("Erro", "Nenhuma série encontrada.")
            return

        filtered_series = []
        for serie in series:
            if (serie.get('type') == 'tvshow' and 
                isinstance(serie.get('studio'), list) and 
                studio in serie['studio']):
                filtered_series.append(serie)

        if not filtered_series:
            xbmcgui.Dialog().ok("Aviso", f"Nenhuma série encontrada para o estúdio {studio}.")
            return

        for serie in filtered_series:
            list_item, url, is_folder = create_video_item(HANDLE,serie)
            if list_item and url:
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_series_by_studio: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Falha ao listar séries por estúdio", xbmcgui.NOTIFICATION_ERROR)
    
def list_series_by_rating(page=1, items_per_page=100):
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 200))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_rated_series():
        cache_key = "series_by_rating_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_series = get_all_videos()
        filtered = [s for s in all_series if s.get('type') == 'tvshow']
        
        seen_titles = set()
        unique_series = []
        for serie in filtered:
            if serie.get('title') not in seen_titles:
                unique_series.append(serie)
                seen_titles.add(serie['title'])
        
        unique_series.sort(key=lambda x: x.get('rating', 0), reverse=True)
        
        VIDEO_CACHE.set(cache_key, json.dumps(unique_series), expiry_hours=12)
        return unique_series

    try:
        series = get_rated_series()
        
        if not series:
            xbmcgui.Dialog().ok("Aviso", "Nenhuma série encontrada.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Melhor Avaliação')
        xbmcplugin.setContent(HANDLE, 'tvshows')

        start = (page - 1) * items_per_page
        end = start + items_per_page
        for serie in series[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE,serie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        if end < len(series):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(
                action='list_series_by_rating',
                page=page + 1,
                items_per_page=items_per_page
            )
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_series_by_rating: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)
    
def list_series_by_specific_year(year):
    def get_year_series():
        cache_key = f"series_year_{year}_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_series = get_all_videos()
        filtered = [
            s for s in all_series
            if s.get('type') == 'tvshow' and s.get('year') == year
        ]
        
        seen_titles = set()
        unique_series = []
        for serie in filtered:
            if serie.get('title') not in seen_titles:
                unique_series.append(serie)
                seen_titles.add(serie['title'])
        
        VIDEO_CACHE.set(cache_key, json.dumps(unique_series), expiry_hours=24)
        return unique_series

    try:
        series = get_year_series()
        title = f"Séries de {year}"
        
        if not series:
            xbmcgui.Dialog().ok("Aviso", f"Nenhuma série encontrada para {title}.")
            return

        xbmcplugin.setPluginCategory(HANDLE, title)
        xbmcplugin.setContent(HANDLE, 'tvshows')

        for serie in series:
            list_item, url, is_folder = create_video_item(HANDLE,serie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_series_by_specific_year: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)
    
def list_series_by_popularity(page=1, items_per_page=70):
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 200))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_popular_series():
        cache_key = "popular_series_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_series = get_all_videos()
        filtered = [s for s in all_series if s.get('type') == 'tvshow']
        
        seen_titles = set()
        unique_series = []
        for serie in filtered:
            if serie.get('title') not in seen_titles:
                unique_series.append(serie)
                seen_titles.add(serie['title'])
        
        unique_series.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        
        VIDEO_CACHE.set(cache_key, json.dumps(unique_series), expiry_hours=12)
        return unique_series

    try:
        series = get_popular_series()
        
        if not series:
            xbmcgui.Dialog().ok("Aviso", "Nenhuma série encontrada.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Séries Mais Populares')
        xbmcplugin.setContent(HANDLE, 'tvshows')

        start = (page - 1) * items_per_page
        end = start + items_per_page
        for serie in series[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE,serie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        if end < len(series):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(
                action='list_series_by_popularity',
                page=page + 1,
                items_per_page=items_per_page
            )
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_series_by_popularity: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)


def list_anime_series(page=1, items_per_page=70):
    """
    Lista as séries que têm "Anime" no campo de gêneros, ordenadas por popularidade com cache.
    """
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 200))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_cached_anime_series():
        cache_key = "anime_series_v2"
        cached = VIDEO_CACHE.get(cache_key)
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)

        videos = get_all_videos()
        anime_series = [v for v in videos if v.get('type') == 'tvshow' and 'Anime' in v.get('genres', [])]
        anime_series = sorted(anime_series, key=lambda s: s.get('popularity', 0), reverse=True)

        VIDEO_CACHE.set(cache_key, json.dumps(anime_series), expiry_hours=12)
        return anime_series

    try:
        anime_series = get_cached_anime_series()

        if not anime_series:
            xbmcgui.Dialog().ok("Aviso", "Nenhuma série de anime encontrada.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Animes')
        xbmcplugin.setContent(HANDLE, 'tvshows')

        start = (page - 1) * items_per_page
        end = start + items_per_page
        for serie in anime_series[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE, serie)
            if list_item and url:
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)

        if end < len(anime_series):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(
                action='list_anime_series',
                page=page + 1,
                items_per_page=items_per_page
            )
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_anime_series: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Ocorreu um erro ao listar animes", xbmcgui.NOTIFICATION_ERROR)

    
def list_novela_series(page=1, items_per_page=70):
    """
    Lista as séries que têm "Novela" no campo de gêneros, ordenadas por popularidade com cache.
    """
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 200))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_cached_novela_series():
        cache_key = "novela_series_v2"
        cached = VIDEO_CACHE.get(cache_key)
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)

        videos = get_all_videos()
        novela_series = [v for v in videos if v.get('type') == 'tvshow' and 'Novela' in v.get('genres', [])]
        novela_series = sorted(novela_series, key=lambda s: s.get('popularity', 0), reverse=True)

        VIDEO_CACHE.set(cache_key, json.dumps(novela_series), expiry_hours=12)
        return novela_series

    try:
        novela_series = get_cached_novela_series()

        if not novela_series:
            xbmcgui.Dialog().ok("Aviso", "Nenhuma novela encontrada.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Novelas')
        xbmcplugin.setContent(HANDLE, 'tvshows')

        # Paginação
        start = (page - 1) * items_per_page
        end = start + items_per_page
        for serie in novela_series[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE, serie)
            if list_item and url:
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)
            else:
                xbmc.log(f"Falha ao criar item para: {serie.get('title', 'Desconhecido')}", xbmc.LOGERROR)

        # Adiciona item para próxima página, se houver
        if end < len(novela_series):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(
                action='list_novela_series',
                page=page + 1,
                items_per_page=items_per_page
            )
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_novela_series: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Ocorreu um erro ao listar novelas", xbmcgui.NOTIFICATION_ERROR)

    
 
def list_recently_added_series():
    def get_recent_series():
        cache_key = "recent_series_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_series = get_all_videos()
        filtered = [
            s for s in all_series
            if s.get('type') == 'tvshow' and s.get('date_added')
        ]
        
        seen_titles = set()
        unique_series = []
        for serie in filtered:
            if serie.get('title') not in seen_titles:
                unique_series.append(serie)
                seen_titles.add(serie['title'])
        
        unique_series.sort(key=lambda x: x['date_added'], reverse=True)
        
        VIDEO_CACHE.set(cache_key, json.dumps(unique_series), expiry_hours=1)
        return unique_series

    try:
        series = get_recent_series()
        
        if not series:
            xbmcgui.Dialog().ok("Aviso", "Nenhuma série adicionada recentemente.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Adicionadas Recentemente')
        xbmcplugin.setContent(HANDLE, 'tvshows')

        for serie in series:
            list_item, url, is_folder = create_video_item(HANDLE,serie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_recently_added_series: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)
    
def list_kids_series():
    """
    Lista as séries classificadas como infantis (Kids), ordenadas por popularidade.
    """
    try:
        xbmcplugin.setPluginCategory(HANDLE, 'Infantil')
        xbmcplugin.setContent(HANDLE, 'tvshows')

        videos = get_all_videos()
        if not videos:
            xbmcgui.Dialog().ok("Erro", "Nenhum vídeo encontrado.")
            return

        # Filtra e remove duplicados
        kids_series = [
            video for video in videos
            if video.get('type') == 'tvshow' and video.get('classification') in ['L', 'Kids', '10']
        ]
        
        unique_series = []
        seen_ids = set()
        for serie in kids_series:
            tmdb_id = serie.get('tmdb_id')
            if tmdb_id and tmdb_id not in seen_ids:
                unique_series.append(serie)
                seen_ids.add(tmdb_id)

        if not unique_series:
            xbmcgui.Dialog().ok("Aviso", "Nenhuma série infantil encontrada.")
            return

        # Ordena por popularidade
        unique_series = sorted(unique_series, key=lambda s: s.get('popularity', 0), reverse=True)

        # Cria itens para cada série
        for serie in unique_series:
            list_item, url, is_folder = create_video_item(HANDLE, serie)
            if list_item and url:
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)
            else:
                xbmc.log(f"Falha ao criar item para: {serie.get('title', 'Desconhecido')}", xbmc.LOGERROR)

        # Métodos de ordenação do Kodi (opcional)
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_kids_series: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Falha ao listar séries infantis", xbmcgui.NOTIFICATION_ERROR)


def list_recently_added_episodes():
    """
    Lista os episódios recém-adicionados agrupados por série, ordenados por data de adição.
    """
    xbmcplugin.setPluginCategory(HANDLE, 'Episódios Recentes')
    xbmcplugin.setContent(HANDLE, 'episodes')
    
    ICON_URL = 'https://i.imgur.com/3yRk5Yp.png'

    try:
        series = get_all_videos()
        if not series:
            xbmcgui.Dialog().ok("Erro", "Nenhum conteúdo encontrado.")
            xbmcplugin.endOfDirectory(HANDLE)
            return

        series_dict = {}

        for serie in series:
            try:
                if serie.get('type') != 'tvshow':
                    continue

                titulo_serie = serie.get('title', 'Sem título')
                if titulo_serie not in series_dict:
                    series_dict[titulo_serie] = {
                        'poster': serie.get('poster', ''),
                        'backdrop': serie.get('backdrop', ''),
                        'episodes': []
                    }

                for temporada in serie.get('temporadas', []):
                    for ep in temporada.get('episodios', []):
                        if isinstance(ep, dict) and ep.get('date_added'):
                            url = ep.get('url', '')
                            if isinstance(url, list):
                                url = url[0] if url else ''

                            if url:  # Só adiciona se tiver URL válida
                                series_dict[titulo_serie]['episodes'].append({
                                    'titulo_ep': ep.get('title', 'Sem título'),
                                    'temporada': temporada.get('title', ''),
                                    'url': url,
                                    'poster': ep.get('poster', serie.get('poster', '')),
                                    'date_added': ep.get('date_added'),
                                    'studio': serie.get('studio', []),
                                    'genres': serie.get('genres', [])
                                })
            except Exception as serie_error:
                xbmc.log(f"Erro ao processar série {serie.get('title')}: {str(serie_error)}", xbmc.LOGERROR)

        # Filtra séries que têm episódios
        valid_series = {k: v for k, v in series_dict.items() if v['episodes']}
        
        if not valid_series:
            xbmcgui.Dialog().ok("Aviso", "Nenhum episódio recente encontrado.")
            xbmcplugin.endOfDirectory(HANDLE)
            return

        # Ordena séries pela data do episódio mais recente (com tratamento para sequências vazias)
        def get_latest_date(episodes):
            if not episodes:
                return ''
            try:
                return max(ep['date_added'] for ep in episodes)
            except ValueError:
                return ''

        sorted_series = sorted(valid_series.items(),
                             key=lambda x: get_latest_date(x[1]['episodes']),
                             reverse=True)

        for serie_title, serie_data in sorted_series:
            try:
                episodes_sorted = sorted(serie_data['episodes'],
                                       key=lambda x: x['date_added'],
                                       reverse=True)[:10]  # Limita a 10 episódios por série

                list_item = xbmcgui.ListItem(label=serie_title)
                list_item.setArt({
                    'thumb': serie_data['poster'],
                    'fanart': serie_data['backdrop'],
                    'icon': ICON_URL
                })
                
                list_item.setInfo('video', {
                    'title': serie_title,
                    'mediatype': 'tvshow',
                    'plot': f"{serie_title}\n\n{len(episodes_sorted)} episódios recentes"
                })

                serie_url = get_url(action='list_series_episodes', serie=serie_title)
                xbmcplugin.addDirectoryItem(HANDLE, serie_url, list_item, isFolder=True)
            except Exception as item_error:
                xbmc.log(f"Erro ao criar item para série {serie_title}: {str(item_error)}", xbmc.LOGERROR)

        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)

    except Exception as global_error:
        xbmc.log(f"Erro global em list_recently_added_episodes: {str(global_error)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", "Ocorreu um erro ao carregar os episódios.")
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def list_series_episodes(serie_title):
    """
    Lista os episódios de uma série específica
    """
    xbmcplugin.setPluginCategory(HANDLE, serie_title)
    xbmcplugin.setContent(HANDLE, 'episodes')
    
    try:
        series = get_all_videos()
        found = False
        
        for serie in series:
            if serie.get('title') == serie_title and serie.get('type') == 'tvshow':
                found = True
                poster_serie = serie.get('poster', '')
                backdrop = serie.get('backdrop', '')
                
                for temporada in serie.get('temporadas', []):
                    for ep in temporada.get('episodios', []):
                        if isinstance(ep, dict) and ep.get('date_added'):
                            try:
                                url = ep.get('url', '')
                                if isinstance(url, list):
                                    url = url[0] if url else ''

                                if not url:
                                    continue

                                ep_title = ep.get('title', 'Sem título')
                                ep_num = ''
                                
                                if 'x' in ep_title and '.' in ep_title:
                                    parts = ep_title.split('.', 1)
                                    ep_num = parts[0].strip()
                                    ep_title = parts[1].strip()
                                
                                label = f"{temporada.get('title', '')} - {ep_num} {ep_title}"
                                if ep.get('date_added'):
                                    label += f" [COLOR=gray]({ep['date_added'].split()[0]})[/COLOR]"
                                
                                list_item = xbmcgui.ListItem(label=label)
                                list_item.setArt({
                                    'thumb': ep.get('poster', temporada.get('poster', poster_serie)),
                                    'fanart': backdrop,
                                    'icon': poster_serie
                                })
                                
                                info = {
                                    'title': ep_title,
                                    'tvshowtitle': serie_title,
                                    'season': temporada.get('title', '').replace('ª Temporada', '').strip(),
                                    'episode': ep_num.split('x')[1] if 'x' in ep_num else '',
                                    'studio': ', '.join(serie.get('studio', [])),
                                    'genre': ', '.join(serie.get('genres', [])),
                                    'dateadded': ep.get('date_added', ''),
                                    'mediatype': 'episode',
                                    'plot': f"Série: {serie_title}\nTemporada: {temporada.get('title', '')}\nEpisódio: {ep_num}\n{ep_title}"
                                }
                                list_item.setInfo('video', info)
                                list_item.setProperty('IsPlayable', 'true')
                                
                                play_url = get_url(action='play', video=url)
                                xbmcplugin.addDirectoryItem(HANDLE, play_url, list_item, isFolder=False)
                            except Exception as ep_error:
                                xbmc.log(f"Erro ao processar episódio {ep.get('title')}: {str(ep_error)}", xbmc.LOGERROR)
                
                break

        if not found:
            xbmcgui.Dialog().ok("Erro", f"Série '{serie_title}' não encontrada.")
        
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_DATEADDED)
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_EPISODE)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=found)

    except Exception as global_error:
        xbmc.log(f"Erro global em list_series_episodes: {str(global_error)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", "Ocorreu um erro ao carregar os episódios.")
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        
def list_series_recommendations(page=1, items_per_page=70):
    """
    Gera e exibe uma lista de séries recomendadas com base nos favoritos do usuário.
    """
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 100))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_and_sort_recommendations():
        """Obtém e ordena séries recomendadas, com cache."""
        all_favorites = load_favorites()
        # Filtra apenas os favoritos que são séries
        user_favorites = [m for m in all_favorites if m.get('type') == 'tvshow']

        if not user_favorites:
            return []

        favorite_titles = sorted([s.get('title', '') for s in user_favorites])
        cache_key = "series_recommendations_" + hashlib.md5(json.dumps(favorite_titles).encode('utf-8')).hexdigest()

        cached_recommendations = VIDEO_CACHE.get(cache_key)

        if cached_recommendations and not VIDEO_CACHE.is_expired(cache_key):
            xbmc.log("[DEBUG] Carregando recomendações de séries do cache.", xbmc.LOGINFO)
            return json.loads(cached_recommendations)

        xbmc.log("[DEBUG] Calculando novas recomendações de séries.", xbmc.LOGINFO)

        # Lógica de análise de preferências de séries
        genres_count = {}
        actors_count = {}
        keywords_count = {}
        for serie in user_favorites:
            genres = serie.get('genres', [])
            if genres:
                first_genre = genres[0]
                genres_count[first_genre] = genres_count.get(first_genre, 0) + 2
                for other_genre in genres[1:]:
                    genres_count[other_genre] = genres_count.get(other_genre, 0) + 1
            
            for actor in serie.get('actors', []):
                actors_count[actor] = actors_count.get(actor, 0) + 1
            for keyword in serie.get('keywords', []):
                keywords_count[keyword] = keywords_count.get(keyword, 0) + 1

        all_series = [s for s in get_all_videos() if s.get('type') == 'tvshow']
        recommendations = []
        favorite_tmdb_ids = {s.get('tmdb_id') for s in user_favorites}

        for serie in all_series:
            if serie.get('tmdb_id') in favorite_tmdb_ids:
                continue

            score = 0
            
            for genre in serie.get('genres', []):
                score += genres_count.get(genre, 0) * 1.5
            for actor in serie.get('actors', []):
                score += actors_count.get(actor, 0) * 1.0
            for keyword in serie.get('keywords', []):
                score += keywords_count.get(keyword, 0) * 0.5
            
            if score > 0:
                serie['recommendation_score'] = score
                recommendations.append(serie)

        recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        top_recommendations = recommendations[:1000]

        VIDEO_CACHE.set(cache_key, json.dumps(top_recommendations), expiry_hours=24)
        return top_recommendations

    try:
        recommendations = get_and_sort_recommendations()

        if not recommendations:
            xbmcgui.Dialog().ok("Aviso", "Nenhuma série recomendada encontrada. Adicione mais séries aos favoritos!")
            xbmcplugin.endOfDirectory(HANDLE)
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Recomendações de Séries')
        xbmcplugin.setContent(HANDLE, 'tvshows')
        
        start = (page - 1) * items_per_page
        end = start + items_per_page

        for serie in recommendations[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE,serie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        if end < len(recommendations):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(action='list_series_recommendations', page=page + 1, items_per_page=items_per_page)
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_series_recommendations: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)        