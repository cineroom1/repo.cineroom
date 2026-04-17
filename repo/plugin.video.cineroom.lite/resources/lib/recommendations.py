# -*- coding: utf-8 -*-
"""
Recommendations Module — Para Você
✅ Só VIP
✅ Sub-menu: Filmes / Séries
✅ Baseado em gêneros + keywords + coleções do histórico (≥75% assistido)
✅ Dialog informativo se histórico insuficiente (sem abrir pasta vazia)
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

MIN_PROGRESS = 75.0  # % mínimo para considerar "assistido"
MIN_ITEMS    = 3     # itens mínimos no histórico para gerar recomendações
MIN_RATING   = 5.0   # rating mínimo dos itens recomendados
LIMIT        = 50    # máximo de recomendações


def _get_url(**kwargs):
    return f"{BASE_URL}?{urlencode(kwargs)}"


def _get_active_profile_id():
    try:
        addon = xbmcaddon.Addon()
        if not addon.getSettingBool('use_profile_isolation'):
            return None
        from resources.lib.profile_manager import ProfileManager
        profile = ProfileManager().get_current_profile()
        return profile.get('id') if profile else None
    except Exception:
        return None


# ── UI ────────────────────────────────────────────────────────────────────────

def show_recommendations_menu():
    """Menu raiz: Filmes / Séries."""
    xbmcplugin.setPluginCategory(HANDLE, 'Para Você')
    xbmcplugin.setContent(HANDLE, 'folder')

    items = [
        ('Filmes', 'list_recommendations_movies',  'movies.png'),
        ('Séries', 'list_recommendations_tvshows', 'tv.png'),
    ]
    for label, action, icon in items:
        li = xbmcgui.ListItem(label=label)
        li.setArt({'thumb': os.path.join(ICON_PATH, icon)})
        xbmcplugin.addDirectoryItem(HANDLE, _get_url(action=action), li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def list_recommendations_movies():
    _list_recommendations('movie', 'Para Você • Filmes')


def list_recommendations_tvshows():
    _list_recommendations('tvshow', 'Para Você • Séries')


def _list_recommendations(media_type, category_label):
    from resources.lib.db.recommendations_db import recommendations_db

    profile_id = _get_active_profile_id()
    tipo = 'filmes' if media_type == 'movie' else 'séries'

    # Histórico insuficiente → dialog e fecha, sem abrir pasta
    if not recommendations_db.has_enough_history(media_type, profile_id, MIN_PROGRESS, MIN_ITEMS):
        xbmcgui.Dialog().ok(
            'Para Você',
            f'Assista pelo menos {MIN_ITEMS} {tipo} até o final para receber recomendações personalizadas.'
        )
        return

    xbmcplugin.setPluginCategory(HANDLE, category_label)
    xbmcplugin.setContent(HANDLE, 'movies' if media_type == 'movie' else 'tvshows')

    items = recommendations_db.get_recommendations(
        media_type   = media_type,
        profile_id   = profile_id,
        min_progress = MIN_PROGRESS,
        limit        = LIMIT,
        min_rating   = MIN_RATING,
    )

    if not items:
        xbmcgui.Dialog().ok(
            'Para Você',
            'Não encontramos sugestões novas no momento. Continue assistindo!'
        )
        return

    _render_list(items, media_type)


def _render_list(items, media_type):
    from resources.lib.utils import create_video_item_with_library

    tuples = []
    for item in items:
        try:
            li = create_video_item_with_library(item, media_type=media_type)

            if media_type == 'movie':
                if ADDON.getSettingBool('movie.enable_details'):
                    url = _get_url(action='show_details', data=json.dumps({
                        'tmdb_id':        item.get('tmdb_id'),
                        'imdb_id':        item.get('imdb_id', ''),
                        'title':          item.get('title', ''),
                        'original_title': item.get('original_title', ''),
                        'clearlogo':      item.get('clearlogo', ''),
                        'poster':         item.get('poster', ''),
                        'synopsis':       item.get('synopsis', ''),
                        'backdrop':       item.get('backdrop', ''),
                        'year':           item.get('year', 0),
                        'runtime':        item.get('runtime', 0),
                        'rating':         float(item.get('rating', 0) or 0),
                        'collection':     item.get('collection', ''),
                        'genre':          ', '.join(item['genres']) if isinstance(item.get('genres'), list) else '',
                        'media_type':     'movie',
                    }, separators=(',', ':')))
                else:
                    url = _get_url(
                        action         = 'find_sources',
                        media_type     = 'movie',
                        tmdb_id        = item.get('tmdb_id'),
                        imdb_id        = item.get('imdb_id', ''),
                        title          = item.get('title', ''),
                        year           = item.get('year', ''),
                        original_title = item.get('original_title', ''),
                        backdrop       = item.get('backdrop', ''),
                        poster         = item.get('poster', ''),
                    )
                tuples.append((url, li, False))

            else:
                if ADDON.getSettingBool('tvshow.enable_details'):
                    url = _get_url(action='show_details', data=json.dumps({
                        'tmdb_id':        item.get('tmdb_id'),
                        'imdb_id':        item.get('imdb_id', ''),
                        'title':          item.get('title', ''),
                        'original_title': item.get('original_title', ''),
                        'clearlogo':      item.get('clearlogo', ''),
                        'poster':         item.get('poster', ''),
                        'synopsis':       item.get('synopsis', ''),
                        'backdrop':       item.get('backdrop', ''),
                        'year':           item.get('year', 0),
                        'rating':         float(item.get('rating', 0) or 0),
                        'genre':          ', '.join(item['genres']) if isinstance(item.get('genres'), list) else '',
                        'media_type':     'tvshow',
                    }, separators=(',', ':')))
                    tuples.append((url, li, False))
                else:
                    url = _get_url(action='list_seasons', tvshow_tmdb_id=item.get('tmdb_id'))
                    tuples.append((url, li, True))

        except Exception as e:
            pass

    if tuples:
        xbmcplugin.addDirectoryItems(HANDLE, tuples, len(tuples))
    xbmcplugin.endOfDirectory(HANDLE)