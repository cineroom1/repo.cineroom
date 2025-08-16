import sys
import urllib.parse
import xbmcgui
import xbmcplugin
import json
import xbmc
import hashlib
import os
import xbmcvfs
import random
import urllib.request
import threading
import time # Adicionado para time.sleep
import urllib.error # Adicionado para urllib.error.HTTPError
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from datetime import datetime, timedelta
from datetime import datetime


from resources.action.video_listing import create_video_item, list_videos
from resources.action.favorites import load_favorites
from resources.lib.utils_view import set_view_mode

from resources.lib.utils import ( 
    get_all_videos, VIDEO_CACHE
)    

from resources.action.constants import (
    PROVEDORES, ESTUDIOS_FILMES, GENRES, KEYWORDS,
    IDIOMA_NOMES, IDIOMA_PARA_PAIS, ANOS_FILMES
)




import xbmcaddon
addon = xbmcaddon.Addon()

use_tmdb = addon.getSettingBool("use_tmdb_art")  # definir essa opção no settings.xml do seu addon

HANDLE = int(sys.argv[1])


def list_countries():
    """
    Lista os países/idiomas de origem disponíveis dos filmes,
    mostrando apenas aqueles que estão no mapeamento IDIOMA_NOMES,
    com bandeira ao lado do nome.
    """
    xbmcplugin.setPluginCategory(HANDLE, 'Filmes por País')
    xbmcplugin.setContent(HANDLE, 'videos')

    all_videos = get_all_videos()
    unique_languages_in_data = set()
    for movie in all_videos:
        if movie.get('type') == 'movie' and movie.get('original_language'):
            unique_languages_in_data.add(movie['original_language'])

    if not unique_languages_in_data:
        xbmcgui.Dialog().ok("Aviso", "Nenhum idioma original encontrado para os filmes.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    displayable_languages = [
        lang_code for lang_code in unique_languages_in_data 
        if lang_code in IDIOMA_NOMES
    ]

    if not displayable_languages:
        xbmcgui.Dialog().ok("Aviso", "Nenhum idioma reconhecido encontrado para os filmes. Verifique o dicionário IDIOMA_NOMES.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    sorted_languages_to_display = sorted(displayable_languages, key=lambda x: IDIOMA_NOMES[x])

    for lang_code in sorted_languages_to_display:
        display_name = IDIOMA_NOMES[lang_code]
        url = get_url(action='list_movies_by_country', country_code=lang_code)
        list_item = xbmcgui.ListItem(label=display_name)
        list_item.setInfo('video', {'title': display_name})

        # Adiciona imagem da bandeira
        country_code = IDIOMA_PARA_PAIS.get(lang_code, lang_code)
        flag_url = f"https://flagcdn.com/w320/{country_code}.png"
        list_item.setArt({
            'icon': flag_url,
            'thumb': flag_url,
            'poster': flag_url
        })


        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
    set_view_mode()


def get_url(action, **kwargs):
    """
    Gera uma URL para chamar ações dentro do addon.
    """
    return f"{sys.argv[0]}?action={action}&{urllib.parse.urlencode(kwargs)}"


def list_movies_by_keyword(keyword, page=1, items_per_page=70):
    def normalize_kw(k):
        if not k:
            return ""
        # Remove caracteres especiais e deixa tudo minúsculo
        return ''.join(e for e in str(k).lower() if e.isalnum())
    
    # Normaliza a keyword de busca
    search_key = normalize_kw(keyword)
    
    # Encontra a keyword na lista KEYWORDS
    keyword_info = next((k for k in KEYWORDS if normalize_kw(k['key']) == search_key), None)
    
    if not keyword_info:
        xbmcgui.Dialog().ok("Erro", f"Palavra-chave '{keyword}' não encontrada.")
        return

    keyword_name = keyword_info['name']
    cache_key = f"keyword_{search_key}_v2"  # Atualizei a versão do cache para forçar refresh
    
    try:
        # Verifica o cache
        cached = VIDEO_CACHE.get(cache_key)
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            movies = json.loads(cached)
        else:
            all_movies = get_all_videos()
            movies = []
            
            for movie in all_movies:
                if movie.get('type') != 'movie':
                    continue
                
                # Normaliza todas as keywords do filme para comparação
                movie_keywords = [normalize_kw(kw) for kw in movie.get('keywords', [])]
                
                # Verifica se a keyword normalizada está nas keywords do filme
                if search_key in movie_keywords:
                    movies.append(movie)
            
            # Armazena no cache
            VIDEO_CACHE.set(cache_key, json.dumps(movies), expiry_hours=12)
            
    except Exception as e:
        xbmc.log(f"Erro ao processar filmes por keyword: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Ocorreu um erro ao buscar os filmes", xbmcgui.NOTIFICATION_ERROR)
        return

    if not movies:
        xbmcgui.Dialog().notification("Aviso", f"Nenhum filme encontrado para '{keyword_name}'", xbmcgui.NOTIFICATION_WARNING)
        return

    # Ordena os filmes por rating e popularidade
    movies.sort(key=lambda x: (x.get('rating', 0) * 0.6 + x.get('popularity', 0) * 0.4), reverse=True)

    # Paginação
    start = (page - 1) * items_per_page
    end = start + items_per_page

    xbmcplugin.setPluginCategory(HANDLE, keyword_name)
    xbmcplugin.setContent(HANDLE, 'movies')

    # Adiciona os itens da página atual
    for movie in movies[start:end]:
        list_item, url, is_folder = create_video_item(HANDLE,movie)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

    # Adiciona link para próxima página se necessário
    if end < len(movies):
        next_item = xbmcgui.ListItem(label="Próxima Página >>")
        next_url = get_url(action='list_movies_by_keyword', keyword=keyword, page=page + 1)
        xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

    xbmcplugin.endOfDirectory(HANDLE)
    set_view_mode()


def list_keywords():
    xbmcplugin.setPluginCategory(HANDLE, 'Palavras-chave')
    xbmcplugin.setContent(HANDLE, 'genres')
    
    for keyword in KEYWORDS:
        list_item = xbmcgui.ListItem(label=keyword['name'])
        url = get_url(action='list_movies_by_keyword', keyword=keyword['key'])
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)
    
    xbmcplugin.endOfDirectory(HANDLE)
    set_view_mode()


