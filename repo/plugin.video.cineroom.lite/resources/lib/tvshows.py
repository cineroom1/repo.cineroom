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


from .db import db
from .utils import create_video_item_with_library, with_view_mode
from .content_filter import get_content_filter
from .tmdb_api import TMDB_API_KEY

# Configurações e funções comuns
ADDON = xbmcaddon.Addon()
BASE_URL = sys.argv[0]


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



def _get_items_per_page():
    try:
        return int(ADDON.getSetting("pages"))
    except Exception:
        return 20

def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"


# --- ✅ NOVAS FUNÇÕES AUXILIARES ---

def _prepare_details_data(item_data):
    """Prepara um dicionário com os dados do item para a URL da tela de detalhes."""
    genre_str = ', '.join(item_data.get('genres', []))
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
        'certification': item_data.get('certification') or item_data.get('classification', ''),
        'genre': genre_str,
        'media_type': 'tvshow',
        'providers': json.dumps(providers_list)
    }


def _create_show_tuple(show_data, track_on_click=False):
    """
    Cria a tupla (url, listitem, is_folder) para séries (TV Shows) usando a função completa.

    Args:
        track_on_click: Quando True (usado em search.py), embute track=1 na URL
                        para que o router registre o clique no Supabase apenas
                        quando o usuário escolher um resultado da busca.
    """
    li = create_video_item_with_library(show_data, 'tvshow')

    extra = {"track": "1"} if track_on_click else {}

    if ADDON.getSettingBool("tvshow.enable_details"):
        details_data = _prepare_details_data(show_data)
        url = get_url(action='show_details', data=json.dumps(details_data, ensure_ascii=False), **extra)
        is_folder = False
    else:
        url = get_url(action='list_seasons', tvshow_tmdb_id=show_data.get('tmdb_id'), **extra)
        is_folder = True

    return (url, li, is_folder)


# --- FUNÇÕES DE NAVEGAÇÃO DE SÉRIES ---

