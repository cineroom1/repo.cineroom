# -*- coding: utf-8 -*-
# Em: resources/lib/movies.py

import json
import xbmc
import os
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode

from .utils import create_video_item_with_library, with_view_mode
from .content_filter import get_content_filter


# --- Configurações gerais ---
ADDON = xbmcaddon.Addon()
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
        return min(base_pages, 20)
    return base_pages

def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"

def _parse_json_field(value, fallback=None):
    """
    Garante que campos vindos do SQLite como string JSON sejam convertidos
    de volta para lista/dict Python.

    O banco armazena genres/streams/providers como json.dumps(...), então ao
    ler com _execute_query eles chegam como str em algumas consultas (ex:
    get_movie_by_id) e como list em outras (quando base_db faz o parse).
    Esta função normaliza os dois casos.
    """
    if fallback is None:
        fallback = []
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, (list, dict)) else fallback
        except (ValueError, TypeError):
            pass
    return fallback


def _create_movie_item_tuple(movie, quality_filter=None, track_on_click=False):
    """
    Cria a tupla padrão para todos os dispositivos usando a função completa.

    Args:
        track_on_click: Quando True (usado em search.py), embute track=1 na URL
                        para que o router registre o clique no Supabase apenas
                        quando o usuário escolher um resultado da busca.
    """
    li = create_video_item_with_library(movie, media_type='movie')

    if ADDON.getSettingBool("movie.enable_details"):

        genres    = _parse_json_field(movie.get('genres'), fallback=[])
        streams   = _parse_json_field(movie.get('streams'), fallback=[])
        providers = _parse_json_field(movie.get('providers'), fallback=[])

        item_data = {
            "title": movie.get('title', ''),
            "original_title": movie.get('original_title', ''),
            "clearlogo": movie.get('clearlogo', ''),
            "poster": movie.get('poster', ''),
            "synopsis": movie.get('synopsis', ''),
            "backdrop": movie.get('backdrop', ''),
            "year": movie.get('year', 0),
            "runtime": movie.get('runtime', 0),
            "collection": movie.get('collection', ''),
            "certification": movie.get('certification', ''),
            "rating": float(movie.get('rating', 0) or 0),
            "genre": ', '.join(str(g) for g in genres),
            "tmdb_id": movie.get('tmdb_id'),
            "imdb_id": movie.get('imdb_id', ''),
            "media_type": 'movie',
            "providers": providers,
            "streams": streams,
            "popularity_updated": movie.get('popularity_updated', ''),
            "quality_filter": quality_filter,
        }
        extra = {"track": "1"} if track_on_click else {}
        url = get_url(action='show_details', data=json.dumps(item_data, separators=(',', ':')), **extra)
    else:
        # Play direto
        extra = {"track": "1"} if track_on_click else {}
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
            poster=movie.get('poster', ''),
            quality_filter=quality_filter or '',
            **extra,
        )

    return (url, li, False)


def _get_cached_listitem(movie):
    """Retorna um ListItem com todas as propriedades necessárias, garantindo strings."""
    cache_key = f"{movie.get('tmdb_id', '')}_{movie.get('year', '')}"
    
    if cache_key in _LISTITEM_CACHE:
        return _LISTITEM_CACHE[cache_key]
    
    li = xbmcgui.ListItem(label=movie.get('title', ''))

    # Artes — aplica qualidade configurada pelo usuário
    from .utils import get_image_resolutions, scale_tmdb
    res = get_image_resolutions()
    _poster   = scale_tmdb(movie.get('poster', ''),   res['poster'])
    _backdrop = scale_tmdb(movie.get('fanart', movie.get('backdrop', '')), res['backdrop'])
    li.setArt({
        'thumb':     _poster,
        'fanart':    _backdrop,
        'clearlogo': movie.get('clearlogo', '') or '',
        'poster':    _poster,
        'backdrop':  _backdrop
    })
    
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

    if len(_LISTITEM_CACHE) < _MAX_CACHE_SIZE:
        _LISTITEM_CACHE[cache_key] = li
    
    return li

# --- MENUS ---

