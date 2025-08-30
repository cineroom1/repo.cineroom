import concurrent.futures
import gzip
import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

# Configurações otimizadas para TCL P8M
ADDON = xbmcaddon.Addon()
CACHE_DIR = xbmcvfs.translatePath(os.path.join(ADDON.getAddonInfo('profile'), 'cache/'))
os.makedirs(CACHE_DIR, exist_ok=True)

# Configurações ajustáveis
RAM_CACHE_ENABLED = True
RAM_CACHE_MAX_SIZE = 5
DISK_CACHE_ENABLED = True
MAX_DISK_CACHE_MB = 50
CACHE_COMPRESSION = True
NETWORK_TIMEOUT = 8
MAX_RETRIES = 1
CACHE_FALLBACK_EXPIRY_HOURS = 14

#----------------------------------------------------------------------------------------------------------------------#
# Cache de RAM simplificado
#----------------------------------------------------------------------------------------------------------------------#
RAM_CACHE = {}

def ram_cache_get(key):
    return RAM_CACHE.get(key)

def ram_cache_set(key, value):
    if len(RAM_CACHE) >= RAM_CACHE_MAX_SIZE:
        RAM_CACHE.pop(next(iter(RAM_CACHE)))
    RAM_CACHE[key] = value

def ram_cache_delete(key):
    RAM_CACHE.pop(key, None)

def ram_cache_clear():
    RAM_CACHE.clear()

#----------------------------------------------------------------------------------------------------------------------#
# VideoCache corrigido
#----------------------------------------------------------------------------------------------------------------------#
class VideoCache:
    def __init__(self):
        self.cache_index = {}
        self.enabled = DISK_CACHE_ENABLED
        self.load_index()
        
    def load_index(self):
        index_file = os.path.join(CACHE_DIR, 'index.json')
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r') as f:
                    self.cache_index = json.load(f)
            except Exception as e:
                xbmc.log(f"[VideoCache] Erro ao carregar índice: {str(e)}", xbmc.LOGERROR)
                self.cache_index = {}
    
    def save_index(self):
        if not self.enabled:  # Usando self.enabled
            return
            
        index_file = os.path.join(CACHE_DIR, 'index.json')
        try:
            temp_file = index_file + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(self.cache_index, f, separators=(',', ':'))
            
            if os.path.exists(index_file):
                os.remove(index_file)
            os.rename(temp_file, index_file)
        except Exception as e:
            xbmc.log(f"[VideoCache] Erro ao salvar índice: {str(e)}", xbmc.LOGERROR)
    
    def get_cache_path(self, key):
        return os.path.join(CACHE_DIR, f"{key}.dat")
    
    def get_cache_size(self):
        try:
            return sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in os.listdir(CACHE_DIR) 
                     if os.path.isfile(os.path.join(CACHE_DIR, f)))
        except:
            return 0
    
    def is_expired(self, key):
        """Verifica se o cache expirou"""
        if key not in self.cache_index:
            return True
        expiry_time = datetime.fromisoformat(self.cache_index[key]['expires'])
        return datetime.now() > expiry_time
    
    def get(self, key):
        """Método get simplificado - removido parâmetro ignore_expiry"""
        if not self.enabled or key not in self.cache_index:  # Usando self.enabled
            return None
            
        if self.is_expired(key):
            return None
            
        cache_file = self.get_cache_path(key)
        try:
            with open(cache_file, 'rb') as f:
                data = f.read()
            return gzip.decompress(data).decode('utf-8') if CACHE_COMPRESSION else data.decode('utf-8')
        except Exception as e:
            xbmc.log(f"[VideoCache] Erro ao ler cache: {str(e)}", xbmc.LOGERROR)
            return None
    
    def set(self, key, data, expiry_hours=CACHE_FALLBACK_EXPIRY_HOURS):
        if not self.enabled:  # Usando self.enabled
            return False
            
        current_size = self.get_cache_size() / (1024 * 1024)
        if current_size >= MAX_DISK_CACHE_MB:
            xbmc.log("[VideoCache] Limite de cache em disco atingido", xbmc.LOGWARNING)
            return False
            
        cache_file = self.get_cache_path(key)
        try:
            data_bytes = data.encode('utf-8')
            if CACHE_COMPRESSION:
                data_bytes = gzip.compress(data_bytes)
            
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'wb') as f:
                f.write(data_bytes)
            
            if os.path.exists(cache_file):
                os.remove(cache_file)
            os.rename(temp_file, cache_file)
            
            self.cache_index[key] = {
                'expires': (datetime.now() + timedelta(hours=expiry_hours)).isoformat(),
                'size': len(data_bytes)
            }
            self.save_index()
            return True
            
        except Exception as e:
            xbmc.log(f"[VideoCache] Erro ao salvar cache: {str(e)}", xbmc.LOGERROR)
            if 'temp_file' in locals() and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            return False

    def delete(self, key):
        try:
            cache_file = self.get_cache_path(key)
            if os.path.exists(cache_file):
                os.remove(cache_file)
            if key in self.cache_index:
                del self.cache_index[key]
            self.save_index()
            ram_cache_delete(key)
        except Exception as e:
            xbmc.log(f"[VideoCache] Erro ao deletar cache: {str(e)}", xbmc.LOGERROR)

    def clear(self):
        ram_cache_clear()
        try:
            for filename in os.listdir(CACHE_DIR):
                file_path = os.path.join(CACHE_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    xbmc.log(f"[VideoCache] Erro ao remover {file_path}: {str(e)}", xbmc.LOGERROR)
            
            self.cache_index = {}
            self.save_index()
        except Exception as e:
            xbmc.log(f"[VideoCache] Erro ao limpar cache: {str(e)}", xbmc.LOGERROR)

VIDEO_CACHE = VideoCache()

#----------------------------------------------------------------------------------------------------------------------#
# Funções de busca corrigidas
#----------------------------------------------------------------------------------------------------------------------#
def fetch_videos(url):
    """Busca vídeos com tratamento de erros corrigido"""
    cache_key = hashlib.md5(url.encode()).hexdigest()
    
    # 1. Tentar cache RAM
    cached = ram_cache_get(cache_key)
    if cached is not None:
        return cached
    
    # 2. Tentar cache em disco
    cached = VIDEO_CACHE.get(cache_key)
    if cached:
        try:
            videos = json.loads(cached)
            ram_cache_set(cache_key, videos)
            return videos
        except:
            VIDEO_CACHE.delete(cache_key)
    
    # 3. Buscar da rede (com timeout corrigido)
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                time.sleep(1)
                
            # Configuração do timeout corrigida
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept-Encoding': 'gzip'
            })
            
            # Timeout aplicado no urlopen, não no Request
            with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as response:
                if response.status == 200:
                    data = response.read()
                    if response.info().get('Content-Encoding') == 'gzip':
                        data = gzip.decompress(data)
                    
                    videos = json.loads(data.decode('utf-8'))
                    videos = [v for v in videos if not v.get('is_vip') and not v.get('vip_exclusive')]
                    
                    if VIDEO_CACHE.set(cache_key, json.dumps(videos)):
                        ram_cache_set(cache_key, videos)
                    
                    return videos
                    
        except Exception as e:
            xbmc.log(f"[ERRO] Falha ao buscar {url}: {str(e)}", xbmc.LOGERROR)
            if attempt == MAX_RETRIES - 1:
                # Tenta usar cache expirado como fallback
                if VIDEO_CACHE.get(cache_key) is None and cache_key in VIDEO_CACHE.cache_index:
                    try:
                        with open(VIDEO_CACHE.get_cache_path(cache_key), 'rb') as f:
                            data = f.read()
                        return json.loads(gzip.decompress(data).decode('utf-8') if CACHE_COMPRESSION else data.decode('utf-8'))
                    except:
                        pass
    return []

