# -*- coding: utf-8 -*-
"""
Sistema de Recomendações Personalizadas baseado no histórico do usuário
Adicione este arquivo como: resources/lib/recommendations.py
"""

import xbmc
import xbmcgui
from collections import Counter
from .db import db
from .tmdb_api import TMDB_API_KEY
import requests


class RecommendationEngine:
    """Engine de recomendações baseado em Machine Learning simplificado"""
    
    def __init__(self):
        self.weights = {
            'genre': 0.35,      # Peso para gêneros
            'year': 0.15,       # Peso para ano (preferências temporais)
            'rating': 0.20,     # Peso para avaliação
            'provider': 0.15,   # Peso para provedores
            'similar': 0.15     # Peso para conteúdo similar
        }
    
    def get_movie_recommendations(self, limit=20):
        """
        Gera recomendações de filmes baseado no histórico
        """
        xbmc.log("[Recommendations] Gerando recomendações de filmes...", xbmc.LOGINFO)
        
        # 1. Analisa histórico do usuário
        watched = db.get_watched_movies()
        
        if not watched or len(watched) < 3:
            xbmc.log(f"[Recommendations] Histórico insuficiente ({len(watched) if watched else 0} filmes)", xbmc.LOGINFO)
            return None  # Retorna None para exibir aviso
        
        # 2. Extrai preferências
        preferences = self._analyze_movie_preferences(watched)
        
        # 3. Busca candidatos no banco local
        candidates = self._get_movie_candidates(preferences, watched)
        
        # 4. Se não tiver candidatos suficientes, busca no TMDB
        if len(candidates) < limit:
            xbmc.log("[Recommendations] Buscando mais no TMDB...", xbmc.LOGINFO)
            tmdb_candidates = self._fetch_tmdb_recommendations(preferences, 'movie')
            candidates.extend(tmdb_candidates)
        
        # 5. Rankeia por relevância
        ranked = self._rank_candidates(candidates, preferences, 'movie')
        
        # 6. Remove duplicatas e limita
        seen_ids = set()
        unique_results = []
        for item in ranked:
            if item['tmdb_id'] not in seen_ids:
                seen_ids.add(item['tmdb_id'])
                unique_results.append(item)
                if len(unique_results) >= limit:
                    break
        
        xbmc.log(f"[Recommendations] {len(unique_results)} filmes recomendados", xbmc.LOGINFO)
        return unique_results
    
    def get_tvshow_recommendations(self, limit=20):
        """
        Gera recomendações de séries baseado no histórico
        """
        xbmc.log("[Recommendations] Gerando recomendações de séries...", xbmc.LOGINFO)
        
        watched = db.get_watched_tvshows()
        
        if not watched or len(watched) < 2:
            xbmc.log(f"[Recommendations] Histórico insuficiente ({len(watched) if watched else 0} séries)", xbmc.LOGINFO)
            return None  # Retorna None para exibir aviso
        
        preferences = self._analyze_tvshow_preferences(watched)
        candidates = self._get_tvshow_candidates(preferences, watched)
        
        if len(candidates) < limit:
            tmdb_candidates = self._fetch_tmdb_recommendations(preferences, 'tvshow')
            candidates.extend(tmdb_candidates)
        
        ranked = self._rank_candidates(candidates, preferences, 'tvshow')
        
        seen_ids = set()
        unique_results = []
        for item in ranked:
            if item['tmdb_id'] not in seen_ids:
                seen_ids.add(item['tmdb_id'])
                unique_results.append(item)
                if len(unique_results) >= limit:
                    break
        
        xbmc.log(f"[Recommendations] {len(unique_results)} séries recomendadas", xbmc.LOGINFO)
        return unique_results
    
    def _analyze_movie_preferences(self, watched_movies):
        """
        Analisa padrões no histórico de filmes
        """
        genres = []
        years = []
        ratings = []
        providers = []
        
        for movie in watched_movies:
            # Busca dados completos
            full_data = db.get_movie_by_id(movie['tmdb_id'])
            if not full_data:
                continue
            
            # Coleta gêneros
            if full_data.get('genres'):
                genres.extend(full_data['genres'])
            
            # Coleta anos
            if full_data.get('year'):
                years.append(full_data['year'])
            
            # Coleta ratings
            if full_data.get('rating'):
                ratings.append(full_data['rating'])
            
            # Coleta provedores
            if full_data.get('providers'):
                providers.extend(full_data['providers'])
        
        # Calcula preferências
        genre_counts = Counter(genres)
        provider_counts = Counter(providers)
        
        preferences = {
            'top_genres': [g for g, _ in genre_counts.most_common(5)],
            'avg_year': sum(years) / len(years) if years else 2020,
            'min_rating': sum(ratings) / len(ratings) * 0.7 if ratings else 6.0,
            'top_providers': [p for p, _ in provider_counts.most_common(3)],
            'year_range': (min(years), max(years)) if years else (2015, 2024)
        }
        
        xbmc.log(f"[Recommendations] Preferências: {preferences}", xbmc.LOGDEBUG)
        return preferences
    
    def _analyze_tvshow_preferences(self, watched_shows):
        """
        Analisa padrões no histórico de séries
        """
        genres = []
        ratings = []
        providers = []
        
        for show in watched_shows:
            full_data = db.get_tvshow_by_id(show['tmdb_id'])
            if not full_data:
                continue
            
            if full_data.get('genres'):
                genres.extend(full_data['genres'])
            
            if full_data.get('rating'):
                ratings.append(full_data['rating'])
            
            if full_data.get('providers'):
                providers.extend(full_data['providers'])
        
        genre_counts = Counter(genres)
        provider_counts = Counter(providers)
        
        preferences = {
            'top_genres': [g for g, _ in genre_counts.most_common(5)],
            'min_rating': sum(ratings) / len(ratings) * 0.7 if ratings else 6.5,
            'top_providers': [p for p, _ in provider_counts.most_common(3)]
        }
        
        return preferences
    
    def _get_movie_candidates(self, preferences, watched):
        """
        Busca candidatos no banco local
        """
        watched_ids = [m['tmdb_id'] for m in watched]
        candidates = []
        
        # Busca por gêneros preferidos (posicional: genre, page, limit)
        for genre in preferences['top_genres'][:3]:
            movies = db.get_movies_by_genre(genre, 1, 20)
            candidates.extend([m for m in movies if m['tmdb_id'] not in watched_ids])
        
        # Busca por ano similar (posicional: year, page, limit)
        year_start, year_end = preferences['year_range']
        for year in range(year_end - 2, year_end + 1):
            movies = db.get_movies_by_year(year, 1, 10)
            candidates.extend([m for m in movies if m['tmdb_id'] not in watched_ids])
        
        return candidates
    
    def _get_tvshow_candidates(self, preferences, watched):
        """
        Busca candidatos de séries no banco local
        """
        watched_ids = [s['tmdb_id'] for s in watched]
        candidates = []
        
        # Busca por gêneros preferidos (posicional: genre, page, limit)
        for genre in preferences['top_genres'][:3]:
            shows = db.get_tvshows_by_genre(genre, 1, 20)
            candidates.extend([s for s in shows if s['tmdb_id'] not in watched_ids])
        
        return candidates
    
    def _fetch_tmdb_recommendations(self, preferences, media_type):
        """
        Busca recomendações adicionais no TMDB
        """
        if not TMDB_API_KEY:
            return []
        
        try:
            # Usa endpoint de discover com filtros baseados em preferências
            endpoint = 'movie' if media_type == 'movie' else 'tv'
            
            params = {
                'api_key': TMDB_API_KEY,
                'language': 'pt-BR',
                'sort_by': 'popularity.desc',
                'vote_average.gte': preferences.get('min_rating', 6.0),
                'page': 1
            }
            
            # Adiciona gêneros
            if preferences.get('top_genres'):
                genre_ids = self._get_genre_ids(preferences['top_genres'][:2], media_type)
                if genre_ids:
                    params['with_genres'] = ','.join(map(str, genre_ids))
            
            # Adiciona range de ano para filmes
            if media_type == 'movie' and preferences.get('year_range'):
                year_start, year_end = preferences['year_range']
                params['primary_release_date.gte'] = f"{year_start}-01-01"
                params['primary_release_date.lte'] = f"{year_end}-12-31"
            
            url = f"https://api.themoviedb.org/3/discover/{endpoint}"
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('results', [])[:10]:
                results.append(self._parse_tmdb_item(item, media_type))
            
            return results
            
        except Exception as e:
            xbmc.log(f"[Recommendations] Erro ao buscar TMDB: {e}", xbmc.LOGERROR)
            return []
    
    def _get_genre_ids(self, genre_names, media_type):
        """
        Converte nomes de gêneros para IDs do TMDB
        """
        # Mapeamento básico (você pode expandir)
        genre_map = {
            'Ação': 28, 'Aventura': 12, 'Animação': 16, 'Comédia': 35,
            'Crime': 80, 'Documentário': 99, 'Drama': 18, 'Família': 10751,
            'Fantasia': 14, 'História': 36, 'Terror': 27, 'Música': 10402,
            'Mistério': 9648, 'Romance': 10749, 'Ficção científica': 878,
            'Cinema TV': 10770, 'Thriller': 53, 'Guerra': 10752, 'Faroeste': 37
        }
        
        return [genre_map.get(name) for name in genre_names if name in genre_map]
    
    def _parse_tmdb_item(self, item, media_type):
        """
        Converte item do TMDB para formato do banco
        """
        if media_type == 'movie':
            return {
                'tmdb_id': item['id'],
                'title': item.get('title', ''),
                'original_title': item.get('original_title', ''),
                'year': int(item.get('release_date', '2000')[:4]) if item.get('release_date') else 2000,
                'rating': item.get('vote_average', 0.0),
                'poster': f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item.get('poster_path') else '',
                'backdrop': f"https://image.tmdb.org/t/p/w1280{item['backdrop_path']}" if item.get('backdrop_path') else '',
                'synopsis': item.get('overview', ''),
                'popularity': item.get('popularity', 0.0),
                'genres': [],  # Seria necessário buscar separadamente
                'providers': []
            }
        else:
            return {
                'tmdb_id': item['id'],
                'title': item.get('name', ''),
                'original_title': item.get('original_name', ''),
                'year': int(item.get('first_air_date', '2000')[:4]) if item.get('first_air_date') else 2000,
                'rating': item.get('vote_average', 0.0),
                'poster': f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item.get('poster_path') else '',
                'backdrop': f"https://image.tmdb.org/t/p/w1280{item['backdrop_path']}" if item.get('backdrop_path') else '',
                'synopsis': item.get('overview', ''),
                'popularity': item.get('popularity', 0.0),
                'genres': [],
                'providers': []
            }
    
    def _rank_candidates(self, candidates, preferences, media_type):
        """
        Rankeia candidatos por relevância usando sistema de pontos
        """
        scored = []
        
        for candidate in candidates:
            score = 0.0
            
            # Pontuação por gênero
            if candidate.get('genres'):
                matching_genres = set(candidate['genres']) & set(preferences['top_genres'])
                score += len(matching_genres) * self.weights['genre'] * 10
            
            # Pontuação por rating
            if candidate.get('rating'):
                rating_diff = abs(candidate['rating'] - preferences.get('min_rating', 7.0))
                score += max(0, (10 - rating_diff)) * self.weights['rating']
            
            # Pontuação por ano (para filmes)
            if media_type == 'movie' and candidate.get('year'):
                year_pref = preferences.get('avg_year', 2020)
                year_diff = abs(candidate['year'] - year_pref)
                score += max(0, (10 - year_diff / 2)) * self.weights['year']
            
            # Pontuação por provider
            if candidate.get('providers'):
                matching_providers = set(candidate['providers']) & set(preferences['top_providers'])
                score += len(matching_providers) * self.weights['provider'] * 10
            
            # Bonus por popularidade
            score += min(candidate.get('popularity', 0) / 100, 5)
            
            candidate['_recommendation_score'] = score
            scored.append(candidate)
        
        # Ordena por pontuação
        scored.sort(key=lambda x: x['_recommendation_score'], reverse=True)
        return scored
    
    
    def _fallback_popular_movies(self):
        """
        REMOVIDO - Agora retorna None para mostrar aviso
        """
        return None
    
    def _fallback_popular_tvshows(self):
        """
        REMOVIDO - Agora retorna None para mostrar aviso
        """
        return None


