# -*- coding: utf-8 -*-
"""
Sistema de busca (local + TMDB) com cache
✅ SEM tracking de queries - apenas tracks de cliques (feito em movies.py/tvshows.py)
"""
import xbmc
import xbmcgui
import xbmcplugin
import sys
from urllib.parse import urlencode

HANDLE   = int(sys.argv[1])
BASE_URL = sys.argv[0]

PAGE_SIZE = 20


# ── Kids filter ──────────────────────────────────────────────────────────────

def _get_kids_age_range():
    """Retorna age_range do perfil ativo se for kids, senão None."""
    try:
        from resources.lib.profile_manager import ProfileManager
        profile = ProfileManager().get_current_profile()
        if profile and profile.get('is_kids'):
            return profile.get('preferences', {}).get('age_range', 'livre')
    except Exception:
        pass
    return None

_KIDS_ALLOWED = {
    '2_6_anos':   {'L', 'G', 'TV-Y', 'TV-G'},
    '7_10_anos':  {'L', 'G', 'TV-Y', 'TV-Y7', 'TV-G', 'TV-PG', '10'},
    '11_14_anos': {'L', 'G', 'TV-Y', 'TV-Y7', 'TV-G', 'TV-PG', '10', '12', 'PG', '14'},
}

def _filter_kids(items, age_range):
    """Remove itens acima da faixa etária do perfil kids."""
    allowed = _KIDS_ALLOWED.get(age_range, set())
    result = []
    for item in items:
        cert = str(item.get('certification') or item.get('classification') or '').strip().upper()
        if not cert or cert in allowed:
            result.append(item)
    return result


def get_url(**kwargs):
    return f"{BASE_URL}?{urlencode(kwargs)}"


def search(query=None, page=1):
    """
    Busca combinada: local (DB) + TMDB (só VIP), com cache automático.
    
    FREE → apenas banco local
    VIP  → banco local + TMDB
    
    ⚠️ TRACKING: Acontece em movies.py/tvshows.py quando usuário CLICA no conteúdo
    """
    page   = int(page)
    offset = (page - 1) * PAGE_SIZE

    # Verifica se é VIP
    try:
        from ..vip_auth import is_session_valid
        is_vip = is_session_valid()
    except Exception:
        is_vip = False

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
    from ..db.db import db_instance as db
    from ..trending_tracker import (
        get_cached_search_results,
        save_search_results,
    )

    # ── 1. Cache (só para VIP) ───────────────────────────────────────────────
    raw_items = None
    cache_hit = False
    
    if is_vip:
        raw_items = get_cached_search_results(query, page)
        cache_hit = raw_items is not None

    if not cache_hit:
        raw_items     = []
        used_tmdb_ids = set()

        # === BUSCA LOCAL (FREE + VIP) ===
        try:
            local_results = db.search_items(query, limit=PAGE_SIZE, offset=offset)
        except Exception as e:
            xbmc.log(f"[Search] Erro local: {e}", xbmc.LOGERROR)
            local_results = []

        for item in local_results:
            tmdb_id = item.get('tmdb_id')
            if tmdb_id:
                used_tmdb_ids.add(str(tmdb_id))
            raw_items.append(item)

        # === BUSCA TMDB (só VIP) ===
        if is_vip:
            try:
                tmdb_results = search_tmdb(query, page=page) or []
            except Exception as e:
                xbmc.log(f"[Search] Erro TMDB: {e}", xbmc.LOGERROR)
                tmdb_results = []

            for item in tmdb_results:
                if str(item.get('id')) in used_tmdb_ids:
                    continue
                raw_items.append(item)

        # Salva no cache (VIP)
        if is_vip and raw_items:
            try:
                save_search_results(query, page, raw_items)
            except Exception as e:
                pass
    else:
        pass

    # ── 2. Monta itens ──────────────────────────────────────────────────────

    # Filtro kids: remove conteúdo fora da faixa etária do perfil ativo
    age_range = _get_kids_age_range()
    if age_range is not None:
        raw_items = _filter_kids(raw_items, age_range)
    
    items = []
    for item in raw_items:
        # Normaliza media_type: banco local usa 'tvshow', TMDB usa 'tv'
        media_type   = item.get('media_type', 'movie')
        is_tv        = media_type in ('tv', 'tvshow', 'series', 'show')
        content_type = 'tv' if is_tv else 'movie'
        creator      = _create_show_tuple if is_tv else _create_movie_item_tuple

        try:
            url, li, is_folder = creator(item, track_on_click=True)
        except Exception as e:
            continue

        items.append((url, li, is_folder))

    # ── 3. Exibe ────────────────────────────────────────────────────────────
    if not items:
        msg = f'Nada encontrado para "{query}"'
        if not is_vip:
            msg += '\n\n[COLOR gold]VIP:[/COLOR] Pesquisa TMDB com artes e metadados completos.'
        xbmcgui.Dialog().notification("Busca", msg, xbmcgui.NOTIFICATION_INFO, 4000)
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