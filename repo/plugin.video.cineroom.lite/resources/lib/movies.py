# -*- coding: utf-8 -*-
# Em: resources/lib/movies.py

import xbmc
import os
import json
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
import urllib.parse
from urllib.parse import urlencode

from .db import db
from resources.lib.extras_dialog import show_details
from .utils import create_video_item, with_view_mode

# --- Configurações gerais ---
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
DEFAULT_ITEMS_PER_PAGE = int(ADDON.getSetting("pages"))

ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"

def _add_movie_item_to_list(movie):
    """
    Função auxiliar interna para criar e adicionar um item de filme à lista.
    Ela contém toda a lógica de decisão de URL (detalhes vs. play direto).
    """
    li = create_video_item(movie, media_type='movie')

    data_for_url = {
        'tmdb_id': movie.get('tmdb_id'),
        'imdb_id': movie.get('imdb_id'),
        'title': movie.get('title'),
        'clearlogo': movie.get('clearlogo'),
        'synopsis': movie.get('synopsis'),
        'poster': movie.get('poster'),
        'backdrop': movie.get('backdrop'),
        'year': movie.get('year'),
        'runtime': movie.get('runtime'),
        'rating': movie.get('rating'),
        'certification': movie.get('certification'),
        'trailer': movie.get('trailer'),
        'genre': ', '.join(movie.get('genres', [])),
        'streams': movie.get('streams', []),
        'media_type': 'movie',
        'original_title': movie.get('original_title', movie.get('title')),
    }
    item_data_json = json.dumps(data_for_url, ensure_ascii=False)

    if ADDON.getSettingBool('enable_details_dialog'):
        url = get_url(action='show_details', data=item_data_json)
        is_folder = False
    else:
        url = get_url(action='play_item_direct', data=item_data_json)
        is_folder = False

    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)

# --- MENUS ---

@with_view_mode('files', is_menu=True)
def show_movies_menu(menu_structure):
    """Cria e exibe o menu da seção 'Filmes'."""
    xbmcplugin.setPluginCategory(HANDLE, 'Filmes')
    xbmcplugin.setContent(HANDLE, 'files')
    for item in menu_structure:
        li = xbmcgui.ListItem(label=item['title'])
        icon = item.get('icon')
        if icon:
            li.setArt({'thumb': icon})
        url = get_url(action=item['action'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

def add_next_page_item(items_on_current_page, current_page, **kwargs):
    """Adiciona o item 'Próxima Página' a uma lista se houver mais itens."""
    if len(items_on_current_page) == DEFAULT_ITEMS_PER_PAGE:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="Próxima Página")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        
        next_page_args = kwargs.copy()
        next_page_args['page'] = current_page + 1
        
        next_page_url = get_url(**next_page_args)
        xbmcplugin.addDirectoryItem(HANDLE, next_page_url, li_next, isFolder=True)

@with_view_mode('genres', is_menu=True)
def list_genres():
    """Cria e exibe a lista de Gêneros de Filmes."""
    xbmcplugin.setPluginCategory(HANDLE, 'Gêneros')
    xbmcplugin.setContent(HANDLE, 'genres')
    xbmc.log(f"[CINEROOM] Iniciando list_genres()", xbmc.LOGINFO)
    genres_from_db = db.get_all_unique_genres()
    xbmc.log(f"[CINEROOM] Gêneros encontrados: {genres_from_db}", xbmc.LOGINFO)

    
    for genre_name in genres_from_db:
        li = xbmcgui.ListItem(label=genre_name)
        url = get_url(action='list_movies_by_genre', genre=genre_name)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('years', is_menu=True)
def list_years():
    """Cria e exibe a lista de Anos disponíveis para filmes."""
    xbmcplugin.setPluginCategory(HANDLE, 'Anos')
    xbmcplugin.setContent(HANDLE, 'years')
    years_from_db = db.get_all_unique_years()
    
    for year in years_from_db:
        li = xbmcgui.ListItem(label=str(year))
        url = get_url(action='list_movies_by_year', year=year)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies', is_menu=True)
def list_collections():
    """Cria a lista de coleções de filmes, agora com pôsteres."""
    xbmcplugin.setPluginCategory(HANDLE, "Coleções")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    collections = db.get_all_collections()
    
    for collection_info in collections:
        collection_name = collection_info.get('collection')
        poster_url = collection_info.get('poster')
        li = xbmcgui.ListItem(label=collection_name)
        if poster_url:
            li.setArt({'poster': poster_url, 'icon': poster_url, 'thumb': poster_url})
        url = get_url(action='list_movies_by_collection', collection=collection_name)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

# --- LISTAGENS DE FILMES ---

@with_view_mode('movies')
def list_movies_by_genre(genre, page=1):
    xbmcplugin.setPluginCategory(HANDLE, genre)
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = db.get_movies_by_genre(genre, page, DEFAULT_ITEMS_PER_PAGE)
    
    for movie in movies:
        _add_movie_item_to_list(movie)
    
    add_next_page_item(movies, page, action='list_movies_by_genre', genre=genre)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_year(year, page=1):
    xbmcplugin.setPluginCategory(HANDLE, str(year))
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = db.get_movies_by_year(year, page, DEFAULT_ITEMS_PER_PAGE)
    
    for movie in movies:
        _add_movie_item_to_list(movie)
    
    add_next_page_item(movies, page, action='list_movies_by_year', year=year)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_collection(collection_name, page=1):
    xbmcplugin.setPluginCategory(HANDLE, collection_name)
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = db.get_movies_by_collection(collection_name)
    
    for movie in movies:
        _add_movie_item_to_list(movie)
    
    add_next_page_item(movies, page, action='list_movies_by_collection', collection=collection_name)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_rating(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Melhores Avaliações")
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = db.get_movies_by_rating(page, DEFAULT_ITEMS_PER_PAGE)
    
    for movie in movies:
        _add_movie_item_to_list(movie)
    
    add_next_page_item(movies, page, action='list_movies_by_rating')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_popularity(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Mais Populares")
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = db.get_movies_by_popularity(page, DEFAULT_ITEMS_PER_PAGE)

    for movie in movies:
        _add_movie_item_to_list(movie)

    add_next_page_item(movies, page, action='list_movies_by_popularity')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_4k_movies(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Filmes em 4K")
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = db.get_4k_movies(page, DEFAULT_ITEMS_PER_PAGE)
    
    for movie in movies:
        _add_movie_item_to_list(movie)
    
    add_next_page_item(movies, page, action='list_4k_movies')
    xbmcplugin.endOfDirectory(HANDLE)
    
@with_view_mode('movies')
def list_recently_added_movies(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Adicionados Recentemente")
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = db.get_recently_added_movies(page, DEFAULT_ITEMS_PER_PAGE)

    for movie in movies:
        _add_movie_item_to_list(movie)

    add_next_page_item(movies, page, action='list_recently_added_movies')
    xbmcplugin.endOfDirectory(HANDLE)
    
@with_view_mode('movies')
def list_movies_by_revenue(page=1):
    """Lista filmes ordenados pelas maiores bilheterias."""
    xbmcplugin.setPluginCategory(HANDLE, "Maiores Bilheterias")
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = db.get_movies_by_revenue(page, DEFAULT_ITEMS_PER_PAGE)
    
    for movie in movies:
        _add_movie_item_to_list(movie)
    
    add_next_page_item(movies, page, action='list_movies_by_revenue')
    xbmcplugin.endOfDirectory(HANDLE)