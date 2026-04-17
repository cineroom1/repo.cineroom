# resources/lib/tmdb_api.py
# -*- coding: utf-8 -*-
import requests
import xbmc
import xbmcaddon
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from .db import db

ADDON = xbmcaddon.Addon()
TMDB_API_KEY = ADDON.getSetting("tmdb_api") or "f0b9cd2de131c900f5bb03a0a5776342"
TMDB_LANG = ADDON.getSetting("tmdb_language") or "pt-BR"
BASE_URL = "https://api.themoviedb.org/3"

# --- CONFIGURAÇÕES DE IMAGEM ---
IMG_POSTER = "https://image.tmdb.org/t/p/w500"
IMG_BACKDROP = "https://image.tmdb.org/t/p/original"

# --- SESSION REUTILIZÁVEL (GRANDE MELHORIA) ---
# Reutilizar conexões HTTP é MUITO mais rápido que criar novas a cada request
_session = None

def get_session():
    """Retorna uma sessão HTTP reutilizável com pool de conexões."""
    global _session
    if _session is None:
        _session = requests.Session()
        # Aumenta o pool de conexões para requisições paralelas
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=20,
            max_retries=2,
            pool_block=False
        )
        _session.mount('https://', adapter)
        _session.mount('http://', adapter)
    return _session

# --- MAPAS DE GÊNEROS (Unificados) ---
GENRES_MAP = {
    'movie': {28: "Ação", 12: "Aventura", 16: "Animação", 35: "Comédia", 80: "Crime", 99: "Documentário", 18: "Drama", 10751: "Família", 14: "Fantasia", 36: "História", 27: "Terror", 10402: "Música", 9648: "Mistério", 10749: "Romance", 878: "Ficção científica", 10770: "Cinema TV", 53: "Suspense", 10752: "Guerra", 37: "Faroeste"},
    'tv': {10759: 'Ação e Aventura', 16: 'Animação', 35: 'Comédia', 80: 'Crime', 99: 'Documentário', 18: 'Drama', 10751: 'Família', 10762: 'Infantil', 9648: 'Mistério', 10763: 'Notícias', 10764: 'Reality Show', 10765: 'Ficção Científica e Fantasia', 10766: 'Novela', 10767: 'Talk Show', 10768: 'Guerra e Política', 37: 'Faroeste'}
}

# --- FUNÇÕES INTERNAS (Helpers) ---

def _normalize_item(item, media_type, extra=None):
    """Padroniza os campos para filmes e séries em um único lugar."""
    is_movie = media_type == 'movie'
    extra = extra or {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0}
    
    g_ids = item.get('genre_ids', [])
    g_map = GENRES_MAP.get('movie' if is_movie else 'tv', {})
    g_names = [g_map.get(gid) for gid in g_ids if gid in g_map]

    backdrop = item.get('backdrop_path')
    return {
        'tmdb_id': item.get('id'),
        'imdb_id': extra.get('imdb_id'),
        'title': item.get('title' if is_movie else 'name'),
        'original_title': item.get('original_title' if is_movie else 'original_name'),
        'genres': g_names or [g.get('name') for g in item.get('genres', [])],
        'poster': f"{IMG_POSTER}{item.get('poster_path')}" if item.get('poster_path') else '',
        'backdrop': f"{IMG_BACKDROP}{backdrop}" if backdrop else '',
        'fanart': f"{IMG_BACKDROP}{backdrop}" if backdrop else '',
        'clearlogo': extra.get('clearlogo'),
        'providers': extra.get('providers'),
        'synopsis': item.get('overview', ''),
        'year': (item.get('release_date' if is_movie else 'first_air_date') or '0000')[:4],
        'rating': item.get('vote_average', 0.0),
        'runtime': extra.get('runtime', 0),
        'certification': extra.get('certification', ''),
        'media_type': 'movie' if is_movie else 'tvshow'
    }