def show_tvshows_menu(menu_structure):
    """Cria e exibe o menu da seção 'Séries'."""
    HANDLE = int(sys.argv[1])
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
    HANDLE = int(sys.argv[1])
    if len(items_on_current_page) == _get_items_per_page():
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
    
    HANDLE = int(sys.argv[1])
    show = db.get_tvshow_by_id(tvshow_tmdb_id)
    
    if not show:
        
        try:
            show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
            
            if not show_details_tmdb:
                xbmcgui.Dialog().ok("Erro", f"Não foi possível buscar informações desta série.\n\nTMDB ID: {tvshow_tmdb_id}")
                xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
                return
            
            seasons_data_list = show_details_tmdb.get('seasons_data', [])
            
            if seasons_data_list:
                db.save_seasons_cache(tvshow_tmdb_id, seasons_data_list)
            
            # Recria o objeto 'show' para continuar a execução normal
            show = {
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
            from .utils import get_image_resolutions, scale_tmdb
            res = get_image_resolutions()
            season_data['poster'] = f"https://image.tmdb.org/t/p/{res['poster']}{season_data['poster_path']}"
        
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



def list_episodes(tvshow_tmdb_id, season_number):
    from .tmdb_api import fetch_show_details
    """
    Lista episódios, AGORA COM CACHE.
    🔧 CORRIGIDO: Busca série do TMDB se não existir localmente
    """
    HANDLE = int(sys.argv[1])
    show_data = db.get_tvshow_by_id(tvshow_tmdb_id)
    
    if not show_data:
        
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
        
        try:
            show_details_tmdb = fetch_show_details(tvshow_tmdb_id)
            if show_details_tmdb and show_details_tmdb.get('imdb_id'):
                show_data['imdb_id'] = show_details_tmdb['imdb_id']
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
        tmdb_episodes = _fetch_tmdb_season_details(tvshow_tmdb_id, season_number)
        
        if tmdb_episodes:
            db.save_episodes_cache(tvshow_tmdb_id, season_number, tmdb_episodes)

    if not tmdb_episodes:
        xbmcgui.Dialog().ok("Aviso", "Nenhum episódio encontrado.")
        xbmcplugin.endOfDirectory(HANDLE)
        return
    
    total_eps = show_data.get('episodes_count')

    # Loop para criar os itens
    for ep_data_tmdb in tmdb_episodes:
        ep_number = ep_data_tmdb.get('episode_number')
        ep_title = f"{ep_number}. {ep_data_tmdb.get('name')}"
        
        episode_poster_url = show_data.get('backdrop')
        if ep_data_tmdb.get('still_path'):
            from .utils import get_image_resolutions
            res = get_image_resolutions()
            episode_poster_url = f"https://image.tmdb.org/t/p/{res['backdrop']}{ep_data_tmdb.get('still_path')}"
            
        abs_ep = _get_absolute_episode(db, tvshow_tmdb_id, season_number, ep_number, total_eps)

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
            'clearlogo': show_data.get('clearlogo', ''),
            'episode_title': ep_data_tmdb.get('name'),
            'plot': ep_data_tmdb.get('overview'),
            'episode_poster': episode_poster_url,
            'rating': ep_data_tmdb.get('vote_average'),
            'season': season_number,
            'episode': ep_number,
            'premiered': ep_data_tmdb.get('air_date'),
            'runtime': ep_data_tmdb.get('runtime', 0),
            'absolute_episode':  abs_ep,
        }
        
        li = xbmcgui.ListItem(label=ep_title)

        tag = li.getVideoInfoTag()
        tag.setTitle(ep_title)
        tag.setPlot(item_data_for_scraper.get('plot') or '')
        tag.setSeason(int(season_number))
        tag.setEpisode(int(ep_number))
        tag.setRating(float(item_data_for_scraper.get('rating') or 0.0))
        tag.setPremiered(item_data_for_scraper.get('premiered') or '')
        tag.setDuration((item_data_for_scraper.get('runtime') or 0) * 60)
        tag.setTvShowTitle(item_data_for_scraper.get('title') or '')
        tag.setMediaType('episode')

        imdb_id = show_data.get('imdb_id', '')
        if imdb_id:
            tag.setIMDBNumber(imdb_id)

        tag.setUniqueIDs({
            'imdb': imdb_id,
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
            action='find_sources',
            media_type='tvshow',
            tmdb_id=tvshow_tmdb_id,
            imdb_id=show_data.get('imdb_id', ''),
            title=show_data.get('title', ''),
            original_title=show_data.get('original_title', show_data.get('title', '')),
            romaji_title=show_data.get('romaji_title', ''),
            year=show_data.get('year', ''),
            clearlogo=show_data.get('clearlogo', ''),
            fanart=show_data.get('backdrop', ''),
            backdrop=show_data.get('backdrop', ''),
            poster=show_data.get('poster', ''),
            season=season_number,
            episode=ep_number,
            absolute_episode=abs_ep if abs_ep is not None else '',
        )
        
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)
    
    
    
def _get_absolute_episode(db, tvshow_tmdb_id, season_number, episode_number, total_episodes=None):
    """
    Converte S{season}E{episode} em número absoluto.
    Se seasons_cache estiver vazio, busca do TMDB e salva — uma única vez.
    Retorna None se não for possível calcular com segurança.
    """
    if season_number <= 1:
        return episode_number

    prev_count = db.get_episode_counts_before_season(tvshow_tmdb_id, season_number)

    # Cache vazio — tenta popular via TMDB agora
    if prev_count is None:
        try:
            from .tmdb_api import fetch_show_details
            xbmc.log(f"[abs_ep] seasons_cache vazio para tmdb={tvshow_tmdb_id}, buscando do TMDB...", xbmc.LOGINFO)
            show_details = fetch_show_details(tvshow_tmdb_id)
            if show_details:
                seasons_data = show_details.get('seasons_data', [])
                if seasons_data:
                    db.save_seasons_cache(tvshow_tmdb_id, seasons_data)
                    # Tenta de novo com o cache recém-populado
                    prev_count = db.get_episode_counts_before_season(tvshow_tmdb_id, season_number)
        except Exception as e:
            xbmc.log(f"[abs_ep] Erro ao buscar seasons do TMDB: {e}", xbmc.LOGWARNING)

    if prev_count is None:
        xbmc.log(f"[abs_ep] Não foi possível calcular absoluto para tmdb={tvshow_tmdb_id} S{season_number:02d}", xbmc.LOGWARNING)
        return None

    abs_ep = prev_count + episode_number

    # Sanidade: absoluto não pode ultrapassar total da série
    if total_episodes and abs_ep > total_episodes:
        xbmc.log(
            f"[abs_ep] ⚠️ Calculado {abs_ep} > total {total_episodes} para "
            f"tmdb={tvshow_tmdb_id} S{season_number:02d}E{episode_number:02d} — ignorando",
            xbmc.LOGWARNING
        )
        return None

    xbmc.log(f"[abs_ep] S{season_number:02d}E{episode_number:02d} → absoluto {abs_ep}", xbmc.LOGDEBUG)
    return abs_ep 
    

