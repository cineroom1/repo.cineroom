import os
import json
import hashlib
import urllib.request
import concurrent.futures
from datetime import datetime, timedelta
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import time
import base64
import random
from urllib.error import HTTPError, URLError
import gzip
import io
import threading
import shutil

from resources.lib.encryption_utils import obfuscate_string, deobfuscate_string

# Configurações do cache
ADDON = xbmcaddon.Addon()
CACHE_DIR = xbmcvfs.translatePath(os.path.join(ADDON.getAddonInfo('profile'), 'cache/'))
os.makedirs(CACHE_DIR, exist_ok=True)

NETWORK_FETCH_INTERVAL_HOURS = 12
CACHE_FALLBACK_EXPIRY_HOURS = 24 # Manter o cache para 24h como fallback

def get_all_videos():
    """
    Carrega todos os vídeos com gestão eficiente de cache, com fetch paralelo
    e progresso fluido usando DialogProgressBG. Tenta buscar novo conteúdo a cada 2 horas,
    usando o cache como fallback se a rede falhar.
    """
    from resources.lib.menus import get_menu # Importar localmente se for uma dependência específica

    all_videos = []
    progress = xbmcgui.DialogProgressBG()
    progress.create('Carregando Conteúdo', 'Inicializando...')

    local_cache = {}
    cache_lock = threading.Lock()

    menu = get_menu()
    if not menu:
        progress.close()
        xbmc.log("[INFO] Menu vazio, nenhum conteúdo para carregar.", xbmc.LOGINFO)
        return all_videos

    def fetch_videos(url):
        """
        Função auxiliar para buscar vídeos de uma URL, com retries e cache.
        Prioriza a busca na rede a cada NETWORK_FETCH_INTERVAL_HOURS (2h),
        usando o cache como fallback.
        """
        max_retries = 3
        base_delay = 0.5 # Atraso inicial para controle de taxa

        # Tentar obter do cache primeiro, mas com controle de tempo para forçar a rede
        cached_data_string = None
        last_fetch_time = None
        
        if VIDEO_CACHE.enabled:
            

            should_fetch_from_network = True # Assumimos que devemos buscar da rede por padrão

            # Tenta obter dados do cache. Se sua classe `VideoCache` tem um `get_timestamp_and_data(url)`
            # seria o ideal para saber quando foi salvo. Se não, vamos simular.
            # Por enquanto, vou manter o seu `VIDEO_CACHE.get(url)` que respeita o expiry_hours do SET.
            # O que significa que se ele expirar em 24h, ele não será retornado.
            # Precisamos de algo que nos diga: "Esse cache tem mais de 2 horas?"

            # Vamos usar o próprio `VIDEO_CACHE` para armazenar o timestamp da última BUSCA REAL de rede.
            # Assumindo que `VIDEO_CACHE` pode armazenar um timestamp para uma dada chave.
            # Ex: `VIDEO_CACHE.get_last_fetch_timestamp(url)`

            last_network_fetch_timestamp = VIDEO_CACHE.get(f"{url}_last_fetch_timestamp", ignore_expiry=True) # Busca o timestamp
            if last_network_fetch_timestamp:
                try:
                    last_fetch_dt = datetime.fromtimestamp(float(last_network_fetch_timestamp))
                    # print(f"Última busca de {url.split('/')[-1]}: {last_fetch_dt}") # Para depuração
                    time_diff = datetime.now() - last_fetch_dt
                    # print(f"Diferença de tempo: {time_diff}") # Para depuração
                    if time_diff < timedelta(hours=NETWORK_FETCH_INTERVAL_HOURS): # Remova o 'datetime.' antes de 'timedelta'
                        should_fetch_from_network = False # Ainda não passou o tempo para nova busca de rede
                except Exception as e:
                    xbmc.log(f"[ERRO] Falha ao ler timestamp de cache para {url.split('/')[-1]}: {str(e)}", xbmc.LOGERROR)
                    should_fetch_from_network = True # Força a busca se o timestamp estiver corrompido
            else:
                should_fetch_from_network = True # Se não tem timestamp, é a primeira vez, busca da rede

        videos = [] # Para armazenar os vídeos buscados ou do cache

        # 1. Tenta buscar da rede (se o tempo de atualização de 2h passou ou é a primeira vez)
        if should_fetch_from_network:
            xbmc.log(f"[DEBUG] Tentando buscar da rede para {url.split('/')[-1]}...", xbmc.LOGDEBUG) # NOVO LOG
            for attempt in range(max_retries):
                try:
                    time.sleep(base_delay * (0.5 ** attempt))

                    xbmc.log(f"[NETWORK] Buscando {url.split('/')[-1]} (tentativa {attempt+1})", xbmc.LOGINFO)
                    req = urllib.request.Request(
                        url,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)',
                            'Accept': 'application/json',
                            'Accept-Encoding': 'gzip, deflate'
                        }
                    )
                    with urllib.request.urlopen(req, timeout=20) as response:
                        if response.status == 200:
                            raw = response.read()
                            if response.info().get('Content-Encoding') == 'gzip' or raw[:2] == b'\x1f\x8b':
                                raw = gzip.decompress(raw)
                           
                            data = json.loads(raw.decode('utf-8'))
                            videos = data[1:] if isinstance(data[0], dict) and "status" in data[0] else data

                            if not videos: # NOVO CHECK
                                xbmc.log(f"[NETWORK] NENHUM VÍDEO NOVO encontrado em {url.split('/')[-1]}", xbmc.LOGINFO)
                                # Se não há vídeos, você pode decidir se quer continuar para o cache ou falhar
                                # Por enquanto, vamos deixar cair para o cache, mas o log te informará.
                                raise ValueError("Nenhum vídeo retornado pela rede") # Força o fluxo para o catch
                            
                            for v in videos:
                                v['external_link'] = url

                            # Salva no cache persistente com expiração de 24 horas
                            if videos and VIDEO_CACHE.enabled:
                                videos_json_string = json.dumps(videos, ensure_ascii=False)
                                VIDEO_CACHE.set(url, videos_json_string, expiry_hours=CACHE_FALLBACK_EXPIRY_HOURS)
                                # Também salva o timestamp da última busca de rede bem-sucedida
                                VIDEO_CACHE.set(f"{url}_last_fetch_timestamp", str(time.time()), expiry_hours=CACHE_FALLBACK_EXPIRY_HOURS)

                            xbmc.log(f"[NETWORK SUCESSO] {url.split('/')[-1]} - {len(videos)} vídeos carregados", xbmc.LOGINFO) # LOG MELHORADO
                            return videos # Retorna os vídeos da rede

                except urllib.error.URLError as e:
                    xbmc.log(f"[ERRO DE REDE] {url.split('/')[-1]}: {str(e)} (tentativa {attempt+1})", xbmc.LOGERROR)
                    time.sleep(1 * (attempt + 1))
                except json.JSONDecodeError as e:
                    xbmc.log(f"[ERRO JSON] {url.split('/')[-1]}: {str(e)} (dados inválidos da rede)", xbmc.LOGERROR)
                    break
                except ValueError as e: # NOVO CATCH para o "Nenhum vídeo novo"
                    xbmc.log(f"[AVISO] {url.split('/')[-1]}: {str(e)} (tentativa {attempt+1})", xbmc.LOGWARNING)
                    break # Se não há vídeos, não adianta tentar de novo
                except Exception as e:
                    xbmc.log(f"[ERRO GERAL] {url.split('/')[-1]}: {str(e)} (tentativa {attempt+1})", xbmc.LOGERROR)
                    time.sleep(1 * (attempt + 1))
            
            # Se chegarmos aqui, significa que todas as tentativas de rede falharam
            xbmc.log(f"[NETWORK FALHA TOTAL] Falha em buscar conteúdo novo para {url.split('/')[-1]}", xbmc.LOGWARNING) # NOVO LOG DE FALHA NA REDE

        else: # NOVO LOG
            xbmc.log(f"[CACHE] Ainda não é hora de buscar da rede para {url.split('/')[-1]}. Verificando cache válido...", xbmc.LOGDEBUG)

        # 2. Se a busca de rede não foi necessária (tempo não passou) ou falhou, tenta o cache persistente válido
        if VIDEO_CACHE.enabled:
            cached_data_string_valid = VIDEO_CACHE.get(url) # Busca o cache respeitando o TTL de 24h
            if cached_data_string_valid:
                try:
                    cached_videos_valid = json.loads(cached_data_string_valid)
                    xbmc.log(f"[CACHE PERSISTENTE VÁLIDO] Encontrado para {url.split('/')[-1]}", xbmc.LOGINFO)
                    with cache_lock:
                        local_cache[url] = cached_videos_valid # Adiciona ao cache local
                    return cached_videos_valid
                except json.JSONDecodeError as e:
                    xbmc.log(f"[ERRO JSON] Cache persistente válido corrompido para {url.split('/')[-1]}: {str(e)}", xbmc.LOGERROR)
                    VIDEO_CACHE.delete(url)
                except Exception as e:
                    xbmc.log(f"[ERRO] Falha ao ler cache persistente válido para {url.split('/')[-1]}: {str(e)}", xbmc.LOGERROR)
                    VIDEO_CACHE.delete(url)

        # 3. Fallback para cache expirado (se todas as tentativas de rede falharam e não há cache válido recente)
        if VIDEO_CACHE.enabled:
            expired_data_string = VIDEO_CACHE.get(url, ignore_expiry=True) # Ignora a expiração para o fallback
            if expired_data_string:
                try:
                    expired_videos = json.loads(expired_data_string)
                    xbmc.log(f"[CACHE FALLBACK] Usando cache expirado para {url.split('/')[-1]} (falha total na rede/cache válido)", xbmc.LOGWARNING)
                    with cache_lock:
                        local_cache[url] = expired_videos
                    return expired_videos
                except json.JSONDecodeError as e:
                    xbmc.log(f"[ERRO JSON] Cache expirado corrompido para {url.split('/')[-1]}: {str(e)}", xbmc.LOGERROR)
                    VIDEO_CACHE.delete(url) # Limpa cache corrompido
                except Exception as e:
                    xbmc.log(f"[ERRO] Falha ao ler cache expirado para {url.split('/')[-1]}: {str(e)}", xbmc.LOGERROR)
                    VIDEO_CACHE.delete(url) # Limpa cache corrompido

        xbmc.log(f"[ERRO] Falha total ao buscar ou carregar qualquer cache para {url.split('/')[-1]}", xbmc.LOGERROR)
        return []

    urls = list({
        sub.get('externallink')
        for menu_item in menu
        for sub in menu_item.get('subcategorias', [])
        if sub.get('externallink')
    })

    try:
        total_urls = len(urls)
        if not total_urls:
            progress.update(100, 'Nenhum conteúdo encontrado')
            time.sleep(1)
            return []

        progress.update(0, 'Iniciando busca de conteúdo...')

        max_workers = 5
        completed_tasks = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(fetch_videos, url): url for url in urls}
            
            for future in concurrent.futures.as_completed(future_to_url):
                if progress.isFinished():
                    xbmc.log("[INFO] Carregamento cancelado pelo usuário.", xbmc.LOGINFO)
                    for f in future_to_url:
                        if not f.done():
                            f.cancel()
                    break

                completed_tasks += 1
                url = future_to_url[future]
                
                progress_percent = int((completed_tasks / total_urls) * 100)
                
                progress.update(progress_percent,
                                f'Extraindo... {completed_tasks}')

                try:
                    result = future.result()
                    if result:
                        all_videos.extend(result)
                except concurrent.futures.CancelledError:
                    xbmc.log(f"[INFO] Tarefa cancelada para {url.split('/')[-1]}", xbmc.LOGINFO)
                except Exception as e:
                    xbmc.log(f"[ERRO] Falha ao processar {url.split('/')[-1]}: {str(e)}", xbmc.LOGERROR)

        if not progress.isFinished():
            progress.update(100, 'Carregamento completo!')
            time.sleep(1.5)

        xbmc.log(f"[SUCESSO] Total de vídeos carregados: {len(all_videos)}", xbmc.LOGINFO)
        if all_videos:
            sample = ", ".join(v.get('title', 'sem título')[:20] for v in all_videos[:3])
            xbmc.log(f"[SUCESSO] Amostra: {sample}...", xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f"[ERRO CRÍTICO] Falha inesperada em get_all_videos: {str(e)}", xbmc.LOGERROR)
        if not progress.isFinished():
            progress.update(100, 'Erro no carregamento')
            time.sleep(2)
    finally:
        if not progress.isFinished():
            progress.close()

    return all_videos

