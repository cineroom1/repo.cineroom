# -*- coding: utf-8 -*-
import sys
from urllib.parse import parse_qsl

import xbmc
import xbmcgui
import xbmcaddon
import os

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

from .context import (
    ADDON, end_dir, get_module, get_profile_manager, init_scrobbler
)
from .actions import handle_generic_action
from .handlers.details import handle_show_details
from .handlers.tv import handle_list_seasons, handle_list_episodes
from .handlers.favorites import handle_favorites
from .handlers.trakt import handle_trakt
from .handlers.navigation import handle_navigation
from .handlers.menu import handle_menu
from .handlers.library import handle_library
from .handlers.profiles import handle_profiles
from .handlers.system import handle_system
from .handlers.vip import handle_vip_gate, handle_vip_logout

try:
    from resources.lib.vip_auth import VIP_ACTIONS, is_session_valid, show_welcome_screen
except Exception:
    VIP_ACTIONS = set()
    is_session_valid    = lambda: False
    show_welcome_screen = lambda: 'anon'

_WELCOME_SHOWN_KEY = 'welcome_screen_shown'

# Actions de recomendações (só PLUS)
_RECOMMENDATIONS_ACTIONS = {
    'show_recommendations_menu',
    'list_recommendations_movies',
    'list_recommendations_tvshows',
}

# Actions de histórico e avaliações — disponíveis para FREE e PLUS
_HISTORY_ACTIONS = {
    'show_history_menu',
    'list_history_all',
    'list_history_movies',
    'list_history_tvshows',
    'list_history_in_progress',
    'list_history_liked',
    'list_history_liked_movies',
    'list_history_liked_tvshows',
    'list_history_disliked',
    'list_history_disliked_movies',
    'list_history_disliked_tvshows',
    'rating_remove',
    'history_remove',
    'history_unwatch',
    'backup_menu',
    'backup_export',
    'backup_import',
    'backup_configure',
    'backup_toggle_auto',
}


def _check_vip(action):
    if action in _HISTORY_ACTIONS:
        return True
    if action not in VIP_ACTIONS:
        return True
    return handle_vip_gate(action)


def _build_anon_menu(nav, const):
    nav.show_main_menu(const.MAIN_MENU_ANON)


def _build_plus_menu(nav, const, pm):
    current_profile = pm.get_current_profile() if pm else None
    is_kids = current_profile.get('is_kids', False) if current_profile else False

    base_menu = const.MAIN_MENU_KIDS if is_kids else const.MAIN_MENU
    base_menu_list = list(base_menu)

    if current_profile:
        profile_name = current_profile.get('name', 'Perfil')
        if is_kids:
            age_range = current_profile.get('preferences', {}).get('age_range', 'livre')
            indicator_plot = f'Perfil infantil ativo. Conteúdo filtrado para {age_range}.'
        else:
            indicator_plot = 'Perfil PLUS ativo. Para trocar, acesse Minha Conta.'

    if not is_kids:
        trakt_token = ADDON.getSetting('trakt_access_token')
        if trakt_token:
            trakt_item = getattr(const, 'MAIN_MENU_TRAKT_ITEM', None)
            if trakt_item:
                base_menu_list = base_menu_list + [trakt_item]

    nav.show_main_menu(base_menu_list)


