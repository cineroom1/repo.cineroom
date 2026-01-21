# -*- coding: utf-8 -*-
# Em: resources/lib/tvshows.py

import json
import os
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode

# Mantenha apenas o db e utils que são leves e essenciais para as listagens
from .db import db
from .utils import create_video_item_with_library, with_view_mode

# Configurações e funções comuns
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
DEFAULT_ITEMS_PER_PAGE = int(ADDON.getSetting("pages"))
TMDB_API_KEY = "f0b9cd2de131c900f5bb03a0a5776342"

ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

PROVIDER_LOGOS = {
    "Amazon Prime Video": "prime_video.png",
    "Netflix": "netflix.png",
    "Max": "hbo_max.png",
    "Disney Plus": "disney_plus.png",
    "Apple TV+": "apple_tv.png",
    "Paramount plus": "paramount_plus.png",
    "Crunchyroll": "crunchyroll.png",
    "Globoplay": "globoplay.png",
    "Looke": "looke.png",
    "Hulu": "hulu.png",
    "Peacock": "peacock.png",
    "Discovery+": "discovery_plus.png",
}



def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"


# --- ✅ NOVAS FUNÇÕES AUXILIARES ---

def _prepare_details_data(item_data):
    """Prepara um dicionário com os dados do item para a URL da tela de detalhes."""
    genre_str = ', '.join(item_data.get('genres', []))  # Lista → string
    providers_list = item_data.get('providers', [])
    return {
        'tmdb_id': item_data.get('tmdb_id'),
        'imdb_id': item_data.get('imdb_id'),
        'title': item_data.get('title'),
        'original_title': item_data.get('original_title', item_data.get('title')),
        'romaji_title': item_data.get('romaji_title', ''),
        'clearlogo': item_data.get('clearlogo'),
        'synopsis': item_data.get('synopsis'),
        'poster': item_data.get('poster'),
        'backdrop': item_data.get('backdrop'),
        'year': item_data.get('year'),
        'rating': item_data.get('rating'),
        'certification': item_data.get('certification'),
        'genre': genre_str,
        'media_type': 'tvshow',
        'providers': json.dumps(providers_list)
    }


def _create_show_tuple(show_data):
    """
    Cria a tupla (url, listitem, is_folder) para séries (TV Shows) usando a função completa.
    """
    # Removido o IF e a chamada ao 'fast'
    li = create_video_item_with_library(show_data, 'tvshow')
    
    if ADDON.getSettingBool("tvshow.enable_details"):

        details_data = _prepare_details_data(show_data)
        url = get_url(action='show_details', data=json.dumps(details_data, ensure_ascii=False))
        is_folder = False
    else:
        url = get_url(action='list_seasons', tvshow_tmdb_id=show_data.get('tmdb_id'))
        is_folder = True

    return (url, li, is_folder)


# --- FUNÇÕES DE NAVEGAÇÃO DE SÉRIES ---

