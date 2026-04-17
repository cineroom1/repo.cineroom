# -*- coding: utf-8 -*-
import sys
import xbmcplugin
import xbmcgui
import xbmcaddon
from urllib.parse import urlencode
from ..context import get_module, get_profile_manager

HANDLE   = int(sys.argv[1])
BASE_URL = sys.argv[0]


def handle_menu(action, params):
    const = get_module('constants')
    if not const:
        return False

    from resources.lib.vip_auth import is_session_valid
    is_vip = is_session_valid()

    # Perfil ativo (só existe se VIP logado)
    pm = get_profile_manager()
    is_kids = False
    if pm and is_vip:
        current_profile = pm.get_current_profile()
        if current_profile and current_profile.get('is_kids'):
            is_kids = True

    # ── Login VIP disparado pelo botão no menu anônimo ────────────────────────
    if action == 'vip_login':
        from resources.lib.router.handlers.vip import handle_vip_gate
        if handle_vip_gate('vip_menu'):
            # Login bem-sucedido → pede seleção de perfil
            if pm:
                pm.show_profile_selector()
            import xbmc
            xbmc.executebuiltin('Container.Refresh')
        return True

    # ── Filmes ────────────────────────────────────────────────────────────────
    if action == 'movies_menu':
        movies = get_module('movies')
        if movies:
            if is_vip:
                menu = const.MOVIES_MENU_KIDS if is_kids else const.MOVIES_MENU
            else:
                menu = const.MOVIES_MENU_ANON
            movies.show_movies_menu(menu)
            return True

    # ── Séries ────────────────────────────────────────────────────────────────
    if action == 'tvshows_menu':
        tv = get_module('tvshows')
        if tv:
            if is_vip:
                menu = const.TVSHOWS_MENU_KIDS if is_kids else const.TVSHOWS_MENU
            else:
                menu = const.TVSHOWS_MENU_ANON
            tv.show_tvshows_menu(menu)
            return True

    # ── Ferramentas ───────────────────────────────────────────────────────────
    if action == 'tools_menu':
        nav = get_module('navigation')
        if nav:
            nav.show_main_menu(const.TOOLS_MENU)
            return True

    # ── Hub VIP ───────────────────────────────────────────────────────────────
    elif action == 'vip_menu':
        from resources.lib.router.handlers.minha_conta_dialog import open_minha_conta
        open_minha_conta()
        return True

    # ── Submenus VIP: Filmes ──────────────────────────────────────────────────
    if action == 'movies_vip_menu':
        _show_simple_menu(
            title='[COLOR gold]Filmes Exclusivos[/COLOR]',
            menu=const.MOVIES_VIP_MENU,
        )
        return True

    # ── Submenus VIP: Séries ──────────────────────────────────────────────────
    if action == 'tvshows_vip_menu':
        _show_simple_menu(
            title='[COLOR gold]Séries Exclusivas[/COLOR]',
            menu=const.TVSHOWS_VIP_MENU,
        )
        return True

    return False


def _show_simple_menu(title, menu):
    """Renderiza lista de dicts {title, action, icon, plot} como diretório Kodi."""
    xbmcplugin.setPluginCategory(HANDLE, title)
    xbmcplugin.setContent(HANDLE, 'files')

    for item in menu:
        li = xbmcgui.ListItem(label=item['title'])

        icon = item.get('icon', '')
        if icon:
            li.setArt({'thumb': icon, 'icon': icon})

        plot = item.get('plot', '')
        if plot:
            li.setInfo('video', {'plot': plot})

        url = f"{BASE_URL}?{urlencode({'action': item['action']})}"
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)
