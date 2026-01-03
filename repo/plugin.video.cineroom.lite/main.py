# -*- coding: utf-8 -*-
import sys
import os
from urllib.parse import parse_qsl

# ============ IMPORTS ESSENCIAIS ============
import xbmcgui
import xbmc
import xbmcaddon

# Variáveis globais
HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")

# ============ INICIALIZA SCROBBLER AUTOMÁTICO ============
_SCROBBLER = None

# Inicializa imediatamente
try:
    from resources.lib.trakt_sync import init_trakt_scrobbler
    _SCROBBLER = init_trakt_scrobbler()
except:
    pass

def _init_scrobbler():
    """Inicializa o monitor de scrobble automático do Trakt"""
    global _SCROBBLER
    
    try:
        # Verifica se o scrobbler está ativado nas configurações
        if not ADDON.getSettingBool('trakt_auto_scrobble'):
            if _SCROBBLER:
                del _SCROBBLER
                _SCROBBLER = None
            return None
        
        # Se já existe, retorna
        if _SCROBBLER is not None:
            return _SCROBBLER
        
        # Tenta importar e criar
        from resources.lib.trakt_sync import TraktScrobbler
        _SCROBBLER = TraktScrobbler()
        xbmc.log("[Cineroom] Scrobbler Trakt iniciado", xbmc.LOGINFO)
        return _SCROBBLER
        
    except Exception as e:
        xbmc.log(f"[Cineroom] Erro ao inicializar Scrobbler: {e}", xbmc.LOGERROR)
        _SCROBBLER = None
        return None


# ============ SISTEMA DE CACHE OTIMIZADO ============
_MODULE_CACHE = {}
_JSON_CACHE = {}
_ACTION_HANDLERS = {}  # ✅ NOVO: Cache de handlers compilados

def _get_module(name):
    """Lazy loading ultrarrápido com cache de módulos"""
    if name in _MODULE_CACHE:
        return _MODULE_CACHE[name]
    
    try:
        if name == 'movies':
            from resources.lib import movies as mod
        elif name == 'tvshows':
            from resources.lib import tvshows as mod
        elif name == 'navigation':
            from resources.lib import navigation as mod
        elif name == 'extras_dialog':
            from resources.lib import extras_dialog as mod
        elif name == 'indexer':
            from resources.lib import indexer as mod
        elif name == 'favorites':
            from resources.lib import favorites as mod
        elif name == 'db':
            from resources.lib.db import db as mod
        elif name == 'constants':
            from resources.lib import constants as mod
        elif name == 'xbmcplugin':
            import xbmcplugin as mod
        elif name == 'donation_window':
            from resources.lib.donation_window import DonationDialog as mod
        elif name == 'trakt_sync':
            from resources.lib import trakt_sync as mod
        elif name == 'library':
            from resources.lib import library as mod
        else:
            return None
        
        _MODULE_CACHE[name] = mod
        return mod
    except ImportError as e:
        xbmc.log(f"[Cineroom] Falha ao importar {name}: {e}", xbmc.LOGERROR)
        return None

def _parse_json(data):
    """Cache inteligente de JSON com limite de memória"""
    if not data:
        return {}
    
    if data in _JSON_CACHE:
        return _JSON_CACHE[data]
    
    try:
        from urllib.parse import unquote_plus
        import json
        parsed = json.loads(unquote_plus(data))
        
        # Limita cache a 50 entradas
        if len(_JSON_CACHE) > 50:
            _JSON_CACHE.clear()
        
        _JSON_CACHE[data] = parsed
        return parsed
    except:
        return {}

def _end_dir(success=True):
    """Helper rápido para endOfDirectory"""
    xbmcplugin = _get_module('xbmcplugin')
    if xbmcplugin:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=success)