def list_movies_by_genre(genre, page=1, items_per_page=70):
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 200))
        genre = urllib.parse.unquote(genre)
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def normalize_genre(g):
        return g.lower().strip().replace(" ", "").replace("-", "")

    genre_info = next((g for g in GENRES 
                     if normalize_genre(g['name']) == normalize_genre(genre) or 
                     normalize_genre(g['key']) == normalize_genre(genre)), None)
    
    if not genre_info:
        xbmcgui.Dialog().ok("Erro", f"Gênero '{genre}' não encontrado.")
        return

    genre_name = genre_info['name']
    normalized_genre = normalize_genre(genre_name)
    
    def get_genre_movies():
        cache_key = f"genre_{normalized_genre}_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_movies = get_all_videos()
        filtered = [
            movie for movie in all_movies
            if (movie.get('type') == 'movie' and 
                '(4K)' not in movie.get('title', '') and
                any(normalized_genre == normalize_genre(g)
                    for g in movie.get('genres', [])))
        ]
        
        seen_ids = set()
        unique_movies = []
        for movie in filtered:
            tmdb_id = movie.get('tmdb_id')
            if tmdb_id and tmdb_id not in seen_ids:
                unique_movies.append(movie)
                seen_ids.add(tmdb_id)
        
        unique_movies.sort(
            key=lambda x: (x.get('rating', 0) * 0.7 + x.get('popularity', 0) * 0.3),
            reverse=True
        )
        
        VIDEO_CACHE.set(cache_key, json.dumps(unique_movies), expiry_hours=12)
        return unique_movies

    try:
        movies = get_genre_movies()
        
        if not movies:
            xbmcgui.Dialog().ok("Aviso", f"Nenhum filme encontrado no gênero {genre_name}.")
            return

        xbmcplugin.setPluginCategory(HANDLE, genre_name)
        xbmcplugin.setContent(HANDLE, 'movies')

        start = (page - 1) * items_per_page
        end = start + items_per_page
        for movie in movies[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE,movie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        if end < len(movies):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(
                action='list_movies_by_genre', 
                genre=genre_name,
                page=page + 1, 
                items_per_page=items_per_page
            )
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)
            
        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_movies_by_genre: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)
    
    
    
def list_movies_by_studio(studio):
    """
    Lista os filmes de um determinado estúdio.
    """
    def studio_criteria(movie, value):
        # Remove espaços extras e converte para minúsculas
        value = value.strip().lower()
        studios = movie.get('studio', [])
        
        # Verifica se o estúdio está na lista de estúdios do filme
        return value in [s.strip().lower() for s in studios]
    
    # Filtra e lista os filmes
    filter_and_list_movies(studio_criteria, studio, f'{studio}')

def list_categories(categories, category_type):
    """
    Lista categorias (gêneros ou estúdios) e gera URLs para listar os filmes correspondentes.
    """
    xbmcplugin.setPluginCategory(HANDLE, category_type)
    xbmcplugin.setContent(HANDLE, "genres")

    for category in categories:
        list_item = xbmcgui.ListItem(label=category['name'] if isinstance(category, dict) else category)
        list_item.setInfo('video', {'title': category['name'] if isinstance(category, dict) else category})
        
        # Gera a URL para listar filmes da categoria específica
        url = get_url(
            action=f'list_movies_by_{category_type.lower()}',
            genre=category['key'] if isinstance(category, dict) else category
        )
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_genres():
    """
    Lista os gêneros de filmes pré-definidos.
    """
    list_categories(GENRES, 'genre')

def list_studios():
    """
    Lista todos os estúdios pré-programados e permite que o usuário escolha um.
    """
    # Configura a categoria e o conteúdo do plugin
    xbmcplugin.setPluginCategory(HANDLE, 'Estúdios')
    xbmcplugin.setContent(HANDLE, 'studios')

    # Adiciona os estúdios pré-programados à lista
    for studio in ESTUDIOS_FILMES:
        list_item = xbmcgui.ListItem(label=studio)
        list_item.setInfo('video', {'title': studio})
        
        # Gera a URL para listar filmes do estúdio específico
        url = get_url(action='list_movies_by_studio', studio=studio)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    # Finaliza a lista
    xbmcplugin.endOfDirectory(HANDLE)
    
def list_movies_by_year(year):
    """
    Lista os filmes de um determinado ano.
    """
    def year_criteria(movie, value):
        return movie.get('year', 0) == value  # Compara diretamente o ano do filme com o valor passado
    
    filter_and_list_movies(year_criteria, int(year), f'Ano: {year}')

