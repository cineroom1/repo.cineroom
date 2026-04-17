# -*- coding: utf-8 -*-
import xbmc
import xbmcgui

from ..context import ADDON, get_module

def handle_trakt(action, params):
    # Menu principal (não precisa importar trakt)
    if action == 'trakt_main_menu':
        nav = get_module('navigation')
        const = get_module('constants')
        if nav and const:
            nav.show_main_menu(const.TRAKT_MENU)
        return True

    if action == 'trakt_sync_menu':
        nav = get_module('navigation')
        const = get_module('constants')
        if nav and const:
            nav.show_main_menu(const.TRAKT_SYNC_MENU)
        return True

    trakt = get_module('trakt_sync')
    if not trakt:
        return False

    tmdb_id = params.get('tmdb_id')
    media_type = params.get('media_type')

    # Ações individuais
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

    # Auth e status
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

    # Menus de listagem
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

    if action == 'trakt_lists_menu':
        trakt.show_trakt_custom_lists()
        return True

    if action == 'trakt_list_items':
        list_id = params.get('list_id')
        trakt.show_trakt_list_items(list_id, page)
        return True

    # Sync
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
        nav = get_module('navigation')
        const = get_module('constants')
        if nav and const:
            nav.show_main_menu(const.TRAKT_MOVIES_MENU)
        return True

    if action == 'trakt_tv_submenu':
        nav = get_module('navigation')
        const = get_module('constants')
        if nav and const:
            nav.show_main_menu(const.TRAKT_TV_MENU)
        return True

    return False
