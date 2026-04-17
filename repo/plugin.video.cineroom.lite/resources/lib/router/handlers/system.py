# -*- coding: utf-8 -*-
import os
import xbmc
import xbmcgui
import xbmcvfs

from ..context import ADDON, ADDON_PATH, get_module

def handle_system(action, params):
    if action == 'run_indexer':
        indexer = get_module('indexer')
        if indexer:
            indexer.run_indexer()
        return True

    if action == 'show_donation':
        DonationDialog = get_module('donation_window')
        if DonationDialog:
            DonationDialog("DonationDialog.xml", ADDON_PATH, "Default", "1080i").doModal()
        return True

    if action == 'open_settings':
        xbmc.executebuiltin(f'Addon.OpenSettings({ADDON.getAddonInfo("id")})')
        return True

    if action == 'show_changelog':
        from resources.lib.dialog.changelog_dialog import ChangelogDialog

        changelog_path = xbmcvfs.translatePath(os.path.join(ADDON_PATH, "changelog.txt"))

        text = "Changelog não encontrado."
        if xbmcvfs.exists(changelog_path):
            f = xbmcvfs.File(changelog_path)
            text = f.read()
            f.close()

        dialog = ChangelogDialog(
            "ChangelogDialog.xml",
            ADDON_PATH,
            "Default",
            "1080i",
            heading="Changelog — Cineroom Lite",
            text=text
        )
        dialog.doModal()
        del dialog
        return True

    if action == 'show_welcome_screen':
        from resources.lib.vip_auth import show_welcome_screen
        from resources.lib.router.handlers.vip import handle_vip_gate
        choice = show_welcome_screen()
        if choice == 'vip':
            handle_vip_gate('vip_menu')
        return True
 
    if action == 'open_provider_manager':
        from resources.lib.dialog.manage_providers_dialog import open_manage_providers_dialog
        open_manage_providers_dialog()
        return True
 
    return False