# -*- coding: utf-8 -*-
"""
db.py - Interface principal para o banco de dados
✅ Herda de BaseDatabase
✅ Compatível com Trakt Sync
✅ Funções otimizadas
"""

from .base_db import BaseDatabase
import xbmc
import json
import time

# ============ INSTÂNCIA GLOBAL ============
class db(BaseDatabase):
    """Wrapper para o banco de dados com métodos específicos"""
    
    def __init__(self):
        super().__init__()
    
    # ============ MÉTODOS ESPECÍFICOS PARA TRAKT ============
    
    def get_movie_by_id(self, tmdb_id):
        """Busca filme pelo TMDB ID"""
        cache_key = f"movie_{tmdb_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = """
            SELECT * FROM movies 
            WHERE tmdb_id = ?
        """
        result = self._execute_query(sql, (tmdb_id,), fetch_one=True)
        
        if result:
            self._cache_set(cache_key, result, ttl=3600)  # 1 hora
        return result
    
    def get_tvshow_by_id(self, tmdb_id):
        """Busca série pelo TMDB ID"""
        cache_key = f"tvshow_{tmdb_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = """
            SELECT * FROM tvshows 
            WHERE tmdb_id = ?
        """
        result = self._execute_query(sql, (tmdb_id,), fetch_one=True)
        
        if result:
            self._cache_set(cache_key, result, ttl=3600)  # 1 hora
        return result
    
    def add_movie(self, movie_data):
        """Adiciona ou atualiza filme no DB"""
        try:
            # Prepara dados
            tmdb_id = movie_data.get('tmdb_id')
            title = movie_data.get('title', '')
            original_title = movie_data.get('original_title', title)
            year = movie_data.get('year', 0)
            imdb_id = movie_data.get('imdb_id', '')
            rating = movie_data.get('rating', 0.0)
            is_4k = 1 if movie_data.get('4K') else 0
            xbmc.log(f"[DB] add_movie tmdb={movie_data.get('tmdb_id')} 4K={movie_data.get('4K')} is_4k={is_4k}", xbmc.LOGINFO)
            poster = movie_data.get('poster', '')
            backdrop = movie_data.get('backdrop', '')
            synopsis = movie_data.get('synopsis', '')
            runtime = movie_data.get('runtime', 0)
            popularity = movie_data.get('popularity', 0.0)
            revenue = movie_data.get('revenue', 0)
            collection = movie_data.get('collection', '')
            genres = json.dumps(movie_data.get('genres', []))
            streams = json.dumps(movie_data.get('streams', []))
            providers = json.dumps(movie_data.get('providers', []))
            clearlogo = movie_data.get('clearlogo', '')
            
            # Normalizações
            title_normalized = self._normalize_text(title)
            genres_normalized = self._normalize_text(' '.join(movie_data.get('genres', [])))
            
            sql = """
                INSERT OR REPLACE INTO movies (
                    tmdb_id, title, original_title, title_normalized,
                    year, imdb_id, rating, poster, backdrop, synopsis,
                    runtime, popularity, revenue, collection, genres,
                    genres_normalized, streams, providers, clearlogo, is_4k,
                    date_added
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            params = (
                tmdb_id, title, original_title, title_normalized,
                year, imdb_id, rating, poster, backdrop, synopsis,
                runtime, popularity, revenue, collection, genres,
                genres_normalized, streams, providers, clearlogo, is_4k
            )
            
            self._execute_query(sql, params, fetch_all=False, fetch_one=False)
            
            # Limpa cache
            self._cache_delete_prefix(f"movie_{tmdb_id}")
            self._cache_delete_prefix("movies_list")
            self._cache_delete_prefix("all_collections")
            
            return True
            
        except Exception as e:
            xbmc.log(f"[DB] Erro adicionando filme {tmdb_id}: {e}", xbmc.LOGERROR)
            return False
    
    def add_tvshow(self, tvshow_data):
        """Adiciona ou atualiza série no DB"""
        try:
            tmdb_id = tvshow_data.get('tmdb_id')
            title = tvshow_data.get('title', '')
            original_title = tvshow_data.get('original_title', title)
            romaji_title = tvshow_data.get('romaji_title', '')
            year = tvshow_data.get('year', 0)
            imdb_id = tvshow_data.get('imdb_id', '')
            poster = tvshow_data.get('poster', '')
            backdrop = tvshow_data.get('backdrop', '')
            synopsis = tvshow_data.get('synopsis', '')
            certification = tvshow_data.get('certification', '')
            popularity = tvshow_data.get('popularity', 0.0)
            rating = tvshow_data.get('rating', 0.0)
            genres = json.dumps(tvshow_data.get('genres', []))
            providers = json.dumps(tvshow_data.get('providers', []))
            seasons_data = json.dumps(tvshow_data.get('seasons_data', []))
            clearlogo = tvshow_data.get('clearlogo', '')
            banner = tvshow_data.get('banner', '')
            landscape = tvshow_data.get('landscape', '')
            season_count = tvshow_data.get('season_count', 0)
            episodes_count = tvshow_data.get('episodes_count', 0)
            status = tvshow_data.get('status', '')
            
            # Normalizações
            title_normalized = self._normalize_text(title)
            genres_normalized = self._normalize_text(' '.join(tvshow_data.get('genres', [])))
            
            sql = """
                INSERT OR REPLACE INTO tvshows (
                    tmdb_id, title, original_title, romaji_title, title_normalized,
                    year, imdb_id, poster, backdrop, synopsis, certification,
                    popularity, rating, genres, genres_normalized, providers,
                    seasons_data, clearlogo, banner, landscape, season_count,
                    episodes_count, status, date_added
                ) VALUES (?,?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            
            params = (
                tmdb_id, title, original_title, romaji_title, title_normalized,
                year, imdb_id, poster, backdrop, synopsis, certification,
                popularity, rating, genres, genres_normalized, providers,
                seasons_data, clearlogo, banner, landscape, season_count,
                episodes_count, status
            )
            
            self._execute_query(sql, params, fetch_all=False, fetch_one=False)
            
            # Limpa cache
            self._cache_delete_prefix(f"tvshow_{tmdb_id}")
            self._cache_delete_prefix("tvshows_list")
            
            return True
            
        except Exception as e:
            xbmc.log(f"[DB] Erro adicionando série {tmdb_id}: {e}", xbmc.LOGERROR)
            return False
    
    def remove_from_favorites(self, tmdb_id, media_type):
        """Remove dos favoritos"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM favorites 
                WHERE tmdb_id = ? AND media_type = ?
            """, (tmdb_id, media_type))
            
            conn.commit()
            self._cache_delete_prefix("favorites")
            return True
        finally:
            self._release_conn(conn)
    
    def is_favorite(self, tmdb_id, media_type):
        """Verifica se é favorito"""
        sql = """
            SELECT 1 FROM favorites 
            WHERE tmdb_id = ? AND media_type = ?
            LIMIT 1
        """
        result = self._execute_query(sql, (tmdb_id, media_type), fetch_one=True)
        return bool(result)
    
    def get_all_movie_ids_set(self):
        """Retorna set com todos IDs de filmes (usado pelo indexer)"""
        sql = "SELECT tmdb_id FROM movies"
        movies = self._execute_query(sql)
        return {str(movie['tmdb_id']) for movie in movies}
    
    def get_all_tvshow_ids_set(self):
        """Retorna set com todos IDs de séries"""
        sql = "SELECT tmdb_id FROM tvshows"
        tvshows = self._execute_query(sql)
        return {str(tvshow['tmdb_id']) for tvshow in tvshows}
    
    def save_season_cache(self, tvshow_tmdb_id, season_number, season_data):
        """Salva cache de temporada"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO seasons_cache 
                (tvshow_tmdb_id, season_number, name, overview, poster, 
                 air_date, episode_count, vote_average)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tvshow_tmdb_id, season_number,
                season_data.get('name', ''),
                season_data.get('overview', ''),
                season_data.get('poster', ''),
                season_data.get('air_date', ''),
                season_data.get('episode_count', 0),
                season_data.get('vote_average', 0.0)
            ))
            
            conn.commit()
            return True
        finally:
            self._release_conn(conn)
    
    def get_season_cache(self, tvshow_tmdb_id, season_number):
        """Busca cache de temporada"""
        sql = """
            SELECT * FROM seasons_cache 
            WHERE tvshow_tmdb_id = ? AND season_number = ?
        """
        return self._execute_query(sql, (tvshow_tmdb_id, season_number), fetch_one=True)
    
    def save_episode_cache(self, tvshow_tmdb_id, season_number, episode_number, episode_data):
        """Salva cache de episódio"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO episodes_cache 
                (tvshow_tmdb_id, season_number, episode_number, 
                 name, overview, still_path, air_date, vote_average, runtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tvshow_tmdb_id, season_number, episode_number,
                episode_data.get('name', ''),
                episode_data.get('overview', ''),
                episode_data.get('still_path', ''),
                episode_data.get('air_date', ''),
                episode_data.get('vote_average', 0.0),
                episode_data.get('runtime', 0)
            ))
            
            conn.commit()
            return True
        finally:
            self._release_conn(conn)
    
    def get_episode_cache(self, tvshow_tmdb_id, season_number, episode_number):
        """Busca cache de episódio"""
        sql = """
            SELECT * FROM episodes_cache 
            WHERE tvshow_tmdb_id = ? 
            AND season_number = ? 
            AND episode_number = ?
        """
        return self._execute_query(sql, (tvshow_tmdb_id, season_number, episode_number), fetch_one=True)
    
    def save_collection_meta(self, collection_name, poster, backdrop):
        """Salva metadados de coleção"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO collections_meta 
                (collection_name, poster, backdrop)
                VALUES (?, ?, ?)
            """, (collection_name, poster, backdrop))
            
            conn.commit()
            return True
        finally:
            self._release_conn(conn)
    
    def get_collection_meta(self, collection_name):
        """Busca metadados de coleção"""
        sql = """
            SELECT * FROM collections_meta 
            WHERE collection_name = ?
        """
        return self._execute_query(sql, (collection_name,), fetch_one=True)
    
    # ============ FILTRO DE CONTEÚDO (kids / adult) ============

    def set_content_filter(self, content_filter):
        """
        Define o filtro de conteúdo para as queries seguintes.
        content_filter pode ser:
            None / ''            → sem filtro
            'kids'               → só certificações infantis
            {'min_rating': X}    → filmes com rating >= X
        O filtro é armazenado no objeto e usado pelas queries que o suportam.
        """
        self._content_filter = content_filter

    def _apply_content_filter(self, table='movies'):
        """
        Retorna cláusula WHERE extra (sem o 'AND' inicial) baseada no filtro ativo.
        Retorna string vazia se não há filtro.
        """
        cf = getattr(self, '_content_filter', None)
        if not cf:
            return '', ()

        if cf == 'kids':
            kids_certs = ('G', 'TV-Y', 'TV-G', 'TV-Y7', 'L', 'Livre', '0', '7')
            placeholders = ','.join('?' * len(kids_certs))
            return f'certification IN ({placeholders})', kids_certs

        if isinstance(cf, dict):
            parts, params = [], []
            if 'min_rating' in cf:
                parts.append('rating >= ?')
                params.append(cf['min_rating'])
            if 'genre' in cf:
                parts.append('genres_normalized LIKE ?')
                params.append(f'%{self._normalize_text(cf["genre"])}%')
            if 'year' in cf:
                parts.append('year = ?')
                params.append(cf['year'])
            if parts:
                return ' AND '.join(parts), tuple(params)

        return '', ()

    # ============ QUERIES DE FILMES ============

    def get_all_unique_genres(self):
        """Retorna lista de gêneros únicos de filmes e séries."""
        cache_key = 'all_unique_genres'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql_m = "SELECT genres FROM movies WHERE genres IS NOT NULL AND genres != '[]'"
        sql_t = "SELECT genres FROM tvshows WHERE genres IS NOT NULL AND genres != '[]'"
        rows_m = self._execute_query(sql_m)
        rows_t = self._execute_query(sql_t)

        genres = set()
        for row in (rows_m or []) + (rows_t or []):
            try:
                raw = row['genres'] if isinstance(row, dict) else row[0]
                for g in json.loads(raw):
                    if g:
                        genres.add(g.strip())
            except Exception:
                pass

        result = sorted(genres, key=lambda x: x.lower())
        self._cache_set(cache_key, result, ttl=600)
        return result

    def get_all_unique_years(self):
        """Retorna lista de anos únicos de filmes (decrescente)."""
        cache_key = 'all_unique_years'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = "SELECT DISTINCT year FROM movies WHERE year IS NOT NULL AND year > 0 ORDER BY year DESC"
        rows = self._execute_query(sql)
        result = [row['year'] if isinstance(row, dict) else row[0] for row in (rows or [])]
        self._cache_set(cache_key, result, ttl=600)
        return result

    def get_movies_by_keywords(self, keywords, limit=100, offset=0):
        """
        Retorna filmes cujos keywords ou géneros contenham pelo menos uma das palavras-chave.
        keywords: lista de strings.
        """
        if not keywords:
            return []

        cache_key = f'movies_kw_{"_".join(sorted(keywords))}_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        conditions, params = [], []
        for kw in keywords:
            kw_norm = self._normalize_text(kw)
            conditions.append('(keywords LIKE ? OR genres_normalized LIKE ? OR title_normalized LIKE ?)')
            params.extend([f'%{kw_norm}%', f'%{kw_norm}%', f'%{kw_norm}%'])

        extra_where, extra_params = self._apply_content_filter('movies')
        where_clause = ' OR '.join(conditions)
        if extra_where:
            where_clause = f'({where_clause}) AND {extra_where}'
            params = params + list(extra_params)

        sql = f"""
            SELECT * FROM movies
            WHERE {where_clause}
            ORDER BY popularity DESC, rating DESC
            LIMIT ? OFFSET ?
        """
        params += [limit, offset]
        rows = self._execute_query(sql, tuple(params))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_movies_by_popularity(self, limit=100, offset=0):
        """Filmes ordenados por popularidade com filtro de conteúdo."""
        extra_where, extra_params = self._apply_content_filter('movies')
        where = f'WHERE {extra_where}' if extra_where else ''
        cache_key = f'movies_pop_{limit}_{offset}_{hash(str(getattr(self, "_content_filter", None)))}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM movies {where} ORDER BY popularity DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_recently_added_movies(self, limit=100, offset=0):
        """Filmes mais recentemente adicionados ao banco."""
        extra_where, extra_params = self._apply_content_filter('movies')
        where = f'WHERE {extra_where}' if extra_where else ''
        cache_key = f'movies_recent_{limit}_{offset}_{hash(str(getattr(self, "_content_filter", None)))}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM movies {where} ORDER BY date_added DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_trending_movies(self, limit=100, offset=0):
        """Filmes em alta: alta popularidade e bom rating."""
        extra_where, extra_params = self._apply_content_filter('movies')
        where = f'WHERE {extra_where}' if extra_where else ''
        cache_key = f'movies_trending_{limit}_{offset}_{hash(str(getattr(self, "_content_filter", None)))}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"""
            SELECT * FROM movies {where}
            ORDER BY (popularity * 0.6 + rating * 0.4) DESC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_movies_by_genre(self, genre, limit=100, offset=0):
        """Filmes filtrados por gênero."""
        genre_norm = self._normalize_text(genre)
        extra_where, extra_params = self._apply_content_filter('movies')
        genre_cond = 'genres_normalized LIKE ?'
        where = f'WHERE {genre_cond}'
        if extra_where:
            where += f' AND {extra_where}'

        cache_key = f'movies_genre_{genre_norm}_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM movies {where} ORDER BY popularity DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, (f'%{genre_norm}%',) + extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_movies_by_year(self, year, limit=100, offset=0):
        """Filmes filtrados por ano."""
        extra_where, extra_params = self._apply_content_filter('movies')
        where = 'WHERE year = ?'
        if extra_where:
            where += f' AND {extra_where}'

        cache_key = f'movies_year_{year}_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM movies {where} ORDER BY popularity DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, (year,) + extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_movies_by_rating(self, min_rating=7.0, limit=100, offset=0):
        """Filmes com rating >= min_rating."""
        extra_where, extra_params = self._apply_content_filter('movies')
        where = 'WHERE rating >= ?'
        if extra_where:
            where += f' AND {extra_where}'

        cache_key = f'movies_rating_{min_rating}_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM movies {where} ORDER BY rating DESC, vote_count DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, (min_rating,) + extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_4k_movies(self, limit=100, offset=0):
        """Filmes disponíveis em 4K (baseado no campo is_4k)."""
        xbmc.log(f"[DB] get_4k_movies chamado", xbmc.LOGINFO)
        extra_where, extra_params = self._apply_content_filter('movies')
        where = 'WHERE is_4k = 1'
        if extra_where:
            where += f' AND {extra_where}'

        cache_key = f'movies_4k_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM movies {where} ORDER BY popularity DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=600)
        return result

    def get_most_searched_movies(self, limit=100, offset=0):
        """Filmes mais buscados (por vote_count como proxy de popularidade de busca)."""
        extra_where, extra_params = self._apply_content_filter('movies')
        where = f'WHERE {extra_where}' if extra_where else ''

        cache_key = f'movies_most_searched_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"""
            SELECT * FROM movies {where}
            ORDER BY vote_count DESC, popularity DESC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_movies_by_collection(self, collection_name, limit=100, offset=0):
        """Filmes de uma coleção específica."""
        cache_key = f'movies_coll_{self._normalize_text(collection_name)}_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = "SELECT * FROM movies WHERE collection LIKE ? ORDER BY year ASC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, (f'%{collection_name}%', limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_all_collections(self, page=1, page_size=20):
        """Retorna coleções paginadas com poster/backdrop para renderização."""
        offset = (page - 1) * page_size
        cache_key = f'all_collections_{page}_{page_size}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = """
            SELECT collection,
                   MAX(poster)   AS poster,
                   MAX(backdrop) AS backdrop
            FROM movies
            WHERE collection IS NOT NULL
              AND collection != ''
              AND collection != 'null'
              AND collection != 'None'
            GROUP BY collection
            ORDER BY collection ASC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, (page_size, offset))
        result = rows if rows else []
        self._cache_set(cache_key, result, ttl=600)
        return result

    # ============ QUERIES DE SÉRIES ============

    def get_tvshows_by_popularity(self, limit=100, offset=0):
        """Séries ordenadas por popularidade com filtro de conteúdo."""
        extra_where, extra_params = self._apply_content_filter('tvshows')
        where = f'WHERE {extra_where}' if extra_where else ''
        cache_key = f'tvshows_pop_{limit}_{offset}_{hash(str(getattr(self, "_content_filter", None)))}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM tvshows {where} ORDER BY popularity DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_recently_added_tvshows(self, limit=100, offset=0):
        """Séries mais recentemente adicionadas ao banco."""
        extra_where, extra_params = self._apply_content_filter('tvshows')
        where = f'WHERE {extra_where}' if extra_where else ''
        cache_key = f'tvshows_recent_{limit}_{offset}_{hash(str(getattr(self, "_content_filter", None)))}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM tvshows {where} ORDER BY date_added DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_trending_tvshows(self, limit=100, offset=0):
        """Séries em alta."""
        extra_where, extra_params = self._apply_content_filter('tvshows')
        where = f'WHERE {extra_where}' if extra_where else ''
        cache_key = f'tvshows_trending_{limit}_{offset}_{hash(str(getattr(self, "_content_filter", None)))}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"""
            SELECT * FROM tvshows {where}
            ORDER BY (popularity * 0.6 + rating * 0.4) DESC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_tvshows_by_genre(self, genre, limit=100, offset=0):
        """Séries filtradas por gênero."""
        genre_norm = self._normalize_text(genre)
        extra_where, extra_params = self._apply_content_filter('tvshows')
        where = 'WHERE genres_normalized LIKE ?'
        if extra_where:
            where += f' AND {extra_where}'

        cache_key = f'tvshows_genre_{genre_norm}_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM tvshows {where} ORDER BY popularity DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, (f'%{genre_norm}%',) + extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_tvshows_by_rating(self, min_rating=7.0, limit=100, offset=0):
        """Séries com rating >= min_rating."""
        extra_where, extra_params = self._apply_content_filter('tvshows')
        where = 'WHERE rating >= ?'
        if extra_where:
            where += f' AND {extra_where}'

        cache_key = f'tvshows_rating_{min_rating}_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"SELECT * FROM tvshows {where} ORDER BY rating DESC, vote_count DESC LIMIT ? OFFSET ?"
        rows = self._execute_query(sql, (min_rating,) + extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_most_searched_tvshows(self, limit=100, offset=0):
        """Séries mais buscadas."""
        extra_where, extra_params = self._apply_content_filter('tvshows')
        where = f'WHERE {extra_where}' if extra_where else ''

        cache_key = f'tvshows_most_searched_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = f"""
            SELECT * FROM tvshows {where}
            ORDER BY vote_count DESC, popularity DESC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, extra_params + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_kids_tvshows(self, limit=100, offset=0):
        """Séries infantis."""
        cache_key = f'tvshows_kids_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        kids_certs = ('G', 'TV-Y', 'TV-G', 'TV-Y7', 'L', 'Livre', '0', '7')
        placeholders = ','.join('?' * len(kids_certs))
        sql = f"""
            SELECT * FROM tvshows
            WHERE certification IN ({placeholders})
               OR genres_normalized LIKE '%animacao%'
               OR genres_normalized LIKE '%animation%'
               OR genres_normalized LIKE '%familia%'
               OR genres_normalized LIKE '%family%'
            ORDER BY popularity DESC LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, kids_certs + (limit, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=600)
        return result

    def get_tvshows_by_keywords(self, keywords, limit=100, offset=0):
        """Séries cujos keywords ou gêneros contenham as palavras-chave."""
        if not keywords:
            return []

        cache_key = f'tvshows_kw_{"_".join(sorted(keywords))}_{limit}_{offset}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        conditions, params = [], []
        for kw in keywords:
            kw_norm = self._normalize_text(kw)
            conditions.append('(keywords LIKE ? OR genres_normalized LIKE ? OR title_normalized LIKE ?)')
            params.extend([f'%{kw_norm}%', f'%{kw_norm}%', f'%{kw_norm}%'])

        extra_where, extra_params = self._apply_content_filter('tvshows')
        where_clause = ' OR '.join(conditions)
        if extra_where:
            where_clause = f'({where_clause}) AND {extra_where}'
            params = params + list(extra_params)

        sql = f"""
            SELECT * FROM tvshows
            WHERE {where_clause}
            ORDER BY popularity DESC, rating DESC
            LIMIT ? OFFSET ?
        """
        params += [limit, offset]
        rows = self._execute_query(sql, tuple(params))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_all_unique_tvshow_genres(self):
        """Retorna gêneros únicos de séries."""
        return self.get_all_unique_genres()  # já inclui filmes + séries

    def get_tvshow_providers(self, limit=50):
        """Retorna lista de provedores disponíveis em séries."""
        cache_key = 'tvshow_providers'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = "SELECT providers FROM tvshows WHERE providers IS NOT NULL AND providers != '[]'"
        rows = self._execute_query(sql)
        providers = set()
        for row in (rows or []):
            try:
                raw = row['providers'] if isinstance(row, dict) else row[0]
                for p in json.loads(raw):
                    if isinstance(p, dict):
                        name = p.get('name') or p.get('provider_name', '')
                    else:
                        name = str(p)
                    if name:
                        providers.add(name.strip())
            except Exception:
                pass

        result = sorted(providers, key=lambda x: x.lower())
        self._cache_set(cache_key, result, ttl=600)
        return result

    def get_animes(self, limit=100, offset=0):
        """Retorna séries do gênero anime."""
        return self.get_tvshows_by_genre('anime', limit, offset) or \
               self.get_tvshows_by_genre('animation', limit, offset)

    # ============ TMDB CACHE (expostos como métodos da classe) ============

    def get_tmdb_cache(self, key, hours=24):
        """Proxy para base_db.get_tmdb_cache."""
        sql = """
            SELECT data_json FROM api_cache
            WHERE cache_key = ?
              AND datetime(timestamp) > datetime('now', ? || ' hours')
            LIMIT 1
        """
        row = self._execute_query(sql, (key, f'-{hours}'), fetch_one=True)
        if row:
            try:
                return json.loads(row['data_json'] if isinstance(row, dict) else row[0])
            except Exception:
                return None
        return None

    def save_tmdb_cache(self, key, data):
        """Proxy para base_db.save_tmdb_cache."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO api_cache (cache_key, data_json, timestamp)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, json.dumps(data)))
            conn.commit()
            return True
        except Exception as e:
            xbmc.log(f'[DB] Erro salvando tmdb cache: {e}', xbmc.LOGERROR)
            return False
        finally:
            self._release_conn(conn)

    # ============ BULK / UTILITÁRIOS ============

    def add_movies_bulk(self, movies):
        """Insere/atualiza uma lista de filmes em lote."""
        if not movies:
            return 0
        count = 0
        for movie in movies:
            try:
                self.add_movie(movie)
                count += 1
            except Exception as e:
                xbmc.log(f'[DB] Erro no bulk add movie: {e}', xbmc.LOGWARNING)
        self._cache_delete_prefix('movies_')
        return count

    def add_tvshows_bulk(self, tvshows):
        """Insere/atualiza uma lista de séries em lote."""
        if not tvshows:
            return 0
        count = 0
        for tvshow in tvshows:
            try:
                self.add_tvshow(tvshow)
                count += 1
            except Exception as e:
                xbmc.log(f'[DB] Erro no bulk add tvshow: {e}', xbmc.LOGWARNING)
        self._cache_delete_prefix('tvshows_')
        return count

    # ============ ALIAS / COMPATIBILIDADE ============

    def get_cached_collection_meta(self, collection_name):
        """Alias de get_collection_meta (compatibilidade com movies.py)."""
        return self.get_collection_meta(collection_name)

    # ============ QUERIES POR PROVEDOR ============

    def get_all_unique_providers(self, table='both'):
        """Retorna provedores únicos de filmes e/ou séries."""
        cache_key = f'providers_{table}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        providers = set()
        tables = []
        if table in ('both', 'movies'):
            tables.append('movies')
        if table in ('both', 'tvshows'):
            tables.append('tvshows')

        for t in tables:
            sql = f"SELECT providers FROM {t} WHERE providers IS NOT NULL AND providers != '[]'"
            rows = self._execute_query(sql)
            for row in (rows or []):
                try:
                    raw = row['providers'] if isinstance(row, dict) else row[0]
                    for p in json.loads(raw):
                        if isinstance(p, dict):
                            name = p.get('name') or p.get('provider_name', '')
                        else:
                            name = str(p)
                        if name:
                            providers.add(name.strip())
                except Exception:
                    pass

        result = sorted(providers, key=lambda x: x.lower())
        self._cache_set(cache_key, result, ttl=600)
        return result

    def get_movies_by_provider(self, provider, page=1, page_size=20):
        """Filmes disponíveis em determinado provedor, com paginação."""
        provider_norm = self._normalize_text(provider)
        offset = (page - 1) * page_size
        cache_key = f'movies_prov_{provider_norm}_{page}_{page_size}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = """
            SELECT * FROM movies
            WHERE providers LIKE ?
            ORDER BY popularity DESC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, (f'%{provider}%', page_size, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_tvshows_by_provider(self, provider, page=1, page_size=20):
        """Séries disponíveis em determinado provedor, com paginação."""
        offset = (page - 1) * page_size
        cache_key = f'tvshows_prov_{self._normalize_text(provider)}_{page}_{page_size}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = """
            SELECT * FROM tvshows
            WHERE providers LIKE ?
            ORDER BY popularity DESC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, (f'%{provider}%', page_size, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    # ============ QUERIES POR FAIXA DE NOTA ============

    def get_movies_by_rating_range(self, min_rating=0.0, max_rating=10.0,
                                   min_votes=0, page=1, page_size=20):
        """Filmes dentro de uma faixa de rating com mínimo de votos, paginados."""
        offset = (page - 1) * page_size
        cache_key = f'movies_rng_{min_rating}_{max_rating}_{min_votes}_{page}_{page_size}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = """
            SELECT * FROM movies
            WHERE rating >= ? AND rating <= ? AND vote_count >= ?
            ORDER BY rating DESC, vote_count DESC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, (min_rating, max_rating, min_votes, page_size, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    def get_tvshows_by_rating_range(self, min_rating=0.0, max_rating=10.0,
                                    min_votes=0, page=1, page_size=20):
        """Séries dentro de uma faixa de rating com mínimo de votos, paginadas."""
        offset = (page - 1) * page_size
        cache_key = f'tvshows_rng_{min_rating}_{max_rating}_{min_votes}_{page}_{page_size}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        sql = """
            SELECT * FROM tvshows
            WHERE rating >= ? AND rating <= ? AND vote_count >= ?
            ORDER BY rating DESC, vote_count DESC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, (min_rating, max_rating, min_votes, page_size, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    # ============ QUERY POR RECEITA ============

    def get_movies_by_revenue(self, page=1, page_size=20):
        """Filmes ordenados por bilheteria (revenue), paginados."""
        offset = (page - 1) * page_size
        cache_key = f'movies_rev_{page}_{page_size}'
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        extra_where, extra_params = self._apply_content_filter('movies')
        where = f'WHERE revenue > 0 AND {extra_where}' if extra_where else 'WHERE revenue > 0'

        sql = f"""
            SELECT * FROM movies {where}
            ORDER BY revenue DESC
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(sql, extra_params + (page_size, offset))
        result = self._rows_to_dict(rows) if rows else []
        self._cache_set(cache_key, result, ttl=300)
        return result

    # ============ CACHE DE TEMPORADAS / EPISÓDIOS (novo formato) ============

    def save_seasons_cache(self, tvshow_tmdb_id, seasons_data_list):
        """
        Salva lista completa de temporadas para uma série.
        seasons_data_list: lista de dicts com season_number, name, overview, poster_path, etc.
        """
        if not seasons_data_list:
            return False
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            for season in seasons_data_list:
                season_number = season.get('season_number', season.get('number', 0))
                cursor.execute("""
                    INSERT OR REPLACE INTO seasons_cache
                    (tvshow_tmdb_id, season_number, name, overview, poster_path,
                     air_date, episode_count, vote_average, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    tvshow_tmdb_id,
                    season_number,
                    season.get('name', f'Temporada {season_number}'),
                    season.get('overview', ''),
                    season.get('poster_path', season.get('poster', '')),
                    season.get('air_date', ''),
                    season.get('episode_count', 0),
                    season.get('vote_average', 0.0),
                ))
            conn.commit()
            return True
        except Exception as e:
            xbmc.log(f'[DB] Erro salvando seasons_cache: {e}', xbmc.LOGERROR)
            return False
        finally:
            self._release_conn(conn)

    def get_cached_seasons(self, tvshow_tmdb_id, cache_hours=12):
        """
        Retorna lista de temporadas do cache.
        Retorna None se o cache estiver expirado ou vazio.
        """
        sql = """
            SELECT *, last_updated FROM seasons_cache
            WHERE tvshow_tmdb_id = ?
              AND datetime(last_updated) > datetime('now', ? || ' hours')
            ORDER BY season_number ASC
        """
        rows = self._execute_query(sql, (tvshow_tmdb_id, f'-{cache_hours}'))
        if not rows:
            return None
        result = []
        for row in rows:
            d = dict(row) if hasattr(row, 'keys') else {
                'season_number': row[1], 'name': row[2], 'overview': row[3],
                'poster_path': row[4], 'air_date': row[5],
                'episode_count': row[6], 'vote_average': row[7],
            }
            result.append(d)
        return result if result else None

    def save_episodes_cache(self, tvshow_tmdb_id, season_number, episodes):
        """
        Salva lista de episódios de uma temporada.
        episodes: lista de dicts com episode_number, name, overview, still_path, etc.
        """
        if not episodes:
            return False
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            for ep in episodes:
                cursor.execute("""
                    INSERT OR REPLACE INTO episodes_cache
                    (tvshow_tmdb_id, season_number, episode_number,
                     name, overview, still_path, air_date, vote_average, runtime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tvshow_tmdb_id,
                    season_number,
                    ep.get('episode_number', ep.get('number', 0)),
                    ep.get('name', ''),
                    ep.get('overview', ''),
                    ep.get('still_path', ep.get('thumb', '')),
                    ep.get('air_date', ''),
                    ep.get('vote_average', 0.0),
                    ep.get('runtime', 0),
                ))
            conn.commit()
            return True
        except Exception as e:
            xbmc.log(f'[DB] Erro salvando episodes_cache: {e}', xbmc.LOGERROR)
            return False
        finally:
            self._release_conn(conn)

    def get_cached_episodes(self, tvshow_tmdb_id, season_number, cache_hours=12):
        """
        Retorna lista de episódios do cache.
        Retorna None se expirado ou vazio.
        """
        sql = """
            SELECT * FROM episodes_cache
            WHERE tvshow_tmdb_id = ? AND season_number = ?
            ORDER BY episode_number ASC
        """
        rows = self._execute_query(sql, (tvshow_tmdb_id, season_number))
        if not rows:
            return None
        result = []
        for row in rows:
            d = dict(row) if hasattr(row, 'keys') else {
                'episode_number': row[2], 'name': row[3], 'overview': row[4],
                'still_path': row[5], 'air_date': row[6],
                'vote_average': row[7], 'runtime': row[8],
            }
            result.append(d)
        return result if result else None

    # ============ MÉTODOS DE ESTATÍSTICAS ============
    
    def get_stats(self):
        """Retorna estatísticas do banco"""
        stats = {}
        
        # Contagem de filmes
        sql_movies = "SELECT COUNT(*) as count FROM movies"
        result = self._execute_query(sql_movies, fetch_one=True)
        stats['movies'] = result['count'] if result else 0
        
        # Contagem de séries
        sql_tvshows = "SELECT COUNT(*) as count FROM tvshows"
        result = self._execute_query(sql_tvshows, fetch_one=True)
        stats['tvshows'] = result['count'] if result else 0
        
        # Contagem de favoritos
        sql_favs = "SELECT COUNT(*) as count FROM favorites"
        result = self._execute_query(sql_favs, fetch_one=True)
        stats['favorites'] = result['count'] if result else 0
        
        # Contagem de filmes assistidos
        sql_watched = "SELECT COUNT(*) as count FROM movies WHERE playcount > 0"
        result = self._execute_query(sql_watched, fetch_one=True)
        stats['watched_movies'] = result['count'] if result else 0
        
        return stats

    # ============ MÉTODOS COMPATIBILIDADE TRAKT ============
    
    def get_last_played_movies(self, limit=10):
        """Filmes recentemente reproduzidos"""
        sql = """
            SELECT * FROM movies 
            WHERE date_added IS NOT NULL 
            ORDER BY date_added DESC 
            LIMIT ?
        """
        return self._execute_query(sql, (limit,))
    
    def get_last_played_tvshows(self, limit=10):
        """Séries recentemente reproduzidas"""
        sql = """
            SELECT * FROM tvshows 
            WHERE date_added IS NOT NULL 
            ORDER BY date_added DESC 
            LIMIT ?
        """
        return self._execute_query(sql, (limit,))

# ============ INSTÂNCIA GLOBAL ============
db_instance = db()

# ============ FUNÇÕES DE CONVENIÊNCIA ============
# (Para compatibilidade com código existente)

def get_watched_movies():
    """Compatibilidade: Retorna filmes assistidos"""
    return db_instance.get_watched_movies()

def get_watched_tvshows():
    """Compatibilidade: Retorna séries assistidas"""
    return db_instance.get_watched_tvshows()

def add_to_favorites(tmdb_id, media_type, profile_id=None):
    """Compatibilidade: Adiciona aos favoritos.
    Delega para favorites.py para garantir resolução automática do perfil ativo.
    NUNCA chame db_instance.add_to_favorites diretamente — use esta função.
    """
    try:
        from resources.lib.favorites import add_item_to_favorites
        add_item_to_favorites(tmdb_id, media_type, profile_id=profile_id)
    except Exception as e:
        db_instance.add_to_favorites(tmdb_id, media_type, profile_id=profile_id)

def remove_from_favorites(tmdb_id, media_type, profile_id=None):
    """Compatibilidade: Remove dos favoritos.
    Delega para favorites.py para garantir resolução automática do perfil ativo.
    """
    try:
        from resources.lib.favorites import remove_item_from_favorites
        remove_item_from_favorites(tmdb_id, media_type, profile_id=profile_id)
    except Exception as e:
        db_instance.remove_from_favorites(tmdb_id, media_type, profile_id=profile_id)

def is_favorite(tmdb_id, media_type, profile_id=None):
    """Compatibilidade: Verifica se é favorito.
    Delega para favorites.py para garantir resolução automática do perfil ativo.
    """
    try:
        from resources.lib.favorites import is_favorite as _is_fav
        return _is_fav(tmdb_id, media_type, profile_id=profile_id)
    except Exception as e:
        return db_instance.is_favorite(tmdb_id, media_type, profile_id=profile_id)

def get_all_favorites(profile_id=None):
    """Compatibilidade: Retorna todos favoritos.
    Delega para favorites.py para garantir resolução automática do perfil ativo.
    """
    try:
        from resources.lib.favorites import get_all_favorites as _get_all
        return _get_all(profile_id=profile_id)
    except Exception as e:
        return db_instance.get_all_favorites()

def get_movie_by_id(tmdb_id):
    """Compatibilidade: Busca filme"""
    return db_instance.get_movie_by_id(tmdb_id)

def get_tvshow_by_id(tmdb_id):
    """Compatibilidade: Busca série"""
    return db_instance.get_tvshow_by_id(tmdb_id)

def update_movie_playcount(tmdb_id, playcount, last_played=None):
    """Compatibilidade: Atualiza playcount filme"""
    return db_instance.update_movie_playcount(tmdb_id, playcount, last_played)

def update_tvshow_playcount(tmdb_id, last_played=None):
    """Compatibilidade: Atualiza playcount série"""
    return db_instance.update_tvshow_playcount(tmdb_id, last_played)

def mark_movie_as_watched(tmdb_id):
    """Compatibilidade: Marca filme como assistido"""
    return db_instance.mark_movie_as_watched(tmdb_id)

# ── Wrappers de conveniência para os novos métodos ──────────────────────────

def set_content_filter(content_filter):
    db_instance.set_content_filter(content_filter)

def get_all_unique_genres():
    return db_instance.get_all_unique_genres()

def get_all_unique_years():
    return db_instance.get_all_unique_years()

def get_movies_by_keywords(keywords, limit=100, offset=0):
    return db_instance.get_movies_by_keywords(keywords, limit, offset)

def get_movies_by_popularity(limit=100, offset=0):
    return db_instance.get_movies_by_popularity(limit, offset)

def get_recently_added_movies(limit=100, offset=0):
    return db_instance.get_recently_added_movies(limit, offset)

def get_trending_movies(limit=100, offset=0):
    return db_instance.get_trending_movies(limit, offset)

def get_movies_by_genre(genre, limit=100, offset=0):
    return db_instance.get_movies_by_genre(genre, limit, offset)

def get_movies_by_year(year, limit=100, offset=0):
    return db_instance.get_movies_by_year(year, limit, offset)

def get_movies_by_rating(min_rating=7.0, limit=100, offset=0):
    return db_instance.get_movies_by_rating(min_rating, limit, offset)

def get_4k_movies(limit=100, offset=0):
    return db_instance.get_4k_movies(limit, offset)

def get_most_searched_movies(limit=100, offset=0):
    return db_instance.get_most_searched_movies(limit, offset)

def get_movies_by_collection(collection_name, limit=100, offset=0):
    return db_instance.get_movies_by_collection(collection_name, limit, offset)

def get_all_collections():
    return db_instance.get_all_collections()

def get_tvshows_by_popularity(limit=100, offset=0):
    return db_instance.get_tvshows_by_popularity(limit, offset)

def get_recently_added_tvshows(limit=100, offset=0):
    return db_instance.get_recently_added_tvshows(limit, offset)

def get_trending_tvshows(limit=100, offset=0):
    return db_instance.get_trending_tvshows(limit, offset)

def get_tvshows_by_genre(genre, limit=100, offset=0):
    return db_instance.get_tvshows_by_genre(genre, limit, offset)

def get_tvshows_by_rating(min_rating=7.0, limit=100, offset=0):
    return db_instance.get_tvshows_by_rating(min_rating, limit, offset)

def get_most_searched_tvshows(limit=100, offset=0):
    return db_instance.get_most_searched_tvshows(limit, offset)

def get_kids_tvshows(limit=100, offset=0):
    return db_instance.get_kids_tvshows(limit, offset)

def get_tvshows_by_keywords(keywords, limit=100, offset=0):
    return db_instance.get_tvshows_by_keywords(keywords, limit, offset)

def get_tvshow_providers(limit=50):
    return db_instance.get_tvshow_providers(limit)

def get_animes(limit=100, offset=0):
    return db_instance.get_animes(limit, offset)

def get_all_unique_tvshow_genres():
    return db_instance.get_all_unique_tvshow_genres()

def get_tmdb_cache(key, hours=24):
    return db_instance.get_tmdb_cache(key, hours)

def save_tmdb_cache(key, data):
    return db_instance.save_tmdb_cache(key, data)

def add_movies_bulk(movies):
    return db_instance.add_movies_bulk(movies)

def add_tvshows_bulk(tvshows):
    return db_instance.add_tvshows_bulk(tvshows)

def get_cached_collection_meta(collection_name):
    return db_instance.get_cached_collection_meta(collection_name)

def get_all_unique_providers(table='both'):
    return db_instance.get_all_unique_providers(table)

def get_movies_by_provider(provider, page=1, page_size=20):
    return db_instance.get_movies_by_provider(provider, page, page_size)

def get_tvshows_by_provider(provider, page=1, page_size=20):
    return db_instance.get_tvshows_by_provider(provider, page, page_size)

def get_movies_by_rating_range(min_rating=0.0, max_rating=10.0, min_votes=0, page=1, page_size=20):
    return db_instance.get_movies_by_rating_range(min_rating, max_rating, min_votes, page, page_size)

def get_tvshows_by_rating_range(min_rating=0.0, max_rating=10.0, min_votes=0, page=1, page_size=20):
    return db_instance.get_tvshows_by_rating_range(min_rating, max_rating, min_votes, page, page_size)

def get_movies_by_revenue(page=1, page_size=20):
    return db_instance.get_movies_by_revenue(page, page_size)

def save_seasons_cache(tvshow_tmdb_id, seasons_data_list):
    return db_instance.save_seasons_cache(tvshow_tmdb_id, seasons_data_list)

def get_cached_seasons(tvshow_tmdb_id, cache_hours=12):
    return db_instance.get_cached_seasons(tvshow_tmdb_id, cache_hours)

def save_episodes_cache(tvshow_tmdb_id, season_number, episodes):
    return db_instance.save_episodes_cache(tvshow_tmdb_id, season_number, episodes)

def get_cached_episodes(tvshow_tmdb_id, season_number, cache_hours=12):
    return db_instance.get_cached_episodes(tvshow_tmdb_id, season_number, cache_hours)