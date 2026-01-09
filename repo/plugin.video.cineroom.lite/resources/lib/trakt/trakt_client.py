# resources/lib/trakt/trakt_client.py
# -*- coding: utf-8 -*-
"""
Cliente Trakt Otimizado
✅ Listas públicas e personalizadas
✅ Paginação correta
✅ Código limpo e reutilizável
🔧 CORRIGIDO: Detecção correta de séries vs filmes
"""

import xbmc
import xbmcaddon
from urllib.parse import quote_plus

ADDON = xbmcaddon.Addon()

class TraktAPI:
    """Cliente base para requests Trakt"""
    
    def __init__(self):
        self.settings = self._get_settings()
        self.base_url = "https://api.trakt.tv"
    
    def _get_settings(self):
        return {
            'client_id': ADDON.getSetting('trakt_client_id') or '',
            'client_secret': ADDON.getSetting('trakt_client_secret') or '',
            'access_token': ADDON.getSetting('trakt_access_token') or '',
            'refresh_token': ADDON.getSetting('trakt_refresh_token') or '',
            'expires_at': float(ADDON.getSetting('trakt_expires_at') or 0),
            'username': ADDON.getSetting('trakt_username') or ''
        }
    
    def _get_headers(self, auth_required=False):
        headers = {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.settings['client_id'] if self.settings['client_id'] else 'f0b9cd2de131c900f5bb03a0a5776342'
        }
        
        if auth_required and self.settings['access_token']:
            headers['Authorization'] = f"Bearer {self.settings['access_token']}"
        
        return headers
    
    def request(self, method, endpoint, params=None, auth_required=False):
        """Request genérico para Trakt"""
        try:
            import requests
            
            url = f"{self.base_url}{endpoint}"
            headers = self._get_headers(auth_required)
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=15)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=params, timeout=15)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, json=params, timeout=15)
            else:
                return None
            
            if response.status_code in [200, 201, 204]:
                if response.content:
                    return response.json()
                return True
            
            xbmc.log(f"[Trakt] Erro {response.status_code} em {endpoint}", xbmc.LOGERROR)
            return None
            
        except Exception as e:
            xbmc.log(f"[Trakt] Erro requisição {endpoint}: {e}", xbmc.LOGERROR)
            return None
    
    def get_public_list(self, endpoint, params=None):
        """Obtém lista pública (não requer auth)"""
        params = params or {}
        params['extended'] = 'full'
        return self.request('GET', endpoint, params, auth_required=False)
    
    def get_auth_list(self, endpoint, params=None):
        """Obtém lista que requer autenticação"""
        params = params or {}
        params['extended'] = 'full'
        return self.request('GET', endpoint, params, auth_required=True)


class TraktLists:
    """Gerencia todas as listas do Trakt"""
    
    def __init__(self):
        self.api = TraktAPI()
    
    # === LISTAS PÚBLICAS (SEM AUTENTICAÇÃO) ===
    
    def get_trending(self, media_type='movies', page=1, limit=30):
        """Em alta"""
        media_type = self._normalize_media_type(media_type)
        endpoint = f'/{media_type}/trending'
        return self.api.get_public_list(endpoint, {'page': page, 'limit': limit})
    
    def get_popular(self, media_type='movies', page=1, limit=30):
        """Populares"""
        media_type = self._normalize_media_type(media_type)
        endpoint = f'/{media_type}/popular'
        return self.api.get_public_list(endpoint, {'page': page, 'limit': limit})
    
    def get_most_watched(self, media_type='movies', period='weekly', page=1, limit=30):
        """Mais assistidos"""
        media_type = self._normalize_media_type(media_type)
        endpoint = f'/{media_type}/watched/{period}'
        return self.api.get_public_list(endpoint, {'page': page, 'limit': limit})
    
    def get_most_collected(self, media_type='movies', period='weekly', page=1, limit=30):
        """Mais coletados"""
        media_type = self._normalize_media_type(media_type)
        endpoint = f'/{media_type}/collected/{period}'
        return self.api.get_public_list(endpoint, {'page': page, 'limit': limit})
    
    def get_most_anticipated(self, media_type='movies', page=1, limit=30):
        """Mais aguardados"""
        media_type = self._normalize_media_type(media_type)
        endpoint = f'/{media_type}/anticipated'
        return self.api.get_public_list(endpoint, {'page': page, 'limit': limit})
    
    def get_box_office(self, page=1, limit=30):
        """Bilheteria (apenas filmes)"""
        endpoint = '/movies/boxoffice'
        return self.api.get_public_list(endpoint, {'page': page, 'limit': limit})
    
    def get_top_rated(self, media_type='movies', page=1, limit=30):
        """Melhor avaliados"""
        media_type = self._normalize_media_type(media_type)
        endpoint = f'/{media_type}/rated'
        return self.api.get_public_list(endpoint, {'page': page, 'limit': limit})
    
    def get_most_played(self, media_type='movies', period='weekly', page=1, limit=30):
        """Mais reproduzidos"""
        media_type = self._normalize_media_type(media_type)
        endpoint = f'/{media_type}/played/{period}'
        return self.api.get_public_list(endpoint, {'page': page, 'limit': limit})
    
    def get_recommended(self, media_type='movies', page=1, limit=30):
        """Recomendações públicas gerais (sem autenticação)"""
        media_type = self._normalize_media_type(media_type)
        endpoint = f'/{media_type}/recommended'
        return self.api.get_public_list(endpoint, {'page': page, 'limit': limit})
    
    # === LISTAS PERSONALIZADAS (COM AUTENTICAÇÃO) ===
    
    def get_personal_recommendations(self, media_type='movies', page=1, limit=30):
        """
        ✅ Recomendações PERSONALIZADAS baseadas no histórico do usuário
        Requer autenticação OAuth
        """
        media_type = self._normalize_media_type(media_type)
        endpoint = f'/recommendations/{media_type}'
        return self.api.get_auth_list(endpoint, {'page': page, 'limit': limit})
    
    def _normalize_media_type(self, media_type):
        """
        🔧 NORMALIZA O TIPO DE MÍDIA
        tvshow/tvshows/show → shows
        movie → movies
        """
        if media_type in ['tvshow', 'tvshows', 'show']:
            return 'shows'
        elif media_type == 'movie':
            return 'movies'
        return media_type


