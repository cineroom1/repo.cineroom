# -*- coding: utf-8 -*-
"""
Watchlist Database — "Quero Assistir"
✅ Mesmo padrão do favorites_db.py
✅ COM ou SEM profile_id
✅ PRAGMA lazy: verificado apenas no primeiro uso
"""

import xbmc
from .base_db import BaseDatabase, SmartCache, ConnectionPool, DB_FILE


class WatchlistDatabase(BaseDatabase):

    def __init__(self):
        # Não chama super().__init__() completo para evitar os upgrades de schema
        # (romaji, favorites, etc.) que dependem do Database principal.
        # Apenas inicializa o pool e cache diretamente.
        self.db_file = DB_FILE
        self._cache = SmartCache(max_size=200, default_ttl=300)
        if BaseDatabase._pool is None:
            BaseDatabase._pool = ConnectionPool(DB_FILE, pool_size=3)
        self._has_profile_column = None

    def _ensure_profile_column_checked(self):
        if self._has_profile_column is not None:
            return
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(watchlist)")
            columns = [col[1] for col in cursor.fetchall()]
            self._has_profile_column = 'profile_id' in columns
            self._release_conn(conn)
        except Exception as e:
            xbmc.log(f"[WatchlistDB] Erro ao verificar coluna: {e}", xbmc.LOGERROR)
            self._has_profile_column = False

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_to_watchlist(self, tmdb_id, media_type, profile_id=None):
        """Adiciona item à watchlist."""
        self._ensure_profile_column_checked()
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            if self._has_profile_column:
                cursor.execute(
                    "INSERT OR IGNORE INTO watchlist (tmdb_id, media_type, profile_id) VALUES (?, ?, ?)",
                    (tmdb_id, media_type, profile_id)
                )
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO watchlist (tmdb_id, media_type) VALUES (?, ?)",
                    (tmdb_id, media_type)
                )
            conn.commit()
            self._cache_delete_prefix("watchlist")
            self._cache_delete_prefix(f"in_wl:{tmdb_id}:{media_type}")
        finally:
            self._release_conn(conn)

    def remove_from_watchlist(self, tmdb_id, media_type, profile_id=None):
        """Remove item da watchlist."""
        self._ensure_profile_column_checked()
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            if profile_id and self._has_profile_column:
                cursor.execute(
                    "DELETE FROM watchlist WHERE tmdb_id = ? AND media_type = ? AND profile_id = ?",
                    (tmdb_id, media_type, profile_id)
                )
            else:
                cursor.execute(
                    "DELETE FROM watchlist WHERE tmdb_id = ? AND media_type = ?",
                    (tmdb_id, media_type)
                )
            conn.commit()
            self._cache_delete_prefix("watchlist")
            self._cache_delete_prefix(f"in_wl:{tmdb_id}:{media_type}")
        finally:
            self._release_conn(conn)

    def is_in_watchlist(self, tmdb_id, media_type, profile_id=None):
        """Verifica se item está na watchlist."""
        cache_key = f"in_wl:{tmdb_id}:{media_type}:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        self._ensure_profile_column_checked()

        if profile_id and self._has_profile_column:
            sql = "SELECT 1 FROM watchlist WHERE tmdb_id = ? AND media_type = ? AND profile_id = ? LIMIT 1"
            result = self._execute_query(sql, (tmdb_id, media_type, profile_id), fetch_one=True)
        else:
            sql = "SELECT 1 FROM watchlist WHERE tmdb_id = ? AND media_type = ? LIMIT 1"
            result = self._execute_query(sql, (tmdb_id, media_type), fetch_one=True)

        in_wl = bool(result)
        self._cache_set(cache_key, in_wl, ttl=300)
        return in_wl

    def get_all_watchlist(self, profile_id=None):
        """Retorna toda a watchlist com dados completos de filmes e séries."""
        cache_key = f"watchlist:all:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        self._ensure_profile_column_checked()

        if profile_id and self._has_profile_column:
            profile_filter = "AND watchlist.profile_id = ?"
            params = (profile_id, profile_id)
        else:
            profile_filter = ""
            params = ()

        sql = f"""
            SELECT
                m.tmdb_id, m.title, m.original_title, m.year, m.rating,
                m.poster, m.backdrop, m.synopsis, m.imdb_id,
                m.clearlogo, m.genres, m.runtime, m.collection,
                'movie' as media_type,
                w.added_at
            FROM watchlist w
            JOIN movies m ON w.tmdb_id = m.tmdb_id
            WHERE w.media_type = 'movie' {profile_filter}

            UNION ALL

            SELECT
                t.tmdb_id, t.title, t.original_title, t.year, t.rating,
                t.poster, t.backdrop, t.synopsis, t.imdb_id,
                t.clearlogo, t.genres, 0 as runtime, '' as collection,
                'tvshow' as media_type,
                w.added_at
            FROM watchlist w
            JOIN tvshows t ON w.tmdb_id = t.tmdb_id
            WHERE w.media_type = 'tvshow' {profile_filter}

            ORDER BY added_at DESC
        """

        results = self._execute_query(sql, params if params else ())
        self._cache_set(cache_key, results, ttl=300)
        return results

    def get_watchlist_by_type(self, media_type, profile_id=None):
        """Retorna watchlist filtrada por tipo."""
        cache_key = f"watchlist:{media_type}:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        self._ensure_profile_column_checked()

        if profile_id and self._has_profile_column:
            profile_filter = "AND w.profile_id = ?"
            params = (profile_id,)
        else:
            profile_filter = ""
            params = ()

        if media_type == 'movie':
            sql = f"""
                SELECT m.*, 'movie' as media_type, w.added_at
                FROM watchlist w
                JOIN movies m ON w.tmdb_id = m.tmdb_id
                WHERE w.media_type = 'movie' {profile_filter}
                ORDER BY w.added_at DESC
            """
        else:
            sql = f"""
                SELECT t.*, 'tvshow' as media_type, w.added_at
                FROM watchlist w
                JOIN tvshows t ON w.tmdb_id = t.tmdb_id
                WHERE w.media_type = 'tvshow' {profile_filter}
                ORDER BY w.added_at DESC
            """

        results = self._execute_query(sql, params if params else ())
        self._cache_set(cache_key, results, ttl=300)
        return results

    def get_watchlist_count(self, profile_id=None):
        """Conta itens na watchlist."""
        cache_key = f"watchlist:count:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        self._ensure_profile_column_checked()
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            if profile_id and self._has_profile_column:
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN media_type = 'movie'  THEN 1 ELSE 0 END) as movies,
                        SUM(CASE WHEN media_type = 'tvshow' THEN 1 ELSE 0 END) as tvshows,
                        COUNT(*) as total
                    FROM watchlist WHERE profile_id = ?
                """, (profile_id,))
            else:
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN media_type = 'movie'  THEN 1 ELSE 0 END) as movies,
                        SUM(CASE WHEN media_type = 'tvshow' THEN 1 ELSE 0 END) as tvshows,
                        COUNT(*) as total
                    FROM watchlist
                """)
            row = cursor.fetchone()
            result = {
                'movies':  row[0] or 0,
                'tvshows': row[1] or 0,
                'total':   row[2] or 0,
            }
            self._cache_set(cache_key, result, ttl=300)
            return result
        finally:
            self._release_conn(conn)

    def clear_watchlist(self, profile_id=None):
        """Limpa watchlist do perfil ou toda."""
        self._ensure_profile_column_checked()
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            if profile_id and self._has_profile_column:
                cursor.execute("DELETE FROM watchlist WHERE profile_id = ?", (profile_id,))
            else:
                cursor.execute("DELETE FROM watchlist")
            conn.commit()
            self._cache_delete_prefix("watchlist")
        finally:
            self._release_conn(conn)


# Instância global
watchlist_db = WatchlistDatabase()