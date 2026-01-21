# -*- coding: utf-8 -*-

import os
import xbmcaddon

# --- Configuração de Caminhos ---
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

MAIN_MENU = [
    {
        'title': 'Pesquisar',
        'action': 'search',
        'icon': os.path.join(ICON_PATH, 'search.png'),
        'plot': 'Pesquisar filmes e séries por título.'
    },
    {
        'title': 'Filmes',
        'action': 'movies_menu',
        'icon': os.path.join(ICON_PATH, 'movies.png'),
        'plot': 'Filmes do catálogo TMDB e listas públicas do Trakt.'
    },
    {
        'title': 'Séries',
        'action': 'tvshows_menu',
        'icon': os.path.join(ICON_PATH, 'tv.png'),
        'plot': 'Séries do TMDB e listas públicas do Trakt.'
    },
    {
        'title': 'Minha Lista',
        'action': 'favorites_menu',
        'icon': os.path.join(ICON_PATH, 'favorites.png'),
        'plot': 'Seus favoritos e itens salvos localmente.'
    },
    {
        'title': 'Trakt',
        'action': 'trakt_main_menu',
        'icon': os.path.join(ICON_PATH, 'trakt.png'),
        'plot': 'Watchlist, coleção, assistidos e sincronização com sua conta Trakt.'
    },   
    {
        'title': '[COLOR orange]Ferramentas[/COLOR]',
        'action': 'tools_menu',
        'icon': os.path.join(ICON_PATH, 'tools.png'),
        'plot': 'Configurações, manutenção e informações do addon.'
    },
]


TOOLS_MENU = [
    {'title': 'Configurações', 'action': 'open_settings', 'icon': os.path.join(ICON_PATH, 'settings.png')},
    {'title': 'Changelog', 'action': 'show_changelog', 'icon': os.path.join(ICON_PATH, 'lists.png')},
    {'title': 'Biblioteca','action': 'library_menu','icon': os.path.join(ICON_PATH, 'premium.png'),'plot': 'Conteúdo salvo e organizado localmente.'},
    {'title': 'Doação', 'action': 'show_donation', 'icon': os.path.join(ICON_PATH, 'lists.png')},
    {'title': 'Atualizar Banco de Dados', 'action': 'run_indexer', 'icon': os.path.join(ICON_PATH, 'github.png'), 'plot': 'Atualiza e reorganiza o banco de dados local.'}
]

MOVIES_MENU = [
    {'title': 'Recomendações', 'action': 'trakt_movies_personal_recommended', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Recentes', 'action': 'list_recently_added_movies', 'icon': os.path.join(ICON_PATH, 'movies.png')},
    {'title': 'Em Alta', 'action': 'list_trending_movies', 'icon': os.path.join(ICON_PATH, 'movies.png')},
    {'title': 'Populares', 'action': 'list_movies_by_popularity', 'icon': os.path.join(ICON_PATH, 'movies.png')},
    {'title': 'Gêneros', 'action': 'list_genres', 'icon': os.path.join(ICON_PATH, 'movies.png')},
    {'title': 'Temas', 'action': 'list_movie_themes', 'icon': os.path.join(ICON_PATH, 'movies.png')},
    {'title': '4K Ultra HD', 'action': 'list_4k_movies', 'icon': os.path.join(ICON_PATH, 'movies.png')},
    {'title': 'Maiores bilheterias', 'action': 'list_movies_by_revenue', 'icon': os.path.join(ICON_PATH, 'movies.png')},
    {'title': 'Por Ano', 'action': 'list_years', 'icon': os.path.join(ICON_PATH, 'movies.png')},
    {'title': 'Coleções', 'action': 'list_collections', 'icon': os.path.join(ICON_PATH, 'movies.png')},

    
]

TVSHOWS_MENU = [
    {'title': 'Recomendações', 'action': 'trakt_tv_personal_recommended', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Recentes', 'action': 'list_recently_added_tvshows', 'icon': os.path.join(ICON_PATH, 'tv.png')},
    {'title': 'Em Alta', 'action': 'list_trending_tvshows', 'icon': os.path.join(ICON_PATH, 'tv.png')},
    {'title': 'Populares', 'action': 'list_tvshows_by_popularity', 'icon': os.path.join(ICON_PATH, 'tv.png')},
    {'title': 'Gêneros', 'action': 'list_tvshows_genres', 'icon': os.path.join(ICON_PATH, 'tv.png')},
    {'title': 'Temas', 'action': 'list_tvshow_themes', 'icon': os.path.join(ICON_PATH, 'tv.png')},
    {'title': 'Provedores', 'action': 'list_providers', 'icon': os.path.join(ICON_PATH, 'tv.png')},
    {'title': 'Animes', 'action': 'list_animes', 'icon': os.path.join(ICON_PATH, 'tv.png')},
    {'title': 'Infantil', 'action': 'list_kids_tvshows', 'icon': os.path.join(ICON_PATH, 'tv.png')},
]
# === MENU TRAKT PRINCIPAL ===
TRAKT_MENU = [
    {'title': 'Status / Autenticar', 'action': 'trakt_auth', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Filmes', 'action': 'trakt_movies_submenu', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Séries', 'action': 'trakt_tv_submenu', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Watchlist', 'action': 'trakt_watchlist_menu', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Coleção', 'action': 'trakt_collection_menu', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Assistidos', 'action': 'trakt_watched_menu', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Minhas Listas', 'action': 'trakt_lists_menu', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Sincronizar', 'action': 'trakt_sync_menu', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

TRAKT_SYNC_MENU = [
    {'title': 'Sincronização Completa', 'action': 'trakt_full_sync', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Enviar → Trakt', 'action': 'trakt_sync_to_trakt', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Importar ← Trakt', 'action': 'trakt_sync_from_trakt', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Limpar Cache', 'action': 'trakt_clear_cache', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

# === SUBMENU FILMES TRAKT ===
TRAKT_MOVIES_MENU = [
    {'title': 'Recomendações', 'action': 'trakt_movies_personal_recommended', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Em Alta', 'action': 'trakt_movies_trending', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Populares', 'action': 'trakt_movies_popular', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Mais Assistidos', 'action': 'trakt_movies_most_watched', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Mais Coletados', 'action': 'trakt_movies_most_collected', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Mais Aguardados', 'action': 'trakt_movies_most_anticipated', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Bilheteria', 'action': 'trakt_movies_box_office', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Melhor Avaliados', 'action': 'trakt_movies_top_rated', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

# === SUBMENU SÉRIES TRAKT ===
TRAKT_TV_MENU = [
    {'title': 'Recomendações', 'action': 'trakt_tv_personal_recommended', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Em Alta', 'action': 'trakt_tv_trending', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Populares', 'action': 'trakt_tv_popular', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Mais Assistidas', 'action': 'trakt_tv_most_watched', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Mais Coletadas', 'action': 'trakt_tv_most_collected', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Mais Aguardadas', 'action': 'trakt_tv_most_anticipated', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Melhor Avaliadas', 'action': 'trakt_tv_top_rated', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]