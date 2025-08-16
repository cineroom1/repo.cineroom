import time
import unicodedata
import os
import sys
import json
import datetime
import urllib.request
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
import xbmc
import xbmcaddon
import xbmcvfs
import xbmcgui
import xbmcplugin

from resources.action.video_listing import create_video_item
from resources.lib.utils import get_all_videos, VIDEO_CACHE

ADDON_ID = xbmcaddon.Addon().getAddonInfo('id')
FIREBASE_BASE_URL = "https://notify-313a5-default-rtdb.firebaseio.com"

CACHE_EXPIRY_HOURS = 12         # Cache de vídeos populares
SEARCH_CACHE_EXPIRY_HOURS = 2   # Cache de buscas
SEARCH_CACHE_KEY = "search_terms_buffer"

URL = sys.argv[0]

# ThreadPoolExecutor para sincronização em background
executor = ThreadPoolExecutor(max_workers=2)


def get_url(**kwargs):
    return f'{URL}?{urlencode(kwargs)}'


def normalize(text):
    if not isinstance(text, str):
        return ''
    normalized = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').lower()
    for ch in ['.', ':', '/', '#', '[', ']', ' ']:
        normalized = normalized.replace(ch, '')
    return normalized

def match_video(video, search_term):
    if not isinstance(video, dict):
        return False
        
    title_norm = normalize(video.get('title', ''))
    tmdb_id = str(video.get('tmdb_id', ''))
    
    if search_term == title_norm:
        return True
    if search_term.isdigit() and search_term == tmdb_id:
        return True
    if search_term in title_norm:
        return True
    
    actors = video.get('actors', [])
    directors = video.get('director', [])
    
    normalized_actors = [normalize(a) for a in actors if isinstance(a, str)]
    normalized_directors = [normalize(d) for d in directors if isinstance(d, str)]
    
    if any(search_term in a for a in normalized_actors) or any(search_term in d for d in normalized_directors):
        return True
        
    return False

def load_search_cache_from_disk(video_type):
    file_path = xbmcvfs.translatePath(
        f"special://profile/addon_data/{ADDON_ID}/search_cache_{video_type}.json"
    )
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            xbmc.log(f"[CACHE] Erro ao ler cache de disco para {video_type}: {e}", xbmc.LOGERROR)
    return {"terms": {}, "timestamp": time.time()}


def save_search_cache_to_disk(buffer_data, video_type):
    file_path = xbmcvfs.translatePath(
        f"special://profile/addon_data/{ADDON_ID}/search_cache_{video_type}.json"
    )
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(buffer_data, f)
    except Exception as e:
        xbmc.log(f"[CACHE] Erro ao salvar cache no disco para {video_type}: {e}", xbmc.LOGERROR)


def save_search_term(term, video_type):
    if not term:
        return
    normalized_term = normalize(term)
    cache_key = f"{SEARCH_CACHE_KEY}_{video_type}"
    
    buffer_data = VIDEO_CACHE.get(cache_key)
    if buffer_data:
        buffer_data = json.loads(buffer_data)
    else:
        buffer_data = load_search_cache_from_disk(video_type)
    
    buffer_data["terms"][normalized_term] = buffer_data["terms"].get(normalized_term, 0) + 1
    buffer_data["timestamp"] = time.time()
    
    VIDEO_CACHE.set(cache_key, json.dumps(buffer_data), expiry_hours=SEARCH_CACHE_EXPIRY_HOURS)
    save_search_cache_to_disk(buffer_data, video_type)

    xbmc.log(f"[CACHE] Cache de buscas de {video_type} atualizado com {len(buffer_data['terms'])} termos.", xbmc.LOGINFO)


