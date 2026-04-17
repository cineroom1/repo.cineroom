# -*- coding: utf-8 -*-
"""
device_limit_dialog.py — Dialog exibido quando a conta atinge o limite de dispositivos.
"""

import xbmc
import xbmcgui
import xbmcaddon

ADDON      = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')


class DeviceLimitDialog(xbmcgui.WindowXMLDialog):

    def onClick(self, control_id):
        if control_id == 9201:
            self.close()

    def onAction(self, action):
        if action.getId() in (
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_STOP,
        ):
            self.close()


def show_device_limit_dialog():
    dlg = DeviceLimitDialog(
        'DeviceLimitDialog.xml',
        ADDON_PATH,
        'Default',
        '1080i',
    )
    dlg.doModal()
    del dlg