class TraktPresentation:
    """Formatação e apresentação dos resultados Trakt"""
    
    @staticmethod
    def normalize_item(item):
        """
        Normaliza item do Trakt para formato padrão
        Suporta múltiplos formatos de resposta da API
        """
        if 'movie' in item:
            media_type = 'movie'
            obj = item['movie']
            extra = item
        elif 'show' in item:
            media_type = 'tvshow'
            obj = item['show']
            extra = item
        else:
            obj = item
            extra = {}
            
            has_serie_fields = any([
                'first_aired' in obj,
                'network' in obj,
                'aired_episodes' in obj,
                'status' in obj and obj.get('status') in ['returning series', 'continuing', 'ended', 'canceled'],
                'airs' in obj  # Campo exclusivo de séries
            ])
            
            # Se tem campos de série, É série!
            if has_serie_fields:
                media_type = 'tvshow'
            else:
                # Fallback: verifica se tem 'title' (filme) ou não
                media_type = 'movie' if 'title' in obj else 'tvshow'
        
        ids = obj.get('ids', {})
        
        return {
            'title': obj.get('title') or obj.get('name', ''),
            'original_title': obj.get('title') or obj.get('name', ''),
            'tmdb_id': ids.get('tmdb'),
            'imdb_id': ids.get('imdb', ''),
            'media_type': media_type,
            'year': obj.get('year'),
            'slug': ids.get('slug', ''),
            'synopsis': obj.get('overview', ''),
            'rating': obj.get('rating', 0),
            'votes': obj.get('votes', 0),
            'genres': obj.get('genres', []),
            'runtime': obj.get('runtime', 0),
            'watchers': extra.get('watchers', 0),
            'play_count': extra.get('play_count', 0),
            'collector_count': extra.get('collector_count', 0),
            'list_count': extra.get('list_count', 0),
            'revenue': extra.get('revenue', 0),
            'poster': '',
            'backdrop': '',
            'clearlogo': ''
        }
    
    @staticmethod
    def build_url(item):
        """
        Constrói URL do plugin para o item
        Séries → list_seasons
        Filmes → find_sources
        """
        media_type = item.get('media_type')
        
        # SÉRIES
        if media_type == 'tvshow':
            url = f"plugin://plugin.video.cineroom.lite/?action=list_seasons&tvshow_tmdb_id={item['tmdb_id']}"
            return url
        
        # FILMES
        title = str(item.get('title', ''))
        url_params = [
            f"action=find_sources",
            f"tmdb_id={item['tmdb_id']}",
            f"media_type=movie",
            f"title={quote_plus(title)}"
        ]
        
        # Metadados opcionais
        if item.get('year'):
            url_params.append(f"year={item['year']}")
        if item.get('imdb_id'):
            url_params.append(f"imdb_id={item['imdb_id']}")
        if item.get('original_title'):
            url_params.append(f"original_title={quote_plus(item['original_title'])}")
        
        # Artes (se disponíveis)
        if item.get('poster'):
            url_params.append(f"poster={quote_plus(item['poster'])}")
        if item.get('backdrop'):
            url_params.append(f"backdrop={quote_plus(item['backdrop'])}")
        if item.get('clearlogo'):
            url_params.append(f"clearlogo={quote_plus(item['clearlogo'])}")
        
        return f"plugin://plugin.video.cineroom.lite/?{'&'.join(url_params)}"