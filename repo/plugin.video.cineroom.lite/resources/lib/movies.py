# -*- coding: utf-8 -*-
# Em: resources/lib/movies.py - VERSÃO OTIMIZADA E FUNCIONAL

import json
import xbmc
import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode

from .utils import create_video_item_with_library, with_view_mode


# --- Configurações gerais ---
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')

# --- Cache e Detecção de Dispositivo ---
_LISTITEM_CACHE = {}
_MAX_CACHE_SIZE = 30

def is_slow_device():
    """Detecta dispositivos de baixo desempenho (MXQ, TCL P8M, etc)"""
    model = xbmc.getInfoLabel('System.Model').lower()
    slow_models = ['mxq', 'p8m', 'x96', 'h96', 'tanix', 'tx3', 't95', 'beelink', 'mecool']
    return any(dev in model for dev in slow_models)

def get_items_per_page():
    """Retorna número de itens por página baseado no dispositivo"""
    base_pages = int(ADDON.getSetting("pages"))
    if is_slow_device():
        return min(base_pages, 20)  # Máximo 20 em dispositivos fracos
    return base_pages

def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"

def _create_movie_item_tuple(movie):
    """Cria a tupla padrão para todos os dispositivos usando a função completa"""
    # li já vem com os IDs corretos no setInfo se você atualizou o utils.py
    li = create_video_item_with_library(movie, media_type='movie')
    
    # Lógica do Dialog de Detalhes
    if ADDON.getSettingBool("movie.enable_details"):
        item_data = {
            "title": movie.get('title', ''),
            "original_title": movie.get('original_title', ''), # ADICIONADO
            "clearlogo": movie.get('clearlogo', ''),
            "poster": movie.get('poster', ''),
            "synopsis": movie.get('synopsis', ''),
            "backdrop": movie.get('backdrop', ''),
            "year": movie.get('year', 0),
            "runtime": movie.get('runtime', 0),
            "collection": movie.get('collection', ''),
            "rating": float(movie.get('rating', 0)),
            "genre": ', '.join(movie.get('genres', [])),
            "tmdb_id": movie.get('tmdb_id'),
            "imdb_id": movie.get('imdb_id', ''), # ESSENCIAL
            "media_type": 'movie',
            "providers": json.dumps(movie.get('providers', [])) if movie.get('providers') else '[]',
            "streams": movie.get('streams', []),
            "popularity_updated": movie.get('popularity_updated', '') 
        }
        # Separadores compactos para economizar memória na URL
        url = get_url(action='show_details', data=json.dumps(item_data, separators=(',', ':')))
    else:
        # Play direto
        url = get_url(
            action='find_sources',
            tmdb_id=str(movie.get('tmdb_id', '')),
            imdb_id=movie.get('imdb_id', ''),
            media_type='movie',
            title=movie.get('title', ''),
            year=movie.get('year', ''),
            original_title=movie.get('original_title', ''),
            clearlogo=movie.get('clearlogo', ''),
            fanart=movie.get('fanart', ''),
            backdrop=movie.get('backdrop', ''),
            poster=movie.get('poster', '')
        )
    
    return (url, li, False)


