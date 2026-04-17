# -*- coding: utf-8 -*-
"""
Watchlist Module — "Quero Assistir"
✅ Mesmo padrão do favorites.py
✅ Retrocompatível (sem perfis funciona normalmente)
✅ Configurável via settings (use_profile_isolation)
✅ UI: show_watchlist_menu, list_watchlist_*
"""

import sys
import os
import json
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from urllib.parse import urlencode

ADDON      = xbmcaddon.Addon()
HANDLE     = int(sys.argv[1])
BASE_URL   = sys.argv[0]
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH  = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')


def _get_url(**kwargs):
    return f"{BASE_URL}?{urlencode(kwargs)}"


def _should_use_profiles():
    try:
        return ADDON.getSettingBool('use_profile_isolation')
    except Exception:
        return False


def add_to_watchlist(tmdb_id, media_type, profile_id=None):
    from .db.watchlist_db import watchlist_db
    if not _should_use_profiles():
        profile_id = None
    watchlist_db.add_to_watchlist(tmdb_id, media_type, profile_id=profile_id)
    xbmcgui.Dialog().notification(
        'Quero Assistir',
        'Adicionado à sua lista!',
        xbmcgui.NOTIFICATION_INFO
    )


def remove_from_watchlist(tmdb_id, media_type, profile_id=None):
    from .db.watchlist_db import watchlist_db
    if not _should_use_profiles():
        profile_id = None
    watchlist_db.remove_from_watchlist(tmdb_id, media_type, profile_id=profile_id)
    xbmcgui.Dialog().notification(
        'Quero Assistir',
        'Removido da sua lista.',
        xbmcgui.NOTIFICATION_INFO
    )


def is_in_watchlist(tmdb_id, media_type, profile_id=None):
    from .db.watchlist_db import watchlist_db
    if not _should_use_profiles():
        profile_id = None
    return watchlist_db.is_in_watchlist(tmdb_id, media_type, profile_id=profile_id)


def get_all_watchlist(profile_id=None):
    from .db.watchlist_db import watchlist_db
    if not _should_use_profiles():
        profile_id = None
    return watchlist_db.get_all_watchlist(profile_id=profile_id)


# ─── UI ───────────────────────────────────────────────────────────────────────