def show_movies_menu(menu_structure):
    """Cria e exibe o menu da seção 'Filmes'."""
    HANDLE = int(sys.argv[1])
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
    HANDLE = int(sys.argv[1])
    items_per_page = get_items_per_page()
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
    HANDLE = int(sys.argv[1])
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
    HANDLE = int(sys.argv[1])
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
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, "Coleções")
    xbmcplugin.setContent(HANDLE, 'movies')

    items_per_page = get_items_per_page()
    collections_data = db.get_all_collections(page, items_per_page)

    if not collections_data:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    total_items = len(collections_data)

    pDialog = xbmcgui.DialogProgressBG()
    pDialog.create("CR Lite", "Buscando capas das coleções, aguarde...")

    def process_collection(col):
        name   = col.get('collection')
        poster = col.get('poster', '')
        fanart = col.get('backdrop', '')

        meta = db.get_cached_collection_meta(name)
        if not meta:
            meta = get_collection_art(name)
            if meta:
                db.save_collection_meta(name, meta['poster'], meta['backdrop'])

        poster = meta['poster']   if meta and meta.get('poster')   else poster
        fanart = meta['backdrop'] if meta and meta.get('backdrop') else fanart

        li = xbmcgui.ListItem(label=name)

        from .utils import get_image_resolutions, scale_tmdb
        res = get_image_resolutions()

        li.setArt({
            'poster': scale_tmdb(poster, res['poster']),
            'icon':   scale_tmdb(poster, res['poster']),
            'thumb':  scale_tmdb(poster, res['poster']),
            'fanart': scale_tmdb(fanart, res['backdrop'])
        })

        li.setInfo('video', {
            'mediatype': 'set',
            'title':     name,
            'sorttitle': name,
            'plot':      f'Coleção {name}'
        })
        li.setProperty('IsPlayable', 'false')

        url = get_url(action='list_movies_by_collection', collection=name)
        return (url, li, True)

    items = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_collection, col): col for col in collections_data}
        for i, future in enumerate(as_completed(futures)):
            try:
                items.append(future.result())
            except Exception as e:
                xbmc.log(f'[CineRoom] Erro ao processar coleção: {e}', xbmc.LOGWARNING)
            percent = int((i + 1) * 100 / total_items)
            pDialog.update(percent, message=f"Processando: {total_items} coleções...")

    pDialog.close()

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))
    add_next_page_item(collections_data, page, action='list_collections')
    xbmcplugin.endOfDirectory(HANDLE)

# --- LISTAGENS DE FILMES ---

@with_view_mode('movies')
def list_movies_by_genre(genre, page=1):
    from .db import db
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, genre)
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()
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
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, str(year))
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()
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
    
    HANDLE = int(sys.argv[1])
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
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, "Melhores Avaliações")
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()
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
    
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, "Mais Populares")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    items_per_page = get_items_per_page()
    page = int(page)
    
    # 1. Tenta buscar do banco local
    movies = db.get_movies_by_popularity(page, items_per_page)

    if not movies and page == 1:
        from .tmdb_api import fetch_popular_movies
        movies = fetch_popular_movies(page)

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
    
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, "4K")
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()
    movies = db.get_4k_movies(page, items_per_page)
    
    
    
    items_to_add = []
    for movie in movies:
        items_to_add.append(_create_movie_item_tuple(movie, quality_filter='4k'))

    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
    
    add_next_page_item(movies, page, action='list_4k_movies')
    xbmcplugin.endOfDirectory(HANDLE)
    
@with_view_mode('movies')
def list_recently_added_movies(page=1):
    from .db import db
    
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, "Adicionados Recentemente")
    xbmcplugin.setContent(HANDLE, 'movies')
    items_per_page = get_items_per_page()
    
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
    
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    """Lista filmes ordenados pelas maiores bilheterias."""
    HANDLE = int(sys.argv[1])
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
    
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)
    
    HANDLE = int(sys.argv[1])
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
    
    content_filter = get_content_filter()
    db.set_content_filter(content_filter) 
    
    HANDLE = int(sys.argv[1])
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
    
# Adicione estas funções no movies.py

@with_view_mode('genres', is_menu=True)
def list_movie_themes():
    """Menu de categorias temáticas de filmes"""
    from .keywords import get_all_theme_categories
    
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, 'Temas')
    xbmcplugin.setContent(HANDLE, 'genres')
    
    categories = get_all_theme_categories()
    
    for cat in categories:
        li = xbmcgui.ListItem(label=cat['name'])
        li.setInfo('video', {'plot': cat['description']})
        
        url = get_url(
            action='list_movies_by_theme',
            theme=cat['slug']
        )
        
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(HANDLE)

@with_view_mode('movies')
def list_movies_by_theme(theme, page=1):
    """Lista filmes de uma categoria temática — filtro 100% local, zero API."""
    from .keywords import get_theme_config, get_theme_keywords
    from .db import db

    config = get_theme_config(theme)
    if not config:
        xbmcgui.Dialog().ok("Erro", "Categoria não encontrada")
        return

    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, config['name'])
    xbmcplugin.setContent(HANDLE, 'movies')

    keyword_list = get_theme_keywords(theme)
    if not keyword_list:
        xbmcgui.Dialog().ok("Erro", f"Sem keywords configuradas para '{config['name']}'")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items_per_page = get_items_per_page()
    page = int(page)
    offset = (page - 1) * items_per_page

    movies = db.get_movies_by_keywords(
        keyword_list,
        items_per_page,
        offset,
    )
    

    if not movies:
        xbmcgui.Dialog().ok("Aviso", f"Nenhum filme encontrado em '{config['name']}'")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items_to_add = [_create_movie_item_tuple(m) for m in movies]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))

    if len(movies) == items_per_page:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="Próxima Página")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        next_url = get_url(action='list_movies_by_theme', theme=theme, page=page + 1)
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li_next, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