def _get_cached_listitem(movie):
    """Retorna um ListItem com todas as propriedades necessárias, garantindo strings."""
    cache_key = f"{movie.get('tmdb_id', '')}_{movie.get('year', '')}"
    
    if cache_key in _LISTITEM_CACHE:
        return _LISTITEM_CACHE[cache_key]
    
    li = xbmcgui.ListItem(label=movie.get('title', ''))

    # Artes
    li.setArt({
        'thumb': movie.get('poster', '') or '',
        'fanart': movie.get('fanart', movie.get('backdrop', '')) or '',
        'clearlogo': movie.get('clearlogo', '') or '',
        'poster': movie.get('poster', '') or '',
        'backdrop': movie.get('backdrop', '') or ''
    })
    
    # Propriedades internas — todas convertidas para str
    li.setProperty('tmdb_id', str(movie.get('tmdb_id', '')))
    li.setProperty('imdb_id', str(movie.get('imdb_id', '')))
    li.setProperty('media_type', str(movie.get('media_type', 'movie')))
    li.setProperty('title', str(movie.get('title', '')))
    li.setProperty('original_title', str(movie.get('original_title', '')))
    li.setProperty('clearlogo', str(movie.get('clearlogo', '')))
    li.setProperty('fanart', str(movie.get('fanart', movie.get('backdrop', ''))))
    li.setProperty('backdrop', str(movie.get('backdrop', '')))
    li.setProperty('poster', str(movie.get('poster', '')))
    li.setProperty('synopsis', str(movie.get('synopsis', '')))
    li.setProperty('year', str(movie.get('year', '0000')))
    li.setProperty('rating', str(movie.get('rating', 0.0)))
    li.setProperty('runtime', str(movie.get('runtime', 0)))
    li.setProperty('genres', ",".join(map(str, movie.get('genres', []))))
    li.setProperty('providers', ",".join(map(str, movie.get('providers', []))))
    li.setProperty('popularity_updated', str(movie.get('popularity_updated', '')))

    # Salva no cache
    if len(_LISTITEM_CACHE) < _MAX_CACHE_SIZE:
        _LISTITEM_CACHE[cache_key] = li
    
    return li

# --- MENUS ---

def show_movies_menu(menu_structure):
    """Cria e exibe o menu da seção 'Filmes'."""
    xbmcplugin.setPluginCategory(HANDLE, 'Filmes')
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
    items_per_page = get_items_per_page()  # ✅ USA função dinâmica
    if len(items_on_current_page) == items_per_page:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="Próxima Página")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        
        next_page_args = kwargs.copy()
        next_page_args['page'] = current_page + 1
        
        next_page_url = get_url(**next_page_args)
        xbmcplugin.addDirectoryItem(HANDLE, next_page_url, li_next, isFolder=True)

@with_view_mode('genres', is_menu=True)
def list_genres():
    from .db import db
    """Cria e exibe a lista de Gêneros de Filmes."""
    xbmcplugin.setPluginCategory(HANDLE, 'Gêneros')
    xbmcplugin.setContent(HANDLE, 'genres')
    genres_from_db = db.get_all_unique_genres()
    
    for genre_name in genres_from_db:
        li = xbmcgui.ListItem(label=genre_name)
        url = get_url(action='list_movies_by_genre', genre=genre_name)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('years', is_menu=True)
def list_years():
    from .db import db
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
def list_collections(page=1):
    from .db import db
    from .tmdb_api import get_collection_art
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    page = int(page)
    xbmcplugin.setPluginCategory(HANDLE, "Coleções")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    items_per_page = get_items_per_page()
    collections_data = db.get_all_collections(page, items_per_page)
    total_items = len(collections_data)

    if not collections_data:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Inicia o Diálogo de Progresso em Segundo Plano
    pDialog = xbmcgui.DialogProgressBG()
    pDialog.create("CR Lite", "Buscando capas das coleções, aguarde...")

    def process_collection(col):
        name = col.get('collection')
        meta = db.get_cached_collection_meta(name)
        
        if not meta:
            meta = get_collection_art(name)
            if meta:
                db.save_collection_meta(name, meta['poster'], meta['backdrop'])
        
        poster = meta['poster'] if meta and meta['poster'] else col.get('poster')
        fanart = meta['backdrop'] if meta and meta['backdrop'] else col.get('backdrop')
        
        li = xbmcgui.ListItem(label=name)
        
        from .utils import get_image_resolutions, scale_tmdb
        res = get_image_resolutions()
        
        li.setArt({
            'poster': scale_tmdb(poster, res['poster']),
            'icon': scale_tmdb(poster, res['poster']),
            'thumb': scale_tmdb(poster, res['poster']),
            'fanart': scale_tmdb(fanart, res['backdrop'])
        })
        
        url = get_url(action='list_movies_by_collection', collection=name)
        return (url, li, True)

    items = []
    # Usamos as_completed para atualizar a barra de progresso conforme as threads terminam
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_collection, col): col for col in collections_data}
        
        for i, future in enumerate(as_completed(futures)):
            items.append(future.result())
            # Atualiza a porcentagem (0 a 100)
            percent = int((i + 1) * 100 / total_items)
            pDialog.update(percent, message=f"Processando: {total_items} coleções...")

    # Fecha o diálogo de progresso
    pDialog.close()

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    add_next_page_item(collections_data, page, action='list_collections')
    xbmcplugin.endOfDirectory(HANDLE)

