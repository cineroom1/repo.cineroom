# -*- coding: utf-8 -*-
# resources/lib/utils.py - VERSÃO OTIMIZADA PARA DISPOSITIVOS FRACOS

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
        self._ttl = 5
    
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

# labelenum retorna índice numérico, não a string
_IMAGE_QUALITY_ENUM = ["low", "medium", "high", "original"]

def get_image_resolutions():
    """
    image_quality é do tipo labelenum no settings.xml.
    getSetting() retorna o índice ("0"=low, "1"=medium, "2"=high, "3"=original).
    """
    raw = _SETTINGS.get("image_quality", "2")  # "2" = high (default do settings.xml)
    try:
        quality = _IMAGE_QUALITY_ENUM[int(raw)]
    except (ValueError, IndexError):
        quality = raw.lower()  # fallback caso venha como string
    return _IMAGE_QUALITY_MAP.get(quality, _IMAGE_QUALITY_MAP["high"])

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


# ============================================================
# CACHE DE BIBLIOTECA — carrega todos os IDs de uma vez só
# evita N chamadas is_in_library() por item na listagem
# ============================================================

_library_ids_cache = {'movie': None, 'tvshow': None, 'time': 0}
_LIBRARY_CACHE_TTL = 60  # segundos — tempo de vida do cache de biblioteca


def _preload_library_ids():
    """
    Tenta carregar TODOS os IDs da biblioteca em uma única operação.
    Usa get_all_library_ids() se disponível; senão, mantém cache vazio
    e cai no fallback individual transparentemente.
    """
    import time
    now = time.time()

    # Ainda válido?
    if _library_ids_cache['movie'] is not None and (now - _library_ids_cache['time']) < _LIBRARY_CACHE_TTL:
        return

    try:
        from resources.lib.library import get_all_library_ids  # bulk preferido
        ids = get_all_library_ids()
        _library_ids_cache['movie']  = set(str(i) for i in ids.get('movie',  []))
        _library_ids_cache['tvshow'] = set(str(i) for i in ids.get('tvshow', []))
    except (ImportError, AttributeError):
        _library_ids_cache['movie']  = set()
        _library_ids_cache['tvshow'] = set()

    _library_ids_cache['time'] = time.time()


def _is_in_library_fast(tmdb_id, media_type):
    """
    Versão O(1) de is_in_library().
    Usa cache de IDs pré-carregado; cai no fallback individual se o
    cache estiver vazio (ex: get_all_library_ids não existe).
    """
    _preload_library_ids()
    cached_set = _library_ids_cache.get(media_type)

    if cached_set is not None and len(cached_set) > 0:
        return str(tmdb_id) in cached_set

    try:
        from resources.lib.library import is_in_library
        result = is_in_library(tmdb_id, media_type)
        if cached_set is not None:
            if result:
                cached_set.add(str(tmdb_id))
        return result
    except ImportError:
        return False


def invalidate_library_cache():
    """Chame após adicionar/remover da biblioteca para forçar reload."""
    _library_ids_cache['movie']  = None
    _library_ids_cache['tvshow'] = None
    _library_ids_cache['time']   = 0


# ============================================================
# CACHE DE TRAKT — verificado UMA vez por sessão
# ============================================================

_trakt_active = None  # None = não verificado ainda


def _is_trakt_active():
    """Retorna True se Trakt está autenticado. Cacheado por sessão."""
    global _trakt_active
    if _trakt_active is None:
        try:
            from resources.lib.trakt.trakt_sync import get_trakt_settings
            _trakt_active = bool(get_trakt_settings().get('access_token'))
        except Exception:
            _trakt_active = False
    return _trakt_active


