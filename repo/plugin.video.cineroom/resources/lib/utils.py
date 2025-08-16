import concurrent.futures
import gzip
import hashlib
import json
import os
import shutil
import time
import urllib.request
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import base64

# NOTA: Assumindo que resources.lib.encryption_utils e resources.lib.menus existem
from resources.lib.encryption_utils import deobfuscate_string, obfuscate_string
# from resources.lib.menus import get_menu # Deixado na função para evitar problemas de importação circular

# Configurações do cache
ADDON = xbmcaddon.Addon()
CACHE_DIR = xbmcvfs.translatePath(os.path.join(ADDON.getAddonInfo('profile'), 'cache/'))
os.makedirs(CACHE_DIR, exist_ok=True)

NETWORK_FETCH_INTERVAL_HOURS = 12
CACHE_FALLBACK_EXPIRY_HOURS = 24
VIP_CACHE_EXPIRY = 4 # Horas para cache de conteúdo VIP

#----------------------------------------------------------------------------------------------------------------------#
# Cache de RAM para acesso rápido
#----------------------------------------------------------------------------------------------------------------------#
RAM_CACHE = {}

#----------------------------------------------------------------------------------------------------------------------#
# Funções de Otimização
#----------------------------------------------------------------------------------------------------------------------#

def get_all_videos():
    """
    Carrega todos os vídeos não-VIP com gestão eficiente de cache,
    filtrando automaticamente conteúdo VIP e otimizando para grandes listas.
    """
    from resources.lib.menus import get_menu

    progress = xbmcgui.DialogProgressBG()
    progress.create('Carregando...')
    xbmc.sleep(500)

    menu = get_menu()
    if not menu:
        progress.close()
        return []

    normal_urls = []
    for menu_item in menu:
        for sub in menu_item.get('subcategorias', []):
            url = sub.get('externallink')
            if url and not sub.get('is_vip'):
                normal_urls.append(url)

    all_videos = []
    try:
        total_urls = len(normal_urls)
        if total_urls == 0:
            return []

        # Limita o número de threads para evitar sobrecarga em dispositivos fracos
        num_threads = min(8, os.cpu_count() * 2) if os.cpu_count() else 4
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            future_to_url = {executor.submit(fetch_videos, url): url for url in normal_urls}
            
            for i, future in enumerate(concurrent.futures.as_completed(future_to_url)):
                if progress.isFinished():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                percentage = int(((i + 1) / total_urls) * 100)
                progress.update(percentage, f'Organizando...')
                
                try:
                    result = future.result()
                    if result:
                        all_videos.extend(result)
                except Exception as e:
                    xbmc.log(f"[ERRO] Processamento falhou para {future_to_url[future]}: {str(e)}", xbmc.LOGERROR)

    except Exception as e:
        xbmc.log(f"[ERRO CRÍTICO] Falha ao carregar vídeos: {str(e)}", xbmc.LOGERROR)
    finally:
        if not progress.isFinished():
            progress.close()

    final_videos = [v for v in all_videos if not v.get('is_vip') and not v.get('vip_exclusive')]
    xbmc.log(f"[FILTRO VIP] Total após filtro: {len(final_videos)} itens", xbmc.LOGINFO)
    
    return final_videos

