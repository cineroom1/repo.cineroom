# -*- coding: utf-8 -*-

import os
import xbmcaddon

# --- Configuração de Caminhos (Melhor Prática) ---
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')
# -------------------------------------------------

MAIN_MENU = [
    {'title': 'Pesquisar', 'action': 'search', 'icon': os.path.join(ICON_PATH, 'search.png')},
    {'title': 'Filmes', 'action': 'movies_menu', 'icon': os.path.join(ICON_PATH, 'movies.png')},
    {'title': 'Séries', 'action': 'tvshows_menu', 'icon': os.path.join(ICON_PATH, 'tv.png')},
    {'title': 'Minha Lista', 'action': 'show_my_list', 'icon': os.path.join(ICON_PATH, 'favorites.png')},
    {'title': 'Doação', 'action': 'show_donation', 'icon': os.path.join(ICON_PATH, 'donation.png')},
    {'title': '[B]Atualizar Banco de Dados[/B]', 'action': 'run_indexer', 'plot': 'Clique aqui para reescrever o banco de dados. ', 'icon': os.path.join(ICON_PATH, 'settings.png')}
]


MOVIES_MENU = [
    {'title': 'Recentes', 'action': 'list_recently_added_movies', 'icon': os.path.join(ICON_PATH, 'calender.png')},
    {'title': 'Populares', 'action': 'list_movies_by_popularity', 'icon': os.path.join(ICON_PATH, 'popular.png')},
    {'title': 'Gêneros', 'action': 'list_genres', 'icon': os.path.join(ICON_PATH, 'genres.png')},
    {'title': '4K Ultra HD', 'action': 'list_4k_movies', 'icon': os.path.join(ICON_PATH, 'flag_4k.png')},
    {'title': 'Maiores bilheterias', 'action': 'list_movies_by_revenue', 'icon': os.path.join(ICON_PATH, 'trending.png')},
    {'title': 'Por Ano', 'action': 'list_years', 'icon': os.path.join(ICON_PATH, 'calender.png')},
    {'title': 'Coleções', 'action': 'list_collections', 'icon': os.path.join(ICON_PATH, 'premium.png')},
    
]

TVSHOWS_MENU = [
    {'title': 'Recentes', 'action': 'list_recently_added_tvshows', 'icon': os.path.join(ICON_PATH, 'calender.png')},
    {'title': 'Populares', 'action': 'list_tvshows_by_popularity', 'icon': os.path.join(ICON_PATH, 'popular.png')},
    {'title': 'Gêneros', 'action': 'list_tvshows_genres', 'icon': os.path.join(ICON_PATH, 'genres.png')},
    {'title': 'Provedores', 'action': 'list_providers', 'icon': os.path.join(ICON_PATH, 'providers.png')},
    {'title': 'Animes', 'action': 'list_animes', 'icon': os.path.join(ICON_PATH, 'anime.png')},
    {'title': 'Infantil', 'action': 'list_kids_tvshows', 'icon': os.path.join(ICON_PATH, 'genre_kids.png')},
]