# -*- coding: utf-8 -*-
"""
TVShowsDatabase - VERSÃO CORRIGIDA com ContentFilter v2.2

MUDANÇAS:
- Método _get_filter_clause() CORRIGIDO (substitui _apply_kids_filter_to_sql)
- Filtro aplicado em TODAS as queries que listam séries
- Cache com chave por perfil
"""

from .base_db import BaseDatabase
import json
import sqlite3
import xbmc

class TVShowsDatabase(BaseDatabase):

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
        
        ⚠️ IMPORTANTE: Para séries use media_type='tvshow'!
        """
        if not self.content_filter or not self.content_filter.should_filter_content():
            return ""
        
        # Gera cláusula SQL para TVSHOWS (não movies!)
        filter_clause = self.content_filter.get_sql_where_clause(
            table_prefix='',
            media_type='tvshow'  # ← IMPORTANTE!
        )
        
        return filter_clause if filter_clause else ""
    
    def _get_cache_key_with_filter(self, base_key):
        """Gera chave de cache considerando o perfil atual"""
        if self.content_filter and self.content_filter.is_kids:
            return f"{base_key}_kids_{self.content_filter.age_range}"
        return base_key

    # ============================================================
    # BULK OPERATIONS
    # ============================================================
    
    def add_tvshows_bulk(self, tvshows_list):
        """Bulk insert otimizado para séries"""
        if not tvshows_list:
            return
        
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            data = []
            for show in tvshows_list:
                original_title = show.get('original_title') or show.get('title', 'N/A')
                title_norm = self._normalize_text(original_title)
                genres = show.get('genres', []) if isinstance(show.get('genres'), list) else []
                normalized_genres = [self._normalize_text(g) for g in genres]
                
                data.append((
                    show.get('tmdb_id'), show.get('title'), original_title, show.get('romaji_title', ''), title_norm,
                    show.get('year'), show.get('imdb_id'), show.get('poster'),
                    show.get('backdrop'), show.get('synopsis'),
                    json.dumps(show.get('providers', [])), show.get('classification', ''),
                    show.get('date_added'), show.get('popularity', 0.0), show.get('rating', 0.0),
                    json.dumps(genres), json.dumps(normalized_genres),
                    json.dumps(show.get('temporadas', [])), show.get('clearlogo'),
                    show.get('banner'), show.get('landscape'), show.get('playcount', 0),
                    show.get('season_count', 0), show.get('episodes_count', 0),
                    show.get('status'), show.get('popularity_updated') or now,
                    json.dumps(show.get('keywords', [])),
                    show.get('vote_count', 0),
                    json.dumps(show.get('cast', []))
                ))
            
            cursor.executemany('''
                INSERT OR REPLACE INTO tvshows (
                    tmdb_id, title, original_title, romaji_title, title_normalized, year, imdb_id,
                    poster, backdrop, synopsis, providers, certification, date_added,
                    popularity, rating, genres, genres_normalized, seasons_data,
                    clearlogo, banner, landscape, playcount, season_count,
                    episodes_count, status, popularity_updated, keywords, vote_count, cast
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', data)
            
            conn.commit()
            
            # Limpa caches relevantes
            self._cache_delete_prefix("tv_")
            self._cache_delete_prefix("tvshow:")
        finally:
            self._release_conn(conn)
    
    def update_tv_popularity_bulk(self, updates):
        """Atualização em massa de popularidade"""
        if not updates:
            return
        
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            data = [(u['popularity'], now, u['tmdb_id']) for u in updates]
            cursor.executemany('UPDATE tvshows SET popularity=?, popularity_updated=? WHERE tmdb_id=?', data)
            conn.commit()
            self._cache_delete_prefix("tv_pop:")
        finally:
            self._release_conn(conn)
    
    # ============================================================
    # SINGLE ITEM QUERIES
    # ============================================================
    
    def get_tvshow_by_id(self, tmdb_id):
        """Busca série específica (com cache)"""
        cache_key = f"tvshow:{tmdb_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        sql = "SELECT * FROM tvshows WHERE tmdb_id = ?"
        show = self._execute_query(sql, (int(tmdb_id),), fetch_one=True)
        
        if show:
            self._cache_set(cache_key, show, ttl=3600)  # 1 hora
        
        return show
    
    def get_all_tvshow_ids_set(self):
        """Retorna SET de IDs (ultra-rápido)"""
        cache_key = "all_tvshow_ids"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT tmdb_id FROM tvshows")
            ids = {row[0] for row in cursor.fetchall() if row[0]}
            self._cache_set(cache_key, ids, ttl=600)
            return ids
        except Exception as e:
            xbmc.log(f"[DB ERROR] Falha ao buscar IDs de séries: {e}", xbmc.LOGERROR)
            return set()
        finally:
            self._release_conn(conn)
    
    # ============================================================
    # CACHE DE TEMPORADAS E EPISÓDIOS
    # ============================================================
    
    def get_cached_seasons(self, tvshow_tmdb_id, max_age_hours=72):
        """Busca temporadas do cache local (com TTL).
        Séries externas (não na biblioteca) usam api_cache."""
        cache_key = f"seasons:{tvshow_tmdb_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        # Verifica se série está na biblioteca local
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT tmdb_id FROM tvshows WHERE tmdb_id = ?", (tvshow_tmdb_id,))
            in_library = cursor.fetchone() is not None
        finally:
            self._release_conn(conn)

        # Série externa → api_cache (sem FK)
        if not in_library:
            return self.get_tmdb_cache(f"seasons:{tvshow_tmdb_id}", hours=max_age_hours)

        sql = """
            SELECT * FROM seasons_cache 
            WHERE tvshow_tmdb_id = ? 
            AND last_updated > datetime('now', ?)
        """

        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (tvshow_tmdb_id, f'-{max_age_hours} hours'))
            results = [dict(row) for row in cursor.fetchall()]

            if results:
                self._cache_set(cache_key, results, ttl=max_age_hours * 3600)

            return results if results else None
        finally:
            self._release_conn(conn)
    
    def save_seasons_cache(self, tvshow_tmdb_id, seasons_data_list):
        """Salva temporadas no cache.
        Séries externas (não na biblioteca) usam api_cache (sem FK)."""
        if not seasons_data_list:
            return

        # Verifica se série está na biblioteca local
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT tmdb_id FROM tvshows WHERE tmdb_id = ?", (tvshow_tmdb_id,))
            in_library = cursor.fetchone() is not None
        finally:
            self._release_conn(conn)

        # Série externa → api_cache (sem FK constraint)
        if not in_library:
            self.save_tmdb_cache(f"seasons:{tvshow_tmdb_id}", seasons_data_list)
            return

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Limpa cache antigo
            cursor.execute("DELETE FROM seasons_cache WHERE tvshow_tmdb_id = ?", (tvshow_tmdb_id,))
            
            # Prepara novos dados
            data = []
            for season in seasons_data_list:
                poster = f"https://image.tmdb.org/t/p/w500{season.get('poster_path')}" if season.get('poster_path') else None
                data.append((
                    tvshow_tmdb_id,
                    season.get('season_number', season.get('number', 0)),
                    season.get('name'),
                    season.get('overview'),
                    poster,
                    season.get('air_date'),
                    season.get('episode_count', 0)
                ))
            
            cursor.executemany('''
                INSERT INTO seasons_cache (
                    tvshow_tmdb_id, season_number, name, overview, poster_path, air_date, episode_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', data)
            
            conn.commit()
            self._cache_delete_prefix(f"seasons:{tvshow_tmdb_id}")
        finally:
            self._release_conn(conn)
    
    def get_cached_episodes(self, tvshow_tmdb_id, season_number, max_age_hours=72):
        """Busca episódios do cache (com TTL).
        Séries externas (não na biblioteca) usam api_cache."""
        cache_key = f"episodes:{tvshow_tmdb_id}:{season_number}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        # Verifica se série está na biblioteca local
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT tmdb_id FROM tvshows WHERE tmdb_id = ?", (tvshow_tmdb_id,))
            in_library = cursor.fetchone() is not None
        finally:
            self._release_conn(conn)

        # Série externa → api_cache (sem FK)
        if not in_library:
            return self.get_tmdb_cache(f"episodes:{tvshow_tmdb_id}:{season_number}", hours=max_age_hours)

        sql = """
            SELECT * FROM episodes_cache
            WHERE tvshow_tmdb_id = ? AND season_number = ?
            AND last_updated > datetime('now', ?)
            ORDER BY episode_number
        """

        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (tvshow_tmdb_id, season_number, f'-{max_age_hours} hours'))
            results = [dict(row) for row in cursor.fetchall()]

            if results:
                self._cache_set(cache_key, results, ttl=max_age_hours * 3600)

            return results if results else None
        finally:
            self._release_conn(conn)
    
    def save_episodes_cache(self, tvshow_tmdb_id, season_number, episodes_list):
        """Salva episódios no cache (batch).
        Séries externas (não na biblioteca) usam api_cache (sem FK)."""
        if not episodes_list:
            return

        # Verifica se série está na biblioteca local
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT tmdb_id FROM tvshows WHERE tmdb_id = ?", (tvshow_tmdb_id,))
            in_library = cursor.fetchone() is not None
        finally:
            self._release_conn(conn)

        # Série externa → api_cache (sem FK constraint)
        if not in_library:
            self.save_tmdb_cache(f"episodes:{tvshow_tmdb_id}:{season_number}", episodes_list)
            return

        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # Limpa episódios antigos da season
            cursor.execute(
                "DELETE FROM episodes_cache WHERE tvshow_tmdb_id = ? AND season_number = ?",
                (tvshow_tmdb_id, season_number)
            )
            
            # Prepara novos dados
            data = []
            for ep in episodes_list:
                data.append((
                    tvshow_tmdb_id,
                    season_number,
                    ep.get('episode_number'),
                    ep.get('name'),
                    ep.get('overview'),
                    ep.get('still_path'),
                    ep.get('air_date'),
                    ep.get('vote_average', 0.0),
                    ep.get('runtime', 0)
                ))
            
            # Insert em lote
            cursor.executemany('''
                INSERT INTO episodes_cache (
                    tvshow_tmdb_id, season_number, episode_number, name, overview,
                    still_path, air_date, vote_average, runtime
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
            
            conn.commit()
            
            # Limpa cache de memória
            self._cache_delete_prefix(f"episodes:{tvshow_tmdb_id}:{season_number}")
        finally:
            self._release_conn(conn)
    
    # ============================================================
    # LIST QUERIES COM FILTRO ✅
    # ============================================================
    
    def get_tvshows_by_popularity(self, page=1, page_size=20):
        """
        ✅ CORRIGIDO: Top séries por popularidade COM FILTRO SQL
        """
        cache_key = self._get_cache_key_with_filter(f"tv_pop:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (int(page) - 1) * page_size
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM tvshows 
                WHERE {filter_clause}
                ORDER BY popularity DESC 
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM tvshows 
                ORDER BY popularity DESC 
                LIMIT ? OFFSET ?
            """
        
        shows = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, shows, ttl=900)
        return shows
    
    def get_recently_added_tvshows(self, page, page_size):
        """
        ✅ CORRIGIDO: Recém-adicionadas COM FILTRO SQL
        """
        cache_key = self._get_cache_key_with_filter(f"tv_recent:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (int(page) - 1) * page_size
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM tvshows 
                WHERE date_added IS NOT NULL 
                AND ({filter_clause})
                ORDER BY date_added DESC 
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM tvshows 
                WHERE date_added IS NOT NULL 
                ORDER BY date_added DESC 
                LIMIT ? OFFSET ?
            """
        
        shows = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, shows, ttl=600)
        return shows
    
    def get_kids_tvshows(self, page, page_size):
        """
        ✅ CORRIGIDO: Kids COM FILTRO SQL
        
        ⚠️ NOTA: Esta query tem filtro próprio + filtro de perfil
        """
        cache_key = self._get_cache_key_with_filter(f"tv_kids:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * page_size
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM tvshows
                WHERE (certification IN ('L', '10', '12') OR genres LIKE '%Kids%')
                AND ({filter_clause})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM tvshows
                WHERE certification IN ('L', '10', '12') OR genres LIKE '%Kids%'
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        
        shows = self._execute_query(sql, (page_size, offset))
        self._cache_set(cache_key, shows, ttl=1200)
        return shows
    
    def get_tvshows_by_genre(self, genre, page=1, items_per_page=20):
        """
        ✅ CORRIGIDO: Séries por gênero COM FILTRO SQL
        """
        normalized_genre = self._normalize_text(genre)
        cache_key = self._get_cache_key_with_filter(f"tv_genre:{normalized_genre}:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM tvshows
                WHERE genres_normalized LIKE ?
                AND ({filter_clause})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM tvshows
                WHERE genres_normalized LIKE ?
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        
        shows = self._execute_query(sql, (f'%"{normalized_genre}"%', items_per_page, offset))
        self._cache_set(cache_key, shows, ttl=600)
        return shows
    
    def get_tvshows_by_provider(self, provider, page=1, items_per_page=20):
        """
        ✅ CORRIGIDO: Séries por provedor COM FILTRO SQL
        """
        cache_key = self._get_cache_key_with_filter(f"tv_provider:{provider}:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        offset = (page - 1) * items_per_page
        filter_clause = self._get_filter_clause()
        
        if filter_clause:
            sql = f"""
                SELECT * FROM tvshows
                WHERE providers LIKE ?
                AND ({filter_clause})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM tvshows
                WHERE providers LIKE ?
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        
        shows = self._execute_query(sql, (f'%"{provider}"%', items_per_page, offset))
        self._cache_set(cache_key, shows, ttl=1200)
        return shows
    
    # ============================================================
    # METADATA QUERIES (SEM FILTRO - são listas de opções)
    # ============================================================
    
    def get_all_unique_tvshow_genres(self):
        """
        Gêneros únicos de séries (cache super longo)
        
        ⚠️ NÃO aplica filtro - isso é lista de CATEGORIAS
        """
        cache_key = "tv_genres"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT genres FROM tvshows")
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
    
    def get_all_unique_providers(self):
        """
        Provedores únicos (cache longo + normalização)
        
        ⚠️ NÃO aplica filtro - isso é lista de CATEGORIAS
        """
        cache_key = "tv_providers"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        # Mapa de normalização
        provider_map = {
            "netflix": "Netflix",
            "netflix basic with ads": "Netflix",
            "amazon": "Amazon Prime Video",
            "prime video": "Amazon Prime Video",
            "amazon prime video": "Amazon Prime Video",
            "amazon with ads": "Amazon Prime Video",
            "hbo": "Max",
            "hbo max": "Max",
            "max": "Max",
            "max channel": "Max",
            "disney plus": "Disney Plus",
            "paramount plus": "Paramount Plus",
            "apple tv+": "Apple TV+",
            "apple tv plus": "Apple TV+",
            "crunchyroll": "Crunchyroll",
            "globoplay": "Globoplay",
            "looke": "Looke",
            "peacock": "Peacock",
            "hulu": "Hulu",
            "discovery+": "Discovery+",
        }
        
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT providers FROM tvshows")
            all_providers = set()
            
            for (providers_json,) in cursor.fetchall():
                try:
                    providers = json.loads(providers_json) if providers_json else []
                    for provider in providers:
                        normalized = provider.strip().lower()
                        if normalized in provider_map:
                            all_providers.add(provider_map[normalized])
                except:
                    pass
            
            result = sorted(all_providers)
            self._cache_set(cache_key, result, ttl=7200)
            return result
        finally:
            self._release_conn(conn)
    def get_tvshows_by_keywords(self, keyword_list, genres=None, page=1, page_size=35):
        """
        Filtra séries pelo campo 'keywords' — 100% local, zero chamada de API.
        keyword_list: ex ['spy', 'espionage']
        Retorna séries que contenham QUALQUER uma das keywords (lógica OR).
        """
        if not keyword_list:
            return []

        cache_key = self._get_cache_key_with_filter(
            f"tv_kw:{'|'.join(sorted(keyword_list))}:{page}"
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
                SELECT * FROM tvshows
                WHERE ({kw_clauses})
                AND ({filter_clause})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = f"""
                SELECT * FROM tvshows
                WHERE ({kw_clauses})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """

        params = tuple(kw_params) + (page_size, offset)
        shows = self._execute_query(sql, params)

        if shows:
            shows[0]['_has_next_page'] = (len(shows) == page_size)

        self._cache_set(cache_key, shows, ttl=600)
        return shows

    # ============================================================
    # QUERY POR FAIXA DE NOTA
    # ============================================================

    def get_tvshows_by_rating_range(self, min_rating=7.0, max_rating=10.1,
                                    min_votes=50, page=1, page_size=35):
        """
        Séries por faixa de nota (ex: Excelente = 8.0-8.9, Obra-prima = 9.0+).

        min_votes menor que filmes (50) pois séries tendem a ter menos votos no TMDB.
        max_rating é exclusivo (usa <) — use 10.1 para incluir nota 10.
        """
        cache_key = self._get_cache_key_with_filter(
            f"tv_rating:{min_rating}-{max_rating}:v{min_votes}:{page}"
        )
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        offset = (page - 1) * page_size
        filter_clause = self._get_filter_clause()

        base_where = "rating >= ? AND rating < ? AND vote_count >= ?"

        if filter_clause:
            sql = f"""
                SELECT * FROM tvshows
                WHERE {base_where}
                AND ({filter_clause})
                ORDER BY rating DESC, popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = f"""
                SELECT * FROM tvshows
                WHERE {base_where}
                ORDER BY rating DESC, popularity DESC
                LIMIT ? OFFSET ?
            """

        params = (min_rating, max_rating, min_votes, page_size, offset)
        shows = self._execute_query(sql, params)

        if shows:
            shows[0]['_has_next_page'] = (len(shows) == page_size)

        self._cache_set(cache_key, shows, ttl=1800)  # 30 min
        return shows
    
    
    def get_episode_counts_before_season(self, tvshow_tmdb_id, season_number):
        """
        Retorna o total de episódios de todas as temporadas anteriores à season_number.
        Usa seasons_cache (episode_count já salvo pelo indexer).
        Retorna None se alguma temporada estiver faltando no cache.
        """
        if season_number <= 1:
            return 0

        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT season_number, episode_count
                FROM seasons_cache
                WHERE tvshow_tmdb_id = ?
                  AND season_number > 0
                  AND season_number < ?
                ORDER BY season_number
            """, (tvshow_tmdb_id, season_number))
            rows = cursor.fetchall()
        finally:
            self._release_conn(conn)

        if not rows:
            return None

        # Garante que tem TODAS as temporadas anteriores
        seasons_found = {r[0] for r in rows}
        seasons_needed = set(range(1, season_number))
        if not seasons_needed.issubset(seasons_found):
            missing = seasons_needed - seasons_found
            xbmc.log(f"[abs_ep] Temporadas faltando no seasons_cache: {missing}", xbmc.LOGWARNING)
            return None

        return sum(r[1] for r in rows)
    
    
    def get_tvshows_by_cast_id(self, tmdb_person_id, page=1, page_size=35):
        """Séries que contêm o ator (busca no JSON do campo cast)."""
        cache_key = self._get_cache_key_with_filter(f"tvshows_cast:{tmdb_person_id}:{page}")
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        offset = (page - 1) * page_size
        filter_clause = self._get_filter_clause()
        pattern = f'%"tmdb_person_id": {tmdb_person_id}%'

        if filter_clause:
            sql = f"""
                SELECT * FROM tvshows
                WHERE "cast" LIKE ?
                AND ({filter_clause})
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """
        else:
            sql = """
                SELECT * FROM tvshows
                WHERE "cast" LIKE ?
                ORDER BY popularity DESC
                LIMIT ? OFFSET ?
            """

        shows = self._execute_query(sql, (pattern, page_size, offset))
        self._cache_set(cache_key, shows, ttl=1800)
        return shows