# ============ MAPEAMENTO DE AÇÕES - OTIMIZADO ============
_ACTIONS = {
    
    
    # == TRAKT.TV ===
    'list_trakt_watchlist': ('trakt_sync', 'list_trakt_watchlist', False, None),
    'list_trakt_collection': ('trakt_sync', 'list_trakt_collection', False, None),
    'list_trakt_watched': ('trakt_sync', 'list_trakt_watched', False, None),

    
    # === TRAKT FILMES ===
    'trakt_movies_trending': ('trakt_sync', 'trakt_movies_trending', True, None),
    'trakt_movies_popular': ('trakt_sync', 'trakt_movies_popular', True, None),
    'trakt_movies_most_watched': ('trakt_sync', 'trakt_movies_most_watched', True, None),
    'trakt_movies_most_collected': ('trakt_sync', 'trakt_movies_most_collected', True, None),
    'trakt_movies_most_anticipated': ('trakt_sync', 'trakt_movies_most_anticipated', True, None),
    'trakt_movies_box_office': ('trakt_sync', 'trakt_movies_box_office', True, None),
    'trakt_movies_top_rated': ('trakt_sync', 'trakt_movies_top_rated', True, None),
    'trakt_movies_personal_recommended': ('trakt_sync', 'trakt_movies_personal_recommended', True, None),
    
    
    # === TRAKT SÉRIES ===
    'trakt_tv_trending': ('trakt_sync', 'trakt_tv_trending', True, None),
    'trakt_tv_popular': ('trakt_sync', 'trakt_tv_popular', True, None),
    'trakt_tv_most_watched': ('trakt_sync', 'trakt_tv_most_watched', True, None),
    'trakt_tv_most_collected': ('trakt_sync', 'trakt_tv_most_collected', True, None),
    'trakt_tv_most_anticipated': ('trakt_sync', 'trakt_tv_most_anticipated', True, None),
    'trakt_tv_top_rated': ('trakt_sync', 'trakt_tv_top_rated', True, None),
    'trakt_tv_recommended': ('trakt_sync', 'trakt_tv_recommended', True, None),
    'trakt_tv_personal_recommended': ('trakt_sync', 'trakt_tv_personal_recommended', True, None),
    
    # === FILMES ===
    'list_genres': ('movies', 'list_genres', False, None),
    'list_years': ('movies', 'list_years', False, None),
    'list_movies_by_genre': ('movies', 'list_movies_by_genre', True, ['genre']),
    'list_movies_by_year': ('movies', 'list_movies_by_year', True, ['year']),
    'list_movies_by_rating': ('movies', 'list_movies_by_rating', True, None),
    'list_movies_by_popularity': ('movies', 'list_movies_by_popularity', True, None),
    'list_4k_movies': ('movies', 'list_4k_movies', True, None),
    'list_collections': ('movies', 'list_collections', True, None),
    'list_movies_by_collection': ('movies', 'list_movies_by_collection', True, ['collection']),
    'list_recently_added_movies': ('movies', 'list_recently_added_movies', True, None),
    'list_movies_by_revenue': ('movies', 'list_movies_by_revenue', True, None),
    'list_movies_by_provider': ('movies', 'list_movies_by_provider', True, ['provider']),
    'list_trending_movies': ('movies', 'list_trending_movies', True, None),
    
    # === SÉRIES ===
    'list_tvshows_genres': ('tvshows', 'list_tvshows_genres', False, None),
    'list_providers': ('tvshows', 'list_providers', False, None),
    'list_trending_tvshows': ('tvshows', 'list_trending_tvshows', True, None),
    'list_tvshows_by_genre': ('tvshows', 'list_tvshows_by_genre', True, ['genre']),
    'list_recently_added_tvshows': ('tvshows', 'list_recently_added_tvshows', True, None),
    'list_tvshows_by_popularity': ('tvshows', 'list_tvshows_by_popularity', True, None),
    'list_tvshows_by_provider': ('tvshows', 'list_tvshows_by_provider', True, ['provider']),
    'list_animes': ('tvshows', 'list_animes', True, None),
    'list_kids_tvshows': ('tvshows', 'list_kids_tvshows', True, None),
}

def _get_action_handler(action):
    """
    ✅ NOVA FUNÇÃO: Retorna handler pré-compilado
    Evita lookup repetido no dicionário _ACTIONS
    """
    if action in _ACTION_HANDLERS:
        return _ACTION_HANDLERS[action]
    
    config = _ACTIONS.get(action)
    if not config:
        return None
    
    module_name, method_name, needs_page, extra_params = config
    
    # Cria handler como tupla (mais rápido que dict)
    handler = (module_name, method_name, needs_page, extra_params)
    _ACTION_HANDLERS[action] = handler
    
    return handler