def _fetch_tmdb_extra(item, media_type):
    tmdb_id = item.get('id')
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url = f"{BASE_URL}/{endpoint}/{tmdb_id}"
    
    append = "external_ids,images,watch/providers"
    append += ",release_dates" if media_type == 'movie' else ",content_ratings"
    
    params = {
        "api_key": TMDB_API_KEY,
        "append_to_response": append,
        "include_image_language": "en,pt,null"
    }
    try:
        res = get_session().get(url, params=params, timeout=3).json()
        logos = res.get('images', {}).get('logos', [])
        watch = res.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_providers = watch.get('flatrate') or watch.get('buy') or []

        # Certification
        certification = ''
        if media_type == 'movie':
            for r in res.get('release_dates', {}).get('results', []):
                if r.get('iso_3166_1') == 'BR':
                    for rd in r.get('release_dates', []):
                        cert = rd.get('certification', '')
                        if cert:
                            certification = cert
                            break
                    break
        else:
            for r in res.get('content_ratings', {}).get('results', []):
                if r.get('iso_3166_1') == 'BR':
                    certification = r.get('rating', '')
                    break

        return {
            'imdb_id': res.get('external_ids', {}).get('imdb_id', ''),
            'clearlogo': f"{IMG_POSTER}{logos[0]['file_path']}" if logos else '',
            'providers': [p.get('provider_name') for p in br_providers],
            'runtime': res.get('runtime', 0) if media_type == 'movie' else 0,
            'certification': certification,  # ← novo
        }
    except Exception:
        return {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0, 'certification': ''}

def _fetch_extras_batch(items, media_type):
    """
    OTIMIZAÇÃO CRÍTICA: Busca extras em paralelo com melhor controle.
    Usa ThreadPoolExecutor de forma mais eficiente.
    """
    if not items:
        return []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_index = {
            executor.submit(_fetch_tmdb_extra, item, media_type): idx 
            for idx, item in enumerate(items)
        }
        
        # Inicializa lista com None para manter ordem
        results = [None] * len(items)
        
        # Coleta resultados conforme completam (mais rápido)
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result(timeout=5)
            except Exception as e:
                results[idx] = {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0, 'certification': ''}
        
        # Preenche qualquer resultado faltante
        for i in range(len(results)):
            if results[i] is None:
                results[i] = results[i] = {'imdb_id': '', 'clearlogo': '', 'providers': [], 'runtime': 0, 'certification': ''}
        
        return results

# --- FUNÇÕES PÚBLICAS DE LISTAGEM ---

def fetch_trending(media_type='movie', page=1):
    """Função genérica para Trending de filmes ou séries - OTIMIZADA."""
    cache_key = f"trending_{media_type}_p{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached: 
        return cached

    url = f"{BASE_URL}/trending/{media_type}/day"
    params = {"api_key": TMDB_API_KEY, "page": page, "language": TMDB_LANG}
    
    try:
        # USA SESSÃO + TIMEOUT REDUZIDO
        r = get_session().get(url, params=params, timeout=5)
        data = r.json().get('results', [])

        # DEBUG: Verifique se os IDs estão corretos
        
        # OTIMIZAÇÃO: Só busca extras se realmente necessário
        extra_results = _fetch_extras_batch(data, media_type)
        
        # DEBUG: Verifique extras IDs

        # Normaliza o resultado final
        results = []
        for item, extra in zip(data, extra_results):
            # Verificação de segurança
            if item.get('id') and extra.get('imdb_id'):
                # Pode adicionar verificação aqui
                pass
            normalized = _normalize_item(item, media_type, extra)
            results.append(normalized)
            
            # DEBUG: Log para identificar problemas

        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro Trending {media_type}: {str(e)}", xbmc.LOGERROR)
        return []
    
    
