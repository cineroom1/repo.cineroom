# -*- coding: utf-8 -*-
# resources/lib/utils.py - VERSÃO OTIMIZADA COM SUPORTE COMPLETO A LEGENDAS

import xbmcaddon
import xbmc
import xbmcgui
import sys
from urllib.parse import urlencode

ADDON = xbmcaddon.Addon()
BASE_URL = sys.argv[0]

# === CACHE INTELIGENTE DE SETTINGS ===
class SettingsCache:
    """Cache de settings com invalidação automática"""
    def __init__(self):
        self._cache = {}
        self._last_check = 0
        self._ttl = 30
    
    def get(self, key, default=''):
        import time
        now = time.time()
        
        if now - self._last_check > self._ttl:
            self._cache.clear()
            self._last_check = now
        
        if key not in self._cache:
            self._cache[key] = ADDON.getSetting(key) or default
        
        return self._cache[key]
    
    def get_bool(self, key, default=False):
        import time
        now = time.time()
        
        if now - self._last_check > self._ttl:
            self._cache.clear()
            self._last_check = now
        
        cache_key = f"{key}_bool"
        if cache_key not in self._cache:
            self._cache[cache_key] = ADDON.getSettingBool(key)
        
        return self._cache[cache_key]

_SETTINGS = SettingsCache()

# === MAPA DE QUALIDADES ===
_IMAGE_QUALITY_MAP = {
    "low":      {"poster": "w342",    "backdrop": "w780"},
    "medium":   {"poster": "w500",    "backdrop": "w1280"},
    "high":     {"poster": "w780",    "backdrop": "original"},
    "original": {"poster": "original", "backdrop": "original"}
}

_resolution_cache = None
_resolution_cache_time = 0

def get_image_resolutions():
    global _resolution_cache, _resolution_cache_time
    import time
    
    now = time.time()
    if _resolution_cache and (now - _resolution_cache_time) < 60:
        return _resolution_cache
    
    quality = _SETTINGS.get("image_quality", "medium").lower()
    _resolution_cache = _IMAGE_QUALITY_MAP.get(quality, _IMAGE_QUALITY_MAP["medium"])
    _resolution_cache_time = now
    
    return _resolution_cache

def get_url(**kwargs):
    return f"{BASE_URL}?{urlencode(kwargs)}"

def scale_tmdb(url, size_key):
    if not url or "/t/p/" not in url:
        return url or ""
    
    try:
        base, rest = url.split("/t/p/", 1)
        if "/" in rest:
            path = rest[rest.index("/"):]
        else:
            path = f"/{rest}"
        return f"{base}/t/p/{size_key}{path}"
    except:
        return url

_genre_cache = {}

def parse_genres(genres):
    if not genres:
        return ""
    
    if isinstance(genres, str):
        return genres
    
    cache_key = str(genres)
    if cache_key in _genre_cache:
        return _genre_cache[cache_key]
    
    if isinstance(genres, list):
        if genres and isinstance(genres[0], dict):
            result = " / ".join(g.get("name", "") for g in genres if g.get("name"))
        else:
            result = " / ".join(str(g) for g in genres if g)
    else:
        result = ""
    
    if len(_genre_cache) > 100:
        _genre_cache.clear()
    
    _genre_cache[cache_key] = result
    return result

def normalize_date(date_str):
    if not date_str or not isinstance(date_str, str):
        return ""
    
    if "-" in date_str and len(date_str) == 10:
        return date_str
    
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3 and len(parts[2]) == 4:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    
    return ""

def safe_int(value, default=0):
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default

def safe_float(value, default=0.0):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default