# ============================================
# FUNÇÕES PARA INTEGRAR NO ROUTER
# ============================================

def show_movie_recommendations():
    """
    Exibe recomendações de filmes
    Adicione no router.py: elif action == 'show_movie_recommendations': recommendations.show_movie_recommendations()
    """
    from resources.lib.movies import _create_movie_item_tuple
    import xbmcplugin
    import sys
    
    HANDLE = int(sys.argv[1])
    
    xbmcplugin.setPluginCategory(HANDLE, "Recomendações para Você")
    xbmcplugin.setContent(HANDLE, 'movies')
    
    # Gera recomendações
    engine = RecommendationEngine()
    movies = engine.get_movie_recommendations(limit=30)
    
    # Se não tiver histórico suficiente, mostra aviso
    if movies is None:
        watched_count = len(db.get_watched_movies()) if db.get_watched_movies() else 0
        
        xbmcgui.Dialog().ok(
            "📊 Histórico Insuficiente",
            f"Você assistiu {watched_count} filme(s).\n\n"
            f"Assista pelo menos 3 filmes para receber\n"
            f"recomendações personalizadas!\n\n"
            f"💡 Suas preferências serão aprendidas automaticamente."
        )
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    
    # Mostra progresso
    pDialog = xbmcgui.DialogProgressBG()
    pDialog.create("Recomendações", "Analisando suas preferências...")
    
    try:
        pDialog.update(50, message="Preparando recomendações...")
        
        items_to_add = []
        for movie in movies:
            items_to_add.append(_create_movie_item_tuple(movie))
        
        pDialog.update(100, message="Pronto!")
        
        xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
        
    finally:
        pDialog.close()
    
    xbmcplugin.endOfDirectory(HANDLE)