def fetch_certification(tmdb_id, media_type='movie'):
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url = f"{BASE_URL}/{endpoint}/{tmdb_id}/release_dates" if media_type == 'movie' \
          else f"{BASE_URL}/{endpoint}/{tmdb_id}/content_ratings"
    params = {"api_key": TMDB_API_KEY}
    try:
        data = get_session().get(url, params=params, timeout=5).json()
        if media_type == 'movie':
            for result in data.get('results', []):
                if result.get('iso_3166_1') == 'BR':
                    for rd in result.get('release_dates', []):
                        cert = rd.get('certification', '')
                        if cert:
                            return cert
        else:
            for result in data.get('results', []):
                if result.get('iso_3166_1') == 'BR':
                    return result.get('rating', '')
    except Exception:
        pass
    return ''

def fetch_recommendations(tmdb_id, media_type='movie', limit=10):
    cache_key = f"rec_{media_type}_{tmdb_id}"
    cached = db.get_tmdb_cache(cache_key, hours=72)
    if cached:
        return cached

    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url = f"{BASE_URL}/{endpoint}/{tmdb_id}/recommendations"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": 1}

    try:
        data = get_session().get(url, params=params, timeout=5).json().get('results', [])[:limit]
        results = [_normalize_item(item, media_type) for item in data]
        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
    except Exception:
        return []


def fetch_similar(tmdb_id, media_type='movie', limit=10):
    cache_key = f"similar_{media_type}_{tmdb_id}"
    cached = db.get_tmdb_cache(cache_key, hours=72)
    if cached:
        return cached

    endpoint = 'movie' if media_type == 'movie' else 'tv'
    url = f"{BASE_URL}/{endpoint}/{tmdb_id}/similar"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": 1}

    try:
        data = get_session().get(url, params=params, timeout=5).json().get('results', [])[:limit]
        results = [_normalize_item(item, media_type) for item in data]
        if results:
            db.save_tmdb_cache(cache_key, results)
        return results
    except Exception:
        return []    

# Wrappers para manter compatibilidade
def fetch_trending_movies(page=1): 
    return fetch_trending('movie', page)

def fetch_trending_tvshows(page=1): 
    return fetch_trending('tv', page)

def search_tmdb(query, page=1):
    """Busca unificada (Filmes e Séries) - OTIMIZADA COM BATCH."""
    url = f"{BASE_URL}/search/multi"
    params = {
        "api_key": TMDB_API_KEY, 
        "query": query, 
        "language": TMDB_LANG, 
        "page": page,
        "include_adult": "false"
    }
    
    try:
        r = get_session().get(url, params=params, timeout=5)
        data = r.json().get('results', [])
        
        # Filtra apenas o que interessa
        filtered = [i for i in data if i.get('media_type') in ['movie', 'tv']]

        # 🔥 SEPARA POR TIPO
        movies = [i for i in filtered if i.get('media_type') == 'movie']
        tvshows = [i for i in filtered if i.get('media_type') == 'tv']
        
        # 🔥 BUSCA EXTRAS EM BATCH SEPARADAMENTE
        movie_extras = _fetch_extras_batch(movies, 'movie')
        tv_extras = _fetch_extras_batch(tvshows, 'tv')
        
        # 🔥 MONTA RESULTADOS NA ORDEM ORIGINAL
        results = []
        movie_idx = 0
        tv_idx = 0
        
        for item in filtered:
            media_type = item.get('media_type')
            
            if media_type == 'movie':
                extra = movie_extras[movie_idx]
                movie_idx += 1
            else:
                extra = tv_extras[tv_idx]
                tv_idx += 1
            
            normalized = _normalize_item(item, media_type, extra)
            results.append(normalized)
        
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB SEARCH] Erro: {str(e)}", xbmc.LOGERROR)
        return []

# --- FUNÇÕES DE POPULARIDADE LOCAL ---

def update_local_popularity():
    """Sincroniza popularidade - OTIMIZADA."""
    _sync_popularity('movie', db.get_all_movie_ids_set(), db.update_popularity_bulk)
    _sync_popularity('tv', db.get_all_tvshow_ids_set(), db.update_tv_popularity_bulk)