def _get_trakt_context_items(tmdb_id, media_type):
    """
    ✅ Menu de contexto LIMPO - SEM Watchlist
    
    Estrutura Final:
    - Favoritos (local + Trakt Watchlist automático)
    - Trakt: Coleção (mídia física)
    - Trakt: Assistido
    - Trakt: Avaliar
    """
    try:
        from resources.lib.trakt_sync import get_trakt_settings
        settings = get_trakt_settings()
        
        if not settings.get('access_token'):
            return []  # Trakt não autenticado
        
        items = []
        
        # ============================================
        # COLEÇÃO (para quem coleciona DVDs/Blu-rays/Arquivos)
        # ============================================
        items.append((
            'Trakt: Adicionar à Coleção',
            f'RunPlugin({get_url(action="trakt_add_collection", tmdb_id=tmdb_id, media_type=media_type)})'
        ))
        
        items.append((
            'Trakt: Remover da Coleção',
            f'RunPlugin({get_url(action="trakt_remove_collection", tmdb_id=tmdb_id, media_type=media_type)})'
        ))
        
        # ============================================
        # ASSISTIDO (marca como visto)
        # ============================================
        items.append((
            'Trakt: Marcar como Assistido',
            f'RunPlugin({get_url(action="trakt_mark_watched", tmdb_id=tmdb_id, media_type=media_type)})'
        ))
        
        items.append((
            'Trakt: Remover Assistido',
            f'RunPlugin({get_url(action="trakt_remove_watched", tmdb_id=tmdb_id, media_type=media_type)})'
        ))
        
        # ============================================
        # AVALIAR (dá nota 1-10)
        # ============================================
        items.append((
            'Trakt: Avaliar',
            f'RunPlugin({get_url(action="trakt_rate", tmdb_id=tmdb_id, media_type=media_type)})'
        ))
        
        return items
        
    except ImportError:
        return []