def _handle_generic_action(action, params):
    """Handler genérico OTIMIZADO"""
    handler = _get_action_handler(action)
    if not handler:
        return False
    
    module_name, method_name, needs_page, extra_params = handler
    
    # Carrega módulo (cached)
    mod = _get_module(module_name)
    if not mod:
        return False
    
    # Pega método (cached pelo Python)
    method = getattr(mod, method_name, None)
    if not method:
        return False
    
    # Monta args
    args = []
    
    if extra_params:
        for param in extra_params:
            val = params.get(param, '')
            if param == 'year':
                val = int(val) if val else 0
            args.append(val)
    
    if needs_page:
        args.append(int(params.get('page', '1')))
    
    # Executa
    method(*args)
    return True

# ============ HANDLERS ESPECÍFICOS OTIMIZADOS ============

def _handle_show_details(params):
    """Handler otimizado para detalhes"""
    item_data = _parse_json(params.get('data', ''))
    if not item_data:
        return False
    
    media_type = item_data.get("media_type")
    setting_key = f"{media_type}.enable_details"
    
    if not ADDON.getSettingBool(setting_key):
        nav = _get_module('navigation')
        if nav:
            autoplay = (media_type == "movie")
            nav.find_and_play_sources(item_data, autoplay=autoplay)
    else:
        dialog = _get_module('extras_dialog')
        if dialog:
            dialog.show_details(item_data)
    
    return True

def _handle_list_seasons(params):
    """Handler otimizado para temporadas"""
    tv = _get_module('tvshows')
    if tv:
        tv.list_seasons(tvshow_tmdb_id=params.get('tvshow_tmdb_id'))
        return True
    return False

def _handle_list_episodes(params):
    """Handler otimizado para episódios"""
    tv = _get_module('tvshows')
    if tv:
        tv.list_episodes(
            params.get('tvshow_tmdb_id'),
            int(params.get('season_number', 1))
        )
        return True
    return False

def _handle_favorites(action, params):
    """Handler otimizado para favoritos"""
    fav = _get_module('favorites')
    if not fav:
        return False
    
    if action == 'add_to_favorites':
        fav.add_item_to_favorites(params.get('tmdb_id'), params.get('media_type'))
    elif action == 'remove_from_favorites':
        fav.remove_item_from_favorites(params.get('tmdb_id'), params.get('media_type'))
    elif action == 'favorites_menu':
        nav = _get_module('navigation')
        if nav:
            nav.show_my_list_menu()
    elif action == 'favorites_movies':
        nav = _get_module('navigation')
        if nav:
            nav.show_favorite_movies()
    elif action == 'favorites_tvshows':
        nav = _get_module('navigation')
        if nav:
            nav.show_favorite_tvshows()
    else:
        return False
    
    return True