def list_years():
    """
    Lista os anos pré-programados para filtrar os filmes.
    """
    xbmcplugin.setPluginCategory(HANDLE, 'Anos')
    xbmcplugin.setContent(HANDLE, "years")

    for year in ANOS_FILMES:
        list_item = xbmcgui.ListItem(label=str(year))
        list_item.setInfo('video', {'title': str(year)})
        
        # Gera a URL para listar filmes do ano específico
        url = get_url(action='list_movies_by_year', year=year)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
    
def filter_and_list_movies(criteria, value, title):
    """
    Filtra e lista os filmes com base em um critério (gênero, estúdio ou ano),
    ignorando filmes com '4K' ou '(4K)' no título.
    """
    xbmcplugin.setPluginCategory(HANDLE, f'{title}')
    xbmcplugin.setContent(HANDLE, 'movies')

    movies = get_all_videos()
    seen_movies = set()
    filtered_movies = []

    for movie in movies:
        movie_title = movie.get('title', '').lower()
        if (
            movie.get('type') == 'movie' and  # Garante que é um filme
            criteria(movie, value) and  # Verifica o critério (gênero, estúdio ou ano)
            movie.get('tmdb_id') not in seen_movies and  # Evita filmes duplicados
            '4k' not in movie_title and  # Ignora filmes com '4k' no título
            '(4k)' not in movie_title  # Ignora filmes com '(4k)' no título
        ):
            seen_movies.add(movie['tmdb_id'])
            filtered_movies.append(movie)

    if not filtered_movies:
        xbmcgui.Dialog().ok("Aviso", f"Nenhum filme encontrado para {title}.")
        return

    for movie in filtered_movies:
        list_item = xbmcgui.ListItem(label=movie['title'])
        list_item.setArt({
           'poster': movie['poster'],
           'fanart': movie['backdrop'],
           'clearlogo': movie.get('clearlogo', '')
        })
        list_item.setInfo('video', {
            'title': movie['title'],
            'plot': movie.get('synopsis', ''),
            'rating': movie.get('rating', 0),
            'year': movie.get('year', 0),
            'studio': ', '.join(movie.get('studio', [])),
            'duration': movie.get("runtime", 0),
            'genre': ', '.join(movie.get('genres', [])),
            "aired": movie.get("premiered", "Ano não disponível"),
            'mediatype': 'movie'
        })

        url = get_url(action='play', video=','.join(movie['url']), tmdb_id=movie.get('tmdb_id', '')) if 'url' in movie else ''
        list_item.setProperty("IsPlayable", "true")
        
        favorites = load_favorites()
        
        if any(fav['title'] == movie['title'] for fav in favorites):
            list_item.addContextMenuItems([
                ('Remover da sua lista', f'RunPlugin({get_url(action="remove_from_favorites", video=json.dumps(movie))})')
            ])
        else:
            list_item.addContextMenuItems([
                ('Adicionar a sua lista', f'RunPlugin({get_url(action="add_to_favorites", video=json.dumps(movie))})')
            ])
        
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=False)

    # Adiciona métodos de ordenação suportados pelo Kodi
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

    xbmcplugin.endOfDirectory(HANDLE)
    set_view_mode()
    
    
def list_movies_by_specific_year(year):
    def get_year_movies():
        cache_key = f"movies_year_{year}_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_movies = get_all_videos()
        unique_movies = []
        seen_ids = set()

        for movie in all_movies:
            if (movie.get('type') == 'movie'
                and movie.get('year') == year
                and movie.get('tmdb_id')
                and '(4K)' not in movie.get('title', '')):
                tmdb_id = movie['tmdb_id']
                if tmdb_id not in seen_ids:
                    unique_movies.append(movie)
                    seen_ids.add(tmdb_id)
        
        VIDEO_CACHE.set(cache_key, json.dumps(unique_movies), expiry_hours=24)
        return unique_movies

    try:
        movies = get_year_movies()
        title = f"Filmes de {year}"
        
        if not movies:
            xbmcgui.Dialog().ok("Aviso", f"Nenhum filme encontrado para {title}.")
            return

        xbmcplugin.setPluginCategory(HANDLE, title)
        xbmcplugin.setContent(HANDLE, 'movies')

        for movie in movies:
            list_item, url, is_folder = create_video_item(HANDLE,movie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_movies_by_specific_year: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)

    
def generate_url(action, **kwargs):
    return f"{sys.argv[0]}?action={action}&{urllib.parse.urlencode(kwargs)}"    
    
