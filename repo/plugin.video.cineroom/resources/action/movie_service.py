# resources/lib/services/movie_service.py
import json
from typing import List, Dict, Callable, Optional
from datetime import datetime
from resources.lib.utils utils import get_all_videos, VIDEO_CACHE, FILTERED_CACHE
from resources.lib.utils_view import set_view_mode

class MovieService:
    def __init__(self, handle: int):
        self.handle = handle
        self.items_per_page = 70  # Configurável

    def get_filtered_movies(self, filter_func: Callable, cache_key: str, 
                          title: str, page: int = 1, **kwargs) -> None:
        """
        Método genérico para filtrar e listar filmes com cache e paginação
        """
        try:
            page = max(1, int(page))
            movies = self._get_cached_or_filter(cache_key, filter_func, **kwargs)
            
            if not movies:
                self._show_notification(f"Nenhum filme encontrado para {title}")
                return

            self._setup_plugin_view(title)
            self._display_paginated_items(movies, page, title, **kwargs)
            
        except Exception as e:
            self._handle_error(e)

    def _get_cached_or_filter(self, cache_key: str, filter_func: Callable, **kwargs):
        cached = VIDEO_CACHE.get(cache_key)
        if cached and not VIDEO_CACHE.is_expired(cache_key):
            return json.loads(cached)
        
        all_movies = get_all_videos()
        filtered = filter_func(all_movies, **kwargs)
        
        VIDEO_CACHE.set(cache_key, json.dumps(filtered), expiry_hours=12)
        return filtered

    def _setup_plugin_view(self, title: str):
        xbmcplugin.setPluginCategory(self.handle, title)
        xbmcplugin.setContent(self.handle, 'movies')

    def _display_paginated_items(self, movies: List[Dict], page: int, title: str, **kwargs):
        start = (page - 1) * self.items_per_page
        end = start + self.items_per_page

        for movie in movies[start:end]:
            self._add_movie_item(movie)

        if end < len(movies):
            self._add_next_page_item(page + 1, title, **kwargs)

        xbmcplugin.endOfDirectory(self.handle)
        set_view_mode()

    def _add_movie_item(self, movie: Dict):
        from ..action.video_listing import create_video_item
        list_item, url, is_folder = create_video_item(movie)
        xbmcplugin.addDirectoryItem(self.handle, url, list_item, is_folder)

    def _add_next_page_item(self, next_page: int, title: str, **kwargs):
        next_item = xbmcgui.ListItem(label="Próxima Página >>")
        next_url = self._generate_next_page_url(next_page, title, **kwargs)
        next_item.setArt({"icon": "https://example.com/next.png"})
        xbmcplugin.addDirectoryItem(self.handle, next_url, next_item, True)

    def _generate_next_page_url(self, next_page: int, title: str, **kwargs):
        from ..utils import get_url
        kwargs.update({'page': next_page})
        return get_url(action=kwargs.get('action'), **kwargs)

    def _show_notification(self, message: str):
        xbmcgui.Dialog().ok("Aviso", message)

    def _handle_error(self, error: Exception):
        xbmc.log(f"Erro no MovieService: {str(error)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(error), xbmcgui.NOTIFICATION_ERROR)