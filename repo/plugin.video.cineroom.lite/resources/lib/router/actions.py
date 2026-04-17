# -*- coding: utf-8 -*-
from .context import get_module

# Cache de handlers pré-compilados
_ACTION_HANDLERS = {}

# Mapeamento de ações -> (module_name, method_name, needs_page, extra_params)
ACTIONS = {
    # === TRAKT.TV ===
    'list_trakt_watchlist': ('trakt_sync', 'list_trakt_watchlist', False, None),
    'list_trakt_collection': ('trakt_sync', 'list_trakt_collection', False, None),
    'list_trakt_watched': ('trakt_sync', 'list_trakt_watched', False, None),

    # === TRAKT FILMES ===
    'trakt_movies_trending': ('trakt_sync', 'trakt_movies_trending', True, None),
    'trakt_movies_popular': ('trakt_sync', 'trakt_movies_popular', True, None),
    'trakt_movies_most_watched': ('trakt_sync', 'trakt_movies_most_watched', True, None),
    'trakt_movies_most_collected': ('trakt_sync', 'trakt_movies_most_collected', True, None),
    'trakt_movies_most_anticipated': ('trakt_sync', 'trakt_movies_most_anticipated', True, None),
    'trakt_movies_box_office': ('trakt_sync', 'trakt_movies_box_office', True, None),
    'trakt_movies_top_rated': ('trakt_sync', 'trakt_movies_top_rated', True, None),
    'trakt_movies_personal_recommended': ('trakt_sync', 'trakt_movies_personal_recommended', True, None),

    # === TRAKT SÉRIES ===
    'trakt_tv_trending': ('trakt_sync', 'trakt_tv_trending', True, None),
    'trakt_tv_popular': ('trakt_sync', 'trakt_tv_popular', True, None),
    'trakt_tv_most_watched': ('trakt_sync', 'trakt_tv_most_watched', True, None),
    'trakt_tv_most_collected': ('trakt_sync', 'trakt_tv_most_collected', True, None),
    'trakt_tv_most_anticipated': ('trakt_sync', 'trakt_tv_most_anticipated', True, None),
    'trakt_tv_top_rated': ('trakt_sync', 'trakt_tv_top_rated', True, None),
    'trakt_tv_recommended': ('trakt_sync', 'trakt_tv_recommended', True, None),
    'trakt_tv_personal_recommended': ('trakt_sync', 'trakt_tv_personal_recommended', True, None),

     # === HISTÓRICO ===
    'show_history_menu':              ('history', 'show_history_menu',        False, None),
    'list_history_all':               ('history', 'list_history_all',         False, None),
    'list_history_movies':            ('history', 'list_history_movies',      False, None),
    'list_history_tvshows':           ('history', 'list_history_tvshows',     False, None),
    'list_history_in_progress':       ('history', 'list_history_in_progress', False, None),
    'list_history_liked':             ('history', 'list_history_liked',             False, None),
    'list_history_liked_movies':      ('history', 'list_history_liked_movies',      False, None),
    'list_history_liked_tvshows':     ('history', 'list_history_liked_tvshows',     False, None),
    'list_history_disliked':          ('history', 'list_history_disliked',          False, None),
    'list_history_disliked_movies':   ('history', 'list_history_disliked_movies',   False, None),
    'list_history_disliked_tvshows':  ('history', 'list_history_disliked_tvshows',  False, None),
    'rating_remove':                  ('history', 'rating_remove',                  False, ['tmdb_id', 'media_type']),
    'history_remove':                 ('history', 'history_remove',           False, ['tmdb_id', 'media_type']),
    'history_unwatch':                ('history', 'history_unwatch',          False, ['tmdb_id', 'media_type']),

    # === RECOMENDAÇÕES (VIP) ===
    'show_recommendations_menu':    ('recommendations', 'show_recommendations_menu',    False, None),
    'list_recommendations_movies':  ('recommendations', 'list_recommendations_movies',  False, None),
    'list_recommendations_tvshows': ('recommendations', 'list_recommendations_tvshows', False, None),

    # === FILMES ===
    'list_most_searched_movies': ('movies', 'list_most_searched_movies', True, None),
    'list_genres': ('movies', 'list_genres', False, None),
    'list_years': ('movies', 'list_years', False, None),
    'list_movie_themes': ('movies', 'list_movie_themes', False, None),
    'list_movies_by_genre': ('movies', 'list_movies_by_genre', True, ['genre']),
    'list_movies_by_year': ('movies', 'list_movies_by_year', True, ['year']),
    'list_movies_by_rating': ('movies', 'list_movies_by_rating', True, None),
    'list_movies_by_popularity': ('movies', 'list_movies_by_popularity', True, None),
    'list_4k_movies': ('movies', 'list_4k_movies', True, None),
    'list_collections': ('movies', 'list_collections', True, None),
    'list_movies_by_collection': ('movies', 'list_movies_by_collection', True, ['collection']),
    'list_recently_added_movies': ('movies', 'list_recently_added_movies', True, None),
    'list_movies_by_revenue': ('movies', 'list_movies_by_revenue', True, None),
    'list_movies_by_provider': ('movies', 'list_movies_by_provider', True, ['provider']),
    'list_trending_movies': ('movies', 'list_trending_movies', True, None),
    'list_movies_by_theme': ('movies', 'list_movies_by_theme', True, ['theme']),
    'list_rating_categories_movies':      ('movies', 'list_rating_categories_movies',      False, None),
    'list_movies_by_rating_category':     ('movies', 'list_movies_by_rating_category',     True,  ['slug']),

    # === SÉRIES ===
    'list_most_searched_shows': ('tvshows', 'list_most_searched_shows', True, None),
    'list_tvshows_genres': ('tvshows', 'list_tvshows_genres', False, None),
    'list_tvshow_themes': ('tvshows', 'list_tvshow_themes', False, None),
    'list_providers': ('tvshows', 'list_providers', False, None),
    'list_trending_tvshows': ('tvshows', 'list_trending_tvshows', True, None),
    'list_tvshows_by_genre': ('tvshows', 'list_tvshows_by_genre', True, ['genre']),
    'list_recently_added_tvshows': ('tvshows', 'list_recently_added_tvshows', True, None),
    'list_tvshows_by_popularity': ('tvshows', 'list_tvshows_by_popularity', True, None),
    'list_tvshows_by_provider': ('tvshows', 'list_tvshows_by_provider', True, ['provider']),
    'list_animes': ('tvshows', 'list_animes', True, None),
    'list_kids_tvshows': ('tvshows', 'list_kids_tvshows', True, None),
    'list_tvshows_by_theme': ('tvshows', 'list_tvshows_by_theme', True, ['theme']),
    'list_rating_categories_tvshows':     ('tvshows', 'list_rating_categories_tvshows',     False, None),
    'list_tvshows_by_rating_category':    ('tvshows', 'list_tvshows_by_rating_category',    True,  ['slug']),
}

def get_action_handler(action):
    if action in _ACTION_HANDLERS:
        return _ACTION_HANDLERS[action]
    config = ACTIONS.get(action)
    if not config:
        return None
    _ACTION_HANDLERS[action] = config
    return config

def handle_generic_action(action, params):
    handler = get_action_handler(action)
    if not handler:
        return False

    module_name, method_name, needs_page, extra_params = handler
    mod = get_module(module_name)
    if not mod:
        return False

    method = getattr(mod, method_name, None)
    if not method:
        return False

    args = []

    if extra_params:
        for param in extra_params:
            val = params.get(param, '')
            if param == 'year':
                val = int(val) if val else 0
            args.append(val)

    if needs_page:
        args.append(int(params.get('page', '1')))

    method(*args)
    return True

def clear_action_handler_cache():
    _ACTION_HANDLERS.clear()