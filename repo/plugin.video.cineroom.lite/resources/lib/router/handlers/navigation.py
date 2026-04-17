# -*- coding: utf-8 -*-
from ..context import get_module, parse_json

def handle_navigation(action, params):
    # Search
    if action == 'search':
        search = get_module('search')
        if search:
            search.search(params.get('query'), params.get('page', '1'))
        return True

    playback = get_module('playback')
    if not playback:
        return False

    if action == 'find_sources':
        raw_abs = params.get('absolute_episode')
        abs_ep = int(raw_abs) if raw_abs and raw_abs.isdigit() else None
        
        if abs_ep is None and params.get('media_type') == 'tvshow':
            try:
                from ..db import db
                from ..tvshows import _get_absolute_episode
                season  = int(params.get('season', 1))
                episode = int(params.get('episode', 1))
                tmdb_id = int(params.get('tmdb_id', 0))
                if tmdb_id and season > 1:
                    abs_ep = _get_absolute_episode(db, tmdb_id, season, episode)
            except Exception as e:
                import xbmc
                xbmc.log(f'[navigation] Erro calculando abs_ep: {e}', xbmc.LOGWARNING)
        
        
        item_data = {
            'tmdb_id':        params.get('tmdb_id', ''),
            'imdb_id':        params.get('imdb_id', ''),
            'media_type':     params.get('media_type', ''),
            'title':          params.get('title', ''),
            'original_title': params.get('original_title', ''),
            'romaji_title':   params.get('romaji_title', ''),
            'year':           params.get('year', ''),
            'clearlogo':      params.get('clearlogo', ''),
            'fanart':         params.get('fanart', ''),
            'backdrop':       params.get('backdrop', ''),
            'poster':         params.get('poster', ''),
            'season':         params.get('season'),
            'episode':        params.get('episode'),
            'absolute_episode':  params.get('absolute_episode') or None,
        }
        # Clique manual → is_autonext=False (padrão)
        playback.find_and_play_sources(
            item_data,
            season=params.get('season'),
            episode=params.get('episode')
        )
        return True

    if action == 'play_item_direct':
        item_data = parse_json(params.get('data', ''))
        if item_data:
            playback.find_and_play_sources(item_data)
        return True

    if action == 'find_and_play_episode':
        # Próximo episódio automático → is_autonext=True
        # Usa playback.autonext_episode + autonext.language (independente do autoplay manual)
        item_data = parse_json(params.get('item_data', ''))
        if item_data:
            playback.find_and_play_sources(
                item_data,
                season=item_data.get('season'),
                episode=item_data.get('episode'),
                is_autonext=True
            )
        return True

    return False