def create_video_item(item_data, media_type, show_data=None):
    """
    Cria ListItem otimizado com suporte COMPLETO para addons de legendas.
    
    MUDANÇAS CRÍTICAS:
    ✅ imdbnumber em video_info (além de uniqueids)
    ✅ season/episode garantidos como int
    ✅ tvshowtitle sempre presente em episódios
    ✅ year como int (alguns addons esperam int, não string)
    """
    
    # === INFO BÁSICA ===
    label = item_data.get('title') or item_data.get('name') or 'Sem Título'
    li = xbmcgui.ListItem(label=label)
    
    # === RESOLUÇÕES (CACHED) ===
    res = get_image_resolutions()
    
    # === DATA E ANO ===
    aired = normalize_date(item_data.get('premiered', ''))
    year = safe_int(item_data.get('year'))
    
    # === RUNTIME ===
    runtime_min = safe_int(item_data.get('runtime'))
    duration_sec = runtime_min * 60
    
    # === STUDIO E MPAA ===
    studios = item_data.get('studio') or item_data.get('networks') or []
    studio_str = " / ".join(studios) if isinstance(studios, list) else str(studios) if studios else ""
    mpaa = item_data.get('certification') or item_data.get('classification') or ""
    
    # ============================================
    # VIDEO INFO - ESTRUTURA CORRIGIDA
    # ============================================
    video_info = {
        'title': label,
        'originaltitle': item_data.get('original_title', ''),
        'plot': item_data.get('synopsis', ''),
        'aired': aired,
        'year': year,
        'duration': duration_sec,
        'studio': studio_str,
        'mpaa': mpaa,
        'mediatype': media_type,
        'genre': parse_genres(item_data.get('genres')),
        'rating': safe_float(item_data.get('rating')),
        'votes': safe_int(item_data.get('vote_count')),
    }
    
    # ============================================
    # ✅ CRÍTICO: imdbnumber PARA LEGENDAS
    # ============================================
    imdb_id = item_data.get('imdb_id', '')
    if imdb_id:
        video_info['imdbnumber'] = imdb_id  # ✅ ESSENCIAL para legendas
    
    # ============================================
    # ✅ LÓGICA ESPECÍFICA PARA EPISÓDIOS
    # ============================================
    if media_type == 'episode':
        # Season/Episode como INT (obrigatório)
        season = safe_int(item_data.get('season'))
        episode = safe_int(item_data.get('episode'))
        
        if season > 0:
            video_info['season'] = season  # ✅ INT, não string
        if episode > 0:
            video_info['episode'] = episode  # ✅ INT, não string
        
        # ✅ CRÍTICO: Título da série (para legendas)
        if show_data:
            video_info['tvshowtitle'] = show_data.get('title', '')
        elif item_data.get('show_title'):
            video_info['tvshowtitle'] = item_data['show_title']
        
        # Título do episódio (opcional)
        if item_data.get('episode_title'):
            video_info['title'] = item_data['episode_title']
    
    # Remove valores vazios
    video_info = {k: v for k, v in video_info.items() if v not in (None, '', 0, 0.0)}
    
    li.setInfo('video', video_info)
    
    # ============================================
    # ✅ UNIQUE IDS (PADRÃO KODI 18+)
    # ============================================
    unique_ids = {}
    
    if imdb_id:
        unique_ids['imdb'] = imdb_id  # ✅ SEM prefixo 'tt' se já tiver
    
    tmdb_id = item_data.get('tmdb_id')
    if tmdb_id:
        unique_ids['tmdb'] = str(tmdb_id)
    
    if unique_ids:
        li.setUniqueIDs(unique_ids, defaultrating='imdb')  # ✅ IMDB como padrão
    
    # ============================================
    # PROPERTIES (PARA SKINS E ADDONS)
    # ============================================
    if tmdb_id:
        li.setProperty('tmdb_id', str(tmdb_id))
    
    if imdb_id:
        li.setProperty('imdb_id', imdb_id)
    
    if aired:
        li.setProperty('premiered', aired)
    
    if year:
        li.setProperty('year', str(year))
    
    if runtime_min:
        li.setProperty('runtime', str(runtime_min))
    
    if studio_str:
        li.setProperty('studio', studio_str)
    
    if mpaa:
        li.setProperty('classification', mpaa)
    
    # ✅ PROPERTIES PARA EPISÓDIOS
    if media_type == 'episode':
        season = safe_int(item_data.get('season'))
        episode = safe_int(item_data.get('episode'))
        
        if season > 0:
            li.setProperty('season', str(season))
        if episode > 0:
            li.setProperty('episode', str(episode))
        
        # Título da série (para skins)
        if show_data:
            li.setProperty('tvshowtitle', show_data.get('title', ''))
        elif item_data.get('show_title'):
            li.setProperty('tvshowtitle', item_data['show_title'])
    
    # === ARTE ===
    poster = scale_tmdb(item_data.get('poster'), res['poster'])
    backdrop = scale_tmdb(item_data.get('backdrop'), res['backdrop'])
    clearlogo = item_data.get('clearlogo') or ""
    
    art_dict = {
        'poster': poster,
        'fanart': backdrop,
        'thumb': poster,
        'icon': poster
    }
    
    if clearlogo:
        art_dict['clearlogo'] = clearlogo
    
    # ✅ Para episódios, pode ter thumb específico
    if media_type == 'episode' and item_data.get('episode_thumb'):
        art_dict['thumb'] = item_data['episode_thumb']
    
    li.setArt(art_dict)
    
    # === PLAYABLE ===
    if media_type in ('movie', 'episode'):
        li.setProperty('IsPlayable', 'true')
    
    # === MENU DE CONTEXTO ===
    if tmdb_id and media_type in ('movie', 'tvshow'):
        context_items = []
        
        # FAVORITOS
        context_items.append((
            'Adicionar à Minha Lista',
            f'RunPlugin({get_url(action="add_to_favorites", tmdb_id=tmdb_id, media_type=media_type)})'
        ))
        
        context_items.append((
            'Remover da Minha Lista',
            f'RunPlugin({get_url(action="remove_from_favorites", tmdb_id=tmdb_id, media_type=media_type)})'
        ))
        
        # ✅ TRAKT (adiciona apenas se autenticado)
        trakt_items = _get_trakt_context_items(tmdb_id, media_type)
        if trakt_items:
            context_items.extend(trakt_items)
        
        li.addContextMenuItems(context_items, replaceItems=False)
    
    return li


# ============================================
# VERSÃO COM BIBLIOTECA E TRAKT
# ============================================