def fetch_videos(url):
    """Busca vídeos com tratamento de cache e filtro VIP."""
    cache_key = url
    
    # 1. Tenta obter do cache na RAM primeiro (o mais rápido)
    if cache_key in RAM_CACHE:
        return RAM_CACHE[cache_key]
    
    # 2. Tenta obter do cache em disco
    if VIDEO_CACHE.enabled:
        cache_data = VIDEO_CACHE.get(cache_key)
        if cache_data:
            try:
                videos = json.loads(cache_data)
                RAM_CACHE[cache_key] = videos
                return videos
            except Exception:
                xbmc.log(f"[ERRO CACHE] Dados corrompidos para {url}", xbmc.LOGERROR)
                VIDEO_CACHE.delete(cache_key)
    
    # Se falhar, tenta buscar da rede
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(2 ** attempt)

            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept-Encoding': 'gzip'
            })
            
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.status == 200:
                    raw = response.read()
                    if response.info().get('Content-Encoding') == 'gzip':
                        raw = gzip.decompress(raw)
                    
                    data = json.loads(raw.decode('utf-8'))
                    videos = data[1:] if isinstance(data[0], dict) and "status" in data[0] else data
                    
                    videos = [v for v in videos if not v.get('is_vip') and not v.get('vip_exclusive')]
                    
                    if videos and VIDEO_CACHE.enabled:
                        VIDEO_CACHE.set(cache_key, json.dumps(videos), expiry_hours=CACHE_FALLBACK_EXPIRY_HOURS)
                        RAM_CACHE[cache_key] = videos
                    
                    return videos

        except Exception as e:
            xbmc.log(f"[ERRO] Falha na tentativa {attempt+1} para {url}: {str(e)}", xbmc.LOGERROR)

    # Fallback para cache mesmo expirado em caso de falha total na rede
    if VIDEO_CACHE.enabled:
        cached = VIDEO_CACHE.get(cache_key, ignore_expiry=True)
        if cached:
            try:
                videos = json.loads(cached)
                RAM_CACHE[cache_key] = videos
                return videos
            except Exception:
                pass
    
    return []

#----------------------------------------------------------------------------------------------------------------------#
# Classe VideoCache
#----------------------------------------------------------------------------------------------------------------------#