def _sync_popularity(media_type, local_ids, update_func):
    """Lógica auxiliar para baixar popularidade - OTIMIZADA."""
    if not local_ids: 
        return
    
    popular_tmdb = []
    
    # OTIMIZAÇÃO: Busca paralela de páginas
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for p in range(1, 4):
            url = f"{BASE_URL}/{media_type}/popular"
            params = {"api_key": TMDB_API_KEY, "page": p}
            futures.append(executor.submit(get_session().get, url, params=params, timeout=5))
        
        for future in as_completed(futures):
            try:
                r = future.result()
                popular_tmdb.extend(r.json().get('results', []))
            except:
                continue

    # Filtra apenas os que temos no banco local
    updates = [
        {'tmdb_id': i['id'], 'popularity': i['popularity']} 
        for i in popular_tmdb if i['id'] in local_ids
    ]

    if updates:
        update_func(updates)

# --- FUNÇÕES DE DETALHES (INDEXER/DB) ---

def get_movie_details(tmdb_id):
    """Busca detalhes completos de um filme - OTIMIZADA."""
    url = f"{BASE_URL}/movie/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY, 
        "language": TMDB_LANG, 
        "append_to_response": "external_ids,images,watch/providers,release_dates",
        "include_image_language": "en,pt,null"
    }
    
    try:
        # USA SESSÃO
        r = get_session().get(url, params=params, timeout=8)
        item = r.json()
        
        logos = item.get('images', {}).get('logos', [])
        watch = item.get('watch/providers', {}).get('results', {}).get('BR', {})
        br_providers = watch.get('flatrate') or watch.get('buy') or []
        
        certification = ''
        for r in item.get('release_dates', {}).get('results', []):
            if r.get('iso_3166_1') == 'BR':
                for rd in r.get('release_dates', []):
                    cert = rd.get('certification', '')
                    if cert:
                        certification = cert
                        break
                break
        
        return {
            'tmdb_id': item.get('id'),
            'imdb_id': item.get('external_ids', {}).get('imdb_id'),
            'title': item.get('title'),
            'original_title': item.get('original_title'),
            'year': item.get('release_date', '0000')[:4],
            'rating': item.get('vote_average', 0.0),
            'poster': f"{IMG_POSTER}{item.get('poster_path')}" if item.get('poster_path') else '',
            'backdrop': f"{IMG_BACKDROP}{item.get('backdrop_path')}" if item.get('backdrop_path') else '',
            'synopsis': item.get('overview', ''),
            'runtime': item.get('runtime', 0),
            'popularity': item.get('popularity', 0.0),
            'genres': [g.get('name') for g in item.get('genres', [])],
            'clearlogo': f"{IMG_POSTER}{logos[0]['file_path']}" if logos else '',
            'providers': [p.get('provider_name') for p in br_providers],
            'certification': certification,
            'popularity_updated': None
        }
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro detalhes filme {tmdb_id}: {str(e)}", xbmc.LOGERROR)
        return None