def _handle_trakt(action, params):
    """Handler COMPLETO para Trakt - com ações individuais"""
    
    # Menu principal - não precisa importar nada
    if action == 'trakt_main_menu':
        nav = _get_module('navigation')
        const = _get_module('constants')
        if nav and const:
            nav.show_main_menu(const.TRAKT_MENU)
        return True
    
    # Sync menu - não precisa importar nada
    if action == 'trakt_sync_menu':
        nav = _get_module('navigation')
        const = _get_module('constants')
        if nav and const:
            nav.show_main_menu(const.TRAKT_SYNC_MENU)
        return True
    

    trakt = _get_module('trakt_sync')
    if not trakt:
        return False

    tmdb_id = params.get('tmdb_id')
    media_type = params.get('media_type')
    
    if action == 'trakt_add_collection':
        if tmdb_id and media_type:
            trakt.trakt_add_to_collection(tmdb_id, media_type)
        return True
    
    if action == 'trakt_remove_collection':
        if tmdb_id and media_type:
            trakt.trakt_remove_from_collection(tmdb_id, media_type)
        return True
    
    if action == 'trakt_mark_watched':
        if tmdb_id and media_type:
            trakt.trakt_mark_as_watched(tmdb_id, media_type)
        return True
    
    if action == 'trakt_remove_watched':
        if tmdb_id and media_type:
            trakt.trakt_remove_watched(tmdb_id, media_type)
        return True
    
    if action == 'trakt_add_watchlist':
        if tmdb_id and media_type:
            trakt.trakt_add_to_watchlist(tmdb_id, media_type)
        return True
    
    if action == 'trakt_remove_watchlist':
        if tmdb_id and media_type:
            trakt.trakt_remove_from_watchlist(tmdb_id, media_type)
        return True
    
    if action == 'trakt_rate':
        if tmdb_id and media_type:
            trakt.trakt_rate_item(tmdb_id, media_type)
        return True
    
    # ============================================
    # AUTH E STATUS
    # ============================================
    
    if action == 'trakt_auth':
        settings = trakt.get_trakt_settings()
        if settings.get('access_token'):
            trakt.show_trakt_status()
        else:
            trakt.authenticate_trakt()
        return True
    
    if action == 'trakt_status':
        trakt.show_trakt_status()
        return True
    
    # ============================================
    # MENUS DE LISTAGEM
    # ============================================
    
    page = int(params.get('page', 1))
    
    if action == 'trakt_watchlist_menu':
        trakt.show_trakt_watchlist_items(page)
        return True
    
    if action == 'trakt_collection_menu':
        trakt.show_trakt_collection_items(page)
        return True
    
    if action == 'trakt_watched_menu':
        trakt.show_trakt_watched_items(page)
        return True
    
    if action == 'trakt_trending_menu':
        trakt.show_trakt_trending_items(page)
        return True
    
    if action == 'trakt_popular_menu':
        trakt.show_trakt_popular_items(page)
        return True
    
    # Listas customizadas
    if action == 'trakt_lists_menu':
        trakt.show_trakt_custom_lists()
        return True
    
    if action == 'trakt_list_items':
        list_id = params.get('list_id')
        trakt.show_trakt_list_items(list_id, page)
        return True
    
    # ============================================
    # SYNC
    # ============================================
    
    if action == 'trakt_full_sync':
        trakt.full_bidirectional_sync()
        return True
    
    if action == 'trakt_sync_to_trakt':
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt", "Enviando dados...")
        trakt.sync_local_to_trakt(progress)
        progress.close()
        return True
    
    if action == 'trakt_sync_from_trakt':
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt", "Importando dados...")
        trakt.sync_trakt_to_local(progress)
        progress.close()
        return True
    
    if action == 'trakt_sync':
        direction = params.get('direction', 'both')
        trakt.full_sync_with_trakt(direction)
        return True
    
    if action == 'trakt_clear_cache':
        trakt.clear_trakt_cache()
        return True
    
    if action == 'trakt_toggle_scrobble':
        current = ADDON.getSettingBool('trakt_auto_scrobble')
        ADDON.setSettingBool('trakt_auto_scrobble', not current)
        status = "ativado ✅" if not current else "desativado ❌"
        xbmcgui.Dialog().notification("Trakt Scrobbler", f"Scrobble automático {status}", xbmcgui.NOTIFICATION_INFO, 3000)
        return True
    
    if action == 'trakt_public_lists':
        trakt.show_trakt_public_lists_menu()
        return True
    
    if action == 'trakt_public_category':
        trakt.show_trakt_public_category(params.get('category'))
        return True
    
    if action == 'trakt_public_list':
        category = params.get('category')
        media_type = params.get('media_type')
        page = int(params.get('page', 1))
        trakt.show_trakt_public_list(category, media_type, page)
        return True
    
    if action == 'trakt_movies_submenu':
        nav = _get_module('navigation')
        const = _get_module('constants')
        if nav and const:
            nav.show_main_menu(const.TRAKT_MOVIES_MENU)
        return True

    if action == 'trakt_tv_submenu':
        nav = _get_module('navigation')
        const = _get_module('constants')
        if nav and const:
            nav.show_main_menu(const.TRAKT_TV_MENU)
        return True
    
    return False
    

