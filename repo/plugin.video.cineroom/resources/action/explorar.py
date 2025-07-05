# explorar.py
import urllib.request
import json
import xbmcgui, xbmcplugin
import sys
from urllib.parse import urlencode, parse_qsl
import xbmc
import os
import time
import random
from xbmcaddon import Addon
import xbmcvfs

from resources.action.video_listing import create_video_item
from resources.action.favorites import load_favorites
from resources.lib.utils import get_all_videos, VIDEO_CACHE, FILTERED_CACHE
from resources.lib.utils_view import set_view_mode


HANDLE = int(sys.argv[1])
URL = sys.argv[0]        
        
        
def get_url(**kwargs):
    """
    Cria uma URL para chamar o plugin recursivamente a partir dos argumentos fornecidos.
    """
    # Serializa objetos JSON, se necessário
    if 'serie' in kwargs and isinstance(kwargs['serie'], dict):
        kwargs['serie'] = json.dumps(kwargs['serie'])
    return '{}?{}'.format(URL, urlencode(kwargs))        
        
def list_trending():
    """Lista filmes e séries com "trending": true usando FilteredCache, com filtro por tipo e limite de 20 itens."""
    from resources.lib.utils import get_all_videos
    from xbmcaddon import Addon

    # 1. Define a função de filtro para trending
    def filter_trending(videos):
        return [video for video in videos if video.get("trending") is True]

    # 2. Obtém os itens em alta do cache filtrado
    try:
        trending_items = FILTERED_CACHE.get_filtered(
            filter_name="trending_items",
            filter_func=filter_trending,
            expiry_hours=12  # Atualiza a cada 12 horas
        )
    except Exception as e:
        xbmcgui.Dialog().ok("Erro", f"Falha ao acessar cache: {str(e)}")
        return

    if not trending_items:
        xbmcgui.Dialog().ok("Aviso", "Nenhum conteúdo em alta encontrado.")
        return

    # Lê a configuração do usuário
    addon = Addon()
    section_setting = addon.getSettingString("trending_section_type")

    show_movies = section_setting in ['Ambos', 'Somente Filmes']
    show_series = section_setting in ['Ambos', 'Somente Séries']

    # Filtra por tipo com base na configuração
    filtered_items = []
    for item in trending_items:
        media_type = item.get('type', '').lower()
        if media_type == 'movie' and show_movies:
            filtered_items.append(item)
        elif media_type == 'tvshow' and show_series:
            filtered_items.append(item)

    if not filtered_items:
        xbmcgui.Dialog().ok("Aviso", "Nenhum conteúdo disponível para essa categoria.")
        return

    # Configurações do plugin
    xbmcplugin.setPluginCategory(HANDLE, 'Em Alta esta Semana')

    if show_series and not show_movies:
        xbmcplugin.setContent(HANDLE, 'tvshows')
    elif show_movies and not show_series:
        xbmcplugin.setContent(HANDLE, 'movies')
    else:
        xbmcplugin.setContent(HANDLE, 'movies')

    # Ordena por popularidade e limita a 50 itens
    filtered_items.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    filtered_items = filtered_items[:50]  # Limite direto de 50 itens

    # Adiciona cada item à lista
    for item in filtered_items:
        if 'title' not in item:
            continue

        list_item, url, is_folder = create_video_item(item)
        if not list_item or not url:
            continue

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)

    xbmcplugin.endOfDirectory(HANDLE)
    set_view_mode()

    