def list_movies_by_rating(page=1, items_per_page=70):
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 100))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_rated_movies():
        cache_key = "movies_by_rating_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_movies = get_all_videos()
        unique_movies = []
        seen_ids = set()
        
        for movie in all_movies:
            if (
                movie.get('type') == 'movie'
                and movie.get('vote_count', 0) > 500  # <-- filtro aqui
                and '(4K)' not in movie.get('title', '')
                and (tmdb_id := movie.get('tmdb_id'))
                and tmdb_id not in seen_ids
            ):
                seen_ids.add(tmdb_id)
                unique_movies.append(movie)
        
        unique_movies.sort(key=lambda x: x.get('rating', 0), reverse=True)
        top_movies = unique_movies[:300]  # Limite de 300 filmes

        VIDEO_CACHE.set(cache_key, json.dumps(top_movies), expiry_hours=12)
        return top_movies

    try:
        movies = get_rated_movies()
        
        if not movies:
            xbmcgui.Dialog().ok("Aviso", "Nenhum filme encontrado.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Melhor Avaliação')
        xbmcplugin.setContent(HANDLE, 'movies')

        start = (page - 1) * items_per_page
        end = start + items_per_page
        for movie in movies[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE,movie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        if end < len(movies):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(
                action='list_movies_by_rating',
                page=page + 1,
                items_per_page=items_per_page
            )
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_movies_by_rating: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)


    
def list_actors():
    """
    Lista todos os atores disponíveis (sem imagens) e permite ao usuário escolher um para ver os filmes/séries correspondentes.
    Exibe também a quantidade de vídeos de cada ator.
    """
    try:
        all_videos = get_all_videos()
    except Exception as e:
        xbmcgui.Dialog().ok("Erro", f"Erro ao obter vídeos: {str(e)}")
        return

    actor_counts = {}

    for video in all_videos:
        for actor in video.get("actors", []):
            if isinstance(actor, str):
                actor_name = actor.strip()
                if actor_name:
                    actor_counts[actor_name] = actor_counts.get(actor_name, 0) + 1

    if not actor_counts:
        xbmcgui.Dialog().ok("Aviso", "Nenhum ator encontrado.")
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Atores')
    xbmcplugin.setContent(HANDLE, 'actors')

    for actor_name in sorted(actor_counts.keys()):
        count = actor_counts[actor_name]
        label = f"{actor_name} ({count})"

        list_item = xbmcgui.ListItem(label=label)
        list_item.setInfo('video', {'title': actor_name})

        url = get_url(action='list_movies_by_actor', actor=actor_name)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def list_movies_by_actor(actor_name):
    """
    Lista os filmes/séries em que um ator específico participou.
    """
    try:
        all_videos = get_all_videos()
    except Exception as e:
        xbmcgui.Dialog().ok("Erro", f"Erro ao obter vídeos: {str(e)}")
        return

    # Filtra os vídeos em que o ator participou
    filtered_videos = []
    for video in all_videos:
        actors = video.get("actors", [])
        if any(actor.lower() == actor_name.lower() for actor in actors):
            filtered_videos.append(video)

    if not filtered_videos:
        xbmcgui.Dialog().ok("Resultado", f"Nenhum vídeo encontrado com o ator: {actor_name}")
        return

    xbmcplugin.setPluginCategory(HANDLE, f'Filmes com: {actor_name}')
    xbmcplugin.setContent(HANDLE, 'movies')

    for video in filtered_videos:
        list_item, url, is_folder = create_video_item(HANDLE,video)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)

    xbmcplugin.endOfDirectory(HANDLE)


def paginate_and_add_items(sorted_items, page, items_per_page, action_name):
    """
    Adiciona itens paginados ao Kodi e cria item 'Próxima Página' se necessário.

    :param sorted_items: lista completa de itens já ordenados
    :param page: página atual (int)
    :param items_per_page: quantidade de itens por página (int)
    :param action_name: nome da ação para montar a URL do próximo page
    """
    start = (page - 1) * items_per_page
    end = start + items_per_page

    for item in sorted_items[start:end]:
        title = item.get('title', '')
        if any('hdcam' in g.lower() for g in item.get('genres', [])):
            title = f"[COLOR red]{title}[/COLOR]"
        item['title'] = title
        list_item, url, is_folder = create_video_item(HANDLE,item)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

    if end < len(sorted_items):
        next_item = xbmcgui.ListItem(label="Próxima Página >>")
        next_url = get_url(action=action_name, page=page + 1, items_per_page=items_per_page)
        next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
        xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)



def list_movies_by_popularity(page=1, items_per_page=70):
    """
    Lista filmes por popularidade usando diretamente get_all_videos() e VideoCache
    com estratégia de cache mais simples e eficiente.
    Colore de vermelho o título se 'hdcam' == True.
    """
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 100))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_and_sort_movies():
        """Obtém e ordena filmes com cache direto no VideoCache"""
        cache_key = "movies_by_popularity_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_videos = get_all_videos()
        if not all_videos:
            return []
            
                # Filtragem e ordenação
        movies = [
            m for m in all_videos 
            if m.get('type') == 'movie' 
            and '(4K)' not in m.get('title', '')
        ]    
            
        unique_movies = {}
        for movie in movies:
            tmdb_id = movie.get('tmdb_id')
            if not tmdb_id:
                continue
                
            current_pop = movie.get('popularity', 0)
            if tmdb_id not in unique_movies or current_pop > unique_movies[tmdb_id].get('popularity', 0):
                unique_movies[tmdb_id] = movie
        
        sorted_movies = sorted(
            unique_movies.values(),
            key=lambda x: x.get('popularity', 0),
            reverse=True
        )[:1000]
        
        VIDEO_CACHE.set(cache_key, json.dumps(sorted_movies), expiry_hours=12)
        xbmc.log(f"[DEBUG] Cache key {cache_key} updated. Expires in 12h.", xbmc.LOGINFO)
        return sorted_movies

    try:
        sorted_movies = get_and_sort_movies()
        
        if not sorted_movies:
            xbmcgui.Dialog().ok("Aviso", "Nenhum filme encontrado.")
            return

        # 🔹 Aplica a cor vermelha no título se for HDCAM
        for movie in sorted_movies:
            if movie.get("hdcam") is True:
                movie["title"] = f"[COLOR red]{movie.get('title', '')}[/COLOR]"

        xbmcplugin.setPluginCategory(HANDLE, 'Mais Populares')
        xbmcplugin.setContent(HANDLE, 'movies')

        paginate_and_add_items(sorted_movies, page, items_per_page, 'list_movies_by_popularity')

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_movies_by_popularity: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)