def router():
    params = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 and sys.argv[2] else {}
    action = params.get('action', '')

    # ── ROOT do addon ─────────────────────────────────────────────────────────
    if not action:
        nav   = get_module('navigation')
        const = get_module('constants')

        if not nav or not const:
            xbmc.log('[Cineroom] Falha ao carregar menu principal', xbmc.LOGERROR)
            return end_dir(False)

        vip_ok = is_session_valid()

        if vip_ok:
            pm = get_profile_manager()
            if pm and pm.should_show_profile_selector():
                profile = pm.show_profile_selector()
                if not profile:
                    _build_anon_menu(nav, const)
                    return end_dir(True)
                return end_dir(True)

            _auto_heal_db()
            _build_plus_menu(nav, const, pm)

        else:
            if ADDON.getSetting('reset_welcome_screen') == 'true':
                ADDON.setSetting('reset_welcome_screen', 'false')
                ADDON.setSetting(_WELCOME_SHOWN_KEY, '')

            welcome_shown = ADDON.getSetting(_WELCOME_SHOWN_KEY)

            if not welcome_shown:
                ADDON.setSetting(_WELCOME_SHOWN_KEY, 'true')
                choice = show_welcome_screen()

                if choice == 'vip':
                    if handle_vip_gate('vip_menu'):
                        pm = get_profile_manager()
                        if pm:
                            pm.show_profile_selector()
                        _auto_heal_db()
                        _build_plus_menu(nav, const, get_profile_manager())
                        return end_dir(True)

            _auto_heal_db()
            _build_anon_menu(nav, const)

        try:
            from resources.lib.notification import show_notifications_panel
            actions = show_notifications_panel()
            for action in actions:
                plugin_url = f'plugin://plugin.video.cineroom.lite/?action={action}'
                xbmc.executebuiltin(f'RunPlugin({plugin_url})')
        except Exception as e:
            xbmc.log(f'[Cineroom] Erro na notificação: {e}', xbmc.LOGWARNING)

        return end_dir(True)

    # ── Noop — indicador de perfil no menu, não faz nada ─────────────────────
    if action == 'noop':
        return end_dir(True)

    # ── Logout PLUS ────────────────────────────────────────────────────────────
    if action == 'vip_logout':
        pm = get_profile_manager()
        if pm:
            pm.logout_profile()
        return end_dir(handle_vip_logout())

    # ── Login PLUS ─────────────────────────────────────────────────────────────
    if action == 'vip_login':
        return end_dir(handle_menu(action, params))

    # ── Gate PLUS ──────────────────────────────────────────────────────────────
    if not _check_vip(action):
        return end_dir(False)

    # ── Troca de perfil (só PLUS) — ainda disponível via URL direta ───────────
    if action.startswith('profile_'):
        result = handle_profiles(action, params)
        addon_id = ADDON.getAddonInfo('id')
        xbmc.executebuiltin(f'Container.Update(plugin://{addon_id}/,replace)')
        return end_dir(result)

    # ── Histórico, Avaliações e Backup (free e PLUS) ───────────────────────────
    if action in _HISTORY_ACTIONS:
        if action in ('backup_menu', 'backup_export', 'backup_import',
                      'backup_configure', 'backup_toggle_auto'):
            from resources.lib.history_backup import (
                show_backup_menu, export_history, import_history,
                configure_backup_folder, toggle_auto_backup,
            )
            _backup_handlers = {
                'backup_menu':        show_backup_menu,
                'backup_export':      export_history,
                'backup_import':      import_history,
                'backup_configure':   configure_backup_folder,
                'backup_toggle_auto': toggle_auto_backup,
            }
            _backup_handlers[action]()
            return end_dir(True)

        from resources.lib import history as hist_mod
        handler = getattr(hist_mod, action, None)
        if handler:
            if action in ('history_remove', 'history_unwatch', 'rating_remove'):
                handler(params.get('tmdb_id'), params.get('media_type', 'movie'))
            else:
                handler()
            return end_dir(True)
        return end_dir(False)

    # ── Recomendações (só PLUS) ───────────────────────────────────────────────
    if action in _RECOMMENDATIONS_ACTIONS:
        from resources.lib import recommendations as rec_mod
        handler = getattr(rec_mod, action, None)
        if handler:
            handler()
            return end_dir(True)
        return end_dir(False)

    # ── Routing genérico ──────────────────────────────────────────────────────
    if handle_generic_action(action, params):
        return end_dir(True)

    if action == 'show_details':
        if params.get('track') == '1':
            try:
                from resources.lib.trending_tracker import queue_track_from_search
                import json as _json
                _data = _json.loads(params.get('data', '{}'))
                queue_track_from_search(
                    tmdb_id=_data.get('tmdb_id'),
                    imdb_id=_data.get('imdb_id'),
                    content_type=_data.get('media_type', 'movie'),
                )
            except Exception as _e:
                pass
        return end_dir(handle_show_details(params))

    if action == 'list_seasons':
        return end_dir(handle_list_seasons(params))

    if action == 'list_episodes':
        return end_dir(handle_list_episodes(params))

    if action in ('add_to_favorites', 'remove_from_favorites',
                  'favorites_menu', 'favorites_movies', 'favorites_tvshows'):
        return end_dir(handle_favorites(action, params))

    if action.startswith('trakt_'):
        return end_dir(handle_trakt(action, params))

    if action == 'track_open':
        from resources.lib.search.search import handle_track_open
        handle_track_open(params)
        return end_dir(True)

    if action in ('search', 'find_sources', 'play_item_direct', 'find_and_play_episode'):
        if action == 'find_sources' and params.get('track') == '1':
            try:
                from resources.lib.trending_tracker import queue_track_from_search
                queue_track_from_search(
                    tmdb_id=params.get('tmdb_id'),
                    imdb_id=params.get('imdb_id'),
                    content_type=params.get('media_type', 'movie'),
                )
            except Exception as _e:
                pass
        return end_dir(handle_navigation(action, params))

    if action in ('movies_menu', 'tvshows_menu', 'tools_menu',
                  'vip_menu', 'movies_vip_menu', 'tvshows_vip_menu'):
        return end_dir(handle_menu(action, params))

    if action.startswith('library_'):
        return end_dir(handle_library(action, params))

    if action in ('run_indexer', 'show_donation', 'open_settings', 'show_changelog', 'show_welcome_screen', 'open_provider_manager'):
        return end_dir(handle_system(action, params))

    return end_dir(False)


def _auto_heal_db():
    try:
        db = get_module('db')
        if db and not db.get_all_movie_ids_set():
            indexer = get_module('indexer')
            if indexer:
                indexer.run_indexer()
    except Exception as e:
        xbmc.log(f'[Cineroom] Erro na checagem de banco: {e}', xbmc.LOGERROR)


def run():
    try:
        init_scrobbler()
        router()
    except Exception as e:
        xbmc.log(f'[Cineroom] ERRO CRÍTICO: {e}', xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        end_dir(False)