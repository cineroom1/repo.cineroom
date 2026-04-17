# -*- coding: utf-8 -*-
import xbmc

from ..context import ADDON, get_module, parse_json


_SUPPORTED_SKINS = {'skin.estuary', 'skin.estouchy'}

def handle_show_details(params):
    item_data = parse_json(params.get('data', ''))
    if not item_data:
        return False

    media_type = item_data.get("media_type")
    setting_key = f"{media_type}.enable_details"
    skin_supported = xbmc.getSkinDir() in _SUPPORTED_SKINS

    if not ADDON.getSettingBool(setting_key) or not skin_supported:
        playback = get_module('playback')
        if playback:
            playback.find_and_play_sources(item_data)
    else:
        dialog = get_module('extras_dialog')
        if dialog:
            dialog.show_details(item_data)

    return True
