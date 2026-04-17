# -*- coding: utf-8 -*-
"""
Navegação e menus (REFATORADO - apenas routing)
"""
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from urllib.parse import urlencode
from .db import db
from .utils import create_video_item

HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
ADDON = xbmcaddon.Addon()


def get_url(**kwargs):
    return f"{BASE_URL}?{urlencode(kwargs)}"


# === MENUS ===

def show_main_menu(menu_structure):
    """Exibe menu principal"""
    xbmcplugin.setPluginCategory(HANDLE, 'Menu Principal')

    for item in menu_structure:
        li = xbmcgui.ListItem(label=item['title'])
        
        icon = item.get('icon')
        if icon:
            li.setArt({'thumb': icon})
        
        plot = item.get('plot', '')
        if plot:
            li.setInfo('video', {'plot': plot})
            
        url = get_url(action=item['action'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
        
    xbmcplugin.endOfDirectory(HANDLE)


def show_my_list_menu():
    """Menu Minha Lista"""
    xbmcplugin.setPluginCategory(HANDLE, "Minha Lista")
    xbmcplugin.setContent(HANDLE, 'folder')

    items = [
        ("Filmes", get_url(action="favorites_movies")),
        ("Séries", get_url(action="favorites_tvshows"))
    ]

    for label, url in items:
        li = xbmcgui.ListItem(label=label)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def show_favorite_movies():
    """Lista filmes favoritos"""
    xbmcplugin.setPluginCategory(HANDLE, "Minha Lista • Filmes")
    xbmcplugin.setContent(HANDLE, 'movies')

    from resources.lib.favorites import get_all_favorites
    all_favs = get_all_favorites()
    favorites = [f for f in all_favs if f['media_type'] == 'movie']

    for item in favorites:
        li = create_video_item(item, 'movie')
        url = get_url(
            action='find_sources',
            media_type='movie',
            tmdb_id=item['tmdb_id'],
            imdb_id=item.get('imdb_id'),
            title=item.get('title'),
            year=item.get('year'),
            original_title=item.get('original_title', ''),
            clearlogo=item.get('clearlogo', ''),
            fanart=item.get('fanart', ''),
            backdrop=item.get('backdrop', ''),
            poster=item.get('poster', '')
        )
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def show_favorite_tvshows():
    """Lista séries favoritas"""
    xbmcplugin.setPluginCategory(HANDLE, "Minha Lista • Séries")
    xbmcplugin.setContent(HANDLE, 'tvshows')

    from resources.lib.favorites import get_all_favorites
    all_favs = get_all_favorites()
    favorites = [f for f in all_favs if f['media_type'] == 'tvshow']

    for item in favorites:
        li = create_video_item(item, 'tvshow')
        url = get_url(action='list_seasons', tvshow_tmdb_id=item['tmdb_id'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


# === IMPORTA FUNÇÕES DE PLAYBACK ===
from .playback import find_and_play_sources, play_url

# Re-exporta para manter compatibilidade
__all__ = [
    'get_url',
    'show_main_menu',
    'show_my_list_menu',
    'show_favorite_movies',
    'show_favorite_tvshows',
    'find_and_play_sources',
    'play_url'
]