def show_tvshow_recommendations():
    """
    Exibe recomendações de séries
    Adicione no router.py: elif action == 'show_tvshow_recommendations': recommendations.show_tvshow_recommendations()
    """
    from resources.lib.tvshows import _create_show_tuple
    import xbmcplugin
    import sys
    
    HANDLE = int(sys.argv[1])
    
    xbmcplugin.setPluginCategory(HANDLE, "Recomendações para Você")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    
    # Gera recomendações
    engine = RecommendationEngine()
    shows = engine.get_tvshow_recommendations(limit=30)
    
    # Se não tiver histórico suficiente, mostra aviso
    if shows is None:
        watched_count = len(db.get_watched_tvshows()) if db.get_watched_tvshows() else 0
        
        xbmcgui.Dialog().ok(
            "📊 Histórico Insuficiente",
            f"Você assistiu {watched_count} série(s).\n\n"
            f"Assista pelo menos 2 séries para receber\n"
            f"recomendações personalizadas!\n\n"
            f"💡 Suas preferências serão aprendidas automaticamente."
        )
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    
    # Mostra progresso
    pDialog = xbmcgui.DialogProgressBG()
    pDialog.create("Recomendações", "Analisando suas preferências...")
    
    try:
        pDialog.update(50, message="Preparando recomendações...")
        
        items_to_add = []
        for show in shows:
            items_to_add.append(_create_show_tuple(show))
        
        pDialog.update(100, message="Pronto!")
        
        xbmcplugin.addDirectoryItems(HANDLE, items_to_add, len(items_to_add))
        
    finally:
        pDialog.close()
    
    xbmcplugin.endOfDirectory(HANDLE)