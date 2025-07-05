# Em utils.py ou view_utils.py

import xbmc
import xbmcaddon

addon = xbmcaddon.Addon()

VIEW_MODE_MAP = {
    'list': 50,
    'poster': 51,
    'iconwall': 52,
    'shift': 53,
    'infowall': 54,
    'widelist': 55,
    'wall': 500,
    'banner': 56,
    'fanart': 502
}

def set_view_mode():
    view_mode = addon.getSetting('view_mode')
    view_mode_id = VIEW_MODE_MAP.get(view_mode, 500)
    xbmc.executebuiltin(f'Container.SetViewMode({view_mode_id})')
