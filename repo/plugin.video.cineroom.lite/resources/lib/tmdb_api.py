# resources/lib/tmdb_api.py

import requests
import xbmc
import json

# Lembre-se de definir esta chave em um lugar seguro ou nas configurações do addon
TMDB_API_KEY = "f0b9cd2de131c900f5bb03a0a5776342" 

# --- MAPA DE GÊNEROS (Necessário para listas rápidas que só retornam IDs) ---
# O TMDB retorna IDs de gênero inteiros nas chamadas de lista (ex: /tv/popular).
TV_GENRES_MAP = {
    10759: 'Ação e Aventura',
    16: 'Animação',
    35: 'Comédia',
    80: 'Crime',
    99: 'Documentário',
    18: 'Drama',
    10751: 'Família',
    10762: 'Infantil',
    9648: 'Mistério',
    10763: 'Notícias',
    10764: 'Reality Show',
    10765: 'Ficção Científica e Fantasia',
    10766: 'Novela',
    10767: 'Talk Show',
    10768: 'Guerra e Política',
    37: 'Faroeste',
    10770: 'Filme para TV',
    # Adicione mais conforme necessário
}


def fetch_tvshows_list(list_type, page=1):
    """
    Busca listas de séries populares, em alta, etc. (Lista rápida e paginada).
    Esta lista NÃO contém detalhes como número de temporadas.
    """
    # ✅ CORREÇÃO do Endpoint 404
    endpoint_map = {
        'popular': 'tv/popular',
        'top_rated': 'tv/top_rated',
        'on_the_air': 'tv/on_the_air',
        'trending': 'trending/tv/week' 
    }
    # Garante que, se o tipo for desconhecido, ele use o endpoint tv/popular
    endpoint = endpoint_map.get(list_type, 'tv/popular')
    base_url = "https://api.themoviedb.org/3/"
    
    url = f"{base_url}{endpoint}?api_key={TMDB_API_KEY}&language=pt-BR&page={page}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        normalized_shows = []
        for show in data.get('results', []):
            
            # ✅ CORREÇÃO DO ERRO 'int' object is not subscriptable (TypeError)
            # Traduz os IDs de gênero (int) para os Nomes (str) usando o mapa.
            genre_names = [
                TV_GENRES_MAP.get(genre_id, 'Desconhecido')
                for genre_id in show.get('genre_ids', [])
            ]
            
            normalized_shows.append({
                'tmdb_id': show.get('id'),
                'title': show.get('name'),
                'original_title': show.get('original_name'),
                'year': show.get('first_air_date', '')[:4],
                'poster': f"https://image.tmdb.org/t/p/w500{show.get('poster_path')}" if show.get('poster_path') else '',
                'backdrop': f"https://image.tmdb.org/t/p/w780{show.get('backdrop_path')}" if show.get('backdrop_path') else '',
                'synopsis': show.get('overview'),
                'popularity': show.get('popularity'),
                'rating': show.get('vote_average'),
                'genres': genre_names # Usa os nomes traduzidos
            })
            
        return normalized_shows
    except requests.exceptions.RequestException as e:
        xbmc.log(f"[TMDB API ERROR] Falha ao buscar lista {list_type}: {e}", xbmc.LOGERROR)
        return []


def fetch_show_details(tmdb_id):
    """
    Busca os detalhes COMPLETOS de uma série específica, 
    incluindo número de temporadas e episódios.
    """
    if not tmdb_id: return None
        
    base_url = "https://api.themoviedb.org/3/tv/"
    # 'append_to_response=external_ids' é crucial para obter o IMDB ID
    url = f"{base_url}{tmdb_id}?api_key={TMDB_API_KEY}&language=pt-BR&append_to_response=external_ids"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        show_data = response.json()
        
        # Normalização dos dados:
        normalized_data = {
            'tmdb_id': show_data.get('id'),
            'imdb_id': show_data.get('external_ids', {}).get('imdb_id'),
            'title': show_data.get('name'),
            'original_title': show_data.get('original_name'),
            'year': show_data.get('first_air_date', '')[:4],
            'poster': f"https://image.tmdb.org/t/p/w500{show_data.get('poster_path')}" if show_data.get('poster_path') else '',
            'backdrop': f"https://image.tmdb.org/t/p/w780{show_data.get('backdrop_path')}" if show_data.get('backdrop_path') else '',
            'synopsis': show_data.get('overview'),
            'popularity': show_data.get('popularity'),
            'rating': show_data.get('vote_average'),
            # A certificação é complexa, pega a primeira encontrada.
            'certification': show_data.get('content_ratings', {}).get('results', [{}])[0].get('rating', 'N/A'),
            # Aqui os gêneros já vêm com 'name', então a coleta é direta:
            'genres': [g.get('name') for g in show_data.get('genres', [])], 
            
            # ✅ NOVAS INFORMAÇÕES ADICIONADAS
            'number_of_seasons': show_data.get('number_of_seasons', 0),
            'number_of_episodes': show_data.get('number_of_episodes', 0),
            'status': show_data.get('status'),
            'tagline': show_data.get('tagline'),
            'seasons_data': show_data.get('seasons', [])
        }
        
        return normalized_data
        
    except requests.exceptions.RequestException as e:
        xbmc.log(f"[TMDB API ERROR] Falha ao buscar detalhes da série {tmdb_id}: {e}", xbmc.LOGERROR)
        return None