def show_tvshows_menu(menu_structure):
    """Cria e exibe o menu da seção 'Séries'."""
    xbmcplugin.setPluginCategory(HANDLE, 'Séries')
    for item in menu_structure:
        li = xbmcgui.ListItem(label=item['title'])
        icon = item.get('icon')
        if icon:
            li.setArt({'thumb': icon})
        url = get_url(action=item['action'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def add_next_page_item(items_on_current_page, current_page, **kwargs):
    """Adiciona o item 'Próxima Página' a uma lista se houver mais itens."""
    if len(items_on_current_page) == DEFAULT_ITEMS_PER_PAGE:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="Próxima Página")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        li_next.setInfo('video', {'plot': f'Ir para a página {current_page + 1}'})

        next_page_args = kwargs.copy()
        next_page_args['page'] = current_page + 1
        next_page_url = get_url(**next_page_args)

        xbmcplugin.addDirectoryItem(HANDLE, next_page_url, li_next, isFolder=True)

def list_seasons(tvshow_tmdb_id):
    from .tmdb_api import fetch_show_details 
    import json
    """
    Lista temporadas, AGORA COM CACHE.
    🔧 CORRIGIDO: Busca automaticamente do TMDB se não existir localmente
    """
    
    # 1. Busca dados da SÉRIE no DB local
    show = db.get_tvshow_by_id(tvshow_tmdb_id)
    
    # 🔧 FALLBACK AUTOMÁTICO: Se não encontrou localmente, busca do TMDB
    if not show:
        xbmc.log(f"[CineRoom] Série {tvshow_tmdb_id} não encontrada no banco, buscando no TMDB...", xbmc.LOGINFO)
        
        try:
            show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
            
            if not show_details_tmdb:
                xbmcgui.Dialog().ok("Erro", f"Não foi possível buscar informações desta série.\n\nTMDB ID: {tvshow_tmdb_id}")
                xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
                return
            
            seasons_data_list = show_details_tmdb.get('seasons_data', [])
            
            if seasons_data_list:
                db.save_seasons_cache(tvshow_tmdb_id, seasons_data_list)
                xbmc.log(f"[CineRoom] Série {tvshow_tmdb_id} salva no cache com {len(seasons_data_list)} temporadas", xbmc.LOGINFO)
            
            # Recria o objeto 'show' para continuar a execução normal
            show = {
                'tmdb_id': show_details_tmdb.get('tmdb_id'),
                'imdb_id': show_details_tmdb.get('imdb_id', ''),  # ← IMPORTANTE para episódios!
                'title': show_details_tmdb.get('title'),
                'original_title': show_details_tmdb.get('original_title', ''),
                'poster': show_details_tmdb.get('poster'),
                'backdrop': show_details_tmdb.get('backdrop'),
                'clearlogo': show_details_tmdb.get('clearlogo', ''),
                'year': show_details_tmdb.get('year', ''),
                'romaji_title': ''  # Animes do Trakt não têm esse campo
            }
            
        except Exception as e:
            xbmc.log(f"[CineRoom] Erro ao buscar série do TMDB: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("Erro", f"Falha ao buscar série do TMDB:\n{str(e)}")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return
        
    xbmcplugin.setPluginCategory(HANDLE, show['title'])
    xbmcplugin.setContent(HANDLE, 'seasons')

    # --- LÓGICA DE CACHE ---
    try:
        cache_hours = int(ADDON.getSetting("cache_age_hours"))
    except:
        cache_hours = 12
        
    seasons_data_list = db.get_cached_seasons(tvshow_tmdb_id, cache_hours)
    
    if not seasons_data_list:
        xbmc.log(f"[CineRoom] Cache miss para temporadas de {tvshow_tmdb_id}, buscando no TMDB...", xbmc.LOGDEBUG)
        
        show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
        if not show_details_tmdb:
            xbmcgui.Dialog().ok("Aviso", f"Não foi possível buscar temporadas de '{show.get('title', 'Unknown')}'.")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return
            
        seasons_data_list = show_details_tmdb.get('seasons_data', [])
        
        if seasons_data_list:
            db.save_seasons_cache(tvshow_tmdb_id, seasons_data_list)
        else:
            xbmcgui.Dialog().ok("Aviso", f"Série '{show.get('title', 'Unknown')}' não possui temporadas disponíveis.")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return

    try:
        show_specials_enabled = ADDON.getSettingBool('show_specials')
    except:
        show_specials_enabled = False
        
    for season_data in seasons_data_list:
        season_number = season_data.get('season_number', season_data.get('number', 0))
        
        if season_number == 0 and not show_specials_enabled:
            continue
            
        tmdb_season_name = season_data.get('name', f"Temporada {season_number}")
        
        if 'poster' not in season_data and season_data.get('poster_path'):
             season_data['poster'] = f"https://image.tmdb.org/t/p/w500{season_data['poster_path']}"
        
        season_data['title'] = tmdb_season_name
        season_data['label'] = tmdb_season_name
        
        li = create_video_item_with_library(season_data, 'season', show_data=show)
        
        li.setInfo('video', {
            'title': tmdb_season_name,
            'plot': season_data.get('overview', 'Sinopse não disponível.'),
            'rating': season_data.get('vote_average', 0.0),
            'season': season_number,
            'mediatype': 'season'
        })
        
        url = get_url(
            action='list_episodes', 
            tvshow_tmdb_id=tvshow_tmdb_id, 
            season_number=season_number
        )
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


# ============================================================
# 2️⃣ SUBSTITUA list_episodes() EM tvshows.py
# ============================================================

def list_episodes(tvshow_tmdb_id, season_number):
    from .tmdb_api import fetch_show_details
    """
    Lista episódios, AGORA COM CACHE.
    🔧 CORRIGIDO: Busca série do TMDB se não existir localmente
    """
    # 1. Obter dados da SÉRIE
    show_data = db.get_tvshow_by_id(tvshow_tmdb_id)
    
    # 🔧 FALLBACK: Se não encontrou, busca do TMDB
    if not show_data:
        xbmc.log(f"[CineRoom] Série {tvshow_tmdb_id} não encontrada para episódios, buscando no TMDB...", xbmc.LOGINFO)
        
        try:
            show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
            
            if not show_details_tmdb:
                xbmcgui.Dialog().ok("Erro", "Não foi possível buscar informações desta série.")
                xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
                return
            
            # Cria objeto show_data temporário
            show_data = {
                'tmdb_id': show_details_tmdb.get('tmdb_id'),
                'imdb_id': show_details_tmdb.get('imdb_id', ''),
                'title': show_details_tmdb.get('title'),
                'original_title': show_details_tmdb.get('original_title', ''),
                'poster': show_details_tmdb.get('poster'),
                'backdrop': show_details_tmdb.get('backdrop'),
                'clearlogo': show_details_tmdb.get('clearlogo', ''),
                'year': show_details_tmdb.get('year', ''),
                'romaji_title': ''
            }
            
        except Exception as e:
            xbmc.log(f"[CineRoom] Erro buscando série: {e}", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("Erro", f"Falha ao buscar série:\n{str(e)}")
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
            return
    
    # Validação do IMDB ID (necessário para scrapers)
    if not show_data.get('imdb_id'):
        xbmc.log(f"[CineRoom] AVISO: Série {tvshow_tmdb_id} sem IMDB ID, buscando novamente...", xbmc.LOGWARNING)
        
        try:
            show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
            if show_details_tmdb and show_details_tmdb.get('imdb_id'):
                show_data['imdb_id'] = show_details_tmdb['imdb_id']
                xbmc.log(f"[CineRoom] IMDB ID obtido: {show_data['imdb_id']}", xbmc.LOGINFO)
        except:
            pass

    xbmcplugin.setPluginCategory(HANDLE, f"{show_data.get('title')} - Temporada {season_number}")
    xbmcplugin.setContent(HANDLE, 'episodes')

    # --- LÓGICA DE CACHE ---
    try:
        cache_hours = int(ADDON.getSetting("cache_age_hours"))
    except:
        cache_hours = 72
        
    tmdb_episodes = db.get_cached_episodes(tvshow_tmdb_id, season_number, cache_hours)
    
    # Se cache falhar, busca na API
    if not tmdb_episodes:
        xbmc.log(f"[CineRoom] Cache miss para episódios S{season_number}, buscando no TMDB...", xbmc.LOGDEBUG)
        tmdb_episodes = _fetch_tmdb_season_details(tvshow_tmdb_id, season_number)
        
        if tmdb_episodes:
            db.save_episodes_cache(tvshow_tmdb_id, season_number, tmdb_episodes)
            xbmc.log(f"[CineRoom] {len(tmdb_episodes)} episódios salvos no cache", xbmc.LOGDEBUG)

    if not tmdb_episodes:
        xbmcgui.Dialog().ok("Aviso", "Nenhum episódio encontrado.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Loop para criar os itens
    for ep_data_tmdb in tmdb_episodes:
        ep_number = ep_data_tmdb.get('episode_number')
        ep_title = f"{ep_number}. {ep_data_tmdb.get('name')}"
        
        episode_poster_url = show_data.get('backdrop')
        if ep_data_tmdb.get('still_path'):
            episode_poster_url = f"https://image.tmdb.org/t/p/w500{ep_data_tmdb.get('still_path')}"

        item_data_for_scraper = {
            'media_type': 'tvshow', 
            'imdb_id': show_data.get('imdb_id', ''),
            'tmdb_id': tvshow_tmdb_id,
            'title': show_data.get('title'),
            'original_title': show_data.get('original_title', show_data.get('title')),
            'romaji_title': show_data.get('romaji_title', ''),
            'year': show_data.get('year'),
            'backdrop': show_data.get('backdrop'),
            'poster': show_data.get('poster'),
<<<<<<< HEAD
            'clearlogo': show_data.get('clearlogo', ''),
=======
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
            'episode_title': ep_data_tmdb.get('name'),
            'plot': ep_data_tmdb.get('overview'),
            'episode_poster': episode_poster_url,
            'rating': ep_data_tmdb.get('vote_average'),
            'season': season_number,
            'episode': ep_number,
            'premiered': ep_data_tmdb.get('air_date'),
            'runtime': ep_data_tmdb.get('runtime', 0)
        }
        
        li = xbmcgui.ListItem(label=ep_title)
        
        info = {
            'title': ep_title,
            'plot': item_data_for_scraper['plot'],
            'season': item_data_for_scraper['season'],
            'episode': item_data_for_scraper['episode'],
            'rating': item_data_for_scraper['rating'],
            'aired': item_data_for_scraper['premiered'],
            'duration': (item_data_for_scraper.get('runtime') or 0) * 60,
            'tvshowtitle': item_data_for_scraper['title'],
            'mediatype': 'episode',
            'imdbnumber': show_data.get('imdb_id', '')
        }
        li.setInfo('video', info)
        
        li.setUniqueIDs({
            'imdb': show_data.get('imdb_id', ''),
            'tmdb': str(tvshow_tmdb_id)
        })
        
        li.setProperty('original_title', show_data.get('original_title', ''))
        if show_data.get('romaji_title'):
            li.setProperty('romaji_title', show_data.get('romaji_title', ''))
        
        art = {
            'thumb': item_data_for_scraper['episode_poster'],
            'fanart': item_data_for_scraper['backdrop'],
            'poster': item_data_for_scraper['poster'],
            'tvshow.poster': show_data.get('poster'),
            'tvshow.fanart': show_data.get('backdrop'),
            'tvshow.clearlogo': show_data.get('clearlogo')
        }
        li.setArt(art)
        li.setProperty('IsPlayable', 'true')

        url = get_url(
            action='find_and_play_episode', 
            item_data=json.dumps(item_data_for_scraper)
        )
        
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)

def _fetch_tmdb_season_details(tmdb_id, season_number):
    import requests
    """Busca os detalhes de uma temporada direto do TMDB."""
    # (Manter inalterada: Esta função busca a lista de episódios do TMDB, o que é o objetivo)
    if not TMDB_API_KEY or TMDB_API_KEY == "SUA_CHAVE_API_V3_DO_TMDB_AQUI":
        xbmc.log("[ERRO] Chave de API do TMDB não configurada.", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro de Configuração", "A chave de API do TMDB não foi definida no arquivo 'tvshows.py'.")
        return []
        
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_number}?api_key={TMDB_API_KEY}&language=pt-BR"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('episodes', [])
    except requests.exceptions.RequestException as e:
        xbmc.log(f"[ERRO TMDB] Falha ao buscar temporada {tmdb_id} S{season_number}: {e}", xbmc.LOGERROR)
        return []



# --- LISTAGENS DE SÉRIES (MENUS) ---

@with_view_mode('genres', is_menu=True)
def list_tvshows_genres():
    """Cria e exibe a lista de Gêneros de Séries."""
    xbmcplugin.setPluginCategory(HANDLE, 'Gêneros de Séries')
    xbmcplugin.setContent(HANDLE, 'genres')
    genres_from_db = db.get_all_unique_tvshow_genres()
    for genre_name in genres_from_db:
        li = xbmcgui.ListItem(label=genre_name)
        url = get_url(action='list_tvshows_by_genre', genre=genre_name)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('files', is_menu=True)
def list_providers():
    xbmcplugin.setPluginCategory(HANDLE, "Provedores")

    providers = db.get_all_unique_providers()

    for provider_name in providers:
        li = xbmcgui.ListItem(label=provider_name)

        logo_file = PROVIDER_LOGOS.get(provider_name)
        if logo_file:
            logo_path = os.path.join(
                ADDON_PATH, 'resources', 'logos', logo_file
            )
            li.setArt({
                'thumb': logo_path,
                'icon': logo_path,
                'poster': logo_path
            })

        url = get_url(
            action='list_tvshows_by_provider',
            provider=provider_name
        )

        xbmcplugin.addDirectoryItem(
            HANDLE, url, li, isFolder=True
        )

    xbmcplugin.endOfDirectory(HANDLE)



# --- LISTAGENS DE CONTEÚDO (SÉRIES) ---

@with_view_mode('tvshows')
def list_tvshows_by_genre(genre, page=1):
    xbmcplugin.setPluginCategory(HANDLE, genre)
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_tvshows_by_genre(genre, page, DEFAULT_ITEMS_PER_PAGE)
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_genre', genre=genre)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_provider(provider, page=1):
    xbmcplugin.setPluginCategory(HANDLE, provider)
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_tvshows_by_provider(provider, page, DEFAULT_ITEMS_PER_PAGE)
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_provider', provider=provider)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_popularity(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Mais Populares")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    shows = db.get_tvshows_by_popularity(page, DEFAULT_ITEMS_PER_PAGE)
    
    # BATCH ADD (O SEGREDO DA VELOCIDADE)
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
    
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(shows, page, action='list_tvshows_by_popularity')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_recently_added_tvshows(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Adicionados Recentemente")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    shows = db.get_recently_added_tvshows(page, DEFAULT_ITEMS_PER_PAGE)
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(shows, page, action='list_recently_added_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_animes(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Animes")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_tvshows_by_genre('anime', page, DEFAULT_ITEMS_PER_PAGE)
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_animes')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_kids_tvshows(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Infantil")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_kids_tvshows(page, DEFAULT_ITEMS_PER_PAGE)
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_kids_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_trending_tvshows(page=1):
    """Lista as séries em alta consumindo a API do TMDB."""
    from .tmdb_api import fetch_trending_tvshows
    
    xbmcplugin.setPluginCategory(HANDLE, "Em Alta")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    # Converte page para int caso venha como string do router
    page = int(page)
    
    # Busca os dados na API (já com Threads e Cache do tmdb_api.py)
    shows = fetch_trending_tvshows(page)

    items_to_add = []
    for show_data in shows:
        # ✅ USAMOS A SUA FUNÇÃO EXISTENTE:
        # Ela já cria o ListItem, define se é pasta e gera a URL correta
        # (show_details ou list_seasons dependendo da sua configuração)
        items_to_add.append(_create_show_tuple(show_data))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    # Adiciona paginação
    add_next_page_item(shows, page, action='list_trending_tvshows')
    
    xbmcplugin.endOfDirectory(HANDLE)
    
    
# Adicione estas funções no tvshows.py

@with_view_mode('genres', is_menu=True)
def list_tvshow_themes():
    """Menu de categorias temáticas de séries"""
    from .keywords import get_all_theme_categories
    
    xbmcplugin.setPluginCategory(HANDLE, 'Temas')
    xbmcplugin.setContent(HANDLE, 'genres')
    
    categories = get_all_theme_categories()
    
    for cat in categories:
        li = xbmcgui.ListItem(label=cat['name'])
        li.setInfo('video', {'plot': cat['description']})
        
        url = get_url(
            action='list_tvshows_by_theme',
            theme=cat['slug']
        )
        
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_tvshows_by_theme(theme, page=1):
    """Lista séries de uma categoria temática"""
    from .keywords import get_theme_config, get_theme_keyword_ids
    from .tmdb_api import fetch_tvshows_by_keywords
    
    config = get_theme_config(theme)
    
    if not config:
        xbmcgui.Dialog().ok("Erro", "Categoria não encontrada")
        return
    
    xbmcplugin.setPluginCategory(HANDLE, config['name'])
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    keyword_ids = get_theme_keyword_ids(theme)
    
    if not keyword_ids:
        xbmcgui.Dialog().ok("Erro", f"Não foi possível resolver keywords para '{config['name']}'")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    shows = fetch_tvshows_by_keywords(
        keyword_ids=keyword_ids,
        genres=config['genres'],
        page=int(page)
    )
    
    if not shows:
        xbmcgui.Dialog().ok("Aviso", f"Nenhuma série encontrada em '{config['name']}'")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
    
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    # ✅ VERIFICA SE TEM PRÓXIMA PÁGINA
    has_next = shows[0].get('_has_next_page', False) if shows else False
    
    if has_next:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="Próxima Página")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        
        next_url = get_url(
            action='list_tvshows_by_theme',
            theme=theme,
            page=int(page) + 1
        )
        
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(HANDLE)