# Em: resources/lib/db/favorites_db.py

import sqlite3
import xbmc
import json
from .base_db import BaseDatabase

class FavoritesDatabase(BaseDatabase):

    def add_to_favorites(self, tmdb_id, media_type):
        """Adiciona um item à tabela de favoritos."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO favorites (tmdb_id, media_type) VALUES (?, ?)", (tmdb_id, media_type))
        conn.commit()
        conn.close()

    def remove_from_favorites(self, tmdb_id, media_type):
        """Remove um item da tabela de favoritos."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favorites WHERE tmdb_id = ? AND media_type = ?", (tmdb_id, media_type))
        conn.commit()
        conn.close()

    def get_all_favorites(self):
        """Busca os detalhes completos de todos os filmes e séries favoritados."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Busca os filmes favoritos usando JOIN
        cursor.execute('''
            SELECT m.*, 'movie' as item_type FROM favorites f
            JOIN movies m ON f.tmdb_id = m.tmdb_id
            WHERE f.media_type = 'movie'
        ''')
        movies = self._rows_to_dict(cursor.fetchall())
        
        # Busca as séries favoritas usando JOIN
        cursor.execute('''
            SELECT t.*, 'tvshow' as item_type FROM favorites f
            JOIN tvshows t ON f.tmdb_id = t.tmdb_id
            WHERE f.media_type = 'tvshow'
        ''')
        tvshows = self._rows_to_dict(cursor.fetchall())
        
        conn.close()
        return movies + tvshows