def list_random():
    """Lista filmes e séries aleatórias usando create_video_item."""
    from resources.lib.utils import get_all_videos
    import random
    from xbmcaddon import Addon

    addon = Addon()
    section_setting = addon.getSettingString("random_section_type")

    show_movies = section_setting in ['Ambos', 'Somente Filmes']
    show_series = section_setting in ['Ambos', 'Somente Séries']

    try:
        videos = get_all_videos()
    except Exception as e:
        xbmcgui.Dialog().ok("Erro", f"Falha ao carregar vídeos: {str(e)}")
        return

    if not videos:
        xbmcgui.Dialog().ok("Aviso", "Nenhum conteúdo disponível.")
        return

    # Remove duplicatas por tmdb_id e ignora títulos com (4K)
    unique_items = {}
    for v in videos:
        tmdb_id = v.get('tmdb_id')
        if not tmdb_id or tmdb_id in unique_items:
            continue
        if '(4K)' in v.get('title', ''):
            continue
        unique_items[tmdb_id] = v

    videos = list(unique_items.values())
    random.shuffle(videos)

    # Separa em filmes e séries
    movies = [v for v in videos if v.get('type') == 'movie']
    series = [v for v in videos if v.get('type') == 'tvshow']

    xbmcplugin.setPluginCategory(HANDLE, 'Aleatórios')

    if show_series and not show_movies:
        xbmcplugin.setContent(HANDLE, 'tvshows')
    elif show_movies and not show_series:
        xbmcplugin.setContent(HANDLE, 'movies')
    else:
        xbmcplugin.setContent(HANDLE, 'videos')

    # ➕ Botão de Atualizar Lista (mantido igual)
    list_item_refresh = xbmcgui.ListItem(label='[COLOR blue]Atualizar Lista[/COLOR]')
    list_item_refresh.setArt({'icon': 'DefaultAddonService.png', 'thumb': 'DefaultAddonService.png'})
    url_refresh = get_url(action='list_random')
    xbmcplugin.addDirectoryItem(HANDLE, url_refresh, list_item_refresh, isFolder=True)

    # ⬇️ Função para adicionar os itens usando create_video_item
    def add_items(items, label):
        if not items:
            return

        for item in items[:20]:  # Limite de 20 itens
            try:
                # Usa create_video_item para criar o item principal
                list_item, url, is_folder = create_video_item(item)
                if list_item and url:
                    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)
            except Exception as e:
                xbmc.log(f"Erro ao criar item {item.get('title')}: {str(e)}", xbmc.LOGERROR)
                continue

    # ➕ Adiciona seções conforme configuração do usuário
    if show_movies:
        add_items(movies, "Filmes Aleatórios")

    if show_series:
        add_items(series, "Séries Aleatórias")

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.endOfDirectory(HANDLE)
    set_view_mode()


CACHE_FILE = os.path.join(xbmcvfs.translatePath(Addon().getAddonInfo('profile')), 'recommend_cache.json')
CACHE_DURATION = 7 * 24 * 60 * 60  # 7 dias em segundos

def list_week_recommendations():
    from resources.lib.utils import get_all_videos

    addon = Addon()
    section_setting = addon.getSettingString("random_section_type")  # Ambos, Somente Filmes, Somente Séries
    show_movies = section_setting in ['Ambos', 'Somente Filmes']
    show_series = section_setting in ['Ambos', 'Somente Séries']

    def carregar_do_cache():
        if not os.path.exists(CACHE_FILE):
            return None
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if time.time() - data.get('timestamp', 0) < CACHE_DURATION:
                return data.get('items', [])
        return None

    def salvar_no_cache(items):
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'timestamp': time.time(), 'items': items}, f, ensure_ascii=False, indent=2)

    # Tenta carregar recomendações do cache
    items = carregar_do_cache()

    if not items:
        try:
            videos = get_all_videos()
        except Exception as e:
            xbmcgui.Dialog().ok("Erro", f"Falha ao carregar vídeos: {str(e)}")
            return

        unique = {}
        for v in videos:
            if '(4K)' in v.get('title', ''):
                continue
            tmdb_id = v.get('tmdb_id')
            if tmdb_id and tmdb_id not in unique:
                unique[tmdb_id] = v

        filtered = list(unique.values())
        random.shuffle(filtered)

        # Separa por tipo e filtra por rating > 6.4
        movies = [v for v in filtered if v.get('type') == 'movie' and v.get('rating', 0) >= 6.4]
        series = [v for v in filtered if v.get('type') == 'tvshow' and v.get('rating', 0) >= 6.4]

        selected = []
        if show_movies:
            selected.extend(movies[:15])
        if show_series:
            selected.extend(series[:15])

        random.shuffle(selected)
        salvar_no_cache(selected)
        items = selected

    xbmcplugin.setPluginCategory(HANDLE, 'Recomendações da Semana')

    if show_series and not show_movies:
        xbmcplugin.setContent(HANDLE, 'tvshows')
    elif show_movies and not show_series:
        xbmcplugin.setContent(HANDLE, 'movies')
    else:
        xbmcplugin.setContent(HANDLE, 'videos')

    for item in items:
        # Usa create_video_item para criar o item principal
        list_item, url, is_folder = create_video_item(item)
        
        if not list_item or not url:
            continue
            
        # Adiciona o menu de contexto extra para atualizar recomendações
        list_item.addContextMenuItems([
            ('Atualizar Recomendações', f'RunPlugin({get_url(action="clear_weekly_cache")})')
        ], replaceItems=False)

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)
        
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.endOfDirectory(HANDLE)
    set_view_mode()