class VideoCache:
    def __init__(self):
        self.cache_index = {}
        self.load_index()
        self.enabled = True

    def is_expired(self, url, ignore_missing=False):
        try:
            cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()
            if cache_key in self.cache_index:
                expiry_time = datetime.fromisoformat(self.cache_index[cache_key]['expires'])
                return datetime.now() > expiry_time
            return ignore_missing
        except Exception:
            return True

    def exists(self, url):
        cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()
        return cache_key in self.cache_index

    def _obfuscate_url(self, url):
        if not url:
            return url
        return base64.b64encode(url[::-1].encode('utf-8')).decode('utf-8')

    def _deobfuscate_url(self, obfuscated_url):
        if not obfuscated_url:
            return obfuscated_url
        try:
            return base64.b64decode(obfuscated_url.encode('utf-8')).decode('utf-8')[::-1]
        except:
            return obfuscated_url

    def _obfuscate_data_payload(self, data_string):
        if not isinstance(data_string, str):
            return data_string
        return base64.b64encode(data_string[::-1].encode('utf-8')).decode('utf-8')

    def _deobfuscate_data_payload(self, obfuscated_string):
        if not isinstance(obfuscated_string, str):
            return obfuscated_string
        try:
            return base64.b64decode(obfuscated_string.encode('utf-8')).decode('utf-8')[::-1]
        except:
            return obfuscated_string

    def get_cache_size(self):
        total_size = 0
        for filename in os.listdir(CACHE_DIR):
            filepath = os.path.join(CACHE_DIR, filename)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
        return total_size

    def load_index(self):
        index_file = os.path.join(CACHE_DIR, 'index.json')

        if not os.path.exists(index_file):
            self.cache_index = {}
            return

        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                obfuscated_index = json.load(f)

            self.cache_index = {}

            def process_entry(item):
                key, entry = item
                try:
                    url = self._deobfuscate_url(entry.get('url', ''))
                    if url and 'expires' in entry:
                        entry['url'] = url
                        return key, entry
                except Exception:
                    pass
                return None

            threads = min(2, os.cpu_count()) if os.cpu_count() else 2
            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                results = list(executor.map(process_entry, obfuscated_index.items()))

            self.cache_index = {key: entry for result in results if result for key, entry in [result]}
        except Exception as e:
            xbmc.log(f"[VideoCache] ERRO ao carregar índice: {str(e)}", xbmc.LOGERROR)
            self.cache_index = {}

    def save_index(self):
        index_file = os.path.join(CACHE_DIR, 'index.json')
        try:
            obfuscated_index = {}
            for key, entry in self.cache_index.items():
                obfuscated_entry = entry.copy()
                obfuscated_entry['url'] = self._obfuscate_url(entry.get('url', ''))
                obfuscated_index[key] = obfuscated_entry

            temp_file = index_file + '.tmp'
            # JSON minificado para salvar espaço
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(obfuscated_index, f, separators=(',', ':'), ensure_ascii=False)

            if os.path.getsize(temp_file) > 0:
                if os.path.exists(index_file):
                    os.remove(index_file)
                os.rename(temp_file, index_file)
        except Exception as e:
            xbmc.log(f"[VideoCache] ERRO ao salvar índice: {str(e)}", xbmc.LOGERROR)

    def get_cache_path(self, url):
        return os.path.join(CACHE_DIR, hashlib.sha256(url.encode('utf-8')).hexdigest() + '.dat')

    def get(self, url, ignore_expiry=False):
        if not self.enabled:
            return None

        cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()

        if cache_key not in self.cache_index:
            return None

        try:
            if not ignore_expiry:
                expiry_time = datetime.fromisoformat(self.cache_index[cache_key]['expires'])
                if datetime.now() > expiry_time:
                    self.delete(url)
                    return None

            cache_file = self.get_cache_path(url)
            if not os.path.exists(cache_file):
                return None

            # Lê o arquivo binário comprimido e o descomprime
            with open(cache_file, 'rb') as f:
                compressed_data = f.read()

            data_string = gzip.decompress(compressed_data).decode('utf-8')
            
            if not isinstance(data_string, str) or not data_string:
                return None

            # Os dados lidos são uma string JSON. Não é necessário desobfuscá-la
            return data_string

        except Exception as e:
            xbmc.log(f"[VideoCache] ERRO ao ler cache para {url.split('/')[-1]}: {str(e)}", xbmc.LOGERROR)
            return None

    def set(self, url, data_payload_string, expiry_hours=24):
        if not self.enabled or not isinstance(data_payload_string, str) or not data_payload_string:
            return False

        try:
            cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()
            cache_file = os.path.join(CACHE_DIR, cache_key + '.dat')
            
            os.makedirs(CACHE_DIR, exist_ok=True)
            
            # Comprime a string JSON antes de salvar
            compressed_data = gzip.compress(data_payload_string.encode('utf-8'))
            
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'wb') as f: # Modo de escrita binária
                f.write(compressed_data)
            
            if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                raise IOError("Falha ao escrever arquivo temporário")
            
            if os.path.exists(cache_file):
                os.remove(cache_file)
            os.rename(temp_file, cache_file)
            
            self.cache_index[cache_key] = {
                'url': url,
                'expires': (datetime.now() + timedelta(hours=expiry_hours)).isoformat(),
                'size': len(compressed_data) # Armazena o tamanho comprimido
            }
            
            self.save_index()
            
            return True

        except Exception as e:
            xbmc.log(f"[ERRO CACHE] Falha ao salvar {url}: {str(e)}", xbmc.LOGERROR)
            if 'temp_file' in locals() and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            return False

    def delete(self, url):
        cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()
        try:
            cache_file = self.get_cache_path(url)
            if os.path.exists(cache_file):
                os.remove(cache_file)
            if cache_key in self.cache_index:
                del self.cache_index[cache_key]
            self.save_index()
            # Remove também do cache de RAM
            if url in RAM_CACHE:
                del RAM_CACHE[url]
        except Exception as e:
            xbmc.log(f"[VideoCache] ERRO ao remover cache: {str(e)}", xbmc.LOGERROR)

    def clear(self):
        try:
            # Limpa o cache de RAM primeiro
            global RAM_CACHE
            RAM_CACHE = {}

            for filename in os.listdir(CACHE_DIR):
                file_path = os.path.join(CACHE_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    xbmc.log(f"[VideoCache] ERRO ao remover {file_path}: {str(e)}", xbmc.LOGERROR)
            
            self.cache_index = {}
            self.save_index()
        except Exception as e:
            xbmc.log(f"[VideoCache] ERRO ao limpar cache: {str(e)}", xbmc.LOGERROR)

VIDEO_CACHE = VideoCache()

#----------------------------------------------------------------------------------------------------------------------#
# Funções de Interface
#----------------------------------------------------------------------------------------------------------------------#

def clear_cache(show_dialog=True):
    """
    Limpeza completa e verificada do cache com notificações aprimoradas
    :param show_dialog: Mostra diálogos de confirmação e resultado
    :return: True se limpeza bem-sucedida, False caso contrário
    """
    if show_dialog:
        if not xbmcgui.Dialog().yesno('Limpar Cache', 'Tem certeza que deseja limpar todo o cache?'):
            xbmcgui.Dialog().notification("Operação Cancelada", "Limpeza de cache não realizada", xbmcgui.NOTIFICATION_INFO)
            return False
        else:
            progress = xbmcgui.DialogProgress()
            progress.create('Limpando Cache', 'Iniciando processo...')

    try:
        if show_dialog:
            progress.update(20, 'Limpando índice de cache...')
        
        VIDEO_CACHE.cache_index = {}
        VIDEO_CACHE.save_index()
        
        if show_dialog:
            progress.update(40, 'Removendo arquivos de cache...')
        
        failed_deletions = []
        cache_files = os.listdir(CACHE_DIR)
        total_files = len(cache_files)
        
        # Limpa o cache de RAM
        global RAM_CACHE
        RAM_CACHE = {}
        
        for index, filename in enumerate(cache_files):
            file_path = os.path.join(CACHE_DIR, filename)
            try:
                if show_dialog:
                    progress.update(40 + int((index/total_files)*50),
                                   f'Removendo {filename}...')
                
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                failed_deletions.append((filename, str(e)))
                xbmc.log(f"[CACHE] Falha ao remover {filename}: {str(e)}", xbmc.LOGERROR)

        remaining_files = [f for f in os.listdir(CACHE_DIR) if f != 'temp']
        
        if show_dialog:
            progress.close()

        if not remaining_files:
            success_msg = "Cache limpo com sucesso"
            xbmc.log(f"[CACHE] {success_msg}", xbmc.LOGINFO)
            if show_dialog:
                xbmcgui.Dialog().notification('Sucesso', success_msg,
                                             xbmcgui.NOTIFICATION_INFO, sound=False)
            return True
        else:
            error_msg = f"{len(remaining_files)} arquivos não removidos"
            xbmc.log(f"[CACHE ERRO] {error_msg}", xbmc.LOGERROR)
            
            if show_dialog:
                if failed_deletions:
                    report = "\n".join([f"• {f[0]}: {f[1]}" for f in failed_deletions[:3]])
                    if len(failed_deletions) > 3:
                        report += f"\n• e mais {len(failed_deletions)-3} arquivos..."
                else:
                    report = "Arquivos residuais encontrados sem registro de erro"
                
                xbmcgui.Dialog().ok('Erro ao Limpar',
                                   f'Alguns arquivos não puderam ser removidos:\n{report}')
            return False

    except Exception as e:
        xbmc.log(f"[CACHE ERRO CRÍTICO] {str(e)}", xbmc.LOGERROR)
        if show_dialog:
            if 'progress' in locals():
                progress.close()
            xbmcgui.Dialog().notification('Erro', 'Falha crítica ao limpar cache',
                                         xbmcgui.NOTIFICATION_ERROR)
        return False