import xbmcgui
from resources.lib.video_cache import CACHE

def clear_cache():
    """Limpa todo o cache de vídeos"""
    VIDEO_CACHE.clear()
    xbmcgui.Dialog().notification("Cache", "Todos os caches foram limpos", xbmcgui.NOTIFICATION_INFO)