def _handle_navigation(action, params):
    """Handler otimizado para navegação"""
    nav = _get_module('navigation')
    if not nav:
        return False
    
    if action == 'search':
        nav.search(params.get('query'), params.get('page', '1'))
        return True
    
    if action == 'find_sources':
        item_data = {
            'tmdb_id': params.get('tmdb_id', ''),
            'imdb_id': params.get('imdb_id', ''),
            'media_type': params.get('media_type', ''),
            'title': params.get('title', ''),
            'original_title': params.get('original_title', ''),
            'year': params.get('year', ''),
            'clearlogo': params.get('clearlogo', ''),
            'fanart': params.get('fanart', ''),
            'backdrop': params.get('backdrop', ''),
            'poster': params.get('poster', ''),
            'season': params.get('season'),
            'episode': params.get('episode')
        }
        nav.find_and_play_sources(
            item_data,
            season=params.get('season'),
            episode=params.get('episode')
        )
        return True
    
    if action == 'play_item_direct':
        item_data = _parse_json(params.get('data', ''))
        if item_data:
            nav.find_and_play_sources(item_data, autoplay=False)
        return True
    
    if action == 'find_and_play_episode':
        item_data = _parse_json(params.get('item_data', ''))
        if item_data:
            nav.find_and_play_sources(
                item_data,
                autoplay=False,
                season=params.get('season'),
                episode=params.get('episode')
            )
        return True
    
    return False

def _handle_menu(action, params):
    """Handler otimizado para menus"""
    const = _get_module('constants')
    if not const:
        return False
    
    if action == 'movies_menu':
        movies = _get_module('movies')
        if movies:
            movies.show_movies_menu(const.MOVIES_MENU)
            return True
    
    if action == 'tvshows_menu':
        tv = _get_module('tvshows')
        if tv:
            tv.show_tvshows_menu(const.TVSHOWS_MENU)
            return True
    
    if action == 'tools_menu':
        nav = _get_module('navigation')
        if nav:
            nav.show_main_menu(const.TOOLS_MENU)
            return True
    
    return False

def _handle_library(action, params):
    """Handler OTIMIZADO para biblioteca - Lazy import"""
    
    # Menu não precisa de import
    if action == 'library_menu':
        win = xbmcgui.Window(10000)
        warned = win.getProperty("cineroom.library.warning")
        
        if not warned:
            ok = xbmcgui.Dialog().yesno(
                "Biblioteca (Experimental)",
                "Função em teste. Recomendado apenas para usuários avançados!\n\nDeseja continuar?"
            )
            if not ok:
                return False
            win.setProperty("cineroom.library.warning", "true")
        
        # ✅ LAZY IMPORT apenas aqui
        lib = _get_module('library')
        if lib and hasattr(lib, 'show_library_menu'):
            lib.show_library_menu()
            return True
        return False
    
    # ✅ LAZY IMPORT apenas para ações que precisam
    lib = _get_module('library')
    if not lib:
        return False
    
    db = _get_module('db')
    
    if action == 'library_add':
        tmdb_id = params.get('tmdb_id')
        media_type = params.get('media_type')
        
        if tmdb_id and media_type and db:
            if media_type == 'movie':
                item_data = db.get_movie_by_id(tmdb_id)
                if item_data and hasattr(lib, 'add_movie_to_library'):
                    lib.add_movie_to_library(item_data)
            
            elif media_type == 'tvshow':
                item_data = db.get_tvshow_by_id(tmdb_id)
                if item_data and xbmcgui.Dialog().yesno("Adicionar", f"Adicionar {item_data.get('title')}?"):
                    if hasattr(lib, 'add_tvshow_to_library'):
                        lib.add_tvshow_to_library(item_data)
                    if xbmcgui.Dialog().yesno("Kodi", "Atualizar biblioteca agora?"):
                        if hasattr(lib, 'update_kodi_library'):
                            lib.update_kodi_library(media_type)
        return True
    
    if action == 'library_remove':
        tmdb_id = params.get('tmdb_id')
        media_type = params.get('media_type')
        if tmdb_id and media_type and xbmcgui.Dialog().yesno("Remover", "Deseja remover da biblioteca?"):
            if hasattr(lib, 'remove_from_library'):
                lib.remove_from_library(tmdb_id, media_type)
        return True
    
    if action == 'library_update':
        if hasattr(lib, 'update_kodi_library'):
            lib.update_kodi_library(params.get('media_type', 'video'))
        return True
    
    if action == 'library_add_all_movies':
        if hasattr(lib, 'add_all_movies_to_library'):
            lib.add_all_movies_to_library()
        return True
    
    if action == 'library_add_all_tvshows':
        if hasattr(lib, 'add_all_tvshows_to_library'):
            lib.add_all_tvshows_to_library()
        return True
    
    if action == 'library_stats':
        if hasattr(lib, 'get_library_stats'):
            stats = lib.get_library_stats()
            xbmcgui.Dialog().ok("Estatísticas", f"Filmes: {stats['movies']}\nSéries: {stats['tvshows']}\nEpisódios: {stats['episodes']}")
        return True
    
    return False