def fetch_show_details(tmdb_id):
    """Busca detalhes completos de uma série - OTIMIZADA."""
    if not tmdb_id: 
        return None
        
    url = f"{BASE_URL}/tv/{tmdb_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "append_to_response": "external_ids"
    }
    
    try:
        # USA SESSÃO
        response = get_session().get(url, params=params, timeout=8)
        response.raise_for_status()
        show_data = response.json()
        
        return {
            'tmdb_id': show_data.get('id'),
            'imdb_id': show_data.get('external_ids', {}).get('imdb_id'),
            'title': show_data.get('name'),
            'original_title': show_data.get('original_name'),
            'year': show_data.get('first_air_date', '')[:4],
            'poster': f"{IMG_POSTER}{show_data.get('poster_path')}" if show_data.get('poster_path') else '',
            'backdrop': f"{IMG_BACKDROP}{show_data.get('backdrop_path')}" if show_data.get('backdrop_path') else '',
            'synopsis': show_data.get('overview'),
            'popularity': show_data.get('popularity'),
            'rating': show_data.get('vote_average'),
            'certification': show_data.get('content_ratings', {}).get('results', [{}])[0].get('rating', 'N/A'),
            'genres': [g.get('name') for g in show_data.get('genres', [])], 
            'number_of_seasons': show_data.get('number_of_seasons', 0),
            'number_of_episodes': show_data.get('number_of_episodes', 0),
            'status': show_data.get('status'),
            'tagline': show_data.get('tagline'),
            'seasons_data': show_data.get('seasons', [])
        }
    except Exception as e:
        xbmc.log(f"[TMDB API ERROR] Falha ao buscar detalhes da série {tmdb_id}: {e}", xbmc.LOGERROR)
        return None

def fetch_tvshows_list(list_type, page=1):
    """Busca listas simples de séries - OTIMIZADA."""
    endpoint_map = {
        'popular': 'tv/popular',
        'top_rated': 'tv/top_rated',
        'on_the_air': 'tv/on_the_air',
        'trending': 'trending/tv/week' 
    }
    endpoint = endpoint_map.get(list_type, 'tv/popular')
    url = f"{BASE_URL}/{endpoint}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": page}
    
    try:
        # USA SESSÃO
        response = get_session().get(url, params=params, timeout=5)
        data = response.json()
        
        normalized_shows = []
        for show in data.get('results', []):
            g_ids = show.get('genre_ids', [])
            g_names = [GENRES_MAP['tv'].get(gid, 'Desconhecido') for gid in g_ids]
            
            normalized_shows.append({
                'tmdb_id': show.get('id'),
                'title': show.get('name'),
                'original_title': show.get('original_name'),
                'year': show.get('first_air_date', '')[:4],
                'poster': f"{IMG_POSTER}{show.get('poster_path')}" if show.get('poster_path') else '',
                'backdrop': f"{IMG_BACKDROP}{show.get('backdrop_path')}" if show.get('backdrop_path') else '',
                'synopsis': show.get('overview'),
                'popularity': show.get('popularity'),
                'rating': show.get('vote_average'),
                'genres': g_names
            })
        return normalized_shows
        
    except Exception as e:
        xbmc.log(f"[TMDB API ERROR] Falha ao buscar lista {list_type}: {e}", xbmc.LOGERROR)
        return []

@lru_cache(maxsize=128)
def get_collection_art(collection_name):
    """Busca arte de coleção - OTIMIZADA com CACHE."""
    url = f"{BASE_URL}/search/collection"
    params = {"api_key": TMDB_API_KEY, "query": collection_name, "language": TMDB_LANG}
    
    try:
        r = get_session().get(url, params=params, timeout=3)
        results = r.json().get('results', [])
        if results:
            poster = results[0].get('poster_path')
            backdrop = results[0].get('backdrop_path')
            return {
                'poster': f"{IMG_BACKDROP}{poster}" if poster else '',
                'backdrop': f"{IMG_BACKDROP}{backdrop}" if backdrop else ''
            }
    except:
        pass
    return None

def fetch_popular_movies_pages(pages=5):
    """Busca páginas populares - OTIMIZADA."""
    all_movies = []
    
    # OTIMIZAÇÃO: Busca paralela
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for page in range(1, pages + 1):
            url = f"{BASE_URL}/movie/popular"
            params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG, "page": page}
            futures.append(executor.submit(get_session().get, url, params=params, timeout=5))
        
        for future in as_completed(futures):
            try:
                r = future.result()
                data = r.json().get('results', [])
                for item in data:
                    all_movies.append({
                        'tmdb_id': item.get('id'),
                        'title': item.get('title'),
                        'original_title': item.get('original_title'),
                        'year': item.get('release_date', '0000')[:4],
                        'rating': item.get('vote_average'),
                        'poster': f"{IMG_POSTER}{item.get('poster_path')}",
                        'backdrop': f"{IMG_BACKDROP}{item.get('backdrop_path')}",
                        'synopsis': item.get('overview'),
                        'popularity': item.get('popularity'),
                        'popularity_updated': None
                    })
            except:
                continue
                
    return all_movies