def clear_weekly_recommendation_cache():
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)


def list_years_explorar():
    """Lista os anos disponíveis a partir dos vídeos para o usuário escolher (Explorar)."""
    from resources.lib.utils import get_all_videos
    from xbmcaddon import Addon

    try:
        videos = get_all_videos()
    except Exception as e:
        xbmcgui.Dialog().ok("Erro", f"Erro ao carregar vídeos: {str(e)}")
        return

    addon = Addon()
    section_setting = addon.getSettingString("year_section_type")

    show_movies = section_setting in ['Ambos', 'Somente Filmes']
    show_series = section_setting in ['Ambos', 'Somente Séries']

    years = set()
    for video in videos:
        title = video.get('title', '').lower()
        if '(4k)' in title:
            continue  # ignora filmes com (4K) no título

        year = video.get('year')
        media_type = video.get('type', '').lower()

        if not isinstance(year, int) or not (1900 < year <= 2100):
            continue

        if (media_type == 'movie' and show_movies) or (media_type == 'tvshow' and show_series):
            years.add(year)

    if not years:
        xbmcgui.Dialog().ok("Aviso", "Nenhum ano encontrado.")
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Por Ano')
    xbmcplugin.setContent(HANDLE, 'years')

    for year in sorted(years, reverse=True):
        label = str(year)
        list_item = xbmcgui.ListItem(label=label)
        url = get_url(action='list_by_year', year=year)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
    set_view_mode()

def list_by_year(year, page=1):
    """Lista filmes e séries lançados em um ano específico usando create_video_item, com paginação."""
    from resources.lib.utils import get_all_videos
    from xbmcaddon import Addon

    try:
        year = int(year)
        videos = get_all_videos()
    except Exception as e:
        xbmcgui.Dialog().notification("Erro", f"Falha ao carregar vídeos: {str(e)}", xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return

    addon = Addon()
    section_setting = addon.getSettingString("year_section_type")
    show_movies = section_setting in ['Ambos', 'Somente Filmes']
    show_series = section_setting in ['Ambos', 'Somente Séries']

    filtered_items = []
    for item in videos:
        if '(4k)' in item.get("title", "").lower():
            continue
        if (item.get("year") == year and 
            ((item.get("type") == "movie" and show_movies) or 
             (item.get("type") == "tvshow" and show_series))):
            filtered_items.append(item)

    if not filtered_items:
        xbmcgui.Dialog().notification("Info", f"Nenhum conteúdo para {year}", xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.setPluginCategory(HANDLE, f"Ano: {year}")

    content_type = 'videos'
    if show_series and not show_movies:
        content_type = 'tvshows'
    elif show_movies and not show_series:
        content_type = 'movies'
    xbmcplugin.setContent(HANDLE, content_type)

    filtered_items.sort(key=lambda x: x.get('rating', 0), reverse=True)

    # Paginação
    itens_por_pagina = int(addon.getSettingString("items_per_page") or 20)
    inicio = (page - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    pagina_atual = filtered_items[inicio:fim]

    for item in pagina_atual:
        try:
            list_item, url, is_folder = create_video_item(item)
            if list_item and url:
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)
        except Exception as e:
            xbmc.log(f"Erro ao criar item {item.get('title')}: {str(e)}", xbmc.LOGERROR)
            continue

    # Botão de próxima página
    if fim < len(filtered_items):
        next_page_url = f"{sys.argv[0]}?action=list_by_year&year={year}&page={page + 1}"
        next_item = xbmcgui.ListItem(label="Próxima página >>")
        next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
        xbmcplugin.addDirectoryItem(HANDLE, next_page_url, next_item, isFolder=True)

    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_TITLE)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=True)

