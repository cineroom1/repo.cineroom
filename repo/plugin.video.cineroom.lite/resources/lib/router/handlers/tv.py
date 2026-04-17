# -*- coding: utf-8 -*-
from ..context import get_module

def handle_list_seasons(params):
    tv = get_module('tvshows')
    if tv:
        tv.list_seasons(tvshow_tmdb_id=params.get('tvshow_tmdb_id'))
        return True
    return False

def handle_list_episodes(params):
    tv = get_module('tvshows')
    if tv:
        tv.list_episodes(
            params.get('tvshow_tmdb_id'),
            int(params.get('season_number', 1))
        )
        return True
    return False