# ============ ROUTER PRINCIPAL - ULTRA OTIMIZADO ============

def router():
    """Router principal - OTIMIZADO"""
    # Parse de parâmetros
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2] else {}
    action = params.get('action', '')
    
    # ============ AUTO-HEAL: CHECAGEM DE BANCO VAZIO ============
    if not action:
        try:
            db = _get_module('db')
            if db and not db.get_all_movie_ids_set():
                indexer = _get_module('indexer')
                if indexer:
                    indexer.run_indexer()
        except Exception as e:
            xbmc.log(f"[Cineroom] Erro na checagem de banco: {e}", xbmc.LOGERROR)
    
    # ============ ROOT DO ADDON ============
    if not action:
        nav = _get_module('navigation')
        const = _get_module('constants')
        
        if nav and const:
            nav.show_main_menu(const.MAIN_MENU)
            return _end_dir(True)
        else:
            xbmc.log("[Cineroom] Falha ao carregar menu principal", xbmc.LOGERROR)
            return _end_dir(False)
    
    # ============ ROUTING OTIMIZADO POR CATEGORIA ============
    
    # ✅ Ações genéricas (mais comuns, testam primeiro)
    if _handle_generic_action(action, params):
        return _end_dir()
    
    # ✅ Detalhes
    if action == 'show_details':
        return _end_dir(_handle_show_details(params))
    
    # ✅ Séries (casos especiais)
    if action == 'list_seasons':
        return _end_dir(_handle_list_seasons(params))
    
    if action == 'list_episodes':
        return _end_dir(_handle_list_episodes(params))
    
    # ✅ Favoritos
    if action in ('add_to_favorites', 'remove_from_favorites', 'favorites_menu', 'favorites_movies', 'favorites_tvshows'):
        return _end_dir(_handle_favorites(action, params))
    
    # ✅ Trakt
    if action.startswith('trakt_'):
        return _end_dir(_handle_trakt(action, params))
    
    # ✅ Navegação
    if action in ('search', 'find_sources', 'play_item_direct', 'find_and_play_episode'):
        return _end_dir(_handle_navigation(action, params))
    
    # ✅ Menus
    if action in ('movies_menu', 'tvshows_menu', 'tools_menu'):
        return _end_dir(_handle_menu(action, params))
    
    # ✅ Biblioteca
    if action.startswith('library_'):
        return _end_dir(_handle_library(action, params))
    
    # ✅ Sistema
    if action == 'run_indexer':
        indexer = _get_module('indexer')
        if indexer:
            indexer.run_indexer()
        return _end_dir()
    
    if action == 'show_donation':
        DonationDialog = _get_module('donation_window')
        if DonationDialog:
            DonationDialog("DonationDialog.xml", ADDON_PATH, "Default", "1080i").doModal()
        return _end_dir()
    
    if action == 'open_settings':
        xbmc.executebuiltin(f'Addon.OpenSettings({ADDON.getAddonInfo("id")})')
        return _end_dir()
    
    if action == 'show_changelog':
        import xbmcvfs
        from resources.lib.dialog.changelog_dialog import ChangelogDialog
        
        changelog_path = xbmcvfs.translatePath(os.path.join(ADDON_PATH, "changelog.txt"))
        
        text = "Changelog não encontrado."
        if xbmcvfs.exists(changelog_path):
            f = xbmcvfs.File(changelog_path)
            text = f.read()
            f.close()
        
        dialog = ChangelogDialog(
            "ChangelogDialog.xml",
            ADDON_PATH,
            "Default",
            "1080i",
            heading="Changelog — Cineroom Lite",
            text=text
        )
        dialog.doModal()
        del dialog
        return _end_dir()
    
    # ============ ACTION NÃO ENCONTRADO ============
    xbmc.log(f"[Cineroom] Action desconhecida: {action}", xbmc.LOGWARNING)
    return _end_dir(False)

if __name__ == '__main__':
    try:
        
        _init_scrobbler()
        
        router()
    except Exception as e:
        xbmc.log(f"[Cineroom] ERRO CRÍTICO: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        _end_dir(False)