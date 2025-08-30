# resources/lib/cache_manager.py
import json
import hashlib
import xbmc
import xbmcgui
from datetime import datetime, timedelta

class CacheManager:
    def __init__(self, video_cache, ram_cache):
        self.video_cache = video_cache
        self.ram_cache = ram_cache
        self.processed_data = None
        self.last_processed_time = None
        self.CACHE_DURATION = 3600  # 1 hora em segundos
        
    def get_processed_data(self, force_refresh=False):
        """Obtém todos os dados processados de uma vez"""
        cache_key = "global_processed_data_v4"
        
        # Verificar se precisa atualizar
        current_time = datetime.now().timestamp()
        if (not force_refresh and self.processed_data and 
            self.last_processed_time and 
            (current_time - self.last_processed_time) < self.CACHE_DURATION):
            return self.processed_data
        
        # Tentar RAM cache
        cached_ram = self.ram_cache.get(cache_key)
        if cached_ram:
            self.processed_data = cached_ram
            self.last_processed_time = current_time
            return cached_ram
        
        # Tentar disco cache
        cached_disk = self.video_cache.get(cache_key)
        if cached_disk:
            try:
                self.processed_data = json.loads(cached_disk)
                self.ram_cache.set(cache_key, self.processed_data)
                self.last_processed_time = current_time
                return self.processed_data
            except:
                self.video_cache.delete(cache_key)
        
        # Processamento único de todos os dados
        from resources.lib.utils import get_all_videos
        all_videos = get_all_videos()
        
        if not all_videos:
            return {}
        
        # Processamento centralizado de TODOS os dados
        processed_data = self._process_all_data(all_videos)
        
        # Salvar em cache
        self.video_cache.set(cache_key, json.dumps(processed_data), expiry_hours=12)
        self.ram_cache.set(cache_key, processed_data)
        self.processed_data = processed_data
        self.last_processed_time = current_time
        
        return processed_data
    
    def _process_all_data(self, all_videos):
        """Processa todos os dados de uma vez só"""
        movies = [m for m in all_videos if m.get('type') == 'movie']
        
        # Estrutura para armazenar todos os dados processados
        processed = {
            'all_movies': movies,
            'by_popularity': [],
            'by_revenue': [],
            'by_rating': [],
            'legendados': [],
            'hdcam_movies': [],
            '4k_movies': [],
            'recent_movies': [],
            'by_genre': {},
            'by_provider': {},
            'by_country': {},
            'by_year': {},
            'by_keyword': {},
            'by_collection': {},
            'by_studio': {},
            'actors': {}
        }
        
        # Processamento em lote de todas as categorias
        self._process_categories(processed, movies)
        
        return processed
    
    def _process_categories(self, processed, movies):
        """Processa todas as categorias de uma vez"""
        seen_ids = set()
        unique_movies_pop = {}
        unique_movies_rev = {}
        unique_movies_rat = {}
        
        for movie in movies:
            tmdb_id = movie.get('tmdb_id')
            if not tmdb_id:
                continue
            
            # Remover duplicatas e processar categorias principais
            self._process_main_categories(movie, tmdb_id, processed, 
                                        unique_movies_pop, unique_movies_rev, 
                                        unique_movies_rat, seen_ids)
            
            # Processar categorias secundárias
            self._process_secondary_categories(movie, processed)
        
        # Ordenações finais
        processed['by_popularity'] = self._sort_movies(unique_movies_pop.values(), 'popularity')
        processed['by_revenue'] = self._sort_movies(unique_movies_rev.values(), 'revenue')
        processed['by_rating'] = self._sort_movies(unique_movies_rat.values(), 'rating')
        
        # Ordenar filmes recentes
        processed['recent_movies'] = sorted(
            [m for m in processed['recent_movies'] if m.get('date_added')],
            key=lambda x: x['date_added'],
            reverse=True
        )[:100]
    
    def _process_main_categories(self, movie, tmdb_id, processed, 
                               unique_movies_pop, unique_movies_rev, 
                               unique_movies_rat, seen_ids):
        """Processa categorias principais"""
        # Popularidade
        current_pop = movie.get('popularity', 0)
        if tmdb_id not in unique_movies_pop or current_pop > unique_movies_pop[tmdb_id].get('popularity', 0):
            unique_movies_pop[tmdb_id] = movie
        
        # Revenue
        if isinstance(movie.get('revenue'), (int, float)) and movie.get('revenue', 0) > 0:
            current_rev = movie.get('revenue', 0)
            if tmdb_id not in unique_movies_rev or current_rev > unique_movies_rev[tmdb_id].get('revenue', 0):
                unique_movies_rev[tmdb_id] = movie
        
        # Rating
        if movie.get('vote_count', 0) > 500:
            current_rat = movie.get('rating', 0)
            if tmdb_id not in unique_movies_rat or current_rat > unique_movies_rat[tmdb_id].get('rating', 0):
                unique_movies_rat[tmdb_id] = movie
        
        # Categorias booleanas
        if movie.get('legendado') is True:
            processed['legendados'].append(movie)
        if movie.get('hdcam') is True:
            processed['hdcam_movies'].append(movie)
        if movie.get('4K') is True:
            processed['4k_movies'].append(movie)
        if movie.get('date_added'):
            processed['recent_movies'].append(movie)
    
    def _process_secondary_categories(self, movie, processed):
        """Processa categorias secundárias"""
        # Gêneros
        for genre in movie.get('genres', []):
            if genre not in processed['by_genre']:
                processed['by_genre'][genre] = []
            processed['by_genre'][genre].append(movie)
        
        # Providers
        for provider in movie.get('providers', []):
            if provider not in processed['by_provider']:
                processed['by_provider'][provider] = []
            processed['by_provider'][provider].append(movie)
        
        # Países
        country = movie.get('original_language')
        if country:
            if country not in processed['by_country']:
                processed['by_country'][country] = []
            processed['by_country'][country].append(movie)
        
        # Anos
        year = movie.get('year')
        if year:
            if year not in processed['by_year']:
                processed['by_year'][year] = []
            processed['by_year'][year].append(movie)
        
        # Keywords
        for keyword in movie.get('keywords', []):
            if keyword not in processed['by_keyword']:
                processed['by_keyword'][keyword] = []
            processed['by_keyword'][keyword].append(movie)
        
        # Collections
        collection = movie.get('collection')
        if collection and collection.lower() != "null":
            if collection not in processed['by_collection']:
                processed['by_collection'][collection] = []
            processed['by_collection'][collection].append(movie)
        
        # Studios
        for studio in movie.get('studio', []):
            if studio not in processed['by_studio']:
                processed['by_studio'][studio] = []
            processed['by_studio'][studio].append(movie)
        
        # Atores
        for actor in movie.get('actors', []):
            if actor not in processed['actors']:
                processed['actors'][actor] = []
            processed['actors'][actor].append(movie)
    
    def _sort_movies(self, movies, key, reverse=True, limit=1000):
        """Ordena filmes por uma chave específica"""
        return sorted(
            movies,
            key=lambda x: x.get(key, 0),
            reverse=reverse
        )[:limit]
    
    def clear_cache(self):
        """Limpa todo o cache"""
        self.processed_data = None
        self.last_processed_time = None

# Inicializar o cache manager
from resources.lib.utils import VIDEO_CACHE, ram_cache_get, ram_cache_set
CACHE_MANAGER = CacheManager(VIDEO_CACHE, {
    'get': ram_cache_get,
    'set': ram_cache_set
})