# Faixas de nota — definição centralizada
RATING_CATEGORIES = [
    {'label': 'Obra-prima',  'slug': 'masterpiece', 'min': 9.0, 'max': 10.1, 'plot': 'Filmes com nota 9.0 ou superior.'},
    {'label': 'Excelente',   'slug': 'excellent',    'min': 8.0, 'max': 9.0,  'plot': 'Filmes com nota entre 8.0 e 8.9.'},
    {'label': 'Muito Bom',   'slug': 'verygood',     'min': 7.0, 'max': 8.0,  'plot': 'Filmes com nota entre 7.0 e 7.9.'},
    {'label': 'Regular',     'slug': 'average',      'min': 5.0, 'max': 7.0,  'plot': 'Filmes com nota entre 5.0 e 6.9.'},
]

@with_view_mode('genres', is_menu=True)
def list_rating_categories_movies():
    """Menu de faixas de nota para filmes."""
    
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, 'Por Nota')
    xbmcplugin.setContent(HANDLE, 'genres')

    for cat in RATING_CATEGORIES:
        li = xbmcgui.ListItem(label=cat['label'])
        li.setInfo('video', {'plot': cat['plot']})
        url = get_url(action='list_movies_by_rating_category', slug=cat['slug'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('movies')
def list_movies_by_rating_category(slug, page=1):
    """Lista filmes de uma faixa de nota específica."""
    from .db import db

    cat = next((c for c in RATING_CATEGORIES if c['slug'] == slug), None)
    if not cat:
        xbmcgui.Dialog().ok('Erro', 'Categoria de nota não encontrada.')
        return

    content_filter = get_content_filter()
    db.set_content_filter(content_filter)

    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, cat['label'])
    xbmcplugin.setContent(HANDLE, 'movies')

    items_per_page = get_items_per_page()
    movies = db.get_movies_by_rating_range(
        min_rating=cat['min'],
        max_rating=cat['max'],
        min_votes=100,
        page=int(page),
        page_size=items_per_page,
    )

    if not movies:
        xbmcgui.Dialog().notification(cat['label'], 'Nenhum filme encontrado.', xbmcgui.NOTIFICATION_INFO, 3000)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    items_to_add = [_create_movie_item_tuple(m) for m in movies]
    xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))

    has_next = movies[0].get('_has_next_page', False)
    if has_next:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label='Próxima Página')
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        next_url = get_url(action='list_movies_by_rating_category', slug=slug, page=int(page) + 1)
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li_next, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('movies')
def list_most_searched_movies(page=1):
    """
    Lista filmes mais buscados baseado nas queries populares do Supabase.
    """
    from .trending_tracker import get_popular_queries_from_supabase
    from .db.db import db_instance as db

    page = int(page)
    HANDLE = int(sys.argv[1])
    xbmcplugin.setPluginCategory(HANDLE, 'Mais Buscados')
    xbmcplugin.setContent(HANDLE, 'movies')

    popular_clicks = get_popular_queries_from_supabase(limit=50, min_count=2)
    popular_clicks = [c for c in popular_clicks if c.get('content_type') == 'movie']

    if not popular_clicks:
        xbmcgui.Dialog().notification(
            "Mais Buscados",
            "Nenhum dado disponível ainda",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        xbmcplugin.endOfDirectory(HANDLE)
        return

    all_movies = []
    for click in popular_clicks:
        tmdb_id    = click.get('tmdb_id')
        view_count = click.get('view_count', 0)
        try:
            movie = db.get_movie_by_id(tmdb_id)
            if movie:
                all_movies.append((movie, view_count))
        except Exception:
            pass

    items_per_page = 20
    start      = (page - 1) * items_per_page
    end        = start + items_per_page
    page_movies = all_movies[start:end]

    items = []
    for movie_data, search_count in page_movies:
        try:
            url, li, is_folder = _create_movie_item_tuple(movie_data)
            title = movie_data.get('title', '')
            li.setLabel(f"{title} [{search_count}🔥]")
            items.append((url, li, is_folder))
        except Exception:
            continue

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))

    # Passa a lista (page_movies), não len() dela
    if len(all_movies) > end:
        add_next_page_item(page_movies, page, action='list_most_searched_movies')

    xbmcplugin.endOfDirectory(HANDLE)