def create_video_item_with_library(item_data, media_type, show_data=None):
    """Versão com menu de contexto estendido"""
    li = create_video_item(item_data, media_type, show_data)
    
    tmdb_id = item_data.get('tmdb_id')
    if tmdb_id and media_type in ('movie', 'tvshow'):
        try:
            from resources.lib.library import is_in_library
            in_library = is_in_library(tmdb_id, media_type)
            
            context_items = []
            
            # FAVORITOS
            add_fav_url = get_url(action='add_to_favorites', tmdb_id=tmdb_id, media_type=media_type)
            context_items.append(('Adicionar à Minha Lista', f'RunPlugin({add_fav_url})'))
            
            remove_fav_url = get_url(action='remove_from_favorites', tmdb_id=tmdb_id, media_type=media_type)
            context_items.append(('Remover da Minha Lista', f'RunPlugin({remove_fav_url})'))
            
            # BIBLIOTECA
            if not in_library:
                lib_add_url = get_url(action='library_add', tmdb_id=tmdb_id, media_type=media_type)
                context_items.append(('Adicionar à Biblioteca', f'RunPlugin({lib_add_url})'))
            else:
                lib_remove_url = get_url(action='library_remove', tmdb_id=tmdb_id, media_type=media_type)
                context_items.append(('Remover da Biblioteca', f'RunPlugin({lib_remove_url})'))
            
            # TRAKT
            try:
                from resources.lib.trakt_sync import get_trakt_settings
                settings = get_trakt_settings()
                if settings.get('access_token'):
                    trakt_add_url = get_url(action='trakt_add_collection', tmdb_id=tmdb_id, media_type=media_type)
                    trakt_watched_url = get_url(action='trakt_mark_watched', tmdb_id=tmdb_id, media_type=media_type)
                    
                    context_items.append(('Trakt: Coleção', f'RunPlugin({trakt_add_url})'))
                    context_items.append(('Trakt: Assistido', f'RunPlugin({trakt_watched_url})'))
            except ImportError:
                pass
            
            li.addContextMenuItems(context_items, replaceItems=False)
            
        except ImportError:
            pass
    
    return li


# ============================================
# VIEW MODE E OUTROS HELPERS
# ============================================

VIEW_MODE_MAP = {
    'list': 50, 'poster': 51, 'iconwall': 52, 'shift': 53,
    'infowall': 54, 'widelist': 55, 'wall': 500,
    'banner': 56, 'fanart': 502
}

def set_view_mode(content_type, view_setting_key='view_mode', default='wall'):
    """View mode otimizado - define e deixa o Kodi aplicar"""
    try:
        view_mode_setting = _SETTINGS.get(view_setting_key, default)
        view_mode_id = VIEW_MODE_MAP.get(view_mode_setting, VIEW_MODE_MAP.get(default, 500))
        
        # ✅ SOLUÇÃO SIMPLES: Apenas define a property
        # O Kodi aplica automaticamente quando o container carrega
        xbmc.executebuiltin(f'Container.SetViewMode({view_mode_id})')
        
    except Exception as e:
        xbmc.log(f"[ViewMode] Erro: {e}", xbmc.LOGERROR)

def with_view_mode(content, is_menu=False):
    def decorator(func):
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            default = 'list' if is_menu else 'wall'
            set_view_mode(content, default=default)
        return wrapper
    return decorator

def build_torrentio_config_string():
    return ""

def format_runtime(minutes):
    if not minutes:
        return ""
    hours = minutes // 60
    mins = minutes % 60
    if hours:
        return f"{hours}h {mins}min" if mins else f"{hours}h"
    return f"{mins}min"

def format_file_size(bytes_size):
    if not bytes_size:
        return ""
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    
    return f"{bytes_size:.1f} PB"

def truncate_text(text, max_length=100):
    if not text or len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


# ============================================
# ✅ HELPER PARA BUSCAR PADRÕES DE ANIME
# ============================================
def get_anime_search_patterns(season, episode):
    """
    Gera variações de S/E para animes (ex: S01E01, S1E1)
    
    Returns:
        list: [(1, 1), (01, 01)] como tuplas de int
    """
    s = safe_int(season)
    e = safe_int(episode)
    
    if s == 0 or e == 0:
        return []
    
    # Retorna variações: [(1,1), (01,01)]
    return [
        (s, e),        # S1:E1
        (f"{s:02d}", f"{e:02d}")  # S01:E01
    ]