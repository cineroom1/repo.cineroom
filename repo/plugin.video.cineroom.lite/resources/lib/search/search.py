# -*- coding: utf-8 -*-
"""
Sistema de busca (local + TMDB)
"""
import xbmc
import xbmcgui
import xbmcplugin
import sys
from urllib.parse import urlencode

HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def get_url(**kwargs):
    return f"{BASE_URL}?{urlencode(kwargs)}"


def search(query=None, page=1):
    """
    Busca combinada: local (DB) + TMDB
    """
    page = int(page)
    PAGE_SIZE = 20
    offset = (page - 1) * PAGE_SIZE

    # Input de busca
    if not query:
        keyboard = xbmc.Keyboard('', 'Pesquisar Filme ou Série')
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            query = keyboard.getText().strip()
        else:
            return

    if not query:
        return

    xbmcplugin.setPluginCategory(HANDLE, f'Pesquisando: {query}')
    xbmcplugin.setContent(HANDLE, 'movies')

    from ..tmdb_api import search_tmdb
    from ..movies import _create_movie_item_tuple
    from ..tvshows import _create_show_tuple
    from ..db import db

    items = []
    used_tmdb_ids = set()

    # === BUSCA LOCAL ===
    try:
        local_results = db.search_items(query)
    except Exception as e:
        xbmc.log(f"[Search] Erro local: {e}", xbmc.LOGERROR)
        local_results = []

    local_page = local_results[offset: offset + PAGE_SIZE]

    for item in local_page:
        tmdb_id = item.get('tmdb_id')
        if tmdb_id:
            used_tmdb_ids.add(str(tmdb_id))

        if item.get('media_type') == 'movie':
            items.append(_create_movie_item_tuple(item))
        else:
            items.append(_create_show_tuple(item))

    # === BUSCA TMDB (complementar) ===
    tmdb_results = search_tmdb(query, page=page) or []

    for item in tmdb_results:
        tmdb_id = str(item.get('id'))
        if tmdb_id in used_tmdb_ids:
            continue

        if item.get('media_type') == 'movie':
            items.append(_create_movie_item_tuple(item))
        else:
            items.append(_create_show_tuple(item))

    if not items:
        xbmcgui.Dialog().notification("Busca", f'Nada encontrado para "{query}"')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))

    # Próxima página
    if len(items) >= PAGE_SIZE:
        next_url = get_url(action='search', query=query, page=page + 1)
        li = xbmcgui.ListItem(label='[COLOR yellow]Próxima Página >>[/COLOR]')
        li.setArt({'thumb': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)