class VideoCache:
    def __init__(self):
        self.cache_index = {}
        self.load_index()
        self.enabled = True
        # xbmc.log(f"[VideoCache] Inicializado. Status: {'Ativado' if self.enabled else 'Desativado'}", xbmc.LOGINFO)

    def is_expired(self, url, ignore_missing=False):
        """Verifica se um item do cache está expirado com tratamento de erro"""
        try:
            cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest() # MUDANÇA AQUI
            if cache_key in self.cache_index:
                expiry_time = datetime.fromisoformat(self.cache_index[cache_key]['expires'])
                return datetime.now() > expiry_time
            return ignore_missing
        except Exception as e:
            # xbmc.log(f"[VideoCache] Erro ao verificar expiração: {str(e)}", xbmc.LOGERROR)
            return True

    def exists(self, url):
        """Verifica rápida se uma URL existe no cache (sem verificar expiração)"""
        cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()
        return cache_key in self.cache_index

    def _obfuscate_url(self, url):
        """Ofusca uma URL para armazenamento seguro no índice"""
        if not url:
            return url
        return base64.b64encode(url[::-1].encode('utf-8')).decode('utf-8')

    def _deobfuscate_url(self, obfuscated_url):
        """Desofusca uma URL armazenada no índice"""
        if not obfuscated_url:
            return obfuscated_url
        try:
            return base64.b64decode(obfuscated_url.encode('utf-8')).decode('utf-8')[::-1]
        except:
            return obfuscated_url

    # NOVOS MÉTODOS PARA OFUSCAÇÃO DO CONTEÚDO DO .DAT
    def _obfuscate_data_payload(self, data_string):
        """Ofusca a string de dados antes de salvá-la no arquivo .dat"""
        if not isinstance(data_string, str):
            return data_string # Retorna como está se não for string
        # Exemplo simples: inverte e codifica em base64
        return base64.b64encode(data_string[::-1].encode('utf-8')).decode('utf-8')

    def _deobfuscate_data_payload(self, obfuscated_string):
        """Desofusca a string de dados lida do arquivo .dat"""
        if not isinstance(obfuscated_string, str):
            return obfuscated_string # Retorna como está se não for string
        try:
            # Reverte a ofuscação: decodifica de base64 e inverte
            return base64.b64decode(obfuscated_string.encode('utf-8')).decode('utf-8')[::-1]
        except:
            # Em caso de erro na desofuscação (ex: arquivo corrompido, não ofuscado)
            # xbmc.log(f"[VideoCache] ERRO ao desofuscar dados, tentando retornar original.", xbmc.LOGWARNING)
            return obfuscated_string # Tenta retornar a string original

    def get_cache_size(self):
        """Retorna o tamanho total do cache em bytes"""
        total_size = 0
        for filename in os.listdir(CACHE_DIR):
            filepath = os.path.join(CACHE_DIR, filename)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
        return total_size

    def load_index(self):
        """Carrega o índice do cache com URLs ofuscadas usando múltiplas threads"""
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
                except Exception as e:
                    # xbmc.log(f"[VideoCache] Erro ao processar entrada {key}: {str(e)}", xbmc.LOGDEBUG)
                    pass # Evita log excessivo em erros de entradas

                return None

            try:
                # threads_str = ADDON.getSetting('threads_cache')
                threads = 4 # int(threads_str) if threads_str.isdigit() else 4
            except Exception:
                threads = 4

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                results = list(executor.map(process_entry, obfuscated_index.items()))

            self.cache_index = {key: entry for result in results if result for key, entry in [result]}

            # xbmc.log(f"[VideoCache] Índice carregado com {len(self.cache_index)} entradas usando {threads} threads", xbmc.LOGDEBUG)

        except Exception as e:
            # xbmc.log(f"[VideoCache] ERRO ao carregar índice: {str(e)}", xbmc.LOGERROR)
            self.cache_index = {}

    def save_index(self):
        """Salva o índice do cache com URLs ofuscadas"""
        index_file = os.path.join(CACHE_DIR, 'index.json')
        try:
            obfuscated_index = {}
            for key, entry in self.cache_index.items():
                obfuscated_entry = entry.copy()
                obfuscated_entry['url'] = self._obfuscate_url(entry.get('url', ''))
                obfuscated_index[key] = obfuscated_entry

            temp_file = index_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(obfuscated_index, f, indent=2, ensure_ascii=False)

            if os.path.getsize(temp_file) > 0:
                if os.path.exists(index_file):
                    os.remove(index_file)
                os.rename(temp_file, index_file)
                # xbmc.log("[VideoCache] Índice salvo com sucesso", xbmc.LOGDEBUG)
            else:
                # xbmc.log("[VideoCache] AVISO: Índice vazio não foi salvo", xbmc.LOGWARNING)
                pass
        except Exception as e:
            # xbmc.log(f"[VideoCache] ERRO ao salvar índice: {str(e)}", xbmc.LOGERROR)
            pass

    def get_cache_path(self, url):
        """Retorna o caminho completo do arquivo de cache"""
        return os.path.join(CACHE_DIR, hashlib.sha256(url.encode('utf-8')).hexdigest() + '.dat')

    def get(self, url, ignore_expiry=False):
        """Obtém dados do cache (espera uma string), com opção para ignorar expiração"""
        if not self.enabled:
            # xbmc.log(f"[VideoCache] Cache DESATIVADO (ignorando get): {url.split('/')[-1]}", xbmc.LOGDEBUG)
            return None

        cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()

        if cache_key not in self.cache_index:
            # xbmc.log(f"[VideoCache] Cache MISS (não encontrado): {url.split('/')[-1]}", xbmc.LOGDEBUG)
            return None

        try:
            if not ignore_expiry:
                expiry_time = datetime.fromisoformat(self.cache_index[cache_key]['expires'])
                if datetime.now() > expiry_time:
                    # xbmc.log(f"[VideoCache] Cache EXPIRADO: {url.split('/')[-1]}", xbmc.LOGDEBUG)
                    self.delete(url)
                    return None

            cache_file = self.get_cache_path(url)
            if not os.path.exists(cache_file):
                # xbmc.log(f"[VideoCache] AVISO: Arquivo de cache não existe: {cache_file}", xbmc.LOGWARNING)
                return None

            with open(cache_file, 'r', encoding='utf-8') as f:
                obfuscated_data_string = f.read() # LÊ A STRING OFUSCADA

            data_string = self._deobfuscate_data_payload(obfuscated_data_string) # DESOFUSCA AQUI

            if not isinstance(data_string, str) or not data_string:
                # xbmc.log(f"[VideoCache] AVISO: Dados inválidos em cache (não é string válida): {cache_file}", xbmc.LOGWARNING)
                return None

            # xbmc.log(f"[VideoCache] Cache HIT: {url.split('/')[-1]} (tamanho da string: {len(data_string)})", xbmc.LOGINFO)
            return data_string

        except Exception as e:
            # xbmc.log(f"[VideoCache] ERRO ao ler cache para {url.split('/')[-1]}: {str(e)}", xbmc.LOGERROR)
            return None

    def set(self, url, data_payload_string, expiry_hours=24):
        """Versão corrigida do método set()"""
        if not self.enabled or not isinstance(data_payload_string, str) or not data_payload_string:
            return False

        try:
            # Usa o mesmo algoritmo de hash para ambos
            cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()
            cache_file = os.path.join(CACHE_DIR, cache_key + '.dat')
        
            # Cria diretório se não existir
            os.makedirs(CACHE_DIR, exist_ok=True)

            # Ofusca os dados
            obfuscated_data = self._obfuscate_data_payload(data_payload_string)
        
            # Escreve em arquivo temporário primeiro
            temp_file = cache_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(obfuscated_data)
        
            # Verifica se o arquivo foi escrito corretamente
            if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                raise IOError("Falha ao escrever arquivo temporário")
        
            # Substitui o arquivo antigo
            if os.path.exists(cache_file):
                os.remove(cache_file)
            os.rename(temp_file, cache_file)
        
           # Atualiza o índice
            self.cache_index[cache_key] = {
               'url': url,
               'expires': (datetime.now() + timedelta(hours=expiry_hours)).isoformat(),
               'size': len(obfuscated_data)
            }
        
           # Garante que o índice seja salvo
            self.save_index()
        
            return True

        except Exception as e:
            xbmc.log(f"[ERRO CACHE] Falha ao salvar {url}: {str(e)}", xbmc.LOGERROR)
            # Limpa arquivos temporários em caso de erro
            if 'temp_file' in locals() and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            return False

    def delete(self, url):
        """Remove um item do cache"""
        cache_key = hashlib.sha256(url.encode('utf-8')).hexdigest()
        try:
            cache_file = self.get_cache_path(url)
            if os.path.exists(cache_file):
                os.remove(cache_file)
            if cache_key in self.cache_index:
                del self.cache_index[cache_key]
            self.save_index()
            # xbmc.log(f"[VideoCache] Cache removido: {url.split('/')[-1]}", xbmc.LOGINFO)
        except Exception as e:
            # xbmc.log(f"[VideoCache] ERRO ao remover cache: {str(e)}", xbmc.LOGERROR)
            pass

    def clear(self):
        """Limpa completamente o cache"""
        try:
            for filename in os.listdir(CACHE_DIR):
                file_path = os.path.join(CACHE_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    # xbmc.log(f"[VideoCache] ERRO ao remover {file_path}: {str(e)}", xbmc.LOGERROR)
                    pass

            self.cache_index = {}
            self.save_index()
            # xbmc.log("[VideoCache] Cache completamente limpo", xbmc.LOGINFO)
        except Exception as e:
            # xbmc.log(f"[VideoCache] ERRO ao limpar cache: {str(e)}", xbmc.LOGERROR)
            pass

VIDEO_CACHE = VideoCache()

# --- Abaixo, o código FilteredCache e get_all_videos com os ajustes necessários ---

import json
import time
import xbmc
import xbmcgui
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

class FilteredCache:
    def __init__(self, video_cache):
        self.cache = video_cache or VideoCache()  # Fallback se None
        self.prefix = "filter_"
        self.sort_prefix = "sorted_"
        self.progress = None
        self.max_items = 5000
        self.compression = True
        self.batch_size = 20
        self.last_update_time = 0
        self.thread_pool = ThreadPoolExecutor(max_workers=2)  # Pool de threads otimizado

    def _init_progress(self, title):
        """Inicializa a barra de progresso em background"""
        try:
            self.progress = xbmcgui.DialogProgressBG()
            self.progress.create(title, 'Aguarde...')
            self.last_update_time = time.time()
        except:
            self.progress = None

    def _update_progress(self, percent, message, estimated_time=None):
        """Atualiza a barra de progresso em background"""
        if not self.progress:
            return
        
        current_time = time.time()
        if current_time - self.last_update_time < 0.3:
            return
        
        self.last_update_time = current_time

        try:
            anim_chars = ['|', '/', '-', '\\']
            anim_index = int(current_time * 3) % len(anim_chars)
            animated_msg = f"{message} {anim_chars[anim_index]}"
            if estimated_time:
                animated_msg += f" [~{estimated_time}s]"
            
            self.progress.update(percent, animated_msg)
        except:
            pass

    def _close_progress(self):
        """Fecha a barra de progresso"""
        if self.progress:
            try:
                self.progress.close()
            except:
                pass
        self.progress = None

    def _compress(self, data):
        """Compacta os dados (lista/dict) para uma string base64 comprimida"""
        if not self.compression:
            return json.dumps(data, separators=(',', ':')) # Retorna JSON string não comprimida

        import zlib, base64
        try:
            json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
            return base64.b64encode(zlib.compress(json_str.encode('utf-8'), 9)).decode('utf-8') # Nível 9 para maior compressão
        except Exception as e:
            xbmc.log(f"[FilteredCache] ERRO ao compactar dados: {str(e)}", xbmc.LOGERROR)
            return json.dumps(data, separators=(',', ':'), ensure_ascii=False) # Fallback para JSON não comprimido

    def _decompress(self, data_string):
        """Descompacta uma string base64 comprimida para os dados originais (lista/dict)"""
        if not self.compression or not isinstance(data_string, str):
            try:
                return json.loads(data_string) # Tenta carregar como JSON se não for comprimido
            except:
                xbmc.log(f"[FilteredCache] ERRO: Dados não são string ou JSON válido para descompressão/deserialização.", xbmc.LOGERROR)
                return data_string # Retorna como está, pode ser um erro

        import zlib, base64
        try:
            return json.loads(zlib.decompress(base64.b64decode(data_string)).decode('utf-8'))
        except Exception as e:
            xbmc.log(f"[FilteredCache] ERRO ao descompactar dados: {str(e)}", xbmc.LOGERROR)
            try:
                return json.loads(data_string) # Tenta carregar como JSON não comprimido em caso de erro
            except:
                return data_string # Retorna a string bruta como último recurso

    def _light_version(self, items):
        """Versão compacta dos itens com processamento paralelo"""
        light_items = []
        total_items = min(len(items), self.max_items)
        
        def process_batch(batch):
            return [{
                'id': item.get('tmdb_id'),
                't': item.get('title')[:30] if item.get('title') else '',
                'r': item.get('rating'),
                'y': item.get('year')
            } for item in batch if item.get('tmdb_id')]

        # Processa em paralelo
        futures = []
        for i in range(0, total_items, self.batch_size):
            batch = items[i:i + self.batch_size]
            futures.append(self.thread_pool.submit(process_batch, batch))

        for future in as_completed(futures):
            light_items.extend(future.result())
            if self.progress:
                percent = 60 + (len(light_items) / total_items * 30)
                self._update_progress(int(percent), f"Processando {len(light_items)}/{total_items}")

        return light_items

    def _expand_items(self, light_items):
        """Expande os itens leves com busca paralelizada"""
        if not light_items:
            return []

        result = []
        lock = threading.Lock()
        all_videos = get_all_videos()
        all_videos_map = {v.get('tmdb_id'): v for v in all_videos}
        
        def expand_chunk(chunk):
            chunk_result = []
            for item in chunk:
                if item.get('id') in all_videos_map:
                    chunk_result.append(all_videos_map[item.get('id')])
            return chunk_result

        # Divide em chunks para processamento paralelo
        chunk_size = 50
        futures = []
        for i in range(0, len(light_items), chunk_size):
            chunk = light_items[i:i + chunk_size]
            futures.append(self.thread_pool.submit(expand_chunk, chunk))

        for i, future in enumerate(as_completed(futures)):
            with lock:
                result.extend(future.result())
                if self.progress and (i % 2 == 0 or i == len(futures) - 1):
                    percent = 10 + (i / len(futures) * 90)
                    self._update_progress(int(percent), f"Recuperando itens ({len(result)}/{len(light_items)})")

        return result

    def get_filtered_async(self, filter_name, filter_func, callback, expiry_hours=24, force_refresh=False):
        """Versão assíncrona que retorna via callback"""
        def _task():
            try:
                result = self.get_filtered(filter_name, filter_func, expiry_hours, force_refresh)
                callback(result)
            except Exception as e:
                xbmc.log(f"[FilteredCache] Erro em get_filtered_async: {str(e)}", xbmc.LOGERROR)
                callback([])

        threading.Thread(target=_task, daemon=True).start()

    def get_filtered(self, filter_name, filter_func, expiry_hours=24, force_refresh=False):
        """Versão com otimizações de thread"""
        cache_key = f"{self.prefix}{filter_name}"

        if not force_refresh:
            cached_data_string = self.cache.get(cache_key)
            if cached_data_string:
                cached_light_data = self._decompress(cached_data_string)
                if cached_light_data and not self.cache.is_expired(cache_key):
                    self._init_progress(f'Expandindo {filter_name.replace("_", " ")}')
                    expanded = self._expand_items(cached_light_data)
                    self._close_progress()
                    if expanded:
                        xbmc.log(f"[FilteredCache] Retornando do cache para '{filter_name}'", xbmc.LOGINFO)
                        return expanded[:self.max_items]

        try:
            self._init_progress(f'Filtrando {filter_name.replace("_", " ")}')
            self._update_progress(10, 'Carregando dados...')
            
            all_videos = get_all_videos()
            if not all_videos:
                raise Exception("Não foi possível carregar os vídeos para filtragem.")

            self._update_progress(30, 'Aplicando filtros...')
            filtered = filter_func(all_videos)
            
            self._update_progress(60, 'Otimizando cache...')
            light_data = self._light_version(filtered)
            compressed_string = self._compress(light_data)
            
            # Salva em cache em background sem bloquear
            def save_cache():
                self.cache.set(cache_key, compressed_string, expiry_hours=expiry_hours)
            threading.Thread(target=save_cache, daemon=True).start()
            
            self._update_progress(100, 'Concluído!')
            return filtered[:self.max_items]
        except Exception as e:
            xbmc.log(f"[FilteredCache] Erro ao filtrar '{filter_name}': {str(e)}", xbmc.LOGERROR)
            return []
        finally:
            self._close_progress()

    def get_sorted(self, sort_name, sort_func, expiry_hours=6, force_refresh=False):
        cache_key = f"{self.sort_prefix}{sort_name}"

        if not force_refresh:
            cached_data_string = self.cache.get(cache_key)
            if cached_data_string:
                cached_light_data = self._decompress(cached_data_string)
                if cached_light_data and not self.cache.is_expired(cache_key):
                    self._init_progress(f'Expandindo {sort_name.replace("_", " ")}')
                    expanded = self._expand_items(cached_light_data)
                    self._close_progress()
                    if expanded:
                        xbmc.log(f"[FilteredCache] Retornando do cache para '{sort_name}'", xbmc.LOGINFO)
                        return expanded

        try:
            self._init_progress(f'Ordenando {sort_name.replace("_", " ")}')
            self._update_progress(20, 'Carregando dados globais...', 2)
            all_videos = get_all_videos()
            if not all_videos:
                raise Exception("Não foi possível carregar os vídeos para ordenação.")

            self._update_progress(40, 'Ordenando...', 3)
            sorted_videos = sort_func(all_videos)

            self._update_progress(70, 'Otimizando cache (versão leve)...', 4)
            light_data = self._light_version(sorted_videos)
            compressed_string = self._compress(light_data)
            
            # Salva em cache em background
            threading.Thread(
                target=self.cache.set,
                args=(cache_key, compressed_string, expiry_hours),
                daemon=True
            ).start()

            self._update_progress(100, 'Concluído!')
            xbmc.log(f"[FilteredCache] Ordem '{sort_name}' gerada e cacheada.", xbmc.LOGINFO)
            return sorted_videos[:self.max_items]
        except Exception as e:
            xbmc.log(f"[FilteredCache] Erro ao obter ordem '{sort_name}': {str(e)}", xbmc.LOGERROR)
            return []
        finally:
            self._close_progress()

# Configuração inicial

# Definindo o limite fixo de 5000 itens
FIXED_MAX_ITEMS = 5000

FILTERED_CACHE = FilteredCache(VIDEO_CACHE)
FILTERED_CACHE.max_items = FIXED_MAX_ITEMS # Define o limite fixo de 5000
FILTERED_CACHE.compression = True

# Ajuste do batch_size para um limite de 5000 itens.
# Um batch_size de 25 ainda é um valor razoável, mas você pode experimentar.
# Para 5000 itens, um batch_size um pouco maior (e.g., 50 ou 100) pode ser eficiente
# dependendo da performance do seu sistema e do que VIDEO_CACHE retorna.
FILTERED_CACHE.batch_size = 50


def clear_cache(show_dialog=True):
    """
    Limpeza completa e verificada do cache com notificações aprimoradas
    :param show_dialog: Mostra diálogos de confirmação e resultado
    :return: True se limpeza bem-sucedida, False caso contrário
    """
    # Notificação de início do processo
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
        
        # Primeiro: Limpa a instância em memória
        VIDEO_CACHE.cache_index = {}
        VIDEO_CACHE.save_index()
        
        if show_dialog:
            progress.update(40, 'Removendo arquivos de cache...')
        
        # Segundo: Remove todos os arquivos do diretório
        failed_deletions = []
        cache_files = os.listdir(CACHE_DIR)
        total_files = len(cache_files)
        
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

        # Verificação final
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
        
        