# Na sua área de utilitários ou onde o FilteredCache está definido
def sort_by_date_added_func(items):
    valid_items = []
    for item in items:
        try:
            date_str = item.get('date_added', '')
            if not date_str or len(date_str) != 10 or date_str[4] != '-' or date_str[7] != '-':
                continue
            
            year, month, day = map(int, date_str.split('-'))
            if year < 1900 or not (1 <= month <= 12) or not (1 <= day <= 31):
                continue
                
            valid_items.append(item)
        except:
            continue
            
    valid_items.sort(
        key=lambda x: (
            int(x['date_added'][:4]),
            int(x['date_added'][5:7]),
            int(x['date_added'][8:10])
        ),
        reverse=True
    )
    return valid_items

# E então, na sua função list_by_date_added:
def list_by_date_added(page=1):
    from datetime import datetime
    from xbmcaddon import Addon
    
    addon = Addon()
    items_per_page = int(addon.getSettingString("items_per_page") or 20)

    def get_recently_added():
        cache_key = "recently_added_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_items = get_all_videos()
        filtered = [item for item in all_items if item.get('date_added')]
        
        # Remove duplicados por tmdb_id
        seen_ids = set()
        unique_items = []
        for item in filtered:
            tmdb_id = item.get('tmdb_id')
            if tmdb_id and tmdb_id not in seen_ids:
                unique_items.append(item)
                seen_ids.add(tmdb_id)
        
        # Ordena por data de adição (mais recente primeiro)
        sorted_items = sorted(unique_items, key=lambda x: x['date_added'], reverse=True)
        
        VIDEO_CACHE.set(cache_key, json.dumps(sorted_items), expiry_hours=6)  # Cache curto (6h)
        return sorted_items

    try:
        items = get_recently_added()
        
        if not items:
            xbmcgui.Dialog().notification("Info", "Nenhum conteúdo disponível", xbmcgui.NOTIFICATION_INFO)
            xbmcplugin.endOfDirectory(HANDLE)
            return

        xbmcplugin.setPluginCategory(HANDLE, "Adicionados Recentemente")
        xbmcplugin.setContent(HANDLE, 'movies')

        # Paginação
        start = (page - 1) * items_per_page
        end = start + items_per_page
        for item in items[start:end]:
            try:
                list_item, url, is_folder = create_video_item(item)
                if list_item and url:
                    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)
            except Exception as e:
                xbmc.log(f"Erro ao adicionar item {item.get('title', '')}: {str(e)}", xbmc.LOGERROR)

        # Próxima página
        if end < len(items):
            next_item = xbmcgui.ListItem(label="Próxima página >>")
            next_url = get_url(action='list_by_date_added', page=page + 1)
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)
        
        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"ERRO em list_by_date_added: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Verifique os logs", xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def list_by_provider(provider, page=1):
    from xbmcaddon import Addon
    
    addon = Addon()
    section_setting = addon.getSettingString("provider_section_type")
    show_movies = section_setting in ['Ambos', 'Somente Filmes']
    show_series = section_setting in ['Ambos', 'Somente Séries']
    provider_lower = provider.strip().lower()
    items_per_page = int(addon.getSettingString("items_per_page") or 20)

    def get_provider_content():
        cache_key = f"provider_{provider_lower}_v2"
        cached = VIDEO_CACHE.get(cache_key)
        
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_items = get_all_videos()
        filtered = [
            item for item in all_items
            if provider_lower in [p.strip().lower() for p in item.get("providers", [])]
            and (
                (item.get("type", "").lower() == "movie" and show_movies) or
                (item.get("type", "").lower() == "tvshow" and show_series)
            )
        ]
        
        # Ordena por popularidade
        filtered.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        
        VIDEO_CACHE.set(cache_key, json.dumps(filtered), expiry_hours=12)
        return filtered

    try:
        items = get_provider_content()
        
        if not items:
            xbmcgui.Dialog().notification("Info", f"Nenhum conteúdo de {provider}", xbmcgui.NOTIFICATION_INFO)
            xbmcplugin.endOfDirectory(HANDLE)
            return

        content_type = 'movies'
        if show_series and not show_movies:
            content_type = 'tvshows'
            
        xbmcplugin.setPluginCategory(HANDLE, f"Conteúdo: {provider}")
        xbmcplugin.setContent(HANDLE, content_type)

        # Paginação
        start = (page - 1) * items_per_page
        end = start + items_per_page
        for item in items[start:end]:
            try:
                list_item, url, is_folder = create_video_item(item)
                if list_item and url:
                    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, is_folder)
            except Exception as e:
                xbmc.log(f"Erro ao criar item {item.get('title')}: {str(e)}", xbmc.LOGERROR)

        # Próxima página
        if end < len(items):
            next_item = xbmcgui.ListItem(label="Próxima página >>")
            next_url = get_url(
                action='list_by_provider',
                provider=provider,
                page=page + 1
            )
            next_item.setArt({"icon": "https://raw.githubusercontent.com/Gael1303/mr/refs/heads/main/1700740365615.png"})
            xbmcplugin.addDirectoryItem(HANDLE, next_url, next_item, True)

        xbmcplugin.endOfDirectory(HANDLE)

    except Exception as e:
        xbmc.log(f"Erro em list_by_provider: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification(
            "Erro", 
            f"Falha ao carregar {provider}",
            xbmcgui.NOTIFICATION_ERROR
        )
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def list_providers():
    for provider in PROVEDORES:
        list_item = xbmcgui.ListItem(label=provider["name"])
        list_item.setArt({
            'thumb': provider["icon"],
            'icon': provider["icon"],
            'poster': provider["icon"]
        })
        url = f"{sys.argv[0]}?action=list_by_provider&provider={urllib.parse.quote_plus(provider['name'])}"
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=list_item, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