def show_watchlist_menu():
    """Menu raiz: Todos / Filmes / Séries."""
    xbmcplugin.setPluginCategory(HANDLE, 'Quero Assistir')
    xbmcplugin.setContent(HANDLE, 'folder')
    items = [
        ('Todos',   'list_watchlist_all',     'favorites.png'),
        ('Filmes',  'list_watchlist_movies',  'movies.png'),
        ('Séries',  'list_watchlist_tvshows', 'tv.png'),
    ]
    for label, action, icon in items:
        li = xbmcgui.ListItem(label=label)
        li.setArt({'thumb': os.path.join(ICON_PATH, icon)})
        xbmcplugin.addDirectoryItem(HANDLE, _get_url(action=action), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _make_item_tuple(item):
    """Cria tupla (url, listitem, is_folder) para um item da watchlist."""
    from .utils import create_video_item_with_library
    media_type = item.get('media_type', 'movie')
    li = create_video_item_with_library(item, media_type=media_type)

    cm = [('Remover da Watchlist',
           f"RunPlugin({_get_url(action='watchlist_remove', tmdb_id=item['tmdb_id'], media_type=media_type)})")]
    li.addContextMenuItems(cm)

    if media_type == 'movie':
        if ADDON.getSettingBool('movie.enable_details'):
            url = _get_url(action='show_details', data=json.dumps({
                'tmdb_id': item.get('tmdb_id'), 'imdb_id': item.get('imdb_id', ''),
                'title': item.get('title', ''), 'original_title': item.get('original_title', ''),
                'clearlogo': item.get('clearlogo', ''), 'poster': item.get('poster', ''),
                'synopsis': item.get('synopsis', ''), 'backdrop': item.get('backdrop', ''),
                'year': item.get('year', 0), 'runtime': item.get('runtime', 0),
                'rating': float(item.get('rating', 0) or 0), 'collection': item.get('collection', ''),
                'genre': ', '.join(item['genres']) if isinstance(item.get('genres'), list) else '',
                'media_type': 'movie',
            }, separators=(',', ':')))
        else:
            url = _get_url(action='find_sources', media_type='movie',
                           tmdb_id=item.get('tmdb_id'), imdb_id=item.get('imdb_id', ''),
                           title=item.get('title', ''), year=item.get('year', ''),
                           original_title=item.get('original_title', ''),
                           backdrop=item.get('backdrop', ''), poster=item.get('poster', ''))
        return (url, li, False)
    else:
        if ADDON.getSettingBool('tvshow.enable_details'):
            url = _get_url(action='show_details', data=json.dumps({
                'tmdb_id': item.get('tmdb_id'), 'imdb_id': item.get('imdb_id', ''),
                'title': item.get('title', ''), 'original_title': item.get('original_title', ''),
                'clearlogo': item.get('clearlogo', ''), 'poster': item.get('poster', ''),
                'synopsis': item.get('synopsis', ''), 'backdrop': item.get('backdrop', ''),
                'year': item.get('year', 0), 'rating': float(item.get('rating', 0) or 0),
                'genre': ', '.join(item['genres']) if isinstance(item.get('genres'), list) else '',
                'media_type': 'tvshow',
            }, separators=(',', ':')))
            return (url, li, False)
        else:
            return (_get_url(action='list_seasons', tvshow_tmdb_id=item.get('tmdb_id')), li, True)


def list_watchlist_all():
    from .db.watchlist_db import watchlist_db
    xbmcplugin.setPluginCategory(HANDLE, 'Quero Assistir')
    xbmcplugin.setContent(HANDLE, 'movies')
    profile_id = None
    if _should_use_profiles():
        profile_id = _get_active_profile_id()
    items = watchlist_db.get_all_watchlist(profile_id=profile_id)
    _render_list(items)


def list_watchlist_movies():
    from .db.watchlist_db import watchlist_db
    xbmcplugin.setPluginCategory(HANDLE, 'Quero Assistir • Filmes')
    xbmcplugin.setContent(HANDLE, 'movies')
    profile_id = None
    if _should_use_profiles():
        profile_id = _get_active_profile_id()
    items = watchlist_db.get_watchlist_by_type('movie', profile_id=profile_id)
    _render_list(items)


def list_watchlist_tvshows():
    from .db.watchlist_db import watchlist_db
    xbmcplugin.setPluginCategory(HANDLE, 'Quero Assistir • Séries')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    profile_id = None
    if _should_use_profiles():
        profile_id = _get_active_profile_id()
    items = watchlist_db.get_watchlist_by_type('tvshow', profile_id=profile_id)
    _render_list(items)


def watchlist_remove(tmdb_id, media_type):
    """Action handler: remove da watchlist e recarrega."""
    profile_id = _get_active_profile_id() if _should_use_profiles() else None
    remove_from_watchlist(int(tmdb_id), media_type, profile_id=profile_id)
    xbmc.executebuiltin('Container.Refresh')


def _get_active_profile_id():
    try:
        from .profile_manager import ProfileManager
        profile = ProfileManager().get_current_profile()
        return profile.get('id') if profile else None
    except Exception:
        return None


def _render_list(items):
    if not items:
        li = xbmcgui.ListItem(label='Sua lista está vazia')
        li.setArt({'thumb': os.path.join(ICON_PATH, 'favorites.png')})
        li.setInfo('video', {'plot': 'Adicione filmes e séries para assistir mais tarde!'})
        xbmcplugin.addDirectoryItem(HANDLE, '', li, isFolder=False)
        xbmcplugin.endOfDirectory(HANDLE)
        return
    tuples = []
    for item in items:
        try:
            tuples.append(_make_item_tuple(item))
        except Exception as e:
            pass
    if tuples:
        xbmcplugin.addDirectoryItems(HANDLE, tuples, len(tuples))
    xbmcplugin.endOfDirectory(HANDLE)