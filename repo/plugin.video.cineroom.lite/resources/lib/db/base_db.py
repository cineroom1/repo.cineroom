# Em: resources/lib/db/base_db.py

import sqlite3
import json
import os
import xbmcaddon
import xbmcvfs
import xbmc

import unicodedata # Adicione esta importação no topo

# --- Configurações do Banco de Dados ---
ADDON = xbmcaddon.Addon()
PROFILE_DIR = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
DB_FILE = os.path.join(PROFILE_DIR, 'cineroom.light.db')
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)


# --- Classe Base ---
class BaseDatabase:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        # Garante que as tabelas sejam criadas na primeira inicialização
        if not os.path.exists(self.db_file):
            self.run_first_time_setup()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_file, timeout=10.0)
    
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size = -8192")
        conn.execute("PRAGMA temp_store = MEMORY")
  
        return conn
    _get_conn_internal = _get_conn    

    def run_first_time_setup(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # --- SIMPLIFICADO ---
        # Este método agora cria TODAS as tabelas, incluindo as de cache
        self._create_all_tables(cursor)
        
        conn.commit()
        conn.close()
        
    def _normalize_text(self, text):
        """Converte para minúsculas e remove acentos."""
        if not isinstance(text, str): return ""
        nfkd_form = unicodedata.normalize('NFKD', text.lower())
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

    def _create_all_tables(self, cursor):
        """Chama os métodos individuais para criar cada tabela."""
        self._create_movies_table(cursor)
        self._create_tvshows_table(cursor)
        self._create_favorites_table(cursor)
        self._create_seasons_cache_table(cursor)
        self._create_episodes_cache_table(cursor)
    
    # ✅ LÓGICA DE CADA TABELA, AGORA EM MÉTODOS SEPARADOS E INDIVIDUAIS
    def _create_movies_table(self, cursor):
        """Cria a tabela de Filmes."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                tmdb_id INTEGER PRIMARY KEY, title TEXT NOT NULL, original_title TEXT, title_normalized TEXT, year INTEGER, imdb_id TEXT, rating REAL,
                poster TEXT, backdrop TEXT, synopsis TEXT, date_added TEXT, runtime INTEGER, popularity REAL, revenue REAL,
                collection TEXT, genres TEXT, genres_normalized TEXT, streams TEXT,
                clearlogo TEXT,
                playcount INTEGER DEFAULT 0
            )
        ''')
        # Índices OTIMIZADOS para ORDER BY DESC
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_title_normalized ON movies(title_normalized)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_popularity ON movies(popularity DESC)") # OTIMIZADO
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_revenue ON movies(revenue DESC)")       # OTIMIZADO
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_date_added ON movies(date_added DESC)") # OTIMIZADO
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year DESC)")             # OTIMIZADO
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_rating ON movies(rating DESC)")         # OTIMIZADO
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_collection ON movies(collection)")
        
        # Este índice é mantido, mas lembre-se: 'LIKE "%...%"' ainda é lento.
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_genres_normalized ON movies(genres_normalized)")
        

    def _create_tvshows_table(self, cursor):
        """Cria a tabela de Séries."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tvshows (
                tmdb_id INTEGER PRIMARY KEY, title TEXT NOT NULL, original_title TEXT NOT NULL, title_normalized TEXT, year INTEGER, imdb_id TEXT, poster TEXT,
                backdrop TEXT, synopsis TEXT, providers TEXT, certification TEXT, date_added TEXT,
                popularity REAL, rating REAL, genres TEXT, genres_normalized TEXT, seasons_data TEXT,
                clearlogo TEXT,
                banner TEXT,
                landscape TEXT,
                playcount INTEGER DEFAULT 0,
                season_count INTEGER DEFAULT 0,
                episodes_count INTEGER DEFAULT 0,
                status TEXT
            )
        ''')
        # Índices OTIMIZADOS para Séries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_title_normalized ON tvshows(title_normalized)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_popularity ON tvshows(popularity DESC)") # OTIMIZADO
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_date_added ON tvshows(date_added DESC)")   # OTIMIZADO
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_providers ON tvshows(providers)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_year ON tvshows(year DESC)")             # OTIMIZADO
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tvshows_rating ON tvshows(rating DESC)")         # NOVO E OTIMIZADO
        
    def _create_seasons_cache_table(self, cursor):
        """Cria a tabela de cache para Temporadas."""
        xbmc.log("[DB] Criando tabela 'seasons_cache'", xbmc.LOGINFO)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seasons_cache (
                season_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tvshow_tmdb_id INTEGER NOT NULL,
                season_number INTEGER NOT NULL,
                name TEXT,
                overview TEXT,
                poster TEXT,
                air_date TEXT,
                episode_count INTEGER,
                vote_average REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                FOREIGN KEY (tvshow_tmdb_id) REFERENCES tvshows (tmdb_id) ON DELETE CASCADE
            )
        ''')
        # Índice para acelerar a busca por ID de série
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_seasons_tvshow_id ON seasons_cache (tvshow_tmdb_id)')

    def _create_episodes_cache_table(self, cursor):
        """Cria a tabela de cache para Episódios."""
        xbmc.log("[DB] Criando tabela 'episodes_cache'", xbmc.LOGINFO)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS episodes_cache (
                episode_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                FOREIGN KEY (tvshow_tmdb_id) REFERENCES tvshows (tmdb_id) ON DELETE CASCADE
            )
        ''')
        # Índice para acelerar a busca por série + temporada
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_tvshow_season ON episodes_cache (tvshow_tmdb_id, season_number)')    

    def _create_favorites_table(self, cursor):
        """Cria a tabela de Favoritos."""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                tmdb_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                PRIMARY KEY (tmdb_id, media_type)
            )
        ''')
    
    def search_items(self, query):
        """
        Busca por filmes e séries em uma única consulta eficiente usando UNION ALL.
        Retorna uma lista combinada de resultados com informações para a UI.
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    
        search_term = f"%{self._normalize_text(query)}%"
    
        # ✅ MUDANÇA: Adicionamos synopsis e rating à consulta
        sql_query = """
            SELECT 
                tmdb_id, title, poster, year, synopsis, rating, imdb_id, 'movie' as item_type 
            FROM 
                movies 
            WHERE 
                title_normalized LIKE ?
        
            UNION ALL
        
            SELECT 
                tmdb_id, title, poster, year, synopsis, rating, NULL as imdb_id, 'tvshow' as item_type 
            FROM 
                tvshows 
            WHERE 
                title_normalized LIKE ?
        """
    
        cursor.execute(sql_query, (search_term, search_term))
    
        results = self._rows_to_dict(cursor.fetchall())
        conn.close()
    
        return results
    
    
    def _rows_to_dict(self, results):
        """Converte os resultados do cursor (com row_factory) em uma lista de dicionários."""
        items = []
        for row in results:
            item = dict(row)
            if 'genres' in item:
                try:
                    if item['genres'] and item['genres'].strip().startswith('['):
                        item['genres'] = json.loads(item['genres'])
                    else:
                        item['genres'] = []
                except (json.JSONDecodeError, TypeError):
                    item['genres'] = []        
            if 'streams' in item:
                item['streams'] = json.loads(item['streams']) if item['streams'] else []
            if 'seasons_data' in item:
                item['seasons_data'] = json.loads(item['seasons_data']) if item['seasons_data'] else []
            if 'providers' in item and item['providers']:
                item['providers'] = json.loads(item['providers'])    
            items.append(item)
        return items

    def clear_database(self, preserve_favorites=True):
        """Apaga e recria todas as tabelas, com opção de manter favoritos."""
        conn = self._get_conn()
        cursor = conn.cursor()

        saved_favorites = []
        if preserve_favorites:
            try:
                cursor.execute("SELECT tmdb_id, media_type FROM favorites")
                saved_favorites = cursor.fetchall()
            except sqlite3.OperationalError:
                pass  # Tabela ainda não existe

        cursor.execute("DROP TABLE IF EXISTS movies")
        cursor.execute("DROP TABLE IF EXISTS tvshows")
        cursor.execute("DROP TABLE IF EXISTS favorites")
        cursor.execute("DROP TABLE IF EXISTS seasons_cache")
        cursor.execute("DROP TABLE IF EXISTS episodes_cache")
        conn.commit()

        self._create_all_tables(cursor)

        if preserve_favorites and saved_favorites:
            cursor.executemany(
                "INSERT OR IGNORE INTO favorites (tmdb_id, media_type) VALUES (?, ?)",
                saved_favorites
            )
            conn.commit()

        conn.close()

