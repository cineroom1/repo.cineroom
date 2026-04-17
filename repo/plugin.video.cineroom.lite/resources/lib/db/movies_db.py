# -*- coding: utf-8 -*-
"""
MoviesDatabase - VERSÃO CORRIGIDA com ContentFilter v2.2

MUDANÇAS:
- Método _apply_kids_filter() CORRIGIDO
- Filtro aplicado em TODAS as queries que listam filmes
- Cache com chave por perfil
"""

from .base_db import BaseDatabase
import json
import xbmc
import sqlite3

class MoviesDatabase(BaseDatabase):

    def __init__(self, db_file=None):
        if db_file is None:
            super().__init__()
        else:
            super().__init__(db_file)
    
        self.content_filter = None
    
    def set_content_filter(self, content_filter):
        """Define o filtro de conteúdo"""
        self.content_filter = content_filter
    
    def _get_filter_clause(self):
        """
        ✅ MÉTODO CORRIGIDO
        
        Retorna a cláusula WHERE do filtro (sem 'WHERE').
        Retorna string vazia se não há filtro ativo.
        """
        if not self.content_filter or not self.content_filter.should_filter_content():
            return ""
        
        # Gera cláusula SQL (sem table prefix pois queries usam nome direto)
        filter_clause = self.content_filter.get_sql_where_clause(
            table_prefix='',  # Sem prefixo (ex: 'genres' não 'm.genres')
            media_type='movie'
        )
        
        return filter_clause if filter_clause else ""
    
    def _get_cache_key_with_filter(self, base_key):
        """
        Gera chave de cache considerando o perfil atual.
        
        Exemplos:
        - "movies_pop:1" → perfil adulto
        - "movies_pop:1_kids_10_anos" → perfil kids de 10 anos
        """
        if self.content_filter and self.content_filter.is_kids:
            return f"{base_key}_kids_{self.content_filter.age_range}"
        return base_key

    # ============================================================
    # BULK OPERATIONS
    # ============================================================
    
    def add_movies_bulk(self, movies_list):
        """Bulk insert otimizado com transaction única"""
        if not movies_list:
            return
        
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Prepara dados
            data = []
            for movie in movies_list:
                title_norm = self._normalize_text(movie.get('title', ''))
                genres = movie.get('genres', []) if isinstance(movie.get('genres'), list) else []
                providers = movie.get('providers', []) if isinstance(movie.get('providers'), list) else []
                normalized_genres = [self._normalize_text(g) for g in genres]
                
                data.append((
                    movie.get('tmdb_id'), movie.get('title'), movie.get('original_title'),
                    title_norm, movie.get('year'), movie.get('imdb_id'), movie.get('rating'),
                    movie.get('poster'), movie.get('backdrop'), movie.get('synopsis'),
                    movie.get('date_added'), movie.get('runtime', 0), movie.get('popularity', 0.0),
                    movie.get('revenue', 0), movie.get('collection'), json.dumps(genres),
                    json.dumps(normalized_genres), json.dumps(movie.get('streams', [])),
                    json.dumps(providers), movie.get('clearlogo'), movie.get('playcount', 0),
                    movie.get('popularity_updated') or now,
                    movie.get('certification', ''),
                    json.dumps(movie.get('keywords', [])),
                    movie.get('vote_count', 0),
                    1 if movie.get('4K') else 0,
                    json.dumps(movie.get('cast', []))
                ))
            
            # Insert em lote
            cursor.executemany('''
                INSERT OR REPLACE INTO movies (
                    tmdb_id, title, original_title, title_normalized, year, imdb_id, rating,
                    poster, backdrop, synopsis, date_added, runtime, popularity, revenue,
                    collection, genres, genres_normalized, streams, providers, clearlogo,
                    playcount, popularity_updated, certification, keywords, vote_count, is_4k, cast
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', data)
            
            conn.commit()
            
            # Limpa caches relevantes
            self._cache_delete_prefix("movies_")
        finally:
            self._release_conn(conn)
    
    def update_popularity_bulk(self, updates):
        """Atualização em massa de popularidade"""
        if not updates:
            return
        
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            data = [(u['popularity'], now, u['tmdb_id']) for u in updates]
            cursor.executemany('UPDATE movies SET popularity=?, popularity_updated=? WHERE tmdb_id=?', data)
            conn.commit()
            self._cache_delete_prefix("movies_pop:")
        finally:
            self._release_conn(conn)
    
    # ============================================================
    # SINGLE ITEM QUERIES
    # ============================================================
    
    def get_movie_by_id(self, tmdb_id):
        """Busca filme específico (com cache)"""
        cache_key = f"movie:{tmdb_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = "SELECT * FROM movies WHERE tmdb_id = ?"
        movie = self._execute_query(sql, (int(tmdb_id),), fetch_one=True)
        
        if movie:
            self._cache_set(cache_key, movie, ttl=3600)  # 1 hora
        
        return movie
    
    def get_all_movie_ids_set(self):
        """Retorna SET de IDs (ultra-rápido, só a coluna ID)"""
        cache_key = "all_movie_ids"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT tmdb_id FROM movies")
            ids = {row[0] for row in cursor.fetchall()}
            self._cache_set(cache_key, ids, ttl=600)
            return ids
        finally:
            self._release_conn(conn)
    
    # ============================================================
    # LIST QUERIES COM FILTRO ✅
    # ============================================================
    
    def get_movies_by_popularity(self, page=1, page_size=35):
        """
        ✅ CORRIGIDO: Top filmes por popularidade COM FILTRO SQL
        """
        cache_key = self._get_cache_key_with_filter(f"movies_pop:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        
        # Monta query com filtro
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM movies 
                WHERE {filter_clause}
                ORDER BY popularity DESC 
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM movies 
                ORDER BY popularity DESC 
                LIMIT ? OFFSET ?
            """
        
        movies = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, movies, ttl=900)  # 15 min
        return movies
    
    def get_4k_movies(self, page=1, page_size=35):
        cache_key = self._get_cache_key_with_filter(f"movies_4k:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        offset = (page - 1) * page_size
        filter_clause = self._get_filter_clause()

        if filter_clause:
            sql = f"""
                SELECT * FROM movies 
                WHERE is_4k = 1
                AND ({filter_clause})
                ORDER BY popularity DESC 
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM movies 
                WHERE is_4k = 1
                ORDER BY popularity DESC 
                LIMIT ? OFFSET ?
            """

        movies = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, movies, ttl=1200)
        return movies
    
    def get_recently_added_movies(self, page=1, page_size=35):
        """
        ✅ CORRIGIDO: Recém-adicionados COM FILTRO
        """
        cache_key = self._get_cache_key_with_filter(f"movies_recent:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM movies 
                WHERE date_added IS NOT NULL 
                AND ({filter_clause})
                ORDER BY date_added DESC 
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM movies 
                WHERE date_added IS NOT NULL 
                ORDER BY date_added DESC 
                LIMIT ? OFFSET ?
            """
        
        movies = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, movies, ttl=600)
        return movies
    
    def get_movies_by_revenue(self, page=1, page_size=35):
        """
        ✅ CORRIGIDO: Top por receita COM FILTRO
        """
        cache_key = self._get_cache_key_with_filter(f"movies_revenue:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM movies 
                WHERE {filter_clause}
                ORDER BY revenue DESC 
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM movies 
                ORDER BY revenue DESC 
                LIMIT ? OFFSET ?
            """
        
        movies = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, movies, ttl=1800)  # 30 min
        return movies
    
    def get_movies_by_provider(self, provider, page=1, items_per_page=35):
        """
        ✅ CORRIGIDO: Filmes por streaming COM FILTRO
        """
        provider_norm = self._normalize_text(provider)
        cache_key = self._get_cache_key_with_filter(f"movies_provider:{provider_norm}:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM movies
                WHERE providers LIKE ?
                AND ({filter_clause})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM movies
                WHERE providers LIKE ?
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        
        movies = self._execute_query(sql, (f'%"{provider}"%', items_per_page, offset))
        self._cache_set(cache_key, movies, ttl=1200)
        return movies
    
    def get_movies_by_genre(self, genre, page=1, items_per_page=35):
        """
        ✅ CORRIGIDO: Busca por gênero COM FILTRO
        """
        normalized_genre = self._normalize_text(genre)
        cache_key = self._get_cache_key_with_filter(f"movies_genre:{normalized_genre}:{page}")
        
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM movies
                WHERE genres_normalized LIKE ?
                AND ({filter_clause})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM movies
                WHERE genres_normalized LIKE ?
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        
        movies = self._execute_query(sql, (f'%"{normalized_genre}"%', items_per_page, offset))
        self._cache_set(cache_key, movies, ttl=600)
        return movies
    
    def get_movies_by_year(self, year, page=1, items_per_page=35):
        """
        ✅ CORRIGIDO: Filmes por ano COM FILTRO
        """
        cache_key = self._get_cache_key_with_filter(f"movies_year:{year}:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM movies 
                WHERE year = ? 
                AND ({filter_clause})
                ORDER BY rating DESC 
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM movies 
                WHERE year = ? 
                ORDER BY rating DESC 
                LIMIT ? OFFSET ?
            """
        
        movies = self._execute_query(sql, (year, items_per_page, offset))
        self._cache_set(cache_key, movies, ttl=1800)
        return movies
    
    def get_movies_by_collection(self, collection_name):
        """
        ✅ CORRIGIDO: Filmes de uma coleção COM FILTRO
        """
        cache_key = self._get_cache_key_with_filter(f"collection:{collection_name}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM movies 
                WHERE collection = ? 
                AND ({filter_clause})
                ORDER BY year
            """
        else:
            sql = """
                SELECT * FROM movies 
                WHERE collection = ? 
                ORDER BY year
            """
        
        movies = self._execute_query(sql, (collection_name,))
        self._cache_set(cache_key, movies, ttl=3600)
        return movies
    
    # ============================================================
    # METADATA QUERIES (SEM FILTRO - são listas de opções)
    # ============================================================
    
    def get_all_collections(self, page=1, page_size=35):
        """
        Lista de coleções (query otimizada)
        
        ⚠️ NÃO aplica filtro aqui - isso é lista de CATEGORIAS, não de filmes
        """
        cache_key = f"collections:{page}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        sql = """
            SELECT 
                collection,
                COUNT(*) AS total,
                MAX(poster) AS poster,
                MAX(backdrop) AS backdrop
            FROM movies
            WHERE collection IS NOT NULL AND collection != ''
            GROUP BY collection
            HAVING total >= 2
            ORDER BY collection COLLATE NOCASE
            LIMIT ? OFFSET ?
        """
        
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (page_size, offset))
            results = [dict(row) for row in cursor.fetchall()]
            self._cache_set(cache_key, results, ttl=3600)
            return results
        finally:
            self._release_conn(conn)
    
    def get_all_unique_years(self):
        """
        Anos únicos (cache super longo)
        
        ⚠️ NÃO aplica filtro - isso é lista de CATEGORIAS
        """
        cache_key = "movies_years"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT year FROM movies WHERE year IS NOT NULL ORDER BY year DESC")
            years = [row[0] for row in cursor.fetchall()]
            self._cache_set(cache_key, years, ttl=7200)  # 2 horas
            return years
        finally:
            self._release_conn(conn)
    
    def get_all_unique_genres(self):
        """
        Gêneros únicos (cache super longo)
        
        ⚠️ NÃO aplica filtro - isso é lista de CATEGORIAS
        """
        cache_key = "movies_genres"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT genres FROM movies")
            all_genres = set()
            
            for (genres_json,) in cursor.fetchall():
                try:
                    genres = json.loads(genres_json) if genres_json else []
                    for g in genres:
                        if isinstance(g, str) and g.strip():
                            all_genres.add(g.strip())
                except:
                    pass
            
            result = sorted(all_genres)
            self._cache_set(cache_key, result, ttl=7200)
            return result
        finally:
            self._release_conn(conn)
    
    # ============================================================
    # COLLECTION METADATA
    # ============================================================
    
    def get_cached_collection_meta(self, name):
        """Metadados de coleção (usado para posters/backdrops da API)"""
        cache_key = f"collection_meta:{name}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = "SELECT poster, backdrop FROM collections_meta WHERE collection_name = ?"
        result = self._execute_query(sql, (name,), fetch_one=True)
        
        if result:
            self._cache_set(cache_key, result, ttl=86400)  # 24h
        
        return result
    
    def save_collection_meta(self, name, poster, backdrop):
        """Salva metadados de coleção"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO collections_meta (collection_name, poster, backdrop)
                VALUES (?, ?, ?)
            """, (name, poster, backdrop))
            conn.commit()
            self._cache_delete_prefix(f"collection_meta:{name}")
        finally:
            self._release_conn(conn)
    def get_movies_by_keywords(self, keyword_list, genres=None, page=1, page_size=35):
        """
        Filtra filmes pelo campo 'keywords' — 100% local, zero chamada de API.
        keyword_list: ex ['heist', 'bank robbery']
        Retorna filmes que contenham QUALQUER uma das keywords (lógica OR).
        """
        if not keyword_list:
            return []

        cache_key = self._get_cache_key_with_filter(
            f"movies_kw:{'|'.join(sorted(keyword_list))}:{page}"
        )
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        offset = (page - 1) * page_size
        filter_clause = self._get_filter_clause()

        kw_clauses = " OR ".join(['keywords LIKE ?'] * len(keyword_list))
        kw_params = [f'%"{kw}"%' for kw in keyword_list]

        if filter_clause:
            sql = f"""
                SELECT * FROM movies
                WHERE ({kw_clauses})
                AND ({filter_clause})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = f"""
                SELECT * FROM movies
                WHERE ({kw_clauses})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """

        params = tuple(kw_params) + (page_size, offset)
        movies = self._execute_query(sql, params)

        if movies:
            movies[0]['_has_next_page'] = (len(movies) == page_size)

        self._cache_set(cache_key, movies, ttl=600)
        return movies

    # ============================================================
    # QUERY POR FAIXA DE NOTA
    # ============================================================

    def get_movies_by_rating_range(self, min_rating=7.0, max_rating=10.1,
                                   min_votes=100, page=1, page_size=35):
        """
        Filmes por faixa de nota (ex: Excelente = 8.0-8.9, Obra-prima = 9.0+).

        min_votes: evita títulos obscuros com poucas avaliações inflando a nota.
        max_rating é exclusivo (usa <) — use 10.1 para incluir nota 10.
        """
        cache_key = self._get_cache_key_with_filter(
            f"movies_rating:{min_rating}-{max_rating}:v{min_votes}:{page}"
        )
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        offset = (page - 1) * page_size
        filter_clause = self._get_filter_clause()

        base_where = "rating >= ? AND rating < ? AND vote_count >= ?"

        if filter_clause:
            sql = f"""
                SELECT * FROM movies
                WHERE {base_where}
                AND ({filter_clause})
                ORDER BY rating DESC, popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = f"""
                SELECT * FROM movies
                WHERE {base_where}
                ORDER BY rating DESC, popularity DESC
                LIMIT ? OFFSET ?
            """

        params = (min_rating, max_rating, min_votes, page_size, offset)
        movies = self._execute_query(sql, params)

        if movies:
            movies[0]['_has_next_page'] = (len(movies) == page_size)

        self._cache_set(cache_key, movies, ttl=1800)  # 30 min
        return movies
    
    
    def get_movies_by_cast_id(self, tmdb_person_id, page=1, page_size=35):
        """Filmes que contêm o ator (busca no JSON do campo cast)."""
        cache_key = self._get_cache_key_with_filter(f"movies_cast:{tmdb_person_id}:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        offset = (page - 1) * page_size
        filter_clause = self._get_filter_clause()
        xbmc.log(f"[CINEROOM] filter_clause cast: '{filter_clause}'", xbmc.LOGINFO)
        pattern = f'%"tmdb_person_id": {tmdb_person_id}%'
        xbmc.log(f"[CINEROOM] cast sql pattern: {repr(pattern)}", xbmc.LOGINFO)

        if filter_clause:
            sql = f"""
                SELECT * FROM movies
                WHERE "cast" LIKE ?
                AND ({filter_clause})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM movies
                WHERE "cast" LIKE ?
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        xbmc.log(f"[CINEROOM] cast sql: {repr(sql)}", xbmc.LOGINFO)
        movies = self._execute_query(sql, (pattern, page_size, offset))
        self._cache_set(cache_key, movies, ttl=1800)
        return movies