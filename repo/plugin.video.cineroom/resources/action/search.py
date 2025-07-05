import xbmcgui
import xbmcplugin
import xbmc
import sys
import threading
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from resources.lib.utils import get_all_videos
from resources.action.video_listing import create_video_item
import json 

URL = sys.argv[0]

def get_url(**kwargs):
    """Cria uma URL para chamar o plugin recursivamente a partir dos argumentos fornecidos."""
    return '{}?{}'.format(URL, urlencode(kwargs))

import unicodedata

def normalize(text):
    """Remove acentos e transforma em minúsculas."""
    if not isinstance(text, str):
        return ''
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').lower()

def search_videos(HANDLE):
    """Permite que o usuário pesquise vídeos por título, TMDb ID, ator ou diretor."""
    search_term_raw = xbmcgui.Dialog().input("Digite o título, ator, diretor ou TMDb ID:").strip()
    search_term = normalize(search_term_raw)

    if not search_term or len(search_term) < 2:
        xbmcgui.Dialog().ok("Aviso", "Por favor, insira um termo de busca com pelo menos 2 caracteres.")
        return

    try:
        # Cria diálogo de progresso antes de começar a busca
        progress_dialog = xbmcgui.DialogProgress()
        progress_dialog.create('Buscando vídeos', 'Pesquisando...')
        
        all_videos = get_all_videos()
        xbmc.log(f"[DEBUG] Total de vídeos carregados: {len(all_videos)}", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"[search_videos] Erro ao obter vídeos: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Erro ao obter vídeos: {str(e)}")
        progress_dialog.close() if 'progress_dialog' in locals() else None
        return

    unique_videos = defaultdict(bool)

    def filter_videos_chunk(videos_chunk, chunk_num, total_chunks):
        """Filtra vídeos dentro de um chunk e armazena os resultados."""
        filtered = []
        try:
            progress = int((chunk_num / total_chunks) * 100)
            progress_dialog.update(progress, f'Processando {chunk_num} de {total_chunks} partes...')
            
            if progress_dialog.iscanceled():
                xbmc.log("[search_videos] Busca cancelada pelo usuário", xbmc.LOGWARNING)
                return None

            for video in videos_chunk:
                if not isinstance(video, dict):
                    xbmc.log(f"[search_videos] Vídeo ignorado (não é dict): {repr(video)}", xbmc.LOGWARNING)
                    continue

                title_raw = video.get('title', '')
                title_norm = normalize(title_raw)
                tmdb_id = str(video.get('tmdb_id', ''))
                video_type = video.get('type', 'movie').lower()

                if '(4k)' in title_norm:
                    continue

                title_match = search_term in title_norm
                tmdb_match = search_term.isdigit() and search_term == tmdb_id

                actor_match = False
                director_match = False

                if video_type == 'movie':
                    actors = video.get('actors', [])
                    if not isinstance(actors, list):
                        actors = []

                    actor_match = any(isinstance(actor, str) and search_term in normalize(actor) for actor in actors)

                    directors = video.get('director', [])
                    if not isinstance(directors, list):
                        directors = []

                    director_match = any(isinstance(director, str) and search_term in normalize(director) for director in directors)

                if any([title_match, tmdb_match, actor_match, director_match]):
                    unique_videos[tmdb_id] = True
                    filtered.append(video)
                    xbmc.log(f"[MATCH] {title_raw} - Tipo: {video_type}", xbmc.LOGINFO)

        except Exception as e:
            xbmc.log(f"[search_videos] Erro na filtragem de chunk: {e}", xbmc.LOGERROR)

        return filtered

    num_threads = min(5, len(all_videos) // 10) or 1
    chunk_size = max(1, len(all_videos) // num_threads)
    chunks = [all_videos[i:i + chunk_size] for i in range(0, len(all_videos), chunk_size)]

    filtered_videos = []
    try:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Atualiza o diálogo para mostrar que está iniciando a busca paralela
            progress_dialog.update(0, 'Iniciando busca em paralelo...')
            
            futures = []
            for i, chunk in enumerate(chunks):
                futures.append(executor.submit(filter_videos_chunk, chunk, i+1, len(chunks)))
            
            for i, future in enumerate(as_completed(futures)):
                progress = int(((i + 1) / len(futures)) * 100)
                progress_dialog.update(progress, f'Analisando resultados {i + 1}/{len(futures)}...')
                
                if progress_dialog.iscanceled():
                    xbmc.log("[search_videos] Busca cancelada pelo usuário", xbmc.LOGWARNING)
                    executor.shutdown(wait=False)
                    progress_dialog.close()
                    return
                
                result = future.result()
                if result:
                    filtered_videos.extend(result)
                    
    except Exception as e:
        xbmc.log(f"[search_videos] Erro na execução paralela: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Erro durante a busca: {str(e)}")
        progress_dialog.close()
        return
    finally:
        progress_dialog.close()

    xbmc.log(f"[DEBUG] Total de vídeos encontrados: {len(filtered_videos)}", xbmc.LOGWARNING)

    if not filtered_videos:
        xbmcgui.Dialog().ok("Resultado", "Nenhum vídeo encontrado com o termo de busca.")
        return

    display_results(HANDLE, filtered_videos, search_term_raw)



def display_results(HANDLE, filtered_videos, search_term):
    """Exibe os vídeos filtrados corretamente na interface do Kodi."""
    xbmcplugin.setPluginCategory(HANDLE, f'Resultados para: {search_term}')
    xbmcplugin.setContent(HANDLE, 'folder')

    for video in filtered_videos:
        tmdb_id = video.get('tmdb_id')
        title = video.get('title', 'Sem título')
        video_type = video.get('type', 'movie')  # assume 'movie' se não vier

        if video_type == 'movie':
            # Filme: criar pasta que chama open_video_folder
            list_item = xbmcgui.ListItem(label=title)
            list_item.setArt({'poster': video.get('poster', ''), 'fanart': video.get('backdrop', '')})
            url = get_url(action='open_video_folder', tmdb_id=tmdb_id)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

        elif video_type == 'tvshow':
            # Série: usar create_video_item direto (sem pasta)
            list_item, url, is_folder = create_video_item(video)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)

    xbmcplugin.endOfDirectory(HANDLE)


def open_video_folder(HANDLE, tmdb_id):
    """Abre uma pasta com o filme correspondente ao tmdb_id."""
    xbmcplugin.setPluginCategory(HANDLE, 'Filme')
    xbmcplugin.setContent(HANDLE, 'videos')

    try:
        all_videos = get_all_videos()
        tmdb_id = str(tmdb_id)

        # Filtra o vídeo que bate com o tmdb_id
        matching_videos = [video for video in all_videos if str(video.get('tmdb_id')) == tmdb_id]

        if not matching_videos:
            xbmcgui.Dialog().ok('Erro', 'Filme não encontrado.')
            return

        # Adiciona o(s) item(ns) encontrado(s)
        for video in matching_videos:
            list_item, url, is_folder = create_video_item(video)
            xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)

    except Exception as e:
        xbmc.log(f"[open_video_folder] Erro: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok('Erro', f"Erro ao abrir o filme: {str(e)}")

    xbmcplugin.endOfDirectory(HANDLE)
