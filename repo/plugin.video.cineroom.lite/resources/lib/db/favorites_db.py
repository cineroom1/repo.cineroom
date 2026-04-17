# -*- coding: utf-8 -*-
"""
Favorites Database - VERSÃO ULTRA-SIMPLIFICADA
✅ Sempre funciona, COM ou SEM profile_id
✅ Queries seguras com verificação automática
✅ PRAGMA lazy: executado apenas no primeiro uso, não no __init__
"""

import sqlite3
import xbmc
from .base_db import BaseDatabase


class FavoritesDatabase(BaseDatabase):

    def __init__(self):
        super().__init__()
        # Inicializado como None para adiar a query PRAGMA ao primeiro uso real.
        # Em dispositivos lentos (eMMC), essa query no __init__ consumia ~50-100ms
        # desnecessários na inicialização do addon.
        self._has_profile_column = None

    def _ensure_profile_column_checked(self):
        """
        Verifica a coluna profile_id somente na primeira chamada que precise saber.
        Resultado fica cacheado em self._has_profile_column para chamadas seguintes.
        """
        if self._has_profile_column is not None:
            return  # já foi verificado

        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(favorites)")
            columns = [col[1] for col in cursor.fetchall()]
            self._has_profile_column = 'profile_id' in columns
            self._release_conn(conn)
        except Exception as e:
            xbmc.log(f"[FavoritesDB] Erro ao verificar coluna: {e}", xbmc.LOGERROR)
            self._has_profile_column = False

    def add_to_favorites(self, tmdb_id, media_type, profile_id=None):
        """Adiciona favorito."""
        self._ensure_profile_column_checked()
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            if self._has_profile_column:
                cursor.execute(
                    "INSERT OR IGNORE INTO favorites (tmdb_id, media_type, profile_id) VALUES (?, ?, ?)",
                    (tmdb_id, media_type, profile_id)
                )
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO favorites (tmdb_id, media_type) VALUES (?, ?)",
                    (tmdb_id, media_type)
                )

            conn.commit()
            self._cache_delete_prefix("favorites")
            self._cache_delete_prefix(f"is_fav:{tmdb_id}:{media_type}")

        finally:
            self._release_conn(conn)

    def remove_from_favorites(self, tmdb_id, media_type, profile_id=None):
        """Remove favorito."""
        self._ensure_profile_column_checked()
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            if profile_id and self._has_profile_column:
                cursor.execute(
                    "DELETE FROM favorites WHERE tmdb_id = ? AND media_type = ? AND profile_id = ?",
                    (tmdb_id, media_type, profile_id)
                )
            else:
                cursor.execute(
                    "DELETE FROM favorites WHERE tmdb_id = ? AND media_type = ?",
                    (tmdb_id, media_type)
                )
            conn.commit()
            self._cache_delete_prefix("favorites")
            # Invalida cache de is_favorite para este item em qualquer perfil
            self._cache_delete_prefix(f"is_fav:{tmdb_id}:{media_type}")

        finally:
            self._release_conn(conn)

    def is_favorite(self, tmdb_id, media_type, profile_id=None):
        """Verifica se é favorito."""
        # Cache key inclui profile_id para não cruzar dados entre perfis
        cache_key = f"is_fav:{tmdb_id}:{media_type}:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        self._ensure_profile_column_checked()

        if profile_id and self._has_profile_column:
            sql = "SELECT 1 FROM favorites WHERE tmdb_id = ? AND media_type = ? AND profile_id = ? LIMIT 1"
            result = self._execute_query(sql, (tmdb_id, media_type, profile_id), fetch_one=True)
        else:
            sql = "SELECT 1 FROM favorites WHERE tmdb_id = ? AND media_type = ? LIMIT 1"
            result = self._execute_query(sql, (tmdb_id, media_type), fetch_one=True)

        is_fav = bool(result)
        self._cache_set(cache_key, is_fav, ttl=300)

        return is_fav

    def get_all_favorites(self, profile_id=None):
        """Busca todos os favoritos, filtrando por perfil quando informado."""
        cache_key = f"favorites:all:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        self._ensure_profile_column_checked()

        if profile_id and self._has_profile_column:
            profile_filter = "AND favorites.profile_id = ?"
            params = (profile_id, profile_id)
        else:
            profile_filter = ""
            params = ()

        sql = f"""
            SELECT 
                m.tmdb_id, m.title, m.original_title, m.year, m.rating,
                m.poster, m.backdrop, m.synopsis, m.imdb_id,
                m.clearlogo, m.genres, m.runtime, m.collection,
                'movie' as media_type
            FROM favorites
            JOIN movies m ON favorites.tmdb_id = m.tmdb_id
            WHERE favorites.media_type = 'movie' {profile_filter}

            UNION ALL

            SELECT
                t.tmdb_id, t.title, t.original_title, t.year, t.rating,
                t.poster, t.backdrop, t.synopsis, t.imdb_id,
                t.clearlogo, t.genres, 0 as runtime, '' as collection,
                'tvshow' as media_type
            FROM favorites
            JOIN tvshows t ON favorites.tmdb_id = t.tmdb_id
            WHERE favorites.media_type = 'tvshow' {profile_filter}

            ORDER BY media_type, title
        """

        results = self._execute_query(sql, params if params else ())
        self._cache_set(cache_key, results, ttl=300)

        return results

    def get_favorites_by_type(self, media_type, profile_id=None):
        """Busca favoritos por tipo, filtrando por perfil quando informado."""
        cache_key = f"favorites:{media_type}:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        self._ensure_profile_column_checked()

        if profile_id and self._has_profile_column:
            profile_filter = "AND favorites.profile_id = ?"
            params = (profile_id,)
        else:
            profile_filter = ""
            params = ()

        if media_type == 'movie':
            sql = f"""
                SELECT m.*, 'movie' as media_type
                FROM favorites
                JOIN movies m ON favorites.tmdb_id = m.tmdb_id
                WHERE favorites.media_type = 'movie' {profile_filter}
                ORDER BY m.title
            """
        else:
            sql = f"""
                SELECT t.*, 'tvshow' as media_type
                FROM favorites
                JOIN tvshows t ON favorites.tmdb_id = t.tmdb_id
                WHERE favorites.media_type = 'tvshow' {profile_filter}
                ORDER BY t.title
            """

        results = self._execute_query(sql, params if params else ())
        self._cache_set(cache_key, results, ttl=300)

        return results

    def get_favorites_count(self, profile_id=None):
        """Retorna contagem de favoritos, filtrando por perfil quando informado."""
        cache_key = f"favorites:count:{profile_id or 'global'}"
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
                    FROM favorites
                    WHERE profile_id = ?
                """, (profile_id,))
            else:
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN media_type = 'movie'  THEN 1 ELSE 0 END) as movies,
                        SUM(CASE WHEN media_type = 'tvshow' THEN 1 ELSE 0 END) as tvshows,
                        COUNT(*) as total
                    FROM favorites
                """)

            row = cursor.fetchone()
            result = {
                'movies':  row[0] or 0,
                'tvshows': row[1] or 0,
                'total':   row[2] or 0
            }

            self._cache_set(cache_key, result, ttl=300)
            return result

        finally:
            self._release_conn(conn)

    def clear_all_favorites(self, profile_id=None):
        """Remove favoritos — do perfil informado, ou todos se profile_id for None."""
        self._ensure_profile_column_checked()
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            if profile_id and self._has_profile_column:
                cursor.execute("DELETE FROM favorites WHERE profile_id = ?", (profile_id,))
            else:
                cursor.execute("DELETE FROM favorites")
            conn.commit()
            self._cache_delete_prefix("favorites")

        finally:
            self._release_conn(conn)
            
favorites_db = FavoritesDatabase()            