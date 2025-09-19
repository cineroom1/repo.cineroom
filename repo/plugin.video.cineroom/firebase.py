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
# Configuração do Supabase
SUPABASE_URL = "https://iyvsukmykhdnmzqzwflo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml5dnN1a215a2hkbm16cXp3ZmxvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY3MzEzNzgsImV4cCI6MjA3MjMwNzM3OH0.j1hosUAlhFxayL0P7rg8_bs13J1i_JJ_jJrckA7pI8g"

CACHE_EXPIRY_HOURS = 24 * 2
SEARCH_CACHE_EXPIRY_HOURS = 0.5
SEARCH_CACHE_KEY = "search_terms_buffer"

URL = sys.argv[0]

# ThreadPoolExecutor para sincronização em background
executor = ThreadPoolExecutor(max_workers=4)

def get_url(**kwargs):
    return f'{URL}?{urlencode(kwargs)}'

def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

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
    
    if search_term == title_norm:
        return True
    if search_term.isdigit() and search_term == tmdb_id:
        return True
    
    if search_term in title_norm:
        return True
    
    if search_term in title_norm or title_norm in search_term:
        common_base = get_common_base(search_term, title_norm)
        if common_base and len(common_base) > 3:
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
    
    # Salva o tipo de vídeo junto do termo no cache local
    term_key = f"{normalized_term}_{video_type}"
    buffer_data["terms"][term_key] = buffer_data["terms"].get(term_key, 0) + 1
    
    buffer_data["timestamp"] = time.time()
    
    VIDEO_CACHE.set(cache_key, json.dumps(buffer_data), expiry_hours=SEARCH_CACHE_EXPIRY_HOURS)
    save_search_cache_to_disk(buffer_data, video_type)

    xbmc.log(f"[CACHE] Cache de buscas de {video_type} atualizado com {len(buffer_data['terms'])} termos.", xbmc.LOGINFO)

