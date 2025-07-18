# -*- coding: utf-8 -*-

# --- Imports da Biblioteca Padrão ---
import sys
import os
import json
import subprocess
from urllib.parse import urlencode, parse_qsl
import urllib.request
from datetime import datetime

# --- Imports da Biblioteca Kodi ---
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
from xbmcaddon import Addon
from xbmcvfs import translatePath

# --- Imports de Módulos Personalizados ---
# resources.lib
from resources.lib.players import play_video
from resources.lib.utils import get_all_videos, clear_cache, VIDEO_CACHE, FILTERED_CACHE
from resources.lib.menus import list_menu, list_subcategories, get_menu, show_donation, show_telegram
from resources.lib.config import login
from resources.lib.configs.urls import data_feed, credenciais
from resources.lib.counter import register_menu_access

# resources.action
from resources.action.search import search_videos, open_video_folder
from resources.action.movies import (
    list_movies_by_genre, list_genres, list_studios, list_movies_by_studio,
    list_years, list_movies_by_year, list_movies_by_specific_year, generate_url,
    list_movies_by_rating, list_actors, list_movies_by_actor,
    list_movies_by_popularity, list_movies_in_cinemas, list_recently_added,
    list_movies_by_collection, list_collections, list_movies_by_country,
    list_countries, list_4k_movies, list_movies_by_revenue, list_movies_by_keyword,
    list_keywords, list_movies_legendados
)
from resources.action.tvshow import (
    list_series_genres, list_series_by_genre, list_series_studios,
    list_series_by_studio, list_series_by_rating, list_series_by_specific_year,
    list_series_by_popularity, list_anime_series, list_novela_series,
    list_recently_added_series, list_kids_series
)

from resources.action.video_listing import (
    list_videos, list_collection, list_seasons, list_episodes, create_video_item
)
from resources.action.explorar import (
    list_trending, list_random, list_week_recommendations,
    clear_weekly_recommendation_cache, list_years_explorar, list_by_year,
    list_by_provider, list_providers, list_by_date_added
)
from resources.action.favorites import (
    list_favorites, add_to_favorites, load_favorites, save_favorites,
    remove_from_favorites, force_update_series
)

# Outros módulos personalizados
from changelog import show_about


# --- Configurações do Plugin ---
URL = sys.argv[0]  # URL base do plugin
HANDLE = int(sys.argv[1])  # Handle do plugin (identificador da janela atual)
ADDON_PATH = translatePath(Addon().getAddonInfo('path'))  # Caminho do diretório do addon
ICONS_DIR = os.path.join(ADDON_PATH, 'resources', 'images', 'icons')  # Diretório de ícones
FANART_DIR = os.path.join(ADDON_PATH, 'resources', 'images', 'fanart')  # Diretório de fanarts



def get_url(**kwargs):
    """
    Cria uma URL para chamar o plugin recursivamente a partir dos argumentos fornecidos.
    :param kwargs: Argumentos para a URL.
    :return: URL formatada.
    """
    return '{}?{}'.format(URL, urlencode(kwargs))