def list_movies_legendados(page=1, items_per_page=70):
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 100))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_legendado_movies():
        cache_key = "movies_legendados_v1"
        cached = VIDEO_CACHE.get(cache_key)

        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)

        all_movies = get_all_videos()
        legendado_movies = [
            movie for movie in all_movies
            if movie.get('type') == 'movie'
            and movie.get('legendado') is True  # <-- Verifica se o campo "legendado" é True
        ]

        VIDEO_CACHE.set(cache_key, json.dumps(legendado_movies), expiry_hours=12)
        return legendado_movies

    try:
        movies = get_legendado_movies()

        if not movies:
            xbmcgui.Dialog().ok("Aviso", "Nenhum filme legendado encontrado.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Filmes Legendados')
        xbmcplugin.setContent(HANDLE, 'movies')

        paginate_and_add_items(movies, page, items_per_page, 'list_movies_legendados')

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_movies_legendados: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)


def list_movies_by_revenue(page=1, items_per_page=70):
    """
    Lista filmes ordenados por bilheteria (revenue), com cache e paginação.
    """
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 100))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_and_sort_by_revenue():
        """Obtém e ordena filmes por receita (bilheteria)"""
        cache_key = "movies_by_revenue"
        cached = VIDEO_CACHE.get(cache_key)

        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)

        all_videos = get_all_videos()
        if not all_videos:
            return []

        movies = [
            m for m in all_videos
            if m.get('type') == 'movie'
            and isinstance(m.get('revenue'), (int, float))  # só com bilheteria válida
            and m.get('revenue', 0) > 0
            and '(4K)' not in m.get('title', '')
        ]

        # Remoção de duplicatas por tmdb_id mantendo a maior receita
        unique_movies = {}
        for movie in movies:
            tmdb_id = movie.get('tmdb_id')
            if not tmdb_id:
                continue
            current_rev = movie.get('revenue', 0)
            if tmdb_id not in unique_movies or current_rev > unique_movies[tmdb_id].get('revenue', 0):
                unique_movies[tmdb_id] = movie

        sorted_movies = sorted(
            unique_movies.values(),
            key=lambda x: x.get('revenue', 0),
            reverse=True
        )[:1000]  # Limita para os 1000 com maior bilheteria

        VIDEO_CACHE.set(cache_key, json.dumps(sorted_movies), expiry_hours=12)
        xbmc.log(f"[DEBUG] Cache key {cache_key} updated (bilheteria). Expires in 12h.", xbmc.LOGINFO)
        return sorted_movies

    try:
        sorted_movies = get_and_sort_by_revenue()

        if not sorted_movies:
            xbmcgui.Dialog().ok("Aviso", "Nenhum filme com bilheteria encontrada.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Maiores Bilheterias')
        xbmcplugin.setContent(HANDLE, 'movies')

        paginate_and_add_items(sorted_movies, page, items_per_page, 'list_movies_by_revenue')

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_movies_by_revenue: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)



def list_movies_in_cinemas(page=1, items_per_page=70):
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 100))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_cinema_movies():
        cache_key = "movies_in_cinemas_v2"
        cached = VIDEO_CACHE.get(cache_key)

        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)

        all_movies = get_all_videos()
        cinema_movies = [
            movie for movie in all_movies
            if movie.get('type') == 'movie' 
            and movie.get('hdcam')  # <-- Verifica se 'hdcam' é true
        ]

        VIDEO_CACHE.set(cache_key, json.dumps(cinema_movies), expiry_hours=12)
        return cinema_movies

    try:
        movies = get_cinema_movies()
        
        if not movies:
            xbmcgui.Dialog().ok("Aviso", "Nenhum filme em cinema encontrado.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Nos Cinemas')
        xbmcplugin.setContent(HANDLE, 'movies')

        # Se quiser ordenar por título
        sorted_movies = sorted(movies, key=lambda x: x.get('title', '').lower())

        paginate_and_add_items(sorted_movies, page, items_per_page, 'list_movies_in_cinemas')

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_movies_in_cinemas: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)



def list_recently_added(page=1, items_per_page=70):
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 100))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_recent_movies():
        cache_key = "recently_added_movies"
        cached = VIDEO_CACHE.get(cache_key)

        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)

        all_movies = get_all_videos()
        recent_movies = [
            movie for movie in all_movies 
            if movie.get('type') == 'movie' and movie.get('date_added') is not None
        ]
        # Ordena do mais recente para o mais antigo
        recent_movies.sort(key=lambda x: x['date_added'], reverse=True)

        VIDEO_CACHE.set(cache_key, json.dumps(recent_movies), expiry_hours=6)
        return recent_movies

    try:
        recent_movies = get_recent_movies()

        if not recent_movies:
            xbmcgui.Dialog().ok("Aviso", "Nenhum filme adicionado recentemente encontrado.")
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Adicionados Recentemente')
        xbmcplugin.setContent(HANDLE, 'movies')

        paginate_and_add_items(recent_movies, page, items_per_page, 'list_recently_added')

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_recently_added: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Ocorreu um erro ao listar filmes recentes", xbmcgui.NOTIFICATION_ERROR)



