# -*- coding: utf-8 -*-
"""
History Module — Histórico de Visualizações
✅ Free: histórico global (sem profile_id)
✅ VIP:  histórico isolado por perfil (com profile_id)
✅ UI: show_history_menu, list_history_*
✅ Seções Gostei / Não Gostei (alimentadas pelo dialog de 80% no player)
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

HISTORY_LIMIT = 50
RATINGS_LIMIT = 100


def _get_url(**kwargs):
    return f"{BASE_URL}?{urlencode(kwargs)}"


def _should_use_profiles():
    """VIP com isolamento de perfil ativo."""
    try:
        return ADDON.getSettingBool('use_profile_isolation')
    except Exception:
        return False


def _get_active_profile_id():
    """Retorna profile_id apenas se VIP com perfis ativos, senão None."""
    if not _should_use_profiles():
        return None
    try:
        from .profile_manager import ProfileManager
        profile = ProfileManager().get_current_profile()
        return profile.get('id') if profile else None
    except Exception:
        return None


# ── API pública ───────────────────────────────────────────────────────────────

def add_to_history(tmdb_id, media_type, profile_id=None,
                   season=None, episode=None, progress=0.0):
    """
    Registra visualização no histórico.
    Free → profile_id sempre None (histórico global).
    VIP  → profile_id do perfil ativo.
    Chamado pelo player.py ao final do scrobble.
    """
    from .db.history_db import history_db
    if not _should_use_profiles():
        profile_id = None
    history_db.add_to_history(
        tmdb_id, media_type,
        profile_id=profile_id,
        season=season,
        episode=episode,
        progress=progress,
    )


def get_history(profile_id=None, limit=50):
    from .db.history_db import history_db
    if not _should_use_profiles():
        profile_id = None
    return history_db.get_history(profile_id=profile_id, limit=limit)


def is_watched(tmdb_id, media_type, profile_id=None,
               season=None, episode=None, min_progress=75.0):
    from .db.history_db import history_db
    if not _should_use_profiles():
        profile_id = None
    return history_db.is_watched(
        tmdb_id, media_type,
        profile_id=profile_id,
        season=season,
        episode=episode,
        min_progress=min_progress,
    )


def get_movie_progress(tmdb_id, profile_id=None):
    from .db.history_db import history_db
    if not _should_use_profiles():
        profile_id = None
    return history_db.get_movie_progress(tmdb_id, profile_id=profile_id)


def clear_history(profile_id=None):
    from .db.history_db import history_db
    if not _should_use_profiles():
        profile_id = None
    history_db.clear_history(profile_id=profile_id)


# ── UI ────────────────────────────────────────────────────────────────────────

def show_history_menu():
    """Menu raiz: Todos / Filmes / Séries / Em Andamento / Gostei / Não Gostei."""
    xbmcplugin.setPluginCategory(HANDLE, 'Histórico')
    xbmcplugin.setContent(HANDLE, 'folder')
    items = [
        ('Todos',              'list_history_all',         'favorites.png'),
        ('Filmes',             'list_history_movies',      'movies.png'),
        ('Séries',             'list_history_tvshows',     'tv.png'),
        ('Em Andamento',       'list_history_in_progress', 'trending.png'),
        ('Gostei',        'list_history_liked',     'para_voce.png'),
        ('Não Gostei',      'list_history_disliked',  'avaliacao.png'),
        ('Backup / Restaurar', 'backup_menu',              'favorites.png'),
    ]
    for label, action, icon in items:
        li = xbmcgui.ListItem(label=label)
        li.setArt({'thumb': os.path.join(ICON_PATH, icon)})
        xbmcplugin.addDirectoryItem(HANDLE, _get_url(action=action), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def _progress_label(title, progress):
    p = float(progress or 0)
    if p >= 90:
        return f"{title}"
    if p >= 5:
        return f"{title} [COLOR yellow]{int(p)}%[/COLOR]"
    return title


def _make_item_tuple(item):
    """Cria tupla (url, listitem, is_folder) para um item do histórico."""
    from .utils import create_video_item_with_library
    media_type = item.get('media_type', 'movie')
    li = create_video_item_with_library(item, media_type=media_type)

    if media_type == 'movie':
        progress = item.get('progress', 0)
        li.setLabel(_progress_label(item.get('title', ''), progress))
        if float(progress or 0) >= 90:
            li.setInfo('video', {'playcount': 1})
        cm = [
            ('Remover do Histórico',
             f"RunPlugin({_get_url(action='history_remove', tmdb_id=item['tmdb_id'], media_type='movie')})"),
            ('Marcar como Não Assistido',
             f"RunPlugin({_get_url(action='history_unwatch', tmdb_id=item['tmdb_id'], media_type='movie')})"),
        ]
        li.addContextMenuItems(cm)
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
        season, episode = item.get('season'), item.get('episode')
        if season and episode:
            li.setLabel(f"{item.get('title', '')} — S{int(season):02d}E{int(episode):02d}")
        cm = [('Remover do Histórico',
               f"RunPlugin({_get_url(action='history_remove', tmdb_id=item['tmdb_id'], media_type='tvshow')})")]
        li.addContextMenuItems(cm)
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
        return (_get_url(action='list_seasons', tvshow_tmdb_id=item.get('tmdb_id')), li, True)


def _make_rated_item_tuple(item, liked=True):
    """
    Cria tupla para um item avaliado (Gostei / Não Gostei).
    Adiciona ícone de avaliação ao label e context menu para remover avaliação.
    """
    from .utils import create_video_item_with_library
    media_type = item.get('media_type', 'movie')
    li = create_video_item_with_library(item, media_type=media_type)

    # Ícone de avaliação no label
    prefix = '[COLOR green]👍[/COLOR]' if liked else '[COLOR red]👎[/COLOR]'
    li.setLabel(f"{prefix} {item.get('title', '')}")

    # Context menu: remover avaliação + opções padrão
    cm = [
        ('Remover Avaliação',
         f"RunPlugin({_get_url(action='rating_remove', tmdb_id=item['tmdb_id'], media_type=media_type)})"),
        ('Remover do Histórico',
         f"RunPlugin({_get_url(action='history_remove', tmdb_id=item['tmdb_id'], media_type=media_type)})"),
    ]
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
        return (_get_url(action='list_seasons', tvshow_tmdb_id=item.get('tmdb_id')), li, True)


def _render_list(items):
    if not items:
        li = xbmcgui.ListItem(label='Histórico vazio')
        li.setArt({'thumb': os.path.join(ICON_PATH, 'favorites.png')})
        li.setInfo('video', {'plot': 'Nenhuma visualização registrada ainda.'})
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


def _render_rated_list(items, liked=True):
    """Renderiza lista de itens avaliados (Gostei ou Não Gostei)."""
    if not items:
        msg = 'Nenhum filme/série marcado como Gostei ainda.' if liked \
              else 'Nenhum filme/série marcado como Não Gostei ainda.'
        li = xbmcgui.ListItem(label='Lista vazia')
        li.setArt({'thumb': os.path.join(ICON_PATH, 'favorites.png')})
        li.setInfo('video', {'plot': msg})
        xbmcplugin.addDirectoryItem(HANDLE, '', li, isFolder=False)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    tuples = []
    for item in items:
        try:
            tuples.append(_make_rated_item_tuple(item, liked=liked))
        except Exception as e:
            pass
    if tuples:
        xbmcplugin.addDirectoryItems(HANDLE, tuples, len(tuples))
    xbmcplugin.endOfDirectory(HANDLE)


# ── Listas de histórico ────────────────────────────────────────────────────────

def list_history_all():
    xbmcplugin.setPluginCategory(HANDLE, 'Histórico')
    xbmcplugin.setContent(HANDLE, 'movies')
    items = get_history(profile_id=_get_active_profile_id(), limit=HISTORY_LIMIT)
    _render_list(items)


def list_history_movies():
    xbmcplugin.setPluginCategory(HANDLE, 'Histórico • Filmes')
    xbmcplugin.setContent(HANDLE, 'movies')
    items = [i for i in get_history(profile_id=_get_active_profile_id(), limit=HISTORY_LIMIT)
             if i.get('media_type') == 'movie']
    _render_list(items)


def list_history_tvshows():
    xbmcplugin.setPluginCategory(HANDLE, 'Histórico • Séries')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    items = [i for i in get_history(profile_id=_get_active_profile_id(), limit=HISTORY_LIMIT)
             if i.get('media_type') == 'tvshow']
    _render_list(items)


def list_history_in_progress():
    """Filmes iniciados mas não concluídos (5% ≤ progresso < 90%)."""
    xbmcplugin.setPluginCategory(HANDLE, 'Em Andamento')
    xbmcplugin.setContent(HANDLE, 'movies')
    all_items = get_history(profile_id=_get_active_profile_id(), limit=200)
    items = [i for i in all_items
             if i.get('media_type') == 'movie'
             and 5.0 <= float(i.get('progress', 0) or 0) < 90.0]
    _render_list(items)


# ── Listas de avaliação ────────────────────────────────────────────────────────

def list_history_liked():
    """
    Exibe filmes e séries marcados como 'Gostei' pelo dialog de avaliação do player.
    Sub-menus separados por tipo de mídia para melhor organização.
    """
    xbmcplugin.setPluginCategory(HANDLE, 'Gostei')
    xbmcplugin.setContent(HANDLE, 'folder')

    items = [
        ('Filmes que Gostei',  'list_history_liked_movies',   'movies.png'),
        ('Séries que Gostei',  'list_history_liked_tvshows',  'tv.png'),
    ]
    for label, action, icon in items:
        li = xbmcgui.ListItem(label=f'[COLOR green]{label}[/COLOR]')
        li.setArt({'thumb': os.path.join(ICON_PATH, icon)})
        xbmcplugin.addDirectoryItem(HANDLE, _get_url(action=action), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def list_history_disliked():
    """
    Exibe filmes e séries marcados como 'Não Gostei' pelo dialog de avaliação do player.
    """
    xbmcplugin.setPluginCategory(HANDLE, 'Não Gostei')
    xbmcplugin.setContent(HANDLE, 'folder')

    items = [
        ('Filmes que Não Gostei',  'list_history_disliked_movies',   'movies.png'),
        ('Séries que Não Gostei',  'list_history_disliked_tvshows',  'tv.png'),
    ]
    for label, action, icon in items:
        li = xbmcgui.ListItem(label=f'[COLOR red]{label}[/COLOR]')
        li.setArt({'thumb': os.path.join(ICON_PATH, icon)})
        xbmcplugin.addDirectoryItem(HANDLE, _get_url(action=action), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def list_history_liked_movies():
    xbmcplugin.setPluginCategory(HANDLE, 'Filmes que Gostei')
    xbmcplugin.setContent(HANDLE, 'movies')
    from .db.history_db import history_db
    items = history_db.get_liked('movie', profile_id=_get_active_profile_id(), limit=RATINGS_LIMIT)
    _render_rated_list(items, liked=True)


def list_history_liked_tvshows():
    xbmcplugin.setPluginCategory(HANDLE, 'Séries que Gostei')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    from .db.history_db import history_db
    items = history_db.get_liked('tvshow', profile_id=_get_active_profile_id(), limit=RATINGS_LIMIT)
    _render_rated_list(items, liked=True)


def list_history_disliked_movies():
    xbmcplugin.setPluginCategory(HANDLE, 'Filmes que Não Gostei')
    xbmcplugin.setContent(HANDLE, 'movies')
    from .db.history_db import history_db
    items = history_db.get_disliked('movie', profile_id=_get_active_profile_id(), limit=RATINGS_LIMIT)
    _render_rated_list(items, liked=False)


def list_history_disliked_tvshows():
    xbmcplugin.setPluginCategory(HANDLE, 'Séries que Não Gostei')
    xbmcplugin.setContent(HANDLE, 'tvshows')
    from .db.history_db import history_db
    items = history_db.get_disliked('tvshow', profile_id=_get_active_profile_id(), limit=RATINGS_LIMIT)
    _render_rated_list(items, liked=False)


# ── Action handlers ────────────────────────────────────────────────────────────

def history_remove(tmdb_id, media_type):
    """Action handler: remove item do histórico e recarrega."""
    from .db.history_db import history_db
    profile_id = _get_active_profile_id()
    conn = history_db._get_conn()
    cursor = conn.cursor()
    try:
        if profile_id:
            cursor.execute(
                "DELETE FROM watch_history WHERE tmdb_id=? AND media_type=? AND profile_id=?",
                (int(tmdb_id), media_type, profile_id))
        else:
            cursor.execute(
                "DELETE FROM watch_history WHERE tmdb_id=? AND media_type=?",
                (int(tmdb_id), media_type))
        conn.commit()
        history_db._cache_delete_prefix(f"history:{profile_id or 'global'}")
        xbmcgui.Dialog().notification('Histórico', 'Removido.', xbmcgui.NOTIFICATION_INFO, 2000)
    except Exception as e:
        xbmc.log(f"[History] Erro ao remover: {e}", xbmc.LOGERROR)
    finally:
        history_db._release_conn(conn)
    xbmc.executebuiltin('Container.Refresh')


def history_unwatch(tmdb_id, media_type):
    """Action handler: zera progresso (marca como não assistido)."""
    from .db.history_db import history_db
    profile_id = _get_active_profile_id()
    conn = history_db._get_conn()
    cursor = conn.cursor()
    try:
        if profile_id:
            cursor.execute(
                "UPDATE watch_history SET progress=0 WHERE tmdb_id=? AND media_type=? AND profile_id=?",
                (int(tmdb_id), media_type, profile_id))
        else:
            cursor.execute(
                "UPDATE watch_history SET progress=0 WHERE tmdb_id=? AND media_type=?",
                (int(tmdb_id), media_type))
        conn.commit()
        history_db._cache_delete_prefix(f"history:{profile_id or 'global'}")
        history_db._cache_delete_prefix(f"history:prog:{tmdb_id}:movie:")
        xbmcgui.Dialog().notification('Histórico', 'Marcado como não assistido.',
                                      xbmcgui.NOTIFICATION_INFO, 2000)
    except Exception as e:
        xbmc.log(f"[History] Erro ao resetar progresso: {e}", xbmc.LOGERROR)
    finally:
        history_db._release_conn(conn)
    xbmc.executebuiltin('Container.Refresh')


def rating_remove(tmdb_id, media_type):
    """
    Action handler: remove avaliação (Gostei/Não Gostei) de um item.
    O item continua no histórico; só a avaliação é removida.
    """
    from .db.history_db import history_db
    profile_id = _get_active_profile_id()
    try:
        history_db.delete_rating(int(tmdb_id), media_type, profile_id=profile_id)
        # Invalida cache de recomendações também
        history_db._cache_delete_prefix(f"ratings:{profile_id or 'global'}")
        history_db._cache_delete_prefix(f"rec:{media_type}:{profile_id or 'global'}")
        xbmcgui.Dialog().notification('Avaliação', 'Avaliação removida.',
                                      xbmcgui.NOTIFICATION_INFO, 2000)
    except Exception as e:
        xbmc.log(f"[History] Erro ao remover avaliação: {e}", xbmc.LOGERROR)
    xbmc.executebuiltin('Container.Refresh')