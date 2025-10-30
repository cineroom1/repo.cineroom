# Em: resources/lib/db/tvshows_db.py

from .base_db import BaseDatabase
import xbmc
import json
import sqlite3 



class TVShowsDatabase(BaseDatabase):
    
    def add_tvshows_bulk(self, tvshows_list):
        """Adiciona séries em massa ao banco de dados."""
        data_to_insert = []
        for show in tvshows_list:
            original_title = show.get('title', 'N/A')
            
            # --- CORREÇÃO AQUI ---
            # 1. Calcule 'title_norm' ANTES de usar
            original_title = show.get('original_title') or show.get('title', 'N/A')  # pega original_title se existir
            title_norm = self._normalize_text(original_title) 

            # 2. Agora o seu log vai funcionar, pois 'title_norm' existe
            log_msg = f"[DEBUG-ADD-SHOW] Título Original: '{original_title}', Título Normalizado: '{title_norm}'"
            xbmc.log(log_msg, level=xbmc.LOGINFO) # Mantive o seu log para debug

            genres = show.get('genres', [])
            normalized_genres = [self._normalize_text(g) for g in genres]
            date_added = show.get('date_added')

            data_to_insert.append((
                show.get('tmdb_id'),
                show.get('title'),
                original_title,
                title_norm,  # 3. E a inserção também funcionará!
                show.get('year'),
                show.get('imdb_id'),
                show.get('poster'),
                show.get('backdrop'),
                show.get('synopsis'),
                json.dumps(show.get('providers', [])),
                show.get('certification'),
                date_added,
                show.get('popularity', 0.0),
                show.get('rating', 0.0),
                json.dumps(genres),
                json.dumps(normalized_genres),
                json.dumps(show.get('temporadas', [])),
                show.get('clearlogo'),
                show.get('banner'),
                show.get('landscape'),
                show.get('playcount', 0),
                show.get('season_count', 0),
                show.get('episodes_count', 0),
                show.get('status')
            ))
        
        # O resto da função continua igual...
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.executemany('''
            INSERT OR REPLACE INTO tvshows (
                tmdb_id, title, original_title, title_normalized, year, imdb_id, poster, backdrop, synopsis,
                providers, certification, date_added, popularity,
                rating, genres, genres_normalized, seasons_data,
                clearlogo, banner, landscape, playcount,
                season_count, episodes_count, status
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', data_to_insert)
        conn.commit()
        conn.close()
        
    def get_tvshow_by_id(self, tmdb_id):
        """✅ NOVA FUNÇÃO para buscar uma série específica pelo ID."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tvshows WHERE tmdb_id = ?", (int(tmdb_id),))
        result = cursor.fetchone()
        conn.close()
        
        if not result: return None
            
        show = dict(result)
        show['genres'] = json.loads(show['genres']) if show['genres'] else []
        show['seasons_data'] = json.loads(show['seasons_data']) if show['seasons_data'] else []
        show['providers'] = json.loads(show['providers']) if show['providers'] else []
        return show    
        
    # Em: resources/lib/db/tvshows_db.py
# (Adicione estas funções dentro da classe TVShowsDatabase)

    def get_cached_seasons(self, tvshow_tmdb_id, max_age_hours=72):
        """
        Busca temporadas do cache local.
        Retorna None se o cache estiver velho ou não existir.
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Calcula o tempo limite do cache
        # (72 horas = 3 dias)
        cursor.execute(
            "SELECT * FROM seasons_cache WHERE tvshow_tmdb_id = ? AND last_updated > datetime('now', ?)",
            (tvshow_tmdb_id, f'-{max_age_hours} hours')
        )
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            xbmc.log(f"[CACHE-MISS] Temporadas para {tvshow_tmdb_id} não encontradas ou velhas.", xbmc.LOGINFO)
            return None
            
        xbmc.log(f"[CACHE-HIT] Carregando {len(results)} temporadas do DB para {tvshow_tmdb_id}.", xbmc.LOGINFO)
        # Converte o resultado (lista de Rows) para lista de dicts
        return [dict(row) for row in results]

    def save_seasons_cache(self, tvshow_tmdb_id, seasons_data_list):
        """
        Salva uma lista de temporadas (da API) no cache.
        """
        xbmc.log(f"[CACHE-SAVE] Salvando {len(seasons_data_list)} temporadas no DB para {tvshow_tmdb_id}.", xbmc.LOGINFO)
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. Limpa o cache antigo para esta série
        cursor.execute("DELETE FROM seasons_cache WHERE tvshow_tmdb_id = ?", (tvshow_tmdb_id,))
        
        # 2. Prepara os novos dados
        data_to_insert = []
        for season in seasons_data_list:
            data_to_insert.append((
                tvshow_tmdb_id,
                season.get('season_number', season.get('number', 0)),
                season.get('name'),
                season.get('overview'),
                f"https://image.tmdb.org/t/p/w500{season.get('poster_path')}" if season.get('poster_path') else None,
                season.get('air_date'),
                season.get('episode_count'),
                season.get('vote_average', 0.0)
            ))
            
        # 3. Insere os novos dados
        cursor.executemany('''
            INSERT INTO seasons_cache (
                tvshow_tmdb_id, season_number, name, overview, poster, 
                air_date, episode_count, vote_average
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', data_to_insert)
        
        conn.commit()
        conn.close()

    def get_cached_episodes(self, tvshow_tmdb_id, season_number, max_age_hours=72):
        """
        Busca episódios do cache local.
        Retorna None se o cache estiver velho ou não existir.
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM episodes_cache WHERE tvshow_tmdb_id = ? AND season_number = ? AND last_updated > datetime('now', ?)",
            (tvshow_tmdb_id, season_number, f'-{max_age_hours} hours')
        )
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            xbmc.log(f"[CACHE-MISS] Episódios para {tvshow_tmdb_id}-S{season_number} não encontrados ou velhos.", xbmc.LOGINFO)
            return None
            
        xbmc.log(f"[CACHE-HIT] Carregando {len(results)} episódios do DB para {tvshow_tmdb_id}-S{season_number}.", xbmc.LOGINFO)
        return [dict(row) for row in results]

    def save_episodes_cache(self, tvshow_tmdb_id, season_number, episodes_data_list):
        """
        Salva uma lista de episódios (da API) no cache.
        """
        xbmc.log(f"[CACHE-SAVE] Salvando {len(episodes_data_list)} episódios no DB para {tvshow_tmdb_id}-S{season_number}.", xbmc.LOGINFO)
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 1. Limpa o cache antigo para esta temporada
        cursor.execute(
            "DELETE FROM episodes_cache WHERE tvshow_tmdb_id = ? AND season_number = ?", 
            (tvshow_tmdb_id, season_number)
        )
        
        # 2. Prepara os novos dados
        data_to_insert = []
        for ep in episodes_data_list:
            data_to_insert.append((
                tvshow_tmdb_id,
                season_number,
                ep.get('episode_number'),
                ep.get('name'),
                ep.get('overview'),
                ep.get('still_path'), # Salva só o path, constrói a URL na hora de ler
                ep.get('air_date'),
                ep.get('vote_average', 0.0),
                ep.get('runtime', 0)
            ))
            
        # 3. Insere os novos dados
        cursor.executemany('''
            INSERT INTO episodes_cache (
                tvshow_tmdb_id, season_number, episode_number, name, overview, 
                still_path, air_date, vote_average, runtime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', data_to_insert)
        
        conn.commit()
        conn.close()    
        
        
    def get_all_tvshow_ids_set(self):
        """Retorna um SET de todos os TMDB IDs de séries no DB."""
        # Usa a conexão interna, pois esta função é chamada fora de um 'with'
        try:
            # Assumindo que _get_conn_internal() existe na classe Base
            with self._get_conn_internal() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT tmdb_id FROM tvshows")
                
                id_set = set()
                for row in cursor.fetchall():
                    # Garante que o ID é um número válido antes de adicionar
                    if row and row[0] is not None:
                        try:
                            # Converte para int para garantir consistência
                            id_set.add(int(row[0]))
                        except (ValueError, TypeError):
                            # Ignora se o valor não for um número (ex: string vazia)
                            continue
                return id_set
                
        except Exception as e:
            xbmc.log(f"[DB ERROR] Falha ao buscar IDs de séries: {e}", xbmc.LOGERROR)
            return set() # Retorna um set vazio em caso de erro   

    def get_all_unique_tvshow_genres(self):
        """Retorna uma lista única e ordenada de todos os gêneros de SÉRIES."""
        conn = self._get_conn()
        cursor = conn.cursor()
        # A consulta agora é na tabela 'tvshows'
        cursor.execute("SELECT genres FROM tvshows")
        results = cursor.fetchall()
        conn.close()
        
        all_genres = set()
        for row in results:
            try:
                genres_list = json.loads(row[0])
                for genre in genres_list:
                    all_genres.add(genre.strip())
            except (json.JSONDecodeError, TypeError):
                continue
        
        return sorted(list(all_genres))

    def get_tvshows_by_genre(self, genre, page=1, items_per_page=20):
        """Busca séries por gênero com paginação."""
        offset = (page - 1) * items_per_page
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        normalized_genre = self._normalize_text(genre)
        
        # A consulta agora é na tabela 'tvshows' e na coluna correta
        cursor.execute(
            "SELECT * FROM tvshows WHERE genres_normalized LIKE ? ORDER BY popularity DESC LIMIT ? OFFSET ?",
            (f'%"{normalized_genre}"%', items_per_page, offset)
        )
        results = cursor.fetchall()
        conn.close()

        return self._rows_to_dict(results)

    def get_recently_added_tvshows(self, page, page_size):
        """Busca as séries mais recentes adicionadas ao banco de dados."""
        offset = (page - 1) * page_size
        # ✅ CORREÇÃO: Adiciona o gerenciamento de conexão e cursor
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            # ✅ MUDANÇA: Adiciona a condição WHERE para ignorar as datas vazias
            "SELECT * FROM tvshows WHERE date_added IS NOT NULL ORDER BY date_added DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        results = cursor.fetchall()
        conn.close()
        return self._rows_to_dict(results)

    def get_kids_tvshows(self, page, page_size):
        """Busca por séries com certificação livre ou para crianças."""
        offset = (page - 1) * page_size
        # ✅ CORREÇÃO: Adiciona o gerenciamento de conexão e cursor
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            # ✅ CORREÇÃO AQUI: Procurando por 'Kids' em vez de 'Infantil'
            "SELECT * FROM tvshows WHERE certification IN ('L', '10', '12') OR genres LIKE '%Kids%' ORDER BY popularity DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        results = cursor.fetchall()
        conn.close()
        return self._rows_to_dict(results)
        
    def get_tvshows_by_popularity(self, page=1, page_size=150):
        """Busca séries ordenadas por popularidade, do maior para o menor."""
        offset = (page - 1) * page_size
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row  # Essencial para _rows_to_dict funcionar
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tvshows ORDER BY popularity DESC LIMIT ? OFFSET ?",
            (page_size, offset)
        )
        results = cursor.fetchall()
        conn.close()
        return self._rows_to_dict(results)
    
    
    
        
    def get_tvshows_by_provider(self, provider, page=1, items_per_page=20):
        """Busca séries filtradas por provedor com paginação."""
        offset = (page - 1) * items_per_page
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tvshows WHERE providers LIKE ? ORDER BY popularity DESC LIMIT ? OFFSET ?",
            (f'%"{provider}"%', items_per_page, offset)
        )
        results = cursor.fetchall()
        conn.close()
        return self._rows_to_dict(results)
    

    def get_all_unique_providers(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT providers FROM tvshows")
        results = cursor.fetchall()
        conn.close()

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

            "paramount plus": "Paramount plus",

            "apple tv+": "Apple TV+",
            "apple tv plus": "Apple TV+",

            "crunchyroll": "Crunchyroll",
            "globoplay": "Globoplay",
            "looke": "Looke",
            "peacock": "Peacock",
            "hulu": "Hulu",
            "discovery+": "Discovery+",
        }

        all_providers = set()
        for row in results:
            try:
                providers_list = json.loads(row[0])
                for provider in providers_list:
                    prov = provider.strip().lower()
                    if prov in provider_map:
                        all_providers.add(provider_map[prov])
            except:
                continue

        return sorted(list(all_providers))
        
        
        conn.close()
        return results     
 