import concurrent.futures
import urllib.request
import json
import hashlib

TMDB_API_KEY = "f0b9cd2de131c900f5bb03a0a5776342"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_BACKDROP_BASE = "https://image.tmdb.org/t/p/original"

def fetch_collection_art(tmdb_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}&language=pt-BR"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        collection = data.get("belongs_to_collection")
        if collection and collection.get("poster_path") and collection.get("backdrop_path"):
            return {
                "poster": TMDB_IMAGE_BASE + collection["poster_path"],
                "backdrop": TMDB_BACKDROP_BASE + collection["backdrop_path"],
                "name": collection["name"]
            }
    except Exception as e:
        xbmc.log(f"[WARN] fetch_collection_art: erro ao buscar coleção TMDb id {tmdb_id}: {e}", xbmc.LOGWARNING)
    return None


# Filmes por coleção

def list_collections(page=1, items_per_page=70, use_tmdb_art=use_tmdb):
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 200))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_cached_collections():
        cache_key = "collections_list_v3"
        if VIDEO_CACHE.enabled:
            cached = VIDEO_CACHE.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except:
                    VIDEO_CACHE.delete(cache_key)

        all_videos = get_all_videos()
        collections = {}

        for movie in all_videos:
            if (movie.get('type') == 'movie' and
                movie.get('collection') and
                movie['collection'].lower() != "null"):

                collection_name = movie['collection']
                if collection_name not in collections:
                    collections[collection_name] = []
                collections[collection_name].append(movie)

        valid_collections = {
            name: movies for name, movies in collections.items()
            if len(movies) >= 2
        }

        if VIDEO_CACHE.enabled and valid_collections:
            VIDEO_CACHE.set(cache_key, json.dumps(valid_collections), expiry_hours=12)

        return valid_collections

    try:
        collections_data = get_cached_collections()
        if not collections_data:
            xbmcgui.Dialog().ok("Aviso", "Nenhuma coleção válida encontrada.")
            xbmcplugin.endOfDirectory(HANDLE)
            return

        def get_collection_art_cached(collection_name, movies):
            cache_key = "collection_art_" + hashlib.md5(collection_name.encode()).hexdigest()
            if VIDEO_CACHE.enabled:
                cached = VIDEO_CACHE.get(cache_key)
                if cached:
                    try:
                        return json.loads(cached)
                    except:
                        VIDEO_CACHE.delete(cache_key)

            art = None
            if use_tmdb_art:
                tmdb_id = None
                for m in movies:
                    if m.get('tmdb_id'):
                        tmdb_id = m['tmdb_id']
                        break
                if tmdb_id:
                    art = fetch_collection_art(tmdb_id)

            if art:
                if VIDEO_CACHE.enabled:
                    VIDEO_CACHE.set(cache_key, json.dumps(art), expiry_hours=24)
                return art

            # fallback
            first_movie = movies[0]
            return {
                "poster": first_movie.get('poster', ''),
                "backdrop": first_movie.get('backdrop', ''),
            }

        xbmcplugin.setPluginCategory(HANDLE, 'Coleções')
        xbmcplugin.setContent(HANDLE, 'sets')

        sorted_names = sorted(collections_data.keys())
        total = len(sorted_names)
        start = (page - 1) * items_per_page
        end = start + items_per_page

        subset_names = sorted_names[start:end]
        subset_movies = [collections_data[name] for name in subset_names]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            arts = list(executor.map(lambda nm_mv: get_collection_art_cached(nm_mv[0], nm_mv[1]), zip(subset_names, subset_movies)))

        for name, art, movies in zip(subset_names, arts, subset_movies):
            item = xbmcgui.ListItem(label=name)
            item.setInfo('video', {
                'title': name,
                'plot': f"Coleção com {len(movies)} filmes",
                'mediatype': 'set'
            })
            item.setArt({
                'poster': art.get('poster', ''),
                'fanart': art.get('backdrop', ''),
                'thumb': art.get('poster', '')
            })
            
            favorites = load_favorites()
            if any(fav.get('title') == name and fav.get('type') == 'set' for fav in favorites):
                item.addContextMenuItems([(
                    'Remover da sua lista',
                    f'RunPlugin({get_url(action="remove_from_favorites", video=json.dumps({"title": name, "type": "set"}))})'
                )])
            else:
                item.addContextMenuItems([(
                    'Adicionar à sua lista',
                    f'RunPlugin({get_url(action="add_to_favorites", video=json.dumps({"title": name, "type": "set"}))})'
                )])

            url = get_url(action='list_movies_by_collection', collection=name)
            xbmcplugin.addDirectoryItem(HANDLE, url, item, True)

        if end < total:
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(
                action='list_collections',
                page=page + 1,
                items_per_page=items_per_page
            )
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"[ERRO] list_collections: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Falha ao carregar coleções", xbmcgui.NOTIFICATION_ERROR)

    
def list_movies_by_collection(collection_name, page=1, items_per_page=70):
    """Lista filmes de uma coleção com cache seguro"""
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 200))
        collection_name = urllib.parse.unquote(collection_name)
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_collection_movies():
        cache_key = f"collection_{hashlib.md5(collection_name.encode()).hexdigest()}"
        if VIDEO_CACHE.enabled:
            cached = VIDEO_CACHE.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except:
                    VIDEO_CACHE.delete(cache_key)
        
        all_videos = get_all_videos()
        movies = [
            m for m in all_videos
            if (m.get('type') == 'movie' and
                m.get('collection') == collection_name and
                '4k' not in m.get('title', '').lower())
        ]
        
        # Remove duplicados e ordena
        seen = set()
        unique_movies = []
        for m in movies:
            if m.get('tmdb_id') not in seen:
                seen.add(m['tmdb_id'])
                unique_movies.append(m)
        
        unique_movies.sort(key=lambda x: x.get('year', 0), reverse=True)
        
        if VIDEO_CACHE.enabled and unique_movies:
            VIDEO_CACHE.set(cache_key, json.dumps(unique_movies), expiry_hours=12)
        
        return unique_movies

    try:
        movies = get_collection_movies()
        if not movies:
            xbmcgui.Dialog().ok("Aviso", f"Nenhum filme válido em '{collection_name}'")
            xbmcplugin.endOfDirectory(HANDLE)
            return

        xbmcplugin.setPluginCategory(HANDLE, collection_name)
        xbmcplugin.setContent(HANDLE, 'movies')

        start = (page - 1) * items_per_page
        end = start + items_per_page
        
        for movie in movies[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE,movie)
            if list_item and url:
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        if end < len(movies):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(
                action='list_movies_by_collection',
                collection=urllib.parse.quote_plus(collection_name),
                page=page + 1,
                items_per_page=items_per_page
            )
            next_item.setArt({"icon": "https://example.com/next.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"[ERRO] list_movies_by_collection: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Falha ao carregar coleção", xbmcgui.NOTIFICATION_ERROR)

# Filmes em 4K
def get_4k_movies():
    """Junta todos os filmes que possuem a flag '4K': true."""
    cache_key = "all_4k_movies_list_v4_explicit_flag_sorted_popularity" # Recomendo mudar a cache key!
    if VIDEO_CACHE.enabled:
        cached = VIDEO_CACHE.get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except:
                VIDEO_CACHE.delete(cache_key)

    all_videos = get_all_videos()
    
    four_k_movies = []

    for movie in all_videos:
        # Verifica se é um filme E se a flag '4K' existe e é True
        if movie.get('type') == 'movie' and movie.get('4K') is True:
            four_k_movies.append(movie)

    # Remove duplicatas (ainda uma boa prática, caso get_all_videos() retorne duplicatas)
    seen_tmdb_ids = set()
    unique_4k_movies = []
    for m in four_k_movies:
        if m.get('tmdb_id') and m['tmdb_id'] not in seen_tmdb_ids:
            unique_4k_movies.append(m)
            seen_tmdb_ids.add(m['tmdb_id'])
    
    # --- MUDANÇA AQUI: Ordenar por popularidade ---
    unique_4k_movies.sort(key=lambda x: x.get('popularity', 0.0), reverse=True)

    if VIDEO_CACHE.enabled and unique_4k_movies:
        VIDEO_CACHE.set(cache_key, json.dumps(unique_4k_movies), expiry_hours=12)
        
    return unique_4k_movies

# Exemplo de como você poderia usar essa função em uma nova "lista" de menu
def list_4k_movies(page=1, items_per_page=70):
    try:
        page = max(1, int(page))
        items_per_per_page = max(10, min(int(items_per_page), 200))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    try:
        movies_4k = get_4k_movies()
        if not movies_4k:
            xbmcgui.Dialog().ok("Aviso", "Nenhum filme 4K encontrado.")
            xbmcplugin.endOfDirectory(HANDLE)
            return

        xbmcplugin.setPluginCategory(HANDLE, '4K Ultra HD')
        xbmcplugin.setContent(HANDLE, 'movies')

        paginate_and_add_items(movies_4k, page, items_per_page, 'list_4k_movies')


        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode() # Assumindo que set_view_mode existe

    except Exception as e:
        xbmc.log(f"[ERRO] list_4k_movies: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Falha ao carregar filmes 4K", xbmcgui.NOTIFICATION_ERROR)
        
        
# Filmes por pais        
def list_movies_by_country(country_code, page=1, items_per_page=70):
    """
    Lista os filmes que pertencem a um idioma original específico, com paginação.
    """
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 200))
        country_code = urllib.parse.unquote(country_code)  # Descodifica para garantir o código correto
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_movies_by_country():
        cache_key = f"country_{hashlib.md5(country_code.encode('utf-8')).hexdigest()}"
        cached = VIDEO_CACHE.get(cache_key)

        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)

        all_movies = get_all_videos()
        filtered = []
        seen_ids = set()
        for movie in all_movies:
            if (
                movie.get('type') == 'movie' and
                movie.get('original_language') == country_code and
                movie.get('tmdb_id') not in seen_ids  # Evita duplicatas
            ):
                seen_ids.add(movie['tmdb_id'])
                filtered.append(movie)

        # Ordena (ano decrescente, título)
        filtered.sort(key=lambda x: (x.get('year', 0), x.get('title', '')), reverse=True)

        VIDEO_CACHE.set(cache_key, json.dumps(filtered), expiry_hours=12)
        return filtered

    try:
        filtered_movies = get_movies_by_country()
    except Exception as e:
        xbmc.log(f"[ERRO] Falha ao acessar cache para filmes por país ({country_code}): {str(e)}", xbmc.LOGERROR)
        filtered_movies = []

    if not filtered_movies:
        display_name = IDIOMA_NOMES.get(country_code, f"Desconhecido ({country_code.upper()})")
        xbmcgui.Dialog().ok("Aviso", f"Nenhum filme encontrado com idioma original: {display_name}.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    display_country_name = IDIOMA_NOMES.get(country_code, f"Filmes em {country_code.upper()}")
    xbmcplugin.setPluginCategory(HANDLE, f'{display_country_name}')
    xbmcplugin.setContent(HANDLE, 'movies')

    # Paginação
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    paginated_movies = filtered_movies[start_index:end_index]

    for movie in paginated_movies:
        list_item, url, is_folder = create_video_item(HANDLE,movie)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)

    # Próxima página
    if end_index < len(filtered_movies):
        next_page_item = xbmcgui.ListItem(label="Próxima Página >>")
        next_page_url = get_url(
            action='list_movies_by_country',
            country_code=urllib.parse.quote_plus(country_code),  # Codifica para URL
            page=page + 1,
            items_per_page=items_per_page
        )
        next_page_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
        xbmcplugin.addDirectoryItem(HANDLE, next_page_url, next_page_item, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE)
    xbmcplugin.endOfDirectory(HANDLE)
    set_view_mode()