def sync_cache(video_type):
    """
    Sincroniza o cache de buscas com o Firebase em background.
    """
    key = f"{SEARCH_CACHE_KEY}_{video_type}"
    cached_data = VIDEO_CACHE.get(key)
    if cached_data:
        try:
            buffer_data = json.loads(cached_data)
        except Exception:
            buffer_data = load_search_cache_from_disk(video_type)
    else:
        buffer_data = load_search_cache_from_disk(video_type)

    if not buffer_data or not buffer_data["terms"]:
        return False

    age_hours = (time.time() - buffer_data.get("timestamp", time.time())) / 3600
    if age_hours < SEARCH_CACHE_EXPIRY_HOURS:
        return False

    def _sync():
        try:
            firebase_url = f"{FIREBASE_BASE_URL}/search_history/{video_type}.json"
            req_get = urllib.request.Request(firebase_url, method="GET")
            with urllib.request.urlopen(req_get) as resp:
                firebase_data = json.loads(resp.read().decode("utf-8")) or {}

            combined_data = firebase_data.copy()
            for k, v in buffer_data["terms"].items():
                combined_data[k] = combined_data.get(k, 0) + v

            payload = json.dumps(combined_data).encode("utf-8")
            req_patch = urllib.request.Request(firebase_url, data=payload, method="PATCH")
            with urllib.request.urlopen(req_patch) as resp:
                xbmc.log(f"[Firebase] {len(buffer_data['terms'])} termos sincronizados para {video_type}. Status: {resp.getcode()}", xbmc.LOGINFO)

            VIDEO_CACHE.delete(key)
            file_path = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}/search_cache_{video_type}.json")
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            xbmc.log(f"[Firebase] Erro ao sincronizar cache para {video_type}: {str(e)}", xbmc.LOGERROR)

    executor.submit(_sync)
    return True


def sync_all_search_caches():
    xbmc.log("[Firebase] Sincronização de caches iniciada.", xbmc.LOGINFO)
    movie_synced = sync_cache('movie')
    tv_synced = sync_cache('tvshow')
    xbmc.log("[Firebase] Sincronização de caches concluída.", xbmc.LOGINFO)
    return movie_synced or tv_synced


def list_most_searched_generic(handle, content_type, title, min_count=10):
    xbmcplugin.setPluginCategory(handle, title)
    xbmcplugin.setContent(handle, 'movies' if content_type == 'movie' else 'tvshows')

    # --- Cache local ---
    cache_key = f"most_searched_{content_type}_{min_count}"
    cached_items = VIDEO_CACHE.get(cache_key)
    if cached_items:
        xbmc.log(f"[CACHE] Usando cache 'mais buscados' de {content_type}", xbmc.LOGINFO)
        for item_data in json.loads(cached_items):
            item, url, is_folder = create_video_item(item_data)
            xbmcplugin.addDirectoryItem(handle, url, item, is_folder)
        xbmcplugin.endOfDirectory(handle)
        return

    # --- Busca no Firebase ---
    try:
        firebase_url = f"{FIREBASE_BASE_URL}/search_history/{content_type}.json"
        req = urllib.request.Request(firebase_url)
        with urllib.request.urlopen(req) as response:
            if response.getcode() != 200:
                xbmcgui.Dialog().ok("Aviso", f"Nenhuma pesquisa registrada ainda para {title.lower()} ou erro de conexão.")
                xbmcplugin.endOfDirectory(handle)
                return

            response_text = response.read().decode('utf-8')
            if response_text == "null":
                xbmcgui.Dialog().ok("Aviso", f"Nenhuma pesquisa registrada ainda para {title.lower()}.")
                xbmcplugin.endOfDirectory(handle)
                return

            search_history = json.loads(response_text)

        filtered_searches = {t: c for t, c in search_history.items() if c > min_count}
        if not filtered_searches:
            xbmcgui.Dialog().ok("Aviso", f"Nenhum(a) {title.lower()} popular o suficiente para ser listado(a).")
            xbmcplugin.endOfDirectory(handle)
            return

        top_searches = sorted(filtered_searches.items(), key=lambda i: i[1], reverse=True)

        all_content = get_all_videos()
        filtered_videos = [v for v in all_content if v.get('type') == content_type]

        added_tmdb_ids = set()
        cache_data = []

        for term, _ in top_searches:
            for video in filtered_videos:
                if match_video(video, term) and video.get('tmdb_id') not in added_tmdb_ids:
                    cache_data.append(video)
                    item, url, is_folder = create_video_item(video)
                    xbmcplugin.addDirectoryItem(handle, url, item, is_folder)
                    added_tmdb_ids.add(video.get('tmdb_id'))
                    break

        if cache_data:
            VIDEO_CACHE.set(cache_key, json.dumps(cache_data), expiry_hours=CACHE_EXPIRY_HOURS)

        xbmcplugin.endOfDirectory(handle)

    except Exception as e:
        xbmc.log(f"[Firebase] Erro em list_most_searched_generic: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(handle)


def list_most_searched(handle):
    list_most_searched_generic(handle, 'movie', 'Filmes Mais Buscados')


def list_most_searched_tvshows(handle):
    list_most_searched_generic(handle, 'tvshow', 'Séries Mais Buscadas')