def _fetch_tmdb_season_details(tmdb_id, season_number):
    """Busca os detalhes de uma temporada direto do TMDB."""
    import urllib.request
    import urllib.error

    if not TMDB_API_KEY or TMDB_API_KEY == "SUA_CHAVE_API_V3_DO_TMDB_AQUI":
        xbmc.log("[ERRO] Chave de API do TMDB não configurada.", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro de Configuração", "A chave de API do TMDB não foi definida.")
        return []

    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_number}?api_key={TMDB_API_KEY}&language=pt-BR"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            import json
            data = json.loads(response.read().decode('utf-8'))
            return data.get('episodes', [])
    except urllib.error.URLError as e:
        xbmc.log(f"[ERRO TMDB] Falha ao buscar temporada {tmdb_id} S{season_number}: {e}", xbmc.LOGERROR)
        return []
    except Exception as e:
        xbmc.log(f"[ERRO TMDB] Erro inesperado: {e}", xbmc.LOGERROR)
        return []



# --- LISTAGENS DE SÉRIES (MENUS) ---

@with_view_mode('genres', is_menu=True)
def list_tvshows_genres():
    """Cria e exibe a lista de Gêneros de Séries."""
    HANDLE = int(sys.argv[1])
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
    HANDLE = int(sys.argv[1])
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
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, genre)
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    # Buscar do banco
    shows = db.get_tvshows_by_genre(genre, page, _get_items_per_page())
    
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_genre', genre=genre)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_provider(provider, page=1):
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, provider)
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    
    shows = db.get_tvshows_by_provider(provider, page, _get_items_per_page())
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_provider', provider=provider)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_popularity(page=1):
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, "Mais Populares")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    shows = db.get_tvshows_by_popularity(page, _get_items_per_page())
    
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
    
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_tvshows_by_popularity')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_recently_added_tvshows(page=1):
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, "Adicionados Recentemente")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    shows = db.get_recently_added_tvshows(page, _get_items_per_page())

    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_recently_added_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_animes(page=1):
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, "Animes")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    shows = db.get_tvshows_by_genre('anime', page, _get_items_per_page())
    
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_animes')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('tvshows')
def list_kids_tvshows(page=1):
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, "Infantil")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    shows = db.get_kids_tvshows(page, _get_items_per_page())

    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_kids_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_trending_tvshows(page=1):
    HANDLE = int(sys.argv[1])
    from .tmdb_api import fetch_trending_tvshows
    xbmcplugin.setPluginCategory(HANDLE, "Em Alta")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    page = int(page)
    
    # Busca os dados na API (já com Threads e Cache do tmdb_api.py)
    shows = fetch_trending_tvshows(page)
    
    items_to_add = []
    for show in shows:
        items_to_add.append(_create_show_tuple(show))
        
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(shows, page, action='list_trending_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)
    
    
# Adicione estas funções no tvshows.py

@with_view_mode('genres', is_menu=True)
def list_tvshow_themes():
    """Menu de categorias temáticas de séries"""
    from .keywords import get_all_theme_categories
    
    HANDLE = int(sys.argv[1])
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
    """Lista séries de uma categoria temática — filtro 100% local, zero API."""
    from .keywords import get_theme_config, get_theme_keywords
    from .db import db

    config = get_theme_config(theme)
    if not config:
        xbmcgui.Dialog().ok("Erro", "Categoria não encontrada")
        return
    
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, config['name'])
    xbmcplugin.setContent(HANDLE, 'tvshows')

    keyword_list = get_theme_keywords(theme)
    if not keyword_list:
        xbmcgui.Dialog().ok("Erro", f"Sem keywords configuradas para '{config['name']}'")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    page = int(page)
    offset = (page - 1) * _get_items_per_page()

    shows = db.get_tvshows_by_keywords(
        keyword_list,
        _get_items_per_page(),
        offset,
    )

    if not shows:
        xbmcgui.Dialog().ok("Aviso", f"Nenhuma série encontrada em '{config['name']}'")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items_to_add = [_create_show_tuple(s) for s in shows]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))

    if len(shows) == _get_items_per_page():
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="Próxima Página")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        next_url = get_url(action='list_tvshows_by_theme', theme=theme, page=page + 1)
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li_next, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