# --- LISTAGENS DE FILMES ---

@with_view_mode('movies')
def list_movies_by_genre(genre, page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, genre)
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()  # ✅ CORREÇÃO
    movies = db.get_movies_by_genre(genre, page, items_per_page)
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(movies, page, action='list_movies_by_genre', genre=genre)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_year(year, page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, str(year))
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()  # ✅ CORREÇÃO
    movies = db.get_movies_by_year(year, page, items_per_page)
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(movies, page, action='list_movies_by_year', year=year)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_collection(collection_name, page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, collection_name)
    xbmcplugin.setContent(HANDLE, 'movies')
    movies = db.get_movies_by_collection(collection_name)
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(movies, page, action='list_movies_by_collection', collection=collection_name)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_rating(page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, "Melhores Avaliações")
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()  # ✅ CORREÇÃO
    movies = db.get_movies_by_rating(page, items_per_page)
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(movies, page, action='list_movies_by_rating')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_popularity(page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, "Mais Populares")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    items_per_page = get_items_per_page()
    page = int(page)
    
    # 1. Tenta buscar do banco local
    movies = db.get_movies_by_popularity(page, items_per_page)

    # 2. Se o banco estiver vazio (ex: primeira instalação), busca direto da API para não ficar em branco
    if not movies and page == 1:
        from .tmdb_api import fetch_popular_movies # Supondo que você tenha essa função
        movies = fetch_popular_movies(page)
        # Opcional: Salva no banco para a próxima vez ser instantâneo
        if movies:
            db.add_movies_bulk(movies)

    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(movies, page, action='list_movies_by_popularity')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_4k_movies(page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, "Filmes em 4K")
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()  # ✅ CORREÇÃO
    movies = db.get_4k_movies(page, items_per_page)
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(movies, page, action='list_4k_movies')
    xbmcplugin.endOfDirectory(HANDLE)
    
@with_view_mode('movies')
def list_recently_added_movies(page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, "Adicionados Recentemente")
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()  # ✅ CORREÇÃO
    movies = db.get_recently_added_movies(page, items_per_page)

    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))

    add_next_page_item(movies, page, action='list_recently_added_movies')
    xbmcplugin.endOfDirectory(HANDLE)
    
@with_view_mode('movies')
def list_movies_by_revenue(page=1):
    from .db import db
    """Lista filmes ordenados pelas maiores bilheterias."""
    xbmcplugin.setPluginCategory(HANDLE, "Maiores Bilheterias")
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()  # ✅ CORREÇÃO
    movies = db.get_movies_by_revenue(page, items_per_page)
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(movies, page, action='list_movies_by_revenue')
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_provider(provider, page=1):
    from .db import db
    xbmcplugin.setPluginCategory(HANDLE, f"{provider}")
    xbmcplugin.setContent(HANDLE, 'movies')

    items_per_page = get_items_per_page()
    movies = db.get_movies_by_provider(provider, page, items_per_page)

    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie))

    if items_to_add:
        xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))

    add_next_page_item(movies, page, action='list_movies_by_provider', provider=provider)
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_trending_movies(page=1):
    from .db import db
    from .tmdb_api import fetch_trending_movies
    xbmcplugin.setPluginCategory(HANDLE, "Em Alta")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    # Busca os dados da API
    movies = fetch_trending_movies(page)

    items_to_add = []
    for m in movies:
        items_to_add.append(_create_movie_item_tuple(m))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    add_next_page_item(movies, page, action='list_trending_movies')
    xbmcplugin.endOfDirectory(HANDLE)