def router():
    """
    Roteia as ações do plugin com base nos parâmetros da URL.
    """
    # Extrai os parâmetros da URL
    params = dict(parse_qsl(sys.argv[2][1:]))
    
    
    is_series = params.get('is_series', 'false').lower() == 'true'

    action = params.get('action')

    # Cria o dicionário kwargs com todos os parâmetros possíveis
    kwargs = {
        'external_link': params.get('external_link', ''),
        'studio': params.get('studio', ''),
        'sort_method': params.get('sort_method', 'title'),
        'page': int(params.get('page', 1)),
        'genre': params.get('genre', ''),
        'year': params.get('year'),
        'collection': params.get('collection', ''),
        'group': params.get('group', ''),
        'channel_url': params.get('channel_url', ''),
        'stream_url': params.get('stream_url', ''),
        'video': params.get('video', ''),
        'serie': params.get('serie', ''),
        'season_title': params.get('season_title', ''),
        'actor': params.get('actor', ''),
        'video_id': params.get('video_id', ''),
        'items_per_page': int(params.get('items_per_page') or xbmcaddon.Addon().getSetting('items_per_page')),
        'menu_index': params.get('menu_index'),
        'title': params.get('title', ''),
        'tmdb_id': params.get('tmdb_id', ''),
        'imdb_id': params.get('imdb_id', ''),
        'movie_poster': params.get('movie_poster', ''),
        'movie_synopsis': params.get('movie_synopsis', ''),
        'collection': params.get('collection', ''),
        'country_code': params.get('country_code', ''),
        'keyword': params.get('keyword', '')
    }

    # Processa parâmetros que podem ser JSON
    for key in ['video', 'serie', 'collection']:
        if kwargs[key] and kwargs[key].startswith('{') and kwargs[key].endswith('}'):
            try:
                kwargs[key] = json.loads(kwargs[key])
            except:
                pass  # Mantém o valor original se falhar

    # Verifica o login antes de continuar
    if not login():
        return

    # Mapeamento de ações para funções
    actions = {
        'list_subcategories': lambda: list_subcategories(int(kwargs['menu_index'])),
        'list_videos': lambda: list_videos(kwargs['external_link'], kwargs['sort_method'], items_per_page=kwargs['items_per_page'], page=kwargs['page']),
        'list_seasons': lambda: list_seasons(kwargs['serie']),
        'list_episodes': lambda: list_episodes(kwargs['serie'], kwargs['season_title']),
        'list_collection': lambda: list_collection(kwargs['collection']),
        'play': lambda: play_video(
            (
                json.loads(kwargs['video'])
                if isinstance(kwargs['video'], str) and kwargs['video'].startswith('[')
                else kwargs['video'].split(',')
                if isinstance(kwargs['video'], str) and ',' in kwargs['video']
                else [kwargs['video']] if kwargs['video'] else []
            ),
            title=kwargs.get('title', ''),
            tmdb_id=kwargs.get('tmdb_id', ''),
            imdb_id=kwargs.get('imdb_id', ''),
            year=kwargs.get('year'),
            movie_poster=kwargs.get('movie_poster', ''),
            movie_synopsis=kwargs.get('movie_synopsis', ''),
            is_series=is_series
        ),
        'search_videos': lambda: search_videos(HANDLE),
        'open_video_folder': lambda: open_video_folder(HANDLE, kwargs['tmdb_id']),
        'list_genres': lambda: list_genres(),
        'list_movies_by_genre': lambda: list_movies_by_genre(kwargs['genre'], page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_movies_by_keyword': lambda: list_movies_by_keyword(
            keyword=kwargs['keyword'],
            page=kwargs['page'],
            items_per_page=kwargs['items_per_page']
        ) if kwargs['keyword'] else xbmcgui.Dialog().ok("Erro", "Palavra-chave não especificada"),
        'list_keywords': lambda: list_keywords(),
        'list_studios': lambda: list_studios(),
        'list_movies_by_studio': lambda: list_movies_by_studio(kwargs['studio']),
        'show_about': lambda: show_about(),
        'list_series_genres': lambda: list_series_genres(),
        'list_series_by_genre': lambda: list_series_by_genre(kwargs['genre']),
        'list_series_studios': lambda: list_series_studios(),
        'list_series_by_studio': lambda: list_series_by_studio(kwargs['studio']),
        'list_movies_by_year': lambda: list_movies_by_year(int(kwargs['year'])) if kwargs['year'] else None,
        'list_years': lambda: list_years(),
        'add_to_favorites': lambda: add_to_favorites(kwargs['video']),
        'remove_from_favorites': lambda: remove_from_favorites(kwargs['video']),
        'list_favorites': lambda: list_favorites(),
        'list_movies_by_specific_year': lambda: list_movies_by_specific_year(2025),
        'list_series_by_specific_year': lambda: list_series_by_specific_year(2025),
        'list_movies_by_rating': lambda: list_movies_by_rating(page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_series_by_rating': lambda: list_series_by_rating(page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_actors': lambda: list_actors(),
        'list_movies_by_actor': lambda: list_movies_by_actor(kwargs['actor']),
        'list_movies_by_popularity': lambda: list_movies_by_popularity(page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_series_by_popularity': lambda: list_series_by_popularity(page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_anime_series': lambda: list_anime_series(),
        'list_novela_series': lambda: list_novela_series(),
        'list_recently_added_series': lambda: list_recently_added_series(),
        'list_kids_series': lambda: list_kids_series(),
        'list_movies_in_cinemas': lambda: list_movies_in_cinemas(page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_random':lambda: list_random(),
        'list_recently_added': lambda: list_recently_added(page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'show_donation': lambda: show_donation(),
        'show_telegram': lambda: show_telegram(),
        'clear_cache': lambda: clear_cache(),
        'list_trending': lambda: list_trending(),
        'force_update_series': lambda: force_update_series(kwargs['video_id']),
        'list_week_recommendations': lambda: list_week_recommendations(),
        'clear_weekly_cache': lambda: [clear_weekly_recommendation_cache(), xbmcgui.Dialog().ok("Recomendações", "Cache limpo com sucesso!\nAs novas sugestões serão carregadas agora."), list_week_recommendations()],
        'list_providers': lambda: list_providers(),
        'list_by_provider': lambda: list_by_provider(
            urllib.parse.unquote_plus(params.get('provider', '')),
            int(params.get('page', '1'))
        ),
        'list_years_explorar': lambda: list_years_explorar(),
        'list_by_year': lambda: list_by_year(kwargs['year'], kwargs['page']),
        'list_by_date_added': lambda: list_by_date_added(page=kwargs['page']),
        'list_collections': lambda: list_collections(page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_movies_by_collection': lambda: list_movies_by_collection(kwargs['collection'], page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_countries': lambda: list_countries(),
        'list_movies_by_country': lambda: list_movies_by_country(
            kwargs['country_code'],
            page=kwargs['page'],
            items_per_page=kwargs['items_per_page']
        ),
        'list_4k_movies': lambda: list_4k_movies(page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_movies_by_revenue': lambda: list_movies_by_revenue(page=kwargs['page'], items_per_page=kwargs['items_per_page']),
        'list_movies_legendados': lambda: list_movies_legendados(page=kwargs['page'], items_per_page=kwargs['items_per_page'])
    }

    # Executa a ação correspondente ou lista o menu principal
    if action in actions:
        try:
            actions[action]()
        except Exception as e:
            xbmc.log(f"Erro ao executar {action}: {str(e)}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("Erro", f"Falha ao executar {action}", xbmcgui.NOTIFICATION_ERROR, 3000)
    else:
        list_menu()

if __name__ == '__main__':
    register_menu_access()
    router()