RATING_CATEGORIES_TV = [
    {'label': 'Obra-prima',  'slug': 'masterpiece', 'min': 9.0, 'max': 10.1, 'plot': 'Séries com nota 9.0 ou superior.'},
    {'label': 'Excelente',   'slug': 'excellent',    'min': 8.0, 'max': 9.0,  'plot': 'Séries com nota entre 8.0 e 8.9.'},
    {'label': 'Muito Bom',   'slug': 'verygood',     'min': 7.0, 'max': 8.0,  'plot': 'Séries com nota entre 7.0 e 7.9.'},
    {'label': 'Regular',     'slug': 'average',      'min': 5.0, 'max': 7.0,  'plot': 'Séries com nota entre 5.0 e 6.9.'},
]

@with_view_mode('genres', is_menu=True)
def list_rating_categories_tvshows():
    """Menu de faixas de nota para séries."""
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, 'Por Nota')
    xbmcplugin.setContent(HANDLE, 'genres')

    for cat in RATING_CATEGORIES_TV:
        li = xbmcgui.ListItem(label=cat['label'])
        li.setInfo('video', {'plot': cat['plot']})
        url = get_url(action='list_tvshows_by_rating_category', slug=cat['slug'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_rating_category(slug, page=1):
    """Lista séries de uma faixa de nota específica."""
    cat = next((c for c in RATING_CATEGORIES_TV if c['slug'] == slug), None)
    if not cat:
        xbmcgui.Dialog().ok('Erro', 'Categoria de nota não encontrada.')
        return

    content_filter = get_content_filter()
    db.set_content_filter(content_filter)

    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, cat['label'])
    xbmcplugin.setContent(HANDLE, 'tvshows')

    shows = db.get_tvshows_by_rating_range(
        min_rating=cat['min'],
        max_rating=cat['max'],
        min_votes=50,
        page=int(page),
        page_size=_get_items_per_page(),
    )

    if not shows:
        xbmcgui.Dialog().notification(cat['label'], 'Nenhuma série encontrada.', xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items_to_add = [_create_show_tuple(s) for s in shows]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))

    has_next = shows[0].get('_has_next_page', False)
    if has_next:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label='Próxima Página')
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        next_url = get_url(action='list_tvshows_by_rating_category', slug=slug, page=int(page) + 1)
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li_next, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('movies')
def list_most_searched_shows(page=1):
    """
    Lista séries mais buscadas baseado nas queries populares do Supabase.
    """
    from .trending_tracker import get_popular_queries_from_supabase
    from .db.db import db_instance as db

    page = int(page)
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, 'Mais Buscadas')
    xbmcplugin.setContent(HANDLE, 'tvshows')

    popular_clicks = get_popular_queries_from_supabase(limit=50, min_count=2)
    popular_clicks = [c for c in popular_clicks if c.get('content_type') in ('tv', 'tvshow')]

    if not popular_clicks:
        xbmcgui.Dialog().notification(
            "Mais Buscadas",
            "Nenhum dado disponível ainda",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    all_shows = []
    for click in popular_clicks:
        tmdb_id    = click.get('tmdb_id')
        view_count = click.get('view_count', 0)
        try:
            show = db.get_tvshow_by_id(tmdb_id)
            if show:
                all_shows.append((show, view_count))
        except Exception:
            pass

    items_per_page = 20
    start     = (page - 1) * items_per_page
    end       = start + items_per_page
    page_shows = all_shows[start:end]

    items = []
    for show_data, search_count in page_shows:
        try:
            url, li, is_folder = _create_show_tuple(show_data)
            title = show_data.get('title', '')
            li.setLabel(f"{title} [{search_count}🔥]")
            items.append((url, li, is_folder))
        except Exception:
            continue

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))

    # Passa a lista (page_shows), não len() dela
    if len(all_shows) > end:
        add_next_page_item(page_shows, page, action='list_most_searched_shows')

    xbmcplugin.endOfDirectory(HANDLE)