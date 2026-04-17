# -*- coding: utf-8 -*-

import os
import xbmcaddon

# --- Configuração de Caminhos ---
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')


# === MENU PERFIS ===
PROFILES_MENU = [
    {'title': 'Selecionar Perfil', 'action': 'profile_select', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Gerenciar Perfis',  'action': 'profile_manage', 'icon': os.path.join(ICON_PATH, 'settings.png')},
    {'title': 'Criar Novo Perfil', 'action': 'profile_create', 'icon': os.path.join(ICON_PATH, 'search.png')},
]

# ============================================================
# MODO ANÔNIMO — sem sessão PLUS
# ============================================================

MAIN_MENU_ANON = [
    {
        'title': 'Pesquisar',
        'action': 'search',
        'icon': os.path.join(ICON_PATH, 'pesquisa.png'),
        'plot': 'Pesquisar filmes e series no banco de dados local.',
    },
    {
        'title': 'Filmes',
        'action': 'movies_menu',
        'icon': os.path.join(ICON_PATH, 'filmes.png'),
        'plot': 'Filmes do banco de dados local.',
    },
    {
        'title': 'Series',
        'action': 'tvshows_menu',
        'icon': os.path.join(ICON_PATH, 'serie.png'),
        'plot': 'Series do banco de dados local.',
    },
    {
        'title': 'Minha Lista',
        'action': 'favorites_menu',
        'icon': os.path.join(ICON_PATH, 'minha_lista.png'),
        'plot': 'Seus favoritos salvos localmente.',
    },
    {
        'title': 'Histórico',
        'action': 'show_history_menu',
        'icon': os.path.join(ICON_PATH, 'historico.png'),
        'plot': 'Tudo que você já assistiu, com progresso salvo.',
    },
    {
        'title': '[COLOR gold]Autenticar[/COLOR]',
        'action': 'vip_login',
        'icon': os.path.join(ICON_PATH, 'vip.png'),
        'plot': (
            '[COLOR gold]Área PLUS — Benefícios exclusivos[/COLOR]'
        ),
    },
]

# Filmes para anônimo — só banco local
MOVIES_MENU_ANON = [
    {'title': 'Recentes',  'action': 'list_recently_added_movies', 'icon': os.path.join(ICON_PATH, 'recentes.png')},
    {'title': 'Populares', 'action': 'list_movies_by_popularity',  'icon': os.path.join(ICON_PATH, 'populares.png')},
    {'title': 'Gêneros',   'action': 'list_genres',                'icon': os.path.join(ICON_PATH, 'generos.png')},
]

# Series para anônimo — só banco local
TVSHOWS_MENU_ANON = [
    {'title': 'Recentes',  'action': 'list_recently_added_tvshows', 'icon': os.path.join(ICON_PATH, 'recentes.png')},
    {'title': 'Populares', 'action': 'list_tvshows_by_popularity',  'icon': os.path.join(ICON_PATH, 'populares.png')},
    {'title': 'Gêneros',   'action': 'list_tvshows_genres',         'icon': os.path.join(ICON_PATH, 'generos.png')},
    {'title': 'Animes',        'action': 'list_animes',                 'icon': os.path.join(ICON_PATH, 'animes.png')},
]


# ============================================================
# MENU PRINCIPAL PLUS
# ============================================================
MAIN_MENU = [
    {
        'title': 'Pesquisar',
        'action': 'search',
        'icon': os.path.join(ICON_PATH, 'pesquisa.png'),
        'plot': 'Pesquisar filmes e series por titulo.'
    },
    {
        'title': 'Filmes',
        'action': 'movies_menu',
        'icon': os.path.join(ICON_PATH, 'filmes.png'),
        'plot': 'Filmes do catalogo TMDB e listas publicas do Trakt.'
    },
    {
        'title': 'Series',
        'action': 'tvshows_menu',
        'icon': os.path.join(ICON_PATH, 'serie.png'),
        'plot': 'Series do TMDB e listas publicas do Trakt.'
    },
    {
        'title': 'Minha Lista',
        'action': 'favorites_menu',
        'icon': os.path.join(ICON_PATH, 'minha_lista.png'),
        'plot': 'Seus favoritos e itens salvos localmente.'
    },
    {
        'title': 'Histórico',
        'action': 'show_history_menu',
        'icon': os.path.join(ICON_PATH, 'historico.png'),
        'plot': 'Tudo que você já assistiu, com progresso salvo.'
    },

    {
        'title': '[COLOR yellow]Minha Conta[/COLOR]',
        'action': 'vip_menu',
        'icon': os.path.join(ICON_PATH, 'minha_conta.png'),
        'plot': 'Histórico, perfis, Trakt, sincronização e configurações.',
    },
    {
        'title': '[COLOR orange]Ferramentas[/COLOR]',
        'action': 'tools_menu',
        'icon': os.path.join(ICON_PATH, 'ferramentas.png'),
        'plot': 'Configuracoes, manutencao e informacoes do addon.'
    },
]

# === MENU PRINCIPAL INFANTIL ===
MAIN_MENU_KIDS = [
    {
        'title': 'Pesquisar',
        'action': 'search',
        'icon': os.path.join(ICON_PATH, 'kids_search.png'),
        'plot': 'Pesquisar filmes e series por titulo.'
    },
    {
        'title': 'Filmes',
        'action': 'movies_menu',
        'icon': os.path.join(ICON_PATH, 'kids_movie.png'),
        'plot': 'Filmes infantis e familiares.'
    },
    {
        'title': 'Series',
        'action': 'tvshows_menu',
        'icon': os.path.join(ICON_PATH, 'kids_tv.png'),
        'plot': 'Series infantis e desenhos animados.'
    },
    {
        'title': 'Minha Lista',
        'action': 'favorites_menu',
        'icon': os.path.join(ICON_PATH, 'kids_list.png'),
        'plot': 'Seus favoritos e itens salvos.'
    },
    {
        'title': '[COLOR yellow]Minha Conta[/COLOR]',
        'action': 'vip_menu',
        'icon': os.path.join(ICON_PATH, 'minha_conta.png'),
        'plot': 'Histórico, perfis, Trakt, sincronização e configurações.',
    },
]


# ============================================================
# FERRAMENTAS
# ============================================================
TOOLS_MENU = [
    {'title': 'Configuracoes',           'action': 'open_settings',  'icon': os.path.join(ICON_PATH, 'settings.png')},
    {'title': 'Changelog',               'action': 'show_changelog', 'icon': os.path.join(ICON_PATH, 'lists.png')},
    {'title': 'Biblioteca',              'action': 'library_menu',   'icon': os.path.join(ICON_PATH, 'premium.png'), 'plot': 'Conteudo salvo e organizado localmente.'},
    {'title': 'Doacao',                  'action': 'show_donation',  'icon': os.path.join(ICON_PATH, 'lists.png')},
    {'title': 'Atualizar Banco de Dados','action': 'run_indexer',    'icon': os.path.join(ICON_PATH, 'github.png'),  'plot': 'Atualiza e reorganiza o banco de dados local.'},
]


# ============================================================
# MENU FILMES PLUS — tudo junto, sem submenu exclusivo
# ============================================================
MOVIES_MENU = [
    {'title': 'Para Você',    'action': 'list_recommendations_movies',  'icon': os.path.join(ICON_PATH, 'para_voce.png')},
    {'title': 'Recentes',      'action': 'list_recently_added_movies',  'icon': os.path.join(ICON_PATH, 'recentes.png')},
    {'title': 'Em Alta',       'action': 'list_trending_movies',        'icon': os.path.join(ICON_PATH, 'em_alta.png')},
    {'title': 'Populares',     'action': 'list_movies_by_popularity',   'icon': os.path.join(ICON_PATH, 'populares.png')},
    {'title': 'Gêneros',       'action': 'list_genres',                 'icon': os.path.join(ICON_PATH, 'generos.png')},
    {'title': 'Por Ano',       'action': 'list_years',                  'icon': os.path.join(ICON_PATH, 'por_ano.png')},
    {'title': 'Temas',         'action': 'list_movie_themes',           'icon': os.path.join(ICON_PATH, 'temas.png')},
    {'title': '4K Ultra HD',   'action': 'list_4k_movies',              'icon': os.path.join(ICON_PATH, '4k.png')},
    {'title': 'Coleções',      'action': 'list_collections',            'icon': os.path.join(ICON_PATH, 'colecoes.png')},
]

# === MENU FILMES INFANTIL ===
MOVIES_MENU_KIDS = [
    {'title': 'Populares', 'action': 'list_movies_by_popularity',  'icon': os.path.join(ICON_PATH, 'populares_kids.png')},
    {'title': 'Recentes',  'action': 'list_recently_added_movies', 'icon': os.path.join(ICON_PATH, 'recentes_kids.png')},
    {'title': 'Gêneros',   'action': 'list_genres',                'icon': os.path.join(ICON_PATH, 'generos_kids.png')},
]


# ============================================================
# MENU SERIES PLUS — tudo junto, sem submenu exclusivo
# ============================================================
TVSHOWS_MENU = [
    {'title': 'Para Você',    'action': 'list_recommendations_tvshows', 'icon': os.path.join(ICON_PATH, 'para_voce.png')},
    {'title': 'Recentes',      'action': 'list_recently_added_tvshows', 'icon': os.path.join(ICON_PATH, 'recentes.png')},
    {'title': 'Em Alta',       'action': 'list_trending_tvshows',       'icon': os.path.join(ICON_PATH, 'em_alta.png')},
    {'title': 'Populares',     'action': 'list_tvshows_by_popularity',  'icon': os.path.join(ICON_PATH, 'populares.png')},
    {'title': 'Gêneros',       'action': 'list_tvshows_genres',         'icon': os.path.join(ICON_PATH, 'generos.png')},
    {'title': 'Temas',         'action': 'list_tvshow_themes',          'icon': os.path.join(ICON_PATH, 'temas.png')},
    {'title': 'Provedores',    'action': 'list_providers',              'icon': os.path.join(ICON_PATH, 'provedores.png')},
    {'title': 'Animes',        'action': 'list_animes',                 'icon': os.path.join(ICON_PATH, 'animes.png')},
]

# === MENU SERIES INFANTIL ===
TVSHOWS_MENU_KIDS = [
    {'title': 'Populares', 'action': 'list_tvshows_by_popularity',  'icon': os.path.join(ICON_PATH, 'populares_kids.png')},
    {'title': 'Recentes',  'action': 'list_recently_added_tvshows', 'icon': os.path.join(ICON_PATH, 'recentes_kids.png')},
    {'title': 'Infantil',  'action': 'list_kids_tvshows',           'icon': os.path.join(ICON_PATH, 'infantil_kids.png')},
]


# ============================================================
# MENU TRAKT
# ============================================================
TRAKT_MENU = [
    {'title': 'Status / Autenticar', 'action': 'trakt_auth',            'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Filmes',              'action': 'trakt_movies_submenu',   'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Series',              'action': 'trakt_tv_submenu',       'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Watchlist',           'action': 'trakt_watchlist_menu',   'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Colecao',             'action': 'trakt_collection_menu',  'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Assistidos',          'action': 'trakt_watched_menu',     'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Minhas Listas',       'action': 'trakt_lists_menu',       'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Sincronizar',         'action': 'trakt_sync_menu',        'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

TRAKT_SYNC_MENU = [
    {'title': 'Sincronizacao Completa', 'action': 'trakt_full_sync',       'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Enviar Trakt',           'action': 'trakt_sync_to_trakt',   'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Importar Trakt',         'action': 'trakt_sync_from_trakt', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Limpar Cache',           'action': 'trakt_clear_cache',     'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

# === SUBMENU FILMES TRAKT ===
TRAKT_MOVIES_MENU = [
    {'title': 'Watchlist',        'action': 'trakt_watchlist_menu',              'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Assistidos',       'action': 'trakt_watched_menu',                'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Coleção',          'action': 'trakt_collection_menu',             'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Recomendações',    'action': 'trakt_movies_personal_recommended', 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Minhas Listas',    'action': 'trakt_lists_menu',                  'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

# === SUBMENU SERIES TRAKT ===
TRAKT_TV_MENU = [
    {'title': 'Watchlist',        'action': 'trakt_watchlist_menu',             'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Assistidas',       'action': 'trakt_watched_menu',               'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Coleção',          'action': 'trakt_collection_menu',            'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Recomendações',    'action': 'trakt_tv_personal_recommended',    'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
    {'title': 'Minhas Listas',    'action': 'trakt_lists_menu',                 'icon': os.path.join(ICON_PATH, 'trakt_menu.png')},
]

# ============================================================
# HUB PLUS — menu central da Área PLUS
# ============================================================
VIP_HUB_MENU = [
    {
        'title': 'Histórico',
        'action': 'show_history_menu',
        'icon': os.path.join(ICON_PATH, 'popular.png'),
        'plot': 'Tudo que você já assistiu, com progresso salvo.',
    },
    {
        'title': 'Perfis',
        'action': 'profile_select',
        'icon': os.path.join(ICON_PATH, 'trakt_menu.png'),
        'plot': 'Trocar ou gerenciar perfis PLUS.',
    },
    {
        'title': 'Trakt',
        'action': 'trakt_main_menu',
        'icon': os.path.join(ICON_PATH, 'trakt_menu.png'),
        'plot': 'Sincronizar histórico, watchlist e coleção com o Trakt.',
    },
    {
        'title': 'Sincronizar Trakt',
        'action': 'trakt_auth',
        'icon': os.path.join(ICON_PATH, 'trakt_menu.png'),
        'plot': 'Sincronização completa com sua conta Trakt agora.',
    },
    {
        'title': 'Configurações',
        'action': 'open_settings',
        'icon': os.path.join(ICON_PATH, 'settings.png'),
        'plot': 'Ajustar preferências do addon.',
    },
    {
        'title': '[COLOR red]Sair do PLUS[/COLOR]',
        'action': 'vip_logout',
        'icon': os.path.join(ICON_PATH, 'settings.png'),
        'plot': 'Encerrar sessão PLUS.',
    },
]