def get_tvshow_seasons(tmdb_id):
    """Busca temporadas de uma série - OTIMIZADA."""
    if not tmdb_id:
        return []
    
    url = f"{BASE_URL}/tv/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        seasons = data.get('seasons', [])
        
        formatted_seasons = []
        for season in seasons:
            formatted_seasons.append({
                'season_number': season.get('season_number', 0),
                'name': season.get('name', ''),
                'overview': season.get('overview', ''),
                'poster_path': season.get('poster_path', ''),
                'air_date': season.get('air_date', ''),
                'episode_count': season.get('episode_count', 0),
                'vote_average': season.get('vote_average', 0.0)
            })
        
        return formatted_seasons
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro ao buscar temporadas {tmdb_id}: {e}", xbmc.LOGERROR)
        return []

def get_season_episodes(tmdb_id, season_number):
    """Busca episódios de uma temporada - OTIMIZADA."""
    if not tmdb_id or season_number is None:
        return []
    
    url = f"{BASE_URL}/tv/{tmdb_id}/season/{season_number}"
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANG}
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        episodes = data.get('episodes', [])
        
        formatted_episodes = []
        for episode in episodes:
            formatted_episodes.append({
                'episode_number': episode.get('episode_number', 0),
                'name': episode.get('name', ''),
                'overview': episode.get('overview', ''),
                'still_path': episode.get('still_path', ''),
                'air_date': episode.get('air_date', ''),
                'vote_average': episode.get('vote_average', 0.0),
                'runtime': episode.get('runtime', 0)
            })
        
        return formatted_episodes
        
    except Exception as e:
        xbmc.log(f"[TMDB API] Erro ao buscar episódios {tmdb_id} S{season_number}: {e}", xbmc.LOGERROR)
        return []
    
def fetch_movies_by_keywords(keyword_ids, genres=None, page=1):
    """
    Busca filmes por keywords (COM INFO DE PAGINAÇÃO)
    """
    if not keyword_ids:
        return []
    
    cache_key = f"keywords_movies_{','.join(map(str, keyword_ids))}_{','.join(map(str, genres or []))}_{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached:
        return cached
    
    url = f"{BASE_URL}/discover/movie"
    
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "page": page,
        "sort_by": "popularity.desc",
        "vote_count.gte": 100,
        "with_keywords": "|".join(map(str, keyword_ids)),
        "include_adult": False
    }
    
    if genres:
        params["with_genres"] = ",".join(map(str, genres))
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        json_data = response.json()  # ✅ Pega o JSON completo
        data = json_data.get('results', [])
        
        # ✅ PEGA INFO DE PÁGINAS
        total_pages = json_data.get('total_pages', 1)
        
        extra_results = _fetch_extras_batch(data, 'movie')
        
        results = []
        for item, extra in zip(data, extra_results):
            normalized = _normalize_item(item, 'movie', extra)
            results.append(normalized)
        
        # ✅ ADICIONA INFO DE PÁGINAS AOS RESULTADOS
        # Hack: adiciona como propriedade do primeiro item
        if results:
            results[0]['_has_next_page'] = (page < total_pages)
            db.save_tmdb_cache(cache_key, results)
        
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB] Erro busca keywords: {e}", xbmc.LOGERROR)
        return []