def create_video_item(item_data, media_type, show_data=None):
    """
    Cria ListItem com metadados, arte e uniqueids.
    NÃO adiciona menu de contexto (responsabilidade do chamador,
    evitando chamadas duplicadas de I/O de biblioteca e Trakt).
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
    studio_str = " / ".join(studios) if isinstance(studios, list) else str(studios) if studios else 'Unknown'
    mpaa = item_data.get('certification') or item_data.get('classification') or 'Not Rated'
    
    # === VIDEO INFO ===
    video_info = {
        'title': label,
        'originaltitle': item_data.get('original_title', ''),
        'plot': item_data.get('synopsis') or item_data.get('overview') or '',
        'plotoutline': item_data.get('tagline', ''),
        'genre': parse_genres(item_data.get('genres')),
        'year': year,
        'rating': safe_float(item_data.get('rating')),
        'votes': safe_int(item_data.get('votes')),
        'premiered': aired,
        'duration': duration_sec,
        'mpaa': mpaa,
        'studio': studio_str,
        'mediatype': media_type
    }
    
    # === EPISÓDIOS ===
    if media_type == 'episode':
        season = safe_int(item_data.get('season'))
        episode = safe_int(item_data.get('episode'))
        
        if season > 0:
            video_info['season'] = season
        if episode > 0:
            video_info['episode'] = episode
        
        if show_data and show_data.get('title'):
            video_info['tvshowtitle'] = show_data['title']
        elif item_data.get('show_title'):
            video_info['tvshowtitle'] = item_data['show_title']
        else:
            video_info['tvshowtitle'] = label
    
    # === IMDB ID ===
    imdb_id = str(item_data.get('imdb_id') or '').strip()
    if imdb_id and not imdb_id.startswith('tt'):
        imdb_id = f"tt{imdb_id}"
    tmdb_id = item_data.get('tmdb_id')

    # === InfoTagVideo (nova API Kodi — substitui setInfo/setUniqueIDs) ===
    tag = li.getVideoInfoTag()

    tag.setTitle(video_info['title'])
    tag.setOriginalTitle(video_info.get('originaltitle', ''))
    tag.setPlot(video_info.get('plot', ''))
    tag.setPlotOutline(video_info.get('plotoutline', ''))
    tag.setGenres(parse_genres(item_data.get('genres')).split(' / ') if item_data.get('genres') else [])
    tag.setYear(video_info.get('year', 0))
    tag.setRating(video_info.get('rating', 0.0))
    tag.setVotes(video_info.get('votes', 0))
    tag.setPremiered(video_info.get('premiered', ''))
    tag.setDuration(video_info.get('duration', 0))
    tag.setMpaa(video_info.get('mpaa', ''))
    tag.setStudios([video_info['studio']] if video_info.get('studio') else [])
    tag.setMediaType(media_type)

    if imdb_id:
        tag.setIMDBNumber(imdb_id)

    if media_type == 'episode':
        tag.setSeason(video_info.get('season', 0))
        tag.setEpisode(video_info.get('episode', 0))
        tag.setTvShowTitle(video_info.get('tvshowtitle', ''))

    # UniqueIDs
    unique_ids = {}
    if imdb_id:
        unique_ids['imdb'] = imdb_id
    if tmdb_id:
        unique_ids['tmdb'] = str(tmdb_id)
    if unique_ids:
        default_rating = 'imdb' if 'imdb' in unique_ids else 'tmdb'
        tag.setUniqueIDs(unique_ids)
    
    # === PROPERTIES ===
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
    
    if media_type == 'episode':
        season = safe_int(item_data.get('season'))
        episode = safe_int(item_data.get('episode'))
        if season > 0:
            li.setProperty('season', str(season))
        if episode > 0:
            li.setProperty('episode', str(episode))
        if show_data:
            li.setProperty('tvshowtitle', show_data.get('title', ''))
        elif item_data.get('show_title'):
            li.setProperty('tvshowtitle', item_data['show_title'])
    
    # === ARTE ===
    poster   = scale_tmdb(item_data.get('poster'),   res['poster'])
    backdrop = scale_tmdb(item_data.get('backdrop'), res['backdrop'])
    clearlogo = item_data.get('clearlogo') or ""
    
    art_dict = {
        'poster': poster,
        'fanart': backdrop,
        'thumb':  poster,
        'icon':   poster
    }
    if clearlogo:
        art_dict['clearlogo'] = clearlogo
    if media_type == 'episode' and item_data.get('episode_thumb'):
        art_dict['thumb'] = item_data['episode_thumb']
    
    li.setArt(art_dict)
    
    # === PLAYABLE ===
    if media_type in ('movie', 'episode'):
        li.setProperty('IsPlayable', 'true')
    
    return li


# ============================================================
# VERSÃO COM BIBLIOTECA E TRAKT
# — menu de contexto montado UMA vez com checks cacheados
# ============================================================

def create_video_item_with_library(item_data, media_type, show_data=None):
    """
    Cria ListItem completo com menu de contexto (favoritos + biblioteca + Trakt).

    OTIMIZAÇÕES vs versão anterior:
    - is_in_library: bulk pre-load → lookup O(1) em set (era N queries I/O)
    - Trakt: flag booleana cacheada por sessão (era 2x get_trakt_settings() por item)
    - Sem duplicação de context menu (create_video_item não adiciona mais)
    """
    li = create_video_item(item_data, media_type, show_data)
    
    tmdb_id = item_data.get('tmdb_id')
    if not tmdb_id or media_type not in ('movie', 'tvshow'):
        return li

    context_items = []

    # --- FAVORITOS (apenas construção de URL, zero I/O) ---
    add_fav_url    = get_url(action='add_to_favorites',    tmdb_id=tmdb_id, media_type=media_type)
    remove_fav_url = get_url(action='remove_from_favorites', tmdb_id=tmdb_id, media_type=media_type)
    context_items.append(('Adicionar à Minha Lista', f'RunPlugin({add_fav_url})'))
    context_items.append(('Remover da Minha Lista',  f'RunPlugin({remove_fav_url})'))

    # --- BIBLIOTECA (O(1) via cache pré-carregado) ---
    try:
        in_library = _is_in_library_fast(tmdb_id, media_type)
        if not in_library:
            lib_add_url = get_url(action='library_add', tmdb_id=tmdb_id, media_type=media_type)
            context_items.append(('Adicionar à Biblioteca', f'RunPlugin({lib_add_url})'))
        else:
            lib_remove_url = get_url(action='library_remove', tmdb_id=tmdb_id, media_type=media_type)
            context_items.append(('Remover da Biblioteca', f'RunPlugin({lib_remove_url})'))
    except Exception:
        pass

    # --- TRAKT (flag cacheada por sessão — zero I/O extra) ---
    if _is_trakt_active():
        trakt_add_url     = get_url(action='trakt_add_collection', tmdb_id=tmdb_id, media_type=media_type)
        trakt_watched_url = get_url(action='trakt_mark_watched',   tmdb_id=tmdb_id, media_type=media_type)
        trakt_rate_url    = get_url(action='trakt_rate',           tmdb_id=tmdb_id, media_type=media_type)
        context_items.append(('Trakt: Coleção',  f'RunPlugin({trakt_add_url})'))
        context_items.append(('Trakt: Assistido', f'RunPlugin({trakt_watched_url})'))
        context_items.append(('Trakt: Avaliar',   f'RunPlugin({trakt_rate_url})'))

    if context_items:
        # replaceItems=True garante que não há duplicatas com o menu base do Kodi
        li.addContextMenuItems(context_items, replaceItems=True)

    return li


# ============================================================
# VIEW MODE — sem sleep síncrono (bloqueava o thread principal)
# ============================================================

VIEW_MODE_MAP = {
    'list': 50, 'poster': 51, 'iconwall': 52, 'shift': 53,
    'infowall': 54, 'widelist': 55, 'wall': 500,
    'banner': 56, 'fanart': 502
}

def set_view_mode(content_type, view_setting_key='view_mode', default='wall'):
    """
    Aplica view mode via AlarmClock (não-bloqueante).
    Removido xbmc.sleep(100) que travava o thread principal em dispositivos lentos.
    """
    try:
        view_mode_setting = _SETTINGS.get(view_setting_key, default)
        view_mode_id = VIEW_MODE_MAP.get(view_mode_setting, VIEW_MODE_MAP.get(default, 500))
        # AlarmClock de 1s é não-bloqueante: retorna imediatamente e
        # aplica o view mode assim que o container estiver pronto.
        xbmc.executebuiltin(f'AlarmClock(SetView,Container.SetViewMode({view_mode_id}),00:00:01,silent)')
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


# ============================================================
# HELPERS DIVERSOS (inalterados)
# ============================================================

def build_torrentio_config_string():
    return ""

def format_runtime(minutes):
    if not minutes:
        return ""
    hours = minutes // 60
    mins  = minutes % 60
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

def get_anime_search_patterns(season, episode):
    s = safe_int(season)
    e = safe_int(episode)
    if s == 0 or e == 0:
        return []
    return [
        (s, e),
        (f"{s:02d}", f"{e:02d}")
    ]