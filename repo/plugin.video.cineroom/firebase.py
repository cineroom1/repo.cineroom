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

CACHE_EXPIRY_HOURS = 24 * 2
SEARCH_CACHE_EXPIRY_HOURS = 5   # Cache de buscas
SEARCH_CACHE_KEY = "search_terms_buffer"

URL = sys.argv[0]

# ThreadPoolExecutor para sincronização em background
executor = ThreadPoolExecutor(max_workers=4)


def get_url(**kwargs):
    return f'{URL}?{urlencode(kwargs)}'


def normalize(text):
    if not isinstance(text, str):
        return ''
    normalized = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').lower()
    for ch in ['.', ':', '/', '#', '[', ']', ' ', '-']:
        normalized = normalized.replace(ch, '')
    return normalized

def match_video(video, search_term):
    if not isinstance(video, dict):
        return False
        
    title_norm = normalize(video.get('title', ''))
    tmdb_id = str(video.get('tmdb_id', ''))
    
    # Busca exata
    if search_term == title_norm:
        return True
    if search_term.isdigit() and search_term == tmdb_id:
        return True
    
    # Busca parcial no título
    if search_term in title_norm:
        return True
    
    # Verificar se é variação do mesmo filme (ex: "sing" vs "sing2")
    # Se o search_term está contido no título OU o título está contido no search_term
    if search_term in title_norm or title_norm in search_term:
        # Verificar se são do mesmo "filme família"
        common_base = get_common_base(search_term, title_norm)
        if common_base and len(common_base) > 3:  # Pelo menos 4 caracteres em comum
            return True
    
    actors = video.get('actors', [])
    directors = video.get('director', [])
    
    normalized_actors = [normalize(a) for a in actors if isinstance(a, str)]
    normalized_directors = [normalize(d) for d in directors if isinstance(d, str)]
    
    if any(search_term in a for a in normalized_actors) or any(search_term in d for d in normalized_directors):
        return True
        
    return False

def get_common_base(term1, term2):
    """Encontra a base comum entre dois termos"""
    # Encontrar a substring comum mais longa
    # Implementação simplificada - pode ser melhorada
    for i in range(min(len(term1), len(term2)), 0, -1):
        if term1[:i] == term2[:i]:
            return term1[:i]
    return ""

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


def get_remote_min_count(content_type):
    """
    Busca o min_count remoto no nó /config do Firebase.
    Retorna 1 se houver algum problema ou se não houver valor configurado.
    """
    try:
        firebase_url = f"{FIREBASE_BASE_URL}/config.json"
        req = urllib.request.Request(firebase_url)
        with urllib.request.urlopen(req) as response:
            if response.getcode() != 200:
                xbmc.log(f"[Firebase] Não foi possível obter config, usando min_count=1 para {content_type}", xbmc.LOGWARNING)
                return 1

            config_data = json.loads(response.read().decode("utf-8"))
            
            # Chave depende do tipo de conteúdo
            if content_type == 'movie':
                min_count = int(config_data.get("min_count_movie", 1))
            elif content_type == 'tvshow':
                min_count = int(config_data.get("min_count_tvshow", 1))
            else:
                min_count = 1

            xbmc.log(f"[Firebase] min_count remoto para {content_type}: {min_count}", xbmc.LOGINFO)
            return min_count

    except Exception as e:
        xbmc.log(f"[Firebase] Erro ao obter min_count remoto para {content_type}: {e}", xbmc.LOGERROR)
        return 1