def fetch_tvshows_by_keywords(keyword_ids, genres=None, page=1):
    """
    Busca séries por keywords (COM INFO DE PAGINAÇÃO)
    """
    if not keyword_ids:
        return []
    
    cache_key = f"keywords_tv_{','.join(map(str, keyword_ids))}_{','.join(map(str, genres or []))}_{page}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached:
        return cached
    
    url = f"{BASE_URL}/discover/tv"
    
    params = {
        "api_key": TMDB_API_KEY,
        "language": TMDB_LANG,
        "page": page,
        "sort_by": "popularity.desc",
        "vote_count.gte": 50,
        "with_keywords": "|".join(map(str, keyword_ids)),
        "include_adult": False
    }
    
    if genres:
        params["with_genres"] = ",".join(map(str, genres))
    
    try:
        response = get_session().get(url, params=params, timeout=5)
        json_data = response.json()
        data = json_data.get('results', [])
        
        # ✅ PEGA INFO DE PÁGINAS
        total_pages = json_data.get('total_pages', 1)
        
        extra_results = _fetch_extras_batch(data, 'tv')
        
        results = []
        for item, extra in zip(data, extra_results):
            normalized = _normalize_item(item, 'tv', extra)
            results.append(normalized)
        
        # ✅ ADICIONA INFO DE PÁGINAS
        if results:
            results[0]['_has_next_page'] = (page < total_pages)
            db.save_tmdb_cache(cache_key, results)
        
        return results
        
    except Exception as e:
        xbmc.log(f"[TMDB] Erro busca keywords séries: {e}", xbmc.LOGERROR)
        return []

def fetch_person_details(tmdb_person_id):
    """
    Busca bio, foto e filmografia do ator via TMDB.
    Usa api_cache do DB (TTL 24h) para não repetir chamadas.
    Retorna dict com: name, biography, birthday, birthplace,
                      profile, known_for, credits (lista de filmes+séries)
    """
    cache_key = f"person:{tmdb_person_id}"
    cached = db.get_tmdb_cache(cache_key, hours=24)
    if cached:
        return cached

    try:
        url = f"{BASE_URL}/person/{tmdb_person_id}"
        params = {
            "api_key": TMDB_API_KEY,
            "language": TMDB_LANG,
            "append_to_response": "combined_credits",
        }
        r = get_session().get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        # Filmografia: filmes + séries ordenados por data (mais recentes primeiro)
        cast_credits = data.get("combined_credits", {}).get("cast", [])

        credits = []
        seen = set()
        for c in cast_credits:
            mid = c.get("id")
            if not mid or mid in seen:
                continue
            seen.add(mid)

            media_type = c.get("media_type", "movie")
            title = c.get("title") or c.get("name") or ""
            poster = c.get("poster_path")
            date = c.get("release_date") or c.get("first_air_date") or ""
            character = c.get("character", "")

            # Filtra entradas sem título ou poster
            if not title or not poster:
                continue

            credits.append({
                "tmdb_id": mid,
                "title": title,
                "character": character,
                "poster": f"{IMG_POSTER}{poster}",
                "year": date[:4] if date else "",
                "media_type": "tvshow" if media_type == "tv" else "movie",
                "popularity": c.get("popularity", 0),
            })

        # Ordena por popularidade (proxy mais confiável que data no TMDB)
        credits.sort(key=lambda x: x.get("popularity", 0), reverse=True)

        result = {
            "tmdb_person_id": tmdb_person_id,
            "name": data.get("name", ""),
            "biography": data.get("biography", ""),
            "birthday": data.get("birthday") or "",
            "birthplace": data.get("place_of_birth") or "",
            "known_for": data.get("known_for_department", "Acting"),
            "profile": f"https://image.tmdb.org/t/p/w300{data['profile_path']}"
                       if data.get("profile_path") else "",
            "credits": credits,
            "credits_count": len(credits),
        }

        db.save_tmdb_cache(cache_key, result)
        return result

    except Exception as e:
        xbmc.log(f"[TMDB] Erro fetch_person_details({tmdb_person_id}): {e}", xbmc.LOGERROR)
        return None