def list_recommendations(page=1, items_per_page=70):
    """
    Gera e exibe uma lista de filmes recomendados com base nos favoritos do usuário,
    usando paginação e cache.
    """
    try:
        page = max(1, int(page))
        items_per_page = max(10, min(int(items_per_page), 100))
    except (ValueError, TypeError):
        page = 1
        items_per_page = 70

    def get_and_sort_recommendations():
        """Obtém e ordena filmes recomendados, com cache."""
        all_favorites = load_favorites()
        # Filtra os favoritos para usar apenas filmes como base da recomendação
        user_favorites = [m for m in all_favorites if m.get('type') == 'movie']

        if not user_favorites:
            return []

        favorite_titles = sorted([m.get('title', '') for m in user_favorites])
        cache_key = "recommendations_" + hashlib.md5(json.dumps(favorite_titles).encode('utf-8')).hexdigest()

        cached_recommendations = VIDEO_CACHE.get(cache_key)

        if cached_recommendations and not VIDEO_CACHE.is_expired(cache_key):
            xbmc.log("[DEBUG] Carregando recomendações do cache.", xbmc.LOGINFO)
            return json.loads(cached_recommendations)

        xbmc.log("[DEBUG] Calculando novas recomendações.", xbmc.LOGINFO)

        # Lógica de análise de preferências
        genres_count = {}
        actors_count = {}
        keywords_count = {}
        for movie in user_favorites:
            genres = movie.get('genres', [])
            if genres:
                first_genre = genres[0]
                genres_count[first_genre] = genres_count.get(first_genre, 0) + 2
                for other_genre in genres[1:]:
                    genres_count[other_genre] = genres_count.get(other_genre, 0) + 1
            
            for actor in movie.get('actors', []):
                actors_count[actor] = actors_count.get(actor, 0) + 1
            for keyword in movie.get('keywords', []):
                keywords_count[keyword] = keywords_count.get(keyword, 0) + 1

        all_content = get_all_videos()
        # Filtra todo o conteúdo para usar apenas filmes
        all_movies = [m for m in all_content if m.get('type') == 'movie']
        recommendations = []
        favorite_tmdb_ids = {m.get('tmdb_id') for m in user_favorites}

        for movie in all_movies:
            if movie.get('tmdb_id') in favorite_tmdb_ids:
                continue

            score = 0
            
            # Pontuação por gênero, ator e palavra-chave
            for genre in movie.get('genres', []):
                score += genres_count.get(genre, 0) * 1.5
            for actor in movie.get('actors', []):
                score += actors_count.get(actor, 0) * 1.0
            for keyword in movie.get('keywords', []):
                score += keywords_count.get(keyword, 0) * 0.5
            
            if score > 0:
                movie['recommendation_score'] = score
                recommendations.append(movie)

        recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        top_recommendations = recommendations[:1000]

        VIDEO_CACHE.set(cache_key, json.dumps(top_recommendations), expiry_hours=24)
        return top_recommendations
    
    try:
        recommendations = get_and_sort_recommendations()

        if not recommendations:
            xbmcgui.Dialog().ok("Aviso", "Nenhum filme recomendado encontrado. Adicione mais favoritos!")
            xbmcplugin.endOfDirectory(HANDLE)
            return

        xbmcplugin.setPluginCategory(HANDLE, 'Recomendações para Você')
        xbmcplugin.setContent(HANDLE, 'movies')
        
        start = (page - 1) * items_per_page
        end = start + items_per_page

        for movie in recommendations[start:end]:
            list_item, url, is_folder = create_video_item(HANDLE, movie)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)

        if end < len(recommendations):
            next_item = xbmcgui.ListItem(label="Próxima Página >>")
            next_url = get_url(action='list_recommendations', page=page + 1, items_per_page=items_per_page)
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"Erro em list_recommendations: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)