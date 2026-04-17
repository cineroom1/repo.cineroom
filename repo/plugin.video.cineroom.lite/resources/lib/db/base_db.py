# -*- coding: utf-8 -*-
import sqlite3
import json
import os
import time
import unicodedata
import xbmcaddon
import xbmcvfs
import xbmc

from contextlib import contextmanager
from collections import OrderedDict

# === CONFIGURAÇÕES ===
ADDON = xbmcaddon.Addon()
PROFILE_DIR = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
DB_FILE = os.path.join(PROFILE_DIR, 'cineroom.light.db')
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)


# === CACHE INTELIGENTE COM TTL - OTIMIZADO COM OrderedDict ===
class SmartCache:
    """Cache com expiração automática e limite de memória - O(1) LRU"""
    def __init__(self, max_size=500, default_ttl=300):
        self._data = OrderedDict()  # ✅ OrderedDict para LRU eficiente
        self.max_size = max_size
        self.default_ttl = default_ttl
    
    def get(self, key):
        if key in self._data:
            value, expires = self._data[key]
            if time.time() < expires:
                self._data.move_to_end(key)  # ✅ LRU automático O(1)
                return value
            del self._data[key]
        return None
    
    def set(self, key, value, ttl=None):
        if len(self._data) >= self.max_size:
            self._data.popitem(last=False)  # ✅ Remove primeiro O(1)
        
        expires = time.time() + (ttl or self.default_ttl)
        self._data[key] = (value, expires)
    
    def delete_prefix(self, prefix):
        to_delete = [k for k in self._data if k.startswith(prefix)]
        for k in to_delete:
            del self._data[k]
    
    def clear(self):
        self._data.clear()


# === POOL DE CONEXÕES ===
class ConnectionPool:
    """Gerencia conexões reutilizáveis para evitar overhead"""
    def __init__(self, db_file, pool_size=3):
        self.db_file = db_file
        self.pool = []
        self.pool_size = pool_size
        self._in_use = set()
        self._temporary = set()
        self._lock = __import__('threading').Lock()  # thread-safe

    def get_connection(self):
        with self._lock:
            # Tenta reusar conexão livre
            for conn in self.pool:
                if conn not in self._in_use:
                    self._in_use.add(conn)
                    return conn

            # Cria nova se pool não está cheio
            if len(self.pool) < self.pool_size:
                conn = self._create_connection()
                self.pool.append(conn)
                self._in_use.add(conn)
                return conn

            # Pool cheio, cria temporária
            conn = self._create_connection()
            self._temporary.add(conn)
            self._in_use.add(conn)
            return conn
    
    def _create_connection(self):
        conn = sqlite3.connect(self.db_file, timeout=10.0, check_same_thread=False)

        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-8192")   
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=8388608") 
        conn.execute("PRAGMA busy_timeout=5000")

        return conn


    
    def release_connection(self, conn):
        with self._lock:
            if conn in self._in_use:
                self._in_use.remove(conn)
            if conn in getattr(self, "_temporary", set()):
                try:
                    conn.close()
                except:
                    pass
                self._temporary.discard(conn)

    def close_all(self):
        with self._lock:
            for conn in list(self.pool):
                try:
                    conn.close()
                except:
                    pass

            for conn in list(getattr(self, "_temporary", set())):
                try:
                   conn.close()
                except:
                    pass

            self.pool.clear()
            self._in_use.clear()
            if hasattr(self, "_temporary"):
                self._temporary.clear()

# === BASE DATABASE OTIMIZADA ===
class BaseDatabase:
    _pool = None
    # Cache compartilhado entre todas as instâncias — evita N caches de 500 entradas em RAM
    _shared_cache = SmartCache(max_size=500, default_ttl=300)

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self._cache = BaseDatabase._shared_cache  # referência única
        
        if BaseDatabase._pool is None:
            BaseDatabase._pool = ConnectionPool(db_file, pool_size=3)
        
        if not os.path.exists(self.db_file):
            self.run_first_time_setup()
        else:
            self._upgrade_create_favorites_table()
            self._upgrade_schema_for_romaji()
            self._upgrade_favorites_add_profile_id()
            self._upgrade_create_watchlist_table()
            self._upgrade_create_watch_history_table()
            self._upgrade_add_keywords_column()
            self._upgrade_add_vote_count_column()
            self._upgrade_episodes_cache_pk()
            self._upgrade_add_is_4k_column()
            self._upgrade_add_cast_column()
            self.optimize()
            
    def _upgrade_schema_for_romaji(self):
        """Adiciona coluna romaji_title se não existir"""
        conn = self._get_conn()
        cursor = conn.cursor()
    
        try:
            # Verifica se coluna já existe
            cursor.execute("PRAGMA table_info(movies)")
            columns = [col[1] for col in cursor.fetchall()]
        
            if 'romaji_title' not in columns:
            
                # Adiciona colunas
                cursor.execute("ALTER TABLE movies ADD COLUMN romaji_title TEXT")
                cursor.execute("ALTER TABLE tvshows ADD COLUMN romaji_title TEXT")
            
                # Cria índices
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_romaji ON movies(romaji_title)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_romaji ON tvshows(romaji_title)")
            
                # Recria FTS com novo campo
                cursor.execute("DROP TABLE IF EXISTS movies_fts")
                cursor.execute("DROP TABLE IF EXISTS tvshows_fts")
                self._create_fts_tables(cursor)
            
                # Repovoar FTS
                cursor.execute("""
                    INSERT INTO movies_fts(tmdb_id, title, romaji_title)
                    SELECT tmdb_id, title, romaji_title FROM movies
                """)
            
                cursor.execute("""
                    INSERT INTO tvshows_fts(tmdb_id, title, romaji_title)
                    SELECT tmdb_id, title, romaji_title FROM tvshows
                """)
            
                conn.commit()
            
        except Exception as e:
            xbmc.log(f"[DB] Erro no upgrade Romaji: {e}", xbmc.LOGERROR)
            conn.rollback()
        finally:
            self._release_conn(conn)
            
    def _upgrade_add_is_4k_column(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(movies)")
            cols = [c[1] for c in cursor.fetchall()]
            if 'is_4k' not in cols:
                cursor.execute("ALTER TABLE movies ADD COLUMN is_4k INTEGER DEFAULT 0")
                conn.commit()
        except Exception as e:
            xbmc.log(f"[DB] Erro upgrade is_4k: {e}", xbmc.LOGERROR)
        finally:
            self._release_conn(conn)        
    
    def _upgrade_favorites_add_profile_id(self):
        """Adiciona coluna profile_id na tabela favorites (para perfis múltiplos)"""
        conn = self._get_conn()
        cursor = conn.cursor()
    
        try:
            cursor.execute("PRAGMA table_info(favorites)")
            columns = [col[1] for col in cursor.fetchall()]
        
            if 'profile_id' not in columns:
            
                
                cursor.execute("ALTER TABLE favorites ADD COLUMN profile_id TEXT DEFAULT 'default'")
            
                
                cursor.execute("""
                    CREATE TABLE favorites_new (
                        tmdb_id INTEGER NOT NULL,
                        media_type TEXT NOT NULL,
                        profile_id TEXT DEFAULT 'default',
                        PRIMARY KEY (tmdb_id, media_type, profile_id)
                    )
                """)
            
                
                cursor.execute("""
                    INSERT INTO favorites_new (tmdb_id, media_type, profile_id)
                    SELECT tmdb_id, media_type, 'default' FROM favorites
                """)
            
                cursor.execute("DROP TABLE favorites")
                cursor.execute("ALTER TABLE favorites_new RENAME TO favorites")
            
                conn.commit()
            
        except Exception as e:
            xbmc.log(f"[DB] Erro no upgrade de favoritos: {e}", xbmc.LOGERROR)
            conn.rollback()
        finally:
            self._release_conn(conn)            

    def _upgrade_create_watchlist_table(self):
        """Cria tabela watchlist se não existir (bancos criados antes da integração)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist'")
            if not cursor.fetchone():
                self._create_watchlist_table(cursor)
                conn.commit()
            else:
                cursor.execute("PRAGMA table_info(watchlist)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'profile_id' not in columns:
                    cursor.execute("ALTER TABLE watchlist ADD COLUMN profile_id TEXT DEFAULT 'default'")
                    conn.commit()
        except Exception as e:
            xbmc.log(f"[DB] Erro no upgrade de watchlist: {e}", xbmc.LOGERROR)
            conn.rollback()
        finally:
            self._release_conn(conn)

    def _upgrade_create_watch_history_table(self):
        """Cria tabela watch_history se não existir (bancos criados antes da integração)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='watch_history'")
            if not cursor.fetchone():
                self._create_watch_history_table(cursor)
                conn.commit()
            else:
                cursor.execute("PRAGMA table_info(watch_history)")
                columns = [col[1] for col in cursor.fetchall()]
                if 'profile_id' not in columns:
                    cursor.execute("ALTER TABLE watch_history ADD COLUMN profile_id TEXT DEFAULT 'default'")
                    conn.commit()
        except Exception as e:
            xbmc.log(f"[DB] Erro no upgrade de watch_history: {e}", xbmc.LOGERROR)
            conn.rollback()
        finally:
            self._release_conn(conn)

    def _upgrade_add_keywords_column(self):
        """Adiciona coluna keywords em movies e tvshows para busca temática local."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            for table in ('movies', 'tvshows'):
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [c[1] for c in cursor.fetchall()]
                if 'keywords' not in cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN keywords TEXT")
            conn.commit()
        except Exception as e:
            xbmc.log(f"[DB] Erro upgrade keywords: {e}", xbmc.LOGERROR)
            conn.rollback()
        finally:
            self._release_conn(conn)
            
    def _upgrade_create_favorites_table(self):
        """Garante que a tabela favorites existe (bancos muito antigos podem não ter)"""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    tmdb_id     INTEGER NOT NULL,
                    media_type  TEXT    NOT NULL,
                    profile_id  INTEGER DEFAULT NULL,
                    PRIMARY KEY (tmdb_id, media_type, profile_id)
                )
            """)
            conn.commit()
        except Exception as e:
            xbmc.log(f"[DB] Erro upgrade favorites table: {e}", xbmc.LOGERROR)
        finally:
            self._release_conn(conn)        

    def _upgrade_add_vote_count_column(self):
        """Adiciona coluna vote_count em movies e tvshows (para filtro de qualidade por nota)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            for table in ('movies', 'tvshows'):
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [c[1] for c in cursor.fetchall()]
                if 'vote_count' not in cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN vote_count INTEGER DEFAULT 0")
            conn.commit()
        except Exception as e:
            xbmc.log(f"[DB] Erro upgrade vote_count: {e}", xbmc.LOGERROR)
            conn.rollback()
        finally:
            self._release_conn(conn)

    def _get_conn(self):
        """Retorna conexão do pool (MAIS RÁPIDO)"""
        return BaseDatabase._pool.get_connection()
    
    def _release_conn(self, conn):
        """Devolve conexão ao pool"""
        BaseDatabase._pool.release_connection(conn)
    
    @contextmanager
    def _db_connection(self):
        """Context manager para garantir liberação de conexões"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            self._release_conn(conn)
    
    def _execute_query(self, sql, params=(), fetch_one=False, fetch_all=True):
        """Helper universal para queries com gerenciamento automático de conexões"""
        with self._db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            
            if fetch_one:
                result = cursor.fetchone()
                return dict(result) if result else None
            elif fetch_all:
                return self._rows_to_dict(cursor.fetchall())
            else:
                conn.commit()
                return cursor.lastrowid
    
    # === CACHE HELPERS ===
    def _cache_get(self, key):
        return self._cache.get(key)
    
    def _cache_set(self, key, value, ttl=None):
        self._cache.set(key, value, ttl)
    
    def _cache_delete_prefix(self, prefix):
        self._cache.delete_prefix(prefix)
    
    # === NORMALIZAÇÃO ===
    @staticmethod
    def _normalize_text(text):
        """Cache interno para textos normalizados"""
        if not isinstance(text, str):
            return ""
        nfkd = unicodedata.normalize('NFKD', text.lower())
        return "".join([c for c in nfkd if not unicodedata.combining(c)])
    
    # === OTIMIZAÇÃO DE _rows_to_dict ===
    def _rows_to_dict(self, rows, skip_json=False):
        """
        Converte rows em dict com opção de pular JSON parse
        skip_json=True: 50% mais rápido quando não precisa dos arrays
        """
        if not rows:
            return []
        
        items = []
        for row in rows:
            item = dict(row)
            
            if not skip_json:
                for field in ['genres', 'streams', 'providers', 'seasons_data', 'keywords', 'cast']:
                    if field in item and item[field]:
                        try:
                            if isinstance(item[field], str) and item[field].startswith('['):
                                item[field] = json.loads(item[field])
                            else:
                                item[field] = []
                        except (json.JSONDecodeError, TypeError):
                            item[field] = []
            
            for field in ['collection', 'certification', 'original_title', 'imdb_id', 
                         'clearlogo', 'synopsis', 'poster', 'backdrop']:
                if field in item and (item[field] == 'None' or item[field] is None):
                    item[field] = ''
            
            numeric_defaults = {
                'rating': 0.0, 'runtime': 0, 'year': 0, 
                'popularity': 0.0, 'revenue': 0, 'playcount': 0,
                'vote_count': 0
            }
            for field, default in numeric_defaults.items():
                if field in item:
                    try:
                        item[field] = float(item[field]) if '.' in str(default) else int(item[field])
                    except (ValueError, TypeError):
                        item[field] = default
            
            items.append(item)
        
        return items
    
    def run_first_time_setup(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            self._create_all_tables(cursor)
            conn.commit()
        finally:
            self._release_conn(conn)
    
    def _create_all_tables(self, cursor):
        self._create_movies_table(cursor)
        self._create_tvshows_table(cursor)
        self._create_favorites_table(cursor)
        self._create_watchlist_table(cursor)
        self._create_watch_history_table(cursor)
        self._create_seasons_cache_table(cursor)
        self._create_episodes_cache_table(cursor)
        self._create_api_cache_table(cursor)
        self._create_collections_meta_table(cursor)
        self._create_fts_tables(cursor)
    
    # === TABELAS COM ÍNDICES COMPOSTOS ===
    def _create_movies_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                tmdb_id INTEGER PRIMARY KEY, title TEXT NOT NULL, original_title TEXT, 
                romaji_title TEXT,
                title_normalized TEXT, year INTEGER, imdb_id TEXT, rating REAL,
                poster TEXT, backdrop TEXT, synopsis TEXT, date_added TEXT, runtime INTEGER, 
                popularity REAL, revenue REAL, collection TEXT, genres TEXT, 
                genres_normalized TEXT, streams TEXT, providers TEXT, clearlogo TEXT,
                playcount INTEGER DEFAULT 0, popularity_updated TEXT, certification TEXT,
                keywords TEXT, vote_count INTEGER DEFAULT 0, is_4k INTEGER DEFAULT 0, cast TEXT
            )
        ''')
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_popularity ON movies(popularity DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_revenue ON movies(revenue DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_date_added ON movies(date_added DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_rating ON movies(rating DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_romaji ON movies(romaji_title)")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_movies_genre_popularity 
            ON movies(genres_normalized, popularity DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_movies_year_rating 
            ON movies(year DESC, rating DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_movies_rating_votes 
            ON movies(rating DESC, vote_count DESC)
        """)
    
    def _create_tvshows_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tvshows (
                tmdb_id INTEGER PRIMARY KEY, title TEXT NOT NULL, original_title TEXT NOT NULL, 
                romaji_title TEXT,
                title_normalized TEXT, year INTEGER, imdb_id TEXT, poster TEXT, backdrop TEXT, 
                synopsis TEXT, providers TEXT, certification TEXT, date_added TEXT,
                popularity REAL, rating REAL, genres TEXT, genres_normalized TEXT, 
                seasons_data TEXT, clearlogo TEXT, banner TEXT, landscape TEXT,
                playcount INTEGER DEFAULT 0, season_count INTEGER DEFAULT 0,
                episodes_count INTEGER DEFAULT 0, status TEXT, popularity_updated TEXT,
                keywords TEXT, vote_count INTEGER DEFAULT 0, cast TEXT
            )
        ''')
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_popularity ON tvshows(popularity DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_date_added ON tvshows(date_added DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_rating ON tvshows(rating DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_romaji ON tvshows(romaji_title)")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tvshows_genre_popularity 
            ON tvshows(genres_normalized, popularity DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tvshows_rating_votes 
            ON tvshows(rating DESC, vote_count DESC)
        """)
        
    def _upgrade_add_cast_column(self):
        """Adiciona coluna cast em movies e tvshows (migration segura)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(movies)")
            cols = {c[1] for c in cursor.fetchall()}
            if 'cast' not in cols:
                cursor.execute("ALTER TABLE movies ADD COLUMN cast TEXT")

            cursor.execute("PRAGMA table_info(tvshows)")
            cols = {c[1] for c in cursor.fetchall()}
            if 'cast' not in cols:
                cursor.execute("ALTER TABLE tvshows ADD COLUMN cast TEXT")

            conn.commit()
        except Exception as e:
            xbmc.log(f"[DB] Erro upgrade cast: {e}", xbmc.LOGERROR)
        finally:
            self._release_conn(conn)    
    
    def _create_favorites_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                tmdb_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                profile_id TEXT DEFAULT 'default',
                PRIMARY KEY (tmdb_id, media_type, profile_id)
            )
        ''')

    def _create_watchlist_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                tmdb_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                profile_id TEXT DEFAULT 'default',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tmdb_id, media_type, profile_id)
            )
        ''')
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watchlist_profile
            ON watchlist(profile_id, added_at DESC)
        """)

    def _create_watch_history_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watch_history (
                tmdb_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                profile_id TEXT DEFAULT 'default',
                season INTEGER,
                episode INTEGER,
                progress REAL DEFAULT 0.0,
                watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tmdb_id, media_type, profile_id, season, episode)
            )
        ''')
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watch_history_profile
            ON watch_history(profile_id, watched_at DESC)
        """)
    
    def _create_seasons_cache_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seasons_cache (
                tvshow_tmdb_id INTEGER NOT NULL, season_number INTEGER NOT NULL,
                name TEXT, overview TEXT, poster_path TEXT, air_date TEXT,
                episode_count INTEGER, vote_average REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tvshow_tmdb_id, season_number),
                FOREIGN KEY (tvshow_tmdb_id) REFERENCES tvshows(tmdb_id) ON DELETE CASCADE
            )
        ''')
    
    def _create_episodes_cache_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS episodes_cache (
                tvshow_tmdb_id INTEGER NOT NULL, season_number INTEGER NOT NULL,
                episode_number INTEGER NOT NULL, name TEXT, overview TEXT,
                still_path TEXT, air_date TEXT, vote_average REAL, runtime INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tvshow_tmdb_id, season_number, episode_number),
                FOREIGN KEY (tvshow_tmdb_id) REFERENCES tvshows(tmdb_id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_tvshow_season ON episodes_cache(tvshow_tmdb_id, season_number)')
        
    def _upgrade_episodes_cache_pk(self):
        """
        Garante PK composta em episodes_cache.
        Se a tabela antiga permitia duplicatas, migra mantendo o registro mais recente.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episodes_cache'")
            if not cursor.fetchone():
                return

            cursor.execute("PRAGMA table_info(episodes_cache)")
            cols = cursor.fetchall()
            has_pk = any(c[5] > 0 for c in cols)  # coluna 'pk' > 0
            if has_pk:
                return

            xbmc.log("[DB] Migrando episodes_cache para PK composta...", xbmc.LOGINFO)
            cursor.execute("BEGIN")

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodes_cache_new (
                    tvshow_tmdb_id INTEGER NOT NULL,
                    season_number INTEGER NOT NULL,
                    episode_number INTEGER NOT NULL,
                    name TEXT,
                    overview TEXT,
                    still_path TEXT,
                    air_date TEXT,
                    vote_average REAL,
                    runtime INTEGER,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tvshow_tmdb_id, season_number, episode_number),
                    FOREIGN KEY (tvshow_tmdb_id) REFERENCES tvshows(tmdb_id) ON DELETE CASCADE
                )
            ''')

            cursor.execute('''
                INSERT OR IGNORE INTO episodes_cache_new (
                    tvshow_tmdb_id, season_number, episode_number, name, overview,
                    still_path, air_date, vote_average, runtime, last_updated
                )
                SELECT
                    tvshow_tmdb_id, season_number, episode_number, name, overview,
                    still_path, air_date, vote_average, runtime, last_updated
                FROM episodes_cache
                ORDER BY last_updated DESC, rowid DESC
            ''')

            cursor.execute("DROP TABLE episodes_cache")
            cursor.execute("ALTER TABLE episodes_cache_new RENAME TO episodes_cache")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_tvshow_season ON episodes_cache(tvshow_tmdb_id, season_number)")

            conn.commit()
            xbmc.log("[DB] Migração episodes_cache concluída.", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[DB] Erro no upgrade episodes_cache PK: {e}", xbmc.LOGERROR)
            try:
                conn.rollback()
            except:
                pass
        finally:
            self._release_conn(conn)    
        
        
    
    def _create_api_cache_table(self, cursor):
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY, data_json TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_cache_timestamp ON api_cache(timestamp)")
    
    def _create_collections_meta_table(self, cursor):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collections_meta (
                collection_name TEXT PRIMARY KEY, poster TEXT, backdrop TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def _create_fts_tables(self, cursor):
        """Cria tabelas FTS para busca ULTRA-RÁPIDA"""
        try:
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS movies_fts 
                USING fts5(tmdb_id UNINDEXED, title, romaji_title, content=movies, content_rowid=tmdb_id)
            ''')
            
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS tvshows_fts 
                USING fts5(tmdb_id UNINDEXED, title, romaji_title, content=tvshows, content_rowid=tmdb_id)
            ''')
            
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS movies_fts_insert AFTER INSERT ON movies BEGIN
                    INSERT INTO movies_fts(tmdb_id, title, romaji_title) VALUES (new.tmdb_id, new.title, new.romaji_title);
                END
            ''')
            
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS movies_fts_update AFTER UPDATE ON movies BEGIN
                    UPDATE movies_fts SET title = new.title, romaji_title = new.romaji_title WHERE tmdb_id = new.tmdb_id;
                END
            ''')
            
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tvshows_fts_insert AFTER INSERT ON tvshows BEGIN
                    INSERT INTO tvshows_fts(tmdb_id, title, romaji_title) 
                    VALUES (new.tmdb_id, new.title, new.romaji_title);
                END
            ''')
        
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS tvshows_fts_update AFTER UPDATE ON tvshows BEGIN
                    UPDATE tvshows_fts 
                    SET title = new.title, romaji_title = new.romaji_title 
                    WHERE tmdb_id = new.tmdb_id;
                END
            ''')
        except sqlite3.OperationalError as e:
            pass
    
    def search_items(self, query, limit=20, offset=0):
        """
        Busca otimizada com FTS (quando disponível) ou LIKE (fallback).
        
        ✅ Verifica se tabelas FTS existem
        ✅ Usa FTS quando disponível (100x mais rápido)
        ✅ Fallback para LIKE quando FTS não existe
        """
        cache_key = f"search:{query}:{limit}:{offset}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached
        
        has_fts = self._check_fts_exists()
        
        if has_fts:
            return self._search_with_fts(query, limit, offset, cache_key)
        else:
            return self._search_with_like(query, limit, offset, cache_key)
    
    def _check_fts_exists(self):
        """
        Verifica se tabelas FTS existem.
        Resultado é cacheado para evitar queries repetidas.
        """
        cache_key = "_fts_exists"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='movies_fts'
            """)
            movies_fts_exists = cursor.fetchone() is not None
            
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='tvshows_fts'
            """)
            tvshows_fts_exists = cursor.fetchone() is not None
            
            has_fts = movies_fts_exists and tvshows_fts_exists
            
            self._cache_set(cache_key, has_fts, ttl=3600)
            
            
            return has_fts
            
        finally:
            self._release_conn(conn)
    
    def _search_with_fts(self, query, limit, offset, cache_key):
        """Busca RÁPIDA usando FTS5 (100x mais rápido que LIKE)"""
        fts_query = self._normalize_text(query)
        
        sql = """
            SELECT m.*, 'movie' AS media_type
            FROM movies m
            JOIN movies_fts ON movies_fts.tmdb_id = m.tmdb_id
            WHERE movies_fts MATCH ?
            
            UNION ALL
            
            SELECT t.*, 'tvshow' AS media_type
            FROM tvshows t
            JOIN tvshows_fts ON tvshows_fts.tmdb_id = t.tmdb_id
            WHERE tvshows_fts MATCH ?
            
            LIMIT ? OFFSET ?
        """
        
        results = self._execute_query(sql, (fts_query, fts_query, limit, offset))
        self._cache_set(cache_key, results, ttl=600)  # 10 min
        return results
    
    def _search_with_like(self, query, limit, offset, cache_key):
        """
        Busca FALLBACK usando LIKE (mais lenta mas sempre funciona).
        Usada quando tabelas FTS não existem.
        
        IMPORTANTE: 
        - Normaliza a query (remove acentos, lowercase)
        - Busca nos campos *_normalized para ignorar acentos
        - Seleciona apenas colunas comuns entre movies e tvshows
        """
        normalized_query = self._normalize_text(query)
        like_query = f"%{normalized_query}%"
        
        
        sql = """
            SELECT 
                m.tmdb_id, m.title, m.original_title, m.year, 
                m.imdb_id, m.rating, m.poster, m.backdrop, 
                m.synopsis, m.clearlogo, m.genres, m.popularity,
                m.date_added, m.playcount,
                'movie' AS media_type
            FROM movies m
            WHERE m.title_normalized LIKE ? 
               OR m.synopsis LIKE ?
            
            UNION ALL
            
            SELECT 
                t.tmdb_id, t.title, t.original_title, t.year,
                t.imdb_id, t.rating, t.poster, t.backdrop,
                t.synopsis, t.clearlogo, t.genres, t.popularity,
                t.date_added, t.playcount,
                'tvshow' AS media_type
            FROM tvshows t
            WHERE t.title_normalized LIKE ?
               OR t.synopsis LIKE ?
            
            ORDER BY 2 ASC
            
            LIMIT ? OFFSET ?
        """
        
        params = (
            like_query, like_query, 
            like_query, like_query,
            limit, offset
        )
        
        results = self._execute_query(sql, params)
        self._cache_set(cache_key, results, ttl=600)
        
        return results
    
    # === MÉTODOS AUXILIARES ===
    def vacuum(self):
        """Otimiza e compacta o banco"""
        conn = self._get_conn()
        try:
            conn.execute("VACUUM")
        finally:
            self._release_conn(conn)
            
    def optimize(self):
        """Manutenção leve do SQLite (estatísticas/planejador)."""
        conn = self._get_conn()
        try:
            conn.execute("PRAGMA optimize")
        except Exception as e:
            xbmc.log(f"[DB] Erro no optimize: {e}", xbmc.LOGERROR)
        finally:
            self._release_conn(conn)        
    
    def get_db_size(self):
        """Retorna tamanho do banco em MB"""
        if os.path.exists(self.db_file):
            size_bytes = os.path.getsize(self.db_file)
            return round(size_bytes / (1024 * 1024), 2)
        return 0
    
    def clear_api_cache(self):
        """Limpa cache de API antigo (>7 dias)"""
        sql = "DELETE FROM api_cache WHERE timestamp < datetime('now', '-7 days')"
        self._execute_query(sql, fetch_all=False)
    
    # === HELPERS PARA API CACHE ===
    def save_tmdb_cache(self, key, data):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO api_cache (cache_key, data_json) VALUES (?, ?)",
                (key, json.dumps(data))
            )
            conn.commit()
        finally:
            self._release_conn(conn)
    
    def get_tmdb_cache(self, key, hours=24):
        hours = int(hours)
        sql = f"SELECT data_json FROM api_cache WHERE cache_key = ? AND timestamp > datetime('now', '-{hours} hours')"
        result = self._execute_query(sql, (key,), fetch_one=True, fetch_all=False)
        return json.loads(result['data_json']) if result else None
    
    
    def get_watched_movies(self):
        """Retorna filmes com playcount > 0"""
        sql = """
            SELECT tmdb_id, imdb_id, title, playcount, 
                   datetime(date_added) as last_played
            FROM movies 
            WHERE playcount > 0
            ORDER BY date_added DESC
        """
        return self._execute_query(sql)
    
    def get_watched_tvshows(self):
        """Retorna séries com playcount > 0"""
        sql = """
            SELECT tmdb_id, imdb_id, title, playcount,
                   datetime(date_added) as last_played
            FROM tvshows 
            WHERE playcount > 0
            ORDER BY date_added DESC
        """
        return self._execute_query(sql)
    
    def update_movie_playcount(self, tmdb_id, playcount, last_played=None):
        """Atualiza playcount de um filme"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE movies 
                SET playcount = ?,
                    date_added = COALESCE(?, date_added)
                WHERE tmdb_id = ?
            """, (playcount, last_played, tmdb_id))
            
            conn.commit()
            self._cache_delete_prefix(f"movie_{tmdb_id}")
        finally:
            self._release_conn(conn)
    
    def update_tvshow_playcount(self, tmdb_id, last_played=None):
        """Atualiza playcount de uma série"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE tvshows 
                SET playcount = playcount + 1,
                    date_added = COALESCE(?, date_added)
                WHERE tmdb_id = ?
            """, (last_played, tmdb_id))
            
            conn.commit()
            self._cache_delete_prefix(f"tvshow_{tmdb_id}")
        finally:
            self._release_conn(conn)
    
    def mark_movie_as_watched(self, tmdb_id):
        """Marca filme como assistido"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE movies 
                SET playcount = playcount + 1,
                    date_added = CURRENT_TIMESTAMP
                WHERE tmdb_id = ?
            """, (tmdb_id,))
            
            conn.commit()
            self._cache_delete_prefix(f"movie_{tmdb_id}")
        finally:
            self._release_conn(conn)
    
    def get_all_favorites(self):
        """Retorna todos favoritos"""
        sql = """
            SELECT tmdb_id, media_type 
            FROM favorites
            ORDER BY rowid DESC
        """
        return self._execute_query(sql)
    
    # === LIMPEZA ===
    def clear_database(self, preserve_favorites=True):
        conn = self._get_conn()
        cursor = conn.cursor()

        # Salva favoritos
        saved_favorites = []
        if preserve_favorites:
            try:
                cursor.execute("SELECT tmdb_id, media_type, profile_id FROM favorites")
                saved_favorites = cursor.fetchall()
            except sqlite3.OperationalError:
                cursor.execute("SELECT tmdb_id, media_type FROM favorites")
                saved_favorites = [(tid, mtype, None) for tid, mtype in cursor.fetchall()]

        # Salva histórico
        saved_history = []
        try:
            cursor.execute("""
                SELECT tmdb_id, media_type, profile_id, season, episode, progress, watched_at
                FROM watch_history
            """)
            saved_history = cursor.fetchall()
        except Exception:
            pass

        # Salva ratings
        saved_ratings = []
        try:
            cursor.execute("""
                SELECT tmdb_id, media_type, profile_id, season, episode, liked, score, rated_at
                FROM user_ratings
            """)
            saved_ratings = cursor.fetchall()
        except Exception:
            pass

        # Salva metadados de coleções (poster/backdrop buscados via API)
        saved_collections_meta = []
        try:
            cursor.execute("SELECT collection_name, poster, backdrop FROM collections_meta")
            saved_collections_meta = cursor.fetchall()
        except Exception:
            pass

        # Drop e recria tudo
        for table in ['movies', 'tvshows', 'favorites', 'watchlist', 'watch_history',
                     'api_cache', 'seasons_cache', 'episodes_cache', 'collections_meta',
                     'movies_fts', 'tvshows_fts']:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")

        conn.commit()
        self._create_all_tables(cursor)

        # Restaura favoritos
        if saved_favorites:
            try:
                cursor.executemany(
                    "INSERT OR IGNORE INTO favorites (tmdb_id, media_type, profile_id) VALUES (?, ?, ?)",
                    saved_favorites
                )
            except sqlite3.OperationalError:
                cursor.executemany(
                    "INSERT OR IGNORE INTO favorites (tmdb_id, media_type) VALUES (?, ?)",
                    [(f[0], f[1]) for f in saved_favorites]
                )

        # Restaura histórico
        if saved_history:
            cursor.executemany("""
                INSERT OR IGNORE INTO watch_history
                    (tmdb_id, media_type, profile_id, season, episode, progress, watched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, saved_history)

        # Restaura ratings
        if saved_ratings:
            cursor.executemany("""
                INSERT OR IGNORE INTO user_ratings
                    (tmdb_id, media_type, profile_id, season, episode, liked, score, rated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, saved_ratings)

        # Restaura metadados de coleções (evita rebuscar na API)
        if saved_collections_meta:
            cursor.executemany(
                "INSERT OR IGNORE INTO collections_meta (collection_name, poster, backdrop) VALUES (?, ?, ?)",
                saved_collections_meta
            )

        conn.commit()
        self._release_conn(conn)
        self._cache.clear()