# -*- coding: utf-8 -*-
import xbmc
import xbmcgui

from ..context import get_profile_manager, clear_runtime_caches, get_module
from ..actions import clear_action_handler_cache

def handle_profiles(action, params):
    pm = get_profile_manager()
    if not pm:
        xbmcgui.Dialog().ok('Erro', 'Não foi possível carregar o gerenciador de perfis.')
        return False

    if action == 'profile_select':
        profile = pm.show_profile_selector()

        if profile:
            clear_runtime_caches()
            clear_action_handler_cache()
            
            xbmc.executebuiltin('ReplaceWindow(Videos,plugin://plugin.video.cineroom.lite/)')

        return True

    if action == 'profile_manage':
        pm.manage_profiles()
        return True

    if action == 'profile_create':
        pm.create_profile_wizard()
        return True

    if action == 'profile_menu':
        nav = get_module('navigation')
        const = get_module('constants')
        if nav and const and hasattr(const, 'PROFILES_MENU'):
            nav.show_main_menu(const.PROFILES_MENU)
        return True

    return False