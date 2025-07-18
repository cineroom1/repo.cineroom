import xbmcgui
import xbmcplugin
import xbmc
import sys
import unicodedata
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from resources.lib.utils import get_all_videos
from resources.action.video_listing import create_video_item

URL = sys.argv[0]

def get_url(**kwargs):
    return '{}?{}'.format(URL, urlencode(kwargs))

def normalize(text):
    if not isinstance(text, str):
        return ''
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').lower()

def prompt_user_input():
    user_input = xbmcgui.Dialog().input("Digite o título, ator, diretor ou TMDb ID:").strip()
    return normalize(user_input), user_input

def chunkify(data, n_chunks):
    chunk_size = max(1, len(data) // n_chunks)
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

def match_video(video, search_term):
    if not isinstance(video, dict):
        return False

    title_norm = normalize(video.get('title', ''))
    tmdb_id = str(video.get('tmdb_id', ''))
    video_type = video.get('type', 'movie').lower()

    if '(4k)' in title_norm:
        return False

    if search_term in title_norm or (search_term.isdigit() and search_term == tmdb_id):
        return True

    if video_type == 'movie':
        actors = video.get('actors', [])
        directors = video.get('director', [])
        normalized_actors = [normalize(a) for a in actors if isinstance(a, str)]
        normalized_directors = [normalize(d) for d in directors if isinstance(d, str)]

        if any(search_term in a for a in normalized_actors) or any(search_term in d for d in normalized_directors):
            return True

    return False

def filter_videos_chunk(videos_chunk, search_term, chunk_num, total_chunks, progress_dialog):
    filtered = []
    try:
        progress = int((chunk_num / total_chunks) * 100)
        if chunk_num % 2 == 0:
            progress_dialog.update(progress, f'Processando {chunk_num} de {total_chunks} partes...')
        if progress_dialog.iscanceled():
            return None

        for video in videos_chunk:
            if match_video(video, search_term):
                filtered.append(video)
                xbmc.log(f"[MATCH] {video.get('title')} - Tipo: {video.get('type')}", xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f"[search_videos] Erro na filtragem de chunk: {e}", xbmc.LOGERROR)

    return filtered

def display_results(handle, filtered_videos, search_term):
    xbmcplugin.setPluginCategory(handle, f'Resultados para: {search_term}')
    xbmcplugin.setContent(handle, 'folder')

    for video in filtered_videos:
        tmdb_id = video.get('tmdb_id')
        title = video.get('title', 'Sem título')
        video_type = video.get('type', 'movie')

        if video_type == 'movie':
            list_item = xbmcgui.ListItem(label=title)
            list_item.setArt({'poster': video.get('poster', ''), 'fanart': video.get('backdrop', '')})
            url = get_url(action='open_video_folder', tmdb_id=tmdb_id)
            xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=True)
        elif video_type == 'tvshow':
            list_item, url, is_folder = create_video_item(video)
            xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=is_folder)

    xbmcplugin.endOfDirectory(handle)

def search_videos(handle):
    search_term, raw_term = prompt_user_input()
    if not search_term or len(search_term) < 2:
        xbmcgui.Dialog().ok("Aviso", "Por favor, insira um termo de busca com pelo menos 2 caracteres.")
        return

    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create('Buscando vídeos', 'Pesquisando...')

    try:
        all_videos = get_all_videos()
        xbmc.log(f"[DEBUG] Total de vídeos carregados: {len(all_videos)}", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"[search_videos] Erro ao obter vídeos: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Erro ao obter vídeos: {str(e)}")
        progress_dialog.close()
        return

    chunks = chunkify(all_videos, min(5, len(all_videos) // 10) or 1)
    filtered_videos = []

    try:
        with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            futures = [
                executor.submit(filter_videos_chunk, chunk, search_term, i + 1, len(chunks), progress_dialog)
                for i, chunk in enumerate(chunks)
            ]
            for i, future in enumerate(as_completed(futures)):
                if progress_dialog.iscanceled():
                    xbmc.log("[search_videos] Busca cancelada pelo usuário", xbmc.LOGWARNING)
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

    xbmc.log(f"[DEBUG] Total de arquivos encontrados: {len(filtered_videos)}", xbmc.LOGWARNING)
    if not filtered_videos:
        xbmcgui.Dialog().ok("Resultado", "Nenhum conteúdo encontrado com o termo de busca.")
        return

    display_results(handle, filtered_videos, raw_term)

def open_video_folder(handle, tmdb_id):
    xbmcplugin.setPluginCategory(handle, 'Filme')
    xbmcplugin.setContent(handle, 'videos')

    try:
        all_videos = get_all_videos()
        tmdb_id = str(tmdb_id)
        matching_videos = [v for v in all_videos if str(v.get('tmdb_id')) == tmdb_id]

        if not matching_videos:
            xbmcgui.Dialog().ok('Erro', 'Filme não encontrado.')
            return

        for video in matching_videos:
            list_item, url, is_folder = create_video_item(video)
            xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=is_folder)

    except Exception as e:
        xbmc.log(f"[open_video_folder] Erro: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok('Erro', f"Erro ao abrir o filme: {str(e)}")

    xbmcplugin.endOfDirectory(handle)
