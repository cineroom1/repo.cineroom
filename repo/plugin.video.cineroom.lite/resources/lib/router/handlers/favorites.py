# -*- coding: utf-8 -*-
from ..context import get_module

def handle_favorites(action, params):
    fav = get_module('favorites')
    if not fav:
        return False

    if action == 'add_to_favorites':
        fav.add_item_to_favorites(params.get('tmdb_id'), params.get('media_type'))
    elif action == 'remove_from_favorites':
        fav.remove_item_from_favorites(params.get('tmdb_id'), params.get('media_type'))
    elif action == 'favorites_menu':
        nav = get_module('navigation')
        if nav:
            nav.show_my_list_menu()
    elif action == 'favorites_movies':
        nav = get_module('navigation')
        if nav:
            nav.show_favorite_movies()
    elif action == 'favorites_tvshows':
        nav = get_module('navigation')
        if nav:
            nav.show_favorite_tvshows()
    else:
        return False

    return True