PROVEDORES = [
    {"name": "Netflix", "icon": "https://logopng.com.br/logos/netflix-94.png"},
    {"name": "Amazon Prime Video", "icon": "https://upload.wikimedia.org/wikipedia/commons/f/f1/Prime_Video.png"},
    {"name": "Disney Plus", "icon": "https://logospng.org/wp-content/uploads/disneyplus.png"},
    {"name": "Max", "icon": "https://logospng.org/wp-content/uploads/hbo-max.png"},
    {"name": "Globoplay", "icon": "https://logospng.org/wp-content/uploads/globoplay.png"},
    {"name": "Star Plus", "icon": "https://logospng.org/wp-content/uploads/star-plus.png"},
    {"name": "Paramount Plus", "icon": "https://logospng.org/wp-content/uploads/paramount-plus.png"},
    {"name": "Apple TV+", "icon": "https://w7.pngwing.com/pngs/911/587/png-transparent-apple-tv-hd-logo.png"},
    {"name": "Telecine Amazon Channel", "icon": "https://logospng.org/wp-content/uploads/telecine.png"},
    {"name": "MUBI", "icon": "https://upload.wikimedia.org/wikipedia/commons/3/3c/Mubi_logo.svg"},
    {"name": "Crunchyroll", "icon": "https://upload.wikimedia.org/wikipedia/commons/1/1e/Crunchyroll_Logo.svg"},
    {"name": "YouTube Premium", "icon": "https://logospng.org/wp-content/uploads/youtube-premium.png"},
    {"name": "Pluto TV", "icon": "https://logospng.org/wp-content/uploads/pluto-tv.png"},
    {"name": "Tubi", "icon": "https://upload.wikimedia.org/wikipedia/commons/5/58/Tubi_logo.svg"},
    {"name": "MGM+ Apple TV Channel", "icon": "https://logodownload.org/wp-content/uploads/2021/10/MGM+logo.png"},
    {"name": "Looke", "icon": "https://seeklogo.com/images/L/looke-logo-4146BCD25D-seeklogo.com.png"}
]