def sync_cache(video_type):
    """
    Sincroniza o cache de buscas com o Supabase em background.
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
            # 1. Obter os termos de busca do Supabase para o tipo específico
            url_get = f"{SUPABASE_URL}/rest/v1/search_history?select=term,count,content_type&content_type=eq.{video_type}"
            req_get = urllib.request.Request(url_get, headers=get_supabase_headers())
            with urllib.request.urlopen(req_get) as resp:
                supabase_data = {(item['term'], item['content_type']): item['count'] for item in json.loads(resp.read().decode("utf-8"))}

            payload_to_insert = []
            
            for term_key, count_local in buffer_data["terms"].items():
                # A chave agora inclui o tipo. Precisamos separá-la.
                term_parts = term_key.rsplit(f"_{video_type}", 1)
                term = term_parts[0]
                
                # A chave de busca agora é a tupla (termo, tipo_de_video)
                if (term, video_type) in supabase_data:
                    new_count = supabase_data[(term, video_type)] + count_local
                    # Atualiza o termo existente
                    # Adicionar filtro pelo tipo de conteúdo na URL de update
                    url_update = f"{SUPABASE_URL}/rest/v1/search_history?term=eq.{term}&content_type=eq.{video_type}"
                    payload = json.dumps({"count": new_count}).encode("utf-8")
                    req_patch = urllib.request.Request(url_update, data=payload, method="PATCH", headers=get_supabase_headers())
                    urllib.request.urlopen(req_patch)
                else:
                    # Prepara para inserir novos termos em um único lote
                    # Adicionar o content_type aqui
                    payload_to_insert.append({"term": term, "count": count_local, "content_type": video_type})
            
            # 2. Inserir os novos termos em lote
            if payload_to_insert:
                url_insert = f"{SUPABASE_URL}/rest/v1/search_history"
                payload = json.dumps(payload_to_insert).encode("utf-8")
                req_post = urllib.request.Request(url_insert, data=payload, method="POST", headers=get_supabase_headers())
                urllib.request.urlopen(req_post)
            
            xbmc.log(f"[Supabase] Sincronização concluída para {video_type}. Novos termos: {len(payload_to_insert)}.", xbmc.LOGINFO)

            VIDEO_CACHE.delete(key)
            file_path = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON_ID}/search_cache_{video_type}.json")
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            xbmc.log(f"[Supabase] Erro ao sincronizar cache para {video_type}: {str(e)}", xbmc.LOGERROR)

    executor.submit(_sync)
    return True

# Resto do código permanece o mesmo.

def sync_all_search_caches():
    xbmc.log("[Supabase] Sincronização de caches iniciada.", xbmc.LOGINFO)
    movie_synced = sync_cache('movie')
    tv_synced = sync_cache('tvshow')
    xbmc.log("[Supabase] Sincronização de caches concluída.", xbmc.LOGINFO)
    return movie_synced or tv_synced

def get_remote_min_count(content_type):
    """
    Busca o min_count remoto no nó 'config' do Supabase (simulando a estrutura do Firebase).
    Retorna 1 se houver algum problema ou se não houver valor configurado.
    """
    try:
        url = f"{SUPABASE_URL}/rest/v1/config?select=*"
        req = urllib.request.Request(url, headers=get_supabase_headers())
        with urllib.request.urlopen(req) as response:
            if response.getcode() != 200:
                xbmc.log(f"[Supabase] Não foi possível obter config, usando min_count=1 para {content_type}", xbmc.LOGWARNING)
                return 1

            config_data = json.loads(response.read().decode("utf-8"))
            
            if not config_data:
                 xbmc.log(f"[Supabase] Config não encontrada, usando min_count=1 para {content_type}", xbmc.LOGWARNING)
                 return 1
            
            # Supondo que você tem uma única linha na tabela 'config'
            config_row = config_data[0]
            
            if content_type == 'movie':
                min_count = int(config_row.get("min_count_movie", 3))
            elif content_type == 'tvshow':
                min_count = int(config_row.get("min_count_tvshow", 3))
            else:
                min_count = 3

            xbmc.log(f"[Supabase] min_count remoto para {content_type}: {min_count}", xbmc.LOGINFO)
            return min_count

    except Exception as e:
        xbmc.log(f"[Supabase] Erro ao obter min_count remoto para {content_type}: {e}", xbmc.LOGERROR)
        return 1

def list_most_searched_generic(handle, content_type, title):
    min_count = get_remote_min_count(content_type)
    MAX_ITEMS = 50

    xbmcplugin.setPluginCategory(handle, title)
    xbmcplugin.setContent(handle, 'movies' if content_type == 'movie' else 'tvshows')

    cache_key = f"most_searched_{content_type}_{min_count}"
    cached_items = VIDEO_CACHE.get(cache_key)
    if cached_items:
        xbmc.log(f"[CACHE] Usando cache 'mais buscados' de {content_type}", xbmc.LOGINFO)
        cached_data = json.loads(cached_items)
        for item_data in cached_data[:MAX_ITEMS]:
            item, url, is_folder = create_video_item(handle, item_data)
            xbmcplugin.addDirectoryItem(handle, url, item, is_folder)
        xbmcplugin.endOfDirectory(handle)
        return

    try:
        # Busca no Supabase, ordenando e filtrando diretamente na URL
        url = f"{SUPABASE_URL}/rest/v1/search_history?select=term,count,content_type&content_type=eq.{content_type}&count=gt.{min_count}&order=count.desc&limit={MAX_ITEMS}"
        req = urllib.request.Request(url, headers=get_supabase_headers())
        with urllib.request.urlopen(req) as response:
            if response.getcode() != 200:
                xbmcgui.Dialog().ok("Aviso", f"Nenhuma pesquisa registrada ainda para {title.lower()} ou erro de conexão.")
                xbmcplugin.endOfDirectory(handle)
                return

            response_text = response.read().decode('utf-8')
            search_history = json.loads(response_text)
            
            if not search_history:
                xbmcgui.Dialog().ok("Aviso", f"Nenhum(a) {title.lower()} popular o suficiente para ser listado(a).")
                xbmcplugin.endOfDirectory(handle)
                return

            xbmc.log(f"[DEBUG] Histórico de busca do Supabase: {json.dumps(search_history, indent=2)}", xbmc.LOGINFO)

            all_content = get_all_videos()
            filtered_videos = [v for v in all_content if v.get('type') == content_type]

            added_tmdb_ids = set()
            cache_data = []
            match_count = 0

            # Iterar sobre os resultados já ordenados do Supabase
            for item in search_history:
                term = item['term']
                count = item['count']
                matched = False
                for video in filtered_videos:
                    if match_video(video, term) and video.get('tmdb_id') not in added_tmdb_ids:
                        xbmc.log(f"[DEBUG] MATCH: term='{term}' count={count} -> video='{video.get('title', '')}' tmdb_id={video.get('tmdb_id', '')}", xbmc.LOGINFO)
                        
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
                    xbmc.log(f"[DEBUG] NO MATCH: term='{term}' count={count} - nenhum vídeo correspondente", xbmc.LOGINFO)

            xbmc.log(f"[DEBUG] Total de matches encontrados: {match_count}", xbmc.LOGINFO)

            if cache_data:
                VIDEO_CACHE.set(cache_key, json.dumps(cache_data), expiry_hours=CACHE_EXPIRY_HOURS)

            xbmcplugin.endOfDirectory(handle)

    except Exception as e:
        xbmc.log(f"[Supabase] Erro em list_most_searched_generic: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", str(e), xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(handle)

def list_most_searched(handle):
    list_most_searched_generic(handle, 'movie', 'Mais Buscados')

def list_most_searched_tvshows(handle):
    list_most_searched_generic(handle, 'tvshow', 'Mais Buscadas')