def list_most_searched_generic(handle, content_type, title):
    # --- Buscar min_count remoto ---
    min_count = get_remote_min_count(content_type)
    MAX_ITEMS = 50  # Limite máximo de itens a serem exibidos

    xbmcplugin.setPluginCategory(handle, title)
    xbmcplugin.setContent(handle, 'movies' if content_type == 'movie' else 'tvshows')

    # --- Cache local ---
    cache_key = f"most_searched_{content_type}_{min_count}"
    cached_items = VIDEO_CACHE.get(cache_key)
    if cached_items:
        xbmc.log(f"[CACHE] Usando cache 'mais buscados' de {content_type}", xbmc.LOGINFO)
        cached_data = json.loads(cached_items)
        # Limitar a exibição aos primeiros 50 itens do cache (já ordenados)
        for item_data in cached_data[:MAX_ITEMS]:
            item, url, is_folder = create_video_item(handle, item_data)
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

        # DEBUG: Log dos top searches
        xbmc.log(f"[DEBUG] Search history completo: {json.dumps(search_history, indent=2)}", xbmc.LOGINFO)

        filtered_searches = {t: c for t, c in search_history.items() if c > min_count}
        
        # DEBUG: Log dos filtered searches
        xbmc.log(f"[DEBUG] Filtrados (count > {min_count}): {json.dumps(filtered_searches, indent=2)}", xbmc.LOGINFO)

        if not filtered_searches:
            xbmcgui.Dialog().ok("Aviso", f"Nenhum(a) {title.lower()} popular o suficiente para ser listado(a).")
            xbmcplugin.endOfDirectory(handle)
            return

        # Ordenar por contagem (decrescente) e pegar os top 50
        top_searches = sorted(filtered_searches.items(), key=lambda i: i[1], reverse=True)[:MAX_ITEMS]

        # DEBUG: Log dos top searches ordenados
        xbmc.log(f"[DEBUG] Top searches ordenados: {top_searches}", xbmc.LOGINFO)

        all_content = get_all_videos()
        filtered_videos = [v for v in all_content if v.get('type') == content_type]

        # DEBUG: Log dos vídeos disponíveis
        video_titles = [v.get('title', '') for v in filtered_videos]
        xbmc.log(f"[DEBUG] Vídeos disponíveis: {video_titles}", xbmc.LOGINFO)

        added_tmdb_ids = set()
        cache_data = []
        match_count = 0

        for term, count in top_searches:
            matched = False
            for video in filtered_videos:
                if match_video(video, term) and video.get('tmdb_id') not in added_tmdb_ids:
                    # DEBUG: Log do match encontrado
                    xbmc.log(f"[DEBUG] MATCH: term='{term}' count={count} -> video='{video.get('title', '')}' tmdb_id={video.get('tmdb_id', '')}", xbmc.LOGINFO)
                    
                    # Adicionar a contagem de buscas ao vídeo para manter a ordem
                    video_with_count = video.copy()
                    video_with_count['search_count'] = count
                    cache_data.append(video_with_count)
                    
                    item, url, is_folder = create_video_item(handle, video)
                    xbmcplugin.addDirectoryItem(handle, url, item, is_folder)
                    added_tmdb_ids.add(video.get('tmdb_id'))
                    matched = True
                    match_count += 1
                    break
            
            if not matched:
                # DEBUG: Log de termos sem match
                xbmc.log(f"[DEBUG] NO MATCH: term='{term}' count={count} - nenhum vídeo correspondente", xbmc.LOGINFO)

        # DEBUG: Log final
        xbmc.log(f"[DEBUG] Total de matches encontrados: {match_count}", xbmc.LOGINFO)

        # Garantir que o cache mantenha a ordem dos mais buscados
        if cache_data:
            # Ordenar pelo search_count para garantir a ordem no cache
            cache_data.sort(key=lambda x: x.get('search_count', 0), reverse=True)
            VIDEO_CACHE.set(cache_key, json.dumps(cache_data), expiry_hours=CACHE_EXPIRY_HOURS)

        xbmcplugin.endOfDirectory(handle)

    except Exception as e:
        xbmc.log(f"[Firebase] Erro em list_most_searched_generic: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(handle)


def list_most_searched(handle):
    list_most_searched_generic(handle, 'movie', 'Mais Buscados')


def list_most_searched_tvshows(handle):
    list_most_searched_generic(handle, 'tvshow', 'Mais Buscadas')
