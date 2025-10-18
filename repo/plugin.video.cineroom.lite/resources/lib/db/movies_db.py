# Em: resources/lib/db/movies_db.py

from .base_db import BaseDatabase
import json
import xbmc
import sqlite3 


class MoviesDatabase(BaseDatabase):
    
    def add_movies_bulk(self, movies_list):
        data_to_insert = []
        
        for movie in movies_list:
            title_norm = self._normalize_text(movie.get('title', ''))
            genres = movie.get('genres', [])
            normalized_genres = [self._normalize_text(g) for g in genres]
            date_added = movie.get('date_added')
            
            data_to_insert.append((
                movie.get('tmdb_id'),
                movie.get('title'),
                title_norm,
                movie.get('year'),
                movie.get('imdb_id'),
                movie.get('rating'),
                movie.get('poster'),
                movie.get('backdrop'),
                movie.get('synopsis'),
                date_added,
                movie.get('runtime', 0),
                movie.get('popularity', 0.0),
                movie.get('revenue', 0),
                
                # --- CORREÇÃO AQUI ---
                # Converte o dicionário 'collection' para uma string JSON
                movie.get('collection'),
                
                json.dumps(genres),
                json.dumps(normalized_genres),
                json.dumps(movie.get('streams', [])),
                
                movie.get('clearlogo'),
                movie.get('playcount', 0)
            ))

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT OR REPLACE INTO movies (
                tmdb_id, title, title_normalized, year, imdb_id, rating, poster, backdrop, synopsis, 
                date_added, runtime, popularity, revenue, collection, 
                genres, genres_normalized, streams,
                clearlogo, playcount
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', data_to_insert)
        conn.commit()
        conn.close()

    def get_movie_by_id(self, tmdb_id):
        """✅ A FUNÇÃO QUE FALTAVA: Busca um filme específico pelo seu TMDB ID."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM movies WHERE tmdb_id = ?", (int(tmdb_id),))
        result = cursor.fetchone()
        conn.close()
        
        if not result: return None
        
        movie = dict(result)
        movie['genres'] = json.loads(movie['genres']) if movie.get('genres') else []
        movie['streams'] = json.loads(movie['streams']) if movie.get('streams') else []
        return movie
        
    def get_all_movie_ids_set(self):
        try:
            with self._get_conn_internal() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT tmdb_id FROM movies")
                return set(row[0] for row in cursor.fetchall())
        except Exception as e:
            xbmc.log(f"[DB ERROR] Falha ao buscar IDs de filmes: {e}", xbmc.LOGERROR)
            return set()  # Retorna um set vazio em caso de erro
    

    def get_movies_by_genre(self, genre, page=1, items_per_page=50):
        offset = (page - 1) * items_per_page
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        normalized_genre = self._normalize_text(genre)
        
        xbmc.log(f"[DEBUG DB-READ] Procurando por Gênero: '{genre}' | Usando Apelido: '{normalized_genre}'", xbmc.LOGWARNING)
        
        # ✅ CORREÇÃO 2: A busca precisa usar a coluna 'genres_normalized'
        cursor.execute(
            "SELECT * FROM movies WHERE genres_normalized LIKE ? ORDER BY popularity DESC LIMIT ? OFFSET ?",
            (f'%"{normalized_genre}"%', items_per_page, offset)
        )
        results = cursor.fetchall()
        conn.close()
        
        movies = []
        for row in results:
            movie = dict(row)
            try:
                movie['genres'] = json.loads(movie['genres']) if movie['genres'] else []
                movie['streams'] = json.loads(movie['streams']) if movie['streams'] else []
            except (json.JSONDecodeError, TypeError):
                movie['genres'] = []
                movie['streams'] = []
            movies.append(movie)
        return movies
        
    def get_movies_by_popularity(self, page=1, page_size=150):
        """Busca filmes ordenados por popularidade, do maior para o menor."""
        offset = (page - 1) * page_size
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row # Essencial para _rows_to_dict funcionar
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM movies ORDER BY popularity DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        results = cursor.fetchall()
        conn.close()
        return self._rows_to_dict(results)
        
        
    def get_movies_by_revenue(self, page=1, page_size=50):
        offset = (page - 1) * page_size
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM movies ORDER BY revenue DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        results = cursor.fetchall()
        conn.close()
        return self._rows_to_dict(results)

      

    def get_4k_movies(self, page=1, page_size=150):
        """Busca filmes que tenham '4K' ou '2160p' na string de streams."""
        offset = (page - 1) * page_size
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM movies WHERE streams LIKE '%4K%' OR streams LIKE '%2160p%' ORDER BY popularity DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        results = cursor.fetchall()
        conn.close()
        return self._rows_to_dict(results)

    # Em: resources/lib/database.py

    def get_all_collections(self):
        """
        Retorna uma lista de coleções que contêm 2 ou mais filmes,
        junto com um pôster de um dos filmes.
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row # Para facilitar a conversão para dicionário
        cursor = conn.cursor()
    
        # Esta query mais avançada faz todo o trabalho pesado
        cursor.execute('''
            SELECT
                collection,
                MIN(poster) as poster, -- Pega um poster (o primeiro em ordem alfabética) do grupo
                COUNT(tmdb_id) as movie_count -- Conta quantos filmes tem no grupo
            FROM movies
            WHERE collection IS NOT NULL AND collection != ''
            GROUP BY collection -- Agrupa todos os filmes com o mesmo nome de coleção
            HAVING movie_count >= 2 -- Filtra para mostrar apenas grupos com 2 ou mais filmes
            ORDER BY collection -- Ordena o resultado final pelo nome da coleção
        ''')
    
        results = cursor.fetchall()
        conn.close()
    
        # Usa a função que já temos para converter o resultado em uma lista de dicionários
        return self._rows_to_dict(results)

    def get_movies_by_collection(self, collection_name):
        """Retorna todos os filmes de uma coleção específica, ordenados por ano."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM movies WHERE collection = ? ORDER BY year",
            (collection_name,)
        )
        results = cursor.fetchall()
        conn.close()
        return self._rows_to_dict(results)       
        
    
    def get_all_unique_years(self):
        """Retorna uma lista de todos os anos únicos, ordenados do mais novo para o mais antigo."""
        conn = self._get_conn()
        cursor = conn.cursor()
        # DISTINCT garante que cada ano apareça apenas uma vez
        cursor.execute("SELECT DISTINCT year FROM movies WHERE year IS NOT NULL ORDER BY year DESC")
        # fetchall() retorna uma lista de tuplas, ex: [(2025,), (2024,)]
        results = cursor.fetchall()
        conn.close()
        # Transforma a lista de tuplas em uma lista simples de números
        return [row[0] for row in results]

    def get_movies_by_year(self, year, page=1, items_per_page=50):
        """Busca filmes de um ano específico com paginação."""
        offset = (page - 1) * items_per_page
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM movies WHERE year = ? ORDER BY rating DESC LIMIT ? OFFSET ?",
            (year, items_per_page, offset)
        )
        results = cursor.fetchall()
        conn.close()
        
        # O mesmo código de deserialização que usamos antes
        movies = []
        for row in results:
            movie = dict(row)
            movie['genres'] = json.loads(movie['genres']) if movie['genres'] else []
            movie['streams'] = json.loads(movie['streams']) if movie['streams'] else []
            movies.append(movie)
        return movies
    
    def get_all_unique_genres(self):
        """
        Lê todos os filmes do banco e retorna uma lista única e ordenada de todos os gêneros.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT genres FROM movies")
        results = cursor.fetchall()
        conn.close()
        
        all_genres = set()
        for row in results:
            try:
                # O resultado de 'row' é uma tupla, então pegamos o primeiro item
                genres_list = json.loads(row[0])
                # Adiciona cada gênero do filme ao nosso set (que automaticamente remove duplicatas)
                for genre in genres_list:
                    all_genres.add(genre.strip())
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Converte o set para uma lista e a ordena alfabeticamente
        return sorted(list(all_genres))
        
    def get_recently_added_movies(self, page, page_size):
        """Busca os filmes mais recentes adicionados ao banco de dados."""
        offset = (page - 1) * page_size
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM movies WHERE date_added IS NOT NULL ORDER BY date_added DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        results = cursor.fetchall()
        conn.close()
        return self._rows_to_dict(results)
    
        
        
        conn.close()
        return results    