def get_all_videos():
    """Carrega todos os vídeos com tratamento de erros"""
    from resources.lib.menus import get_menu
    
    progress = xbmcgui.DialogProgressBG()
    progress.create('Carregando vídeos...')
    
    try:
        menu = get_menu()
        if not menu:
            return []
        
        urls = []
        for menu_item in menu:
            for sub in menu_item.get('subcategorias', []):
                if url := sub.get('externallink'):
                    if not sub.get('is_vip'):
                        urls.append(url)
        
        max_workers = min(2, len(urls))
        all_videos = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_videos, url): url for url in urls}
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    if videos := future.result():
                        all_videos.extend(videos)
                    progress.update(int((i + 1) / len(urls) * 100))
                except Exception as e:
                    xbmc.log(f"[ERRO] Processamento falhou: {str(e)}", xbmc.LOGERROR)
        
        return all_videos
        
    except Exception as e:
        xbmc.log(f"[ERRO CRÍTICO] Falha ao carregar vídeos: {str(e)}", xbmc.LOGERROR)
        return []
    finally:
        if not progress.isFinished():
            progress.close()

def clear_cache(show_dialog=True):
    """
    Limpa o cache de forma seletiva com base na escolha do usuário.
    """
    if show_dialog:
        dialog = xbmcgui.Dialog()
        options = ["Limpar Cache Temporário", "Limpar Todo o Cache"]
        choice = dialog.select("Escolha o tipo de limpeza de cache", options)

        # Se o usuário cancelar a seleção (-1)
        if choice == -1:
            dialog.notification("Cancelado", "Ação de limpeza cancelada", xbmcgui.NOTIFICATION_INFO)
            return False

    try:
        # Ação baseada na escolha do usuário
        if choice == 0:  # Limpar Cache Temporário
            # Define as chaves de cache que são temporárias
            temp_cache_keys = ["search_terms_buffer_movie", "search_terms_buffer_tvshow"]
            
            # Limpa o cache de RAM
            ram_cache_clear()
            
            # Limpa as chaves temporárias do cache de disco
            for key in temp_cache_keys:
                VIDEO_CACHE.delete(key)
            
            xbmc.log("[CACHE] Cache temporário limpo com sucesso.", xbmc.LOGINFO)
            
            if show_dialog:
                dialog.notification('Sucesso', 'Cache temporário limpo!', xbmcgui.NOTIFICATION_INFO)
            
        elif choice == 1:  # Limpar Todo o Cache
            if not dialog.yesno('Confirmação', 'Tem certeza que deseja apagar todo o cache?\nIsso pode levar mais tempo para recarregar as listas.'):
                dialog.notification("Cancelado", "Ação de limpeza cancelada", xbmcgui.NOTIFICATION_INFO)
                return False

            ram_cache_clear()
            VIDEO_CACHE.clear()
            xbmc.log("[CACHE] Todo o cache limpo com sucesso.", xbmc.LOGINFO)

            if show_dialog:
                dialog.notification('Sucesso', 'Todo o cache limpo!', xbmcgui.NOTIFICATION_INFO)

        return True

    except Exception as e:
        xbmc.log(f"[ERRO] Falha ao limpar cache: {str(e)}", xbmc.LOGERROR)
        if show_dialog:
            xbmcgui.Dialog().notification('Erro', 'Falha ao limpar cache', xbmcgui.NOTIFICATION_ERROR)
        return False