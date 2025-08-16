import xbmcgui
import xbmcplugin
import xbmc
import sys
import unicodedata
import urllib.request
import urllib.error
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from resources.lib.utils import get_all_videos, VIDEO_CACHE
from resources.action.video_listing import create_video_item
import re
import xbmcaddon

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
URL = sys.argv[0]

def get_url(**kwargs):
    return '{}?{}'.format(URL, urlencode(kwargs))

def normalize(text):
    if not isinstance(text, str):
        return ''
    normalized = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII').lower()
    normalized = normalized.replace('.', '').replace(':', '').replace('/', '').replace('#', '').replace('[', '').replace(']', '')
    return normalized

def prompt_user_input():
    user_input = xbmcgui.Dialog().input("Digite o título, ator, diretor ou TMDb ID:").strip()
    return user_input

def chunkify(data, n_chunks):
    chunk_size = max(1, len(data) // n_chunks)
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

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

def filter_videos_chunk(videos_chunk, search_term, chunk_num, total_chunks, progress_dialog):
    filtered = []
    try:
        progress = int(((chunk_num - 1) / total_chunks) * 100)
        if chunk_num % 2 == 0:
            progress_dialog.update(progress, f'Pesquisando... ({progress}%)')
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
        video_type = video.get('type', 'movie')

        # Lógica corrigida para criar um folder apenas para filmes
        if video_type == 'movie':
            title = video.get('title', 'Sem título')
            list_item = xbmcgui.ListItem(label=title)
            list_item.setArt({'poster': video.get('poster', ''), 'fanart': video.get('backdrop', '')})
            url = get_url(action='open_video_folder', tmdb_id=tmdb_id)
            xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=True)
        else:
            list_item, url, is_folder = create_video_item(HANDLE,video)
            xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=is_folder)

    xbmcplugin.endOfDirectory(handle)
    

    
# -------------------------------------------------------------
# FUNÇÃO PRINCIPAL DE BUSCA - ADAPTADA
# -------------------------------------------------------------

def search_videos(handle):
    from firebase import save_search_term
    raw_term = prompt_user_input()
    if not raw_term or len(raw_term) < 2:
        xbmcgui.Dialog().ok("Aviso", "Por favor, insira um termo de busca com pelo menos 2 caracteres.")
        return
    search_term = normalize(raw_term)
    
    dialog = xbmcgui.Dialog()
    choice = dialog.select("Selecione o tipo de conteúdo:", ["Filmes", "Séries"])
    
    if choice == -1: # Usuário cancelou
        return
    
    content_type = 'movie' if choice == 0 else 'tvshow'
    
    progress_dialog = xbmcgui.DialogProgress()
    progress_dialog.create('Buscando vídeos', 'Pesquisando...')

    try:
        all_videos = get_all_videos()
        filtered_by_type = [v for v in all_videos if v.get('type', 'movie') == content_type]
        
        xbmc.log(f"[DEBUG] Total de vídeos carregados para '{content_type}': {len(filtered_by_type)}", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"[search_videos] Erro ao obter vídeos: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Erro ao obter vídeos: {str(e)}")
        progress_dialog.close()
        return

    chunks = chunkify(filtered_by_type, min(5, len(filtered_by_type) // 10) or 1)
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
    else:
        save_search_term(raw_term, content_type)

    display_results(handle, filtered_videos, raw_term)

def open_video_folder(handle, tmdb_id):
    """
    Exibe opções de reprodução para um vídeo específico.
    Busca automaticamente fontes no JackTook ou Elementum se necessário.
    Inclui suporte a legendas.
    """
    # Importe as dependências necessárias aqui
    import xbmcgui, xbmcplugin, xbmc
    # Certifique-se de que get_url, ADDON, etc. estão disponíveis.
    from resources.lib.players import play_video, is_elementum_installed, is_jacktook_installed, get_jacktook_search_link, play_elementum
    
    xbmcplugin.setPluginCategory(handle, 'Fontes de Video')

    try:
        tmdb_id = str(tmdb_id)
        cache_key = f"video_{tmdb_id}"

        # Tenta pegar do cache
        main_video_json = VIDEO_CACHE.get(cache_key)
        if main_video_json:
            try:
                main_video = json.loads(main_video_json)
            except Exception:
                main_video = None
                VIDEO_CACHE.delete(cache_key)
        else:
            main_video = None

        # Se não achou no cache, pega da lista geral
        if not main_video:
            all_videos = get_all_videos()
            main_video = next((v for v in all_videos if str(v.get('tmdb_id')) == tmdb_id), None)
            if main_video and VIDEO_CACHE.enabled:
                try:
                    VIDEO_CACHE.set(cache_key, json.dumps(main_video), expiry_hours=12)
                except Exception:
                    pass

        if not main_video:
            xbmcgui.Dialog().ok('Erro', 'Conteúdo não encontrado.')
            xbmcplugin.endOfDirectory(handle)
            return

        streams = main_video.get('streams', [])

        # Se não houver streams, faz a busca automática
        if not streams:
            provider = ADDON.getSetting('default_search_provider')
            
            xbmcgui.Dialog().notification('Buscando fontes', 'Aguarde...')

            if provider == "0":  # Elementum
                if not is_elementum_installed():
                    xbmcgui.Dialog().notification('Elementum não instalado', 'Instale o Elementum para usar esta função.', xbmcgui.NOTIFICATION_ERROR)
                    xbmcplugin.endOfDirectory(handle)
                    return
                
                xbmc.executebuiltin(f'RunPlugin(plugin://plugin.video.elementum/search?tmdb={tmdb_id})')
            else:  # JackTook
                if not is_jacktook_installed():
                    xbmcgui.Dialog().notification('JackTook não instalado', 'Instale o plugin JackTook para usar esta função.', xbmcgui.NOTIFICATION_ERROR)
                    xbmcplugin.endOfDirectory(handle)
                    return
                
                is_movie = 'season' not in main_video
                search_link = get_jacktook_search_link(
                    is_movie=is_movie,
                    title=main_video.get('title', ''),
                    tmdb_id=tmdb_id,
                    imdb_id=main_video.get('imdb_id', ''),
                    season=main_video.get('season'),
                    episode=main_video.get('episode'),
                    showname=main_video.get('showname')
                )
                if search_link:
                    xbmc.executebuiltin(f'RunPlugin({search_link})')

            # Encerra o diretório para que o Kodi possa exibir a nova interface do plugin de busca
            xbmcplugin.endOfDirectory(handle)
            return

        # Resto do código para exibir os streams, que só será executado se existirem streams
        quality_priority = {"4K": 1, "2160P": 1, "1080P": 2, "720P": 3, "SD": 4}
        quality_colors = {"4K": "orange", "2160P": "orange", "1080P": "deepskyblue",
                          "720P": "lightgreen", "SD": "white"}

        if streams:
            streams = sorted(streams, key=lambda s: quality_priority.get(s.get('quality', 'SD').upper(), 99))

            for stream in streams:
                quality = stream.get('quality', 'N/A').upper()
                extras = stream.get('extras', [])
                server = stream.get('server_name', 'Servidor')
                color = quality_colors.get(quality, "white")
                parts = [f"[COLOR {color}][B]{quality}[/B][/COLOR]"]
                if server:
                    parts.append(f"[COLOR yellow]{server}[/COLOR]")
                if extras:
                    parts.append(f"[COLOR gray]{' | '.join(extras)}[/COLOR]")
                display_label = " • ".join(parts)

                list_item = xbmcgui.ListItem(label=display_label)
                list_item.setArt({
                    'poster': main_video.get('poster', ''),
                    'thumb': main_video.get('poster', ''),
                    'fanart': main_video.get('backdrop', ''),
                    'clearlogo': main_video.get('clearlogo', '')
                })
                list_item.setInfo('video', {
                    'title': main_video.get('title', 'Sem título'),
                    'plot': main_video.get('synopsis', 'Sem sinopse'),
                    'year': int(main_video.get('year') or 0),
                    'genre': main_video.get('genres', []),
                    'mediatype': 'video'
                })
                subtitles = stream.get('subtitles') or main_video.get('subtitles')
                if subtitles:
                    if isinstance(subtitles, str):
                        subtitles = [subtitles]
                    list_item.setSubtitles(subtitles)

                play_url = get_url(
                    action='play',
                    video=stream['url'],
                    tmdb_id=main_video.get('tmdb_id', ''),
                    title=main_video.get('title', ''),
                    imdb_id=main_video.get('imdb_id', ''),
                    year=main_video.get('year', 0),
                    is_series='false'
                )
                list_item.setProperty('IsPlayable', 'true')
                
                xbmcplugin.addDirectoryItem(handle, play_url, list_item, isFolder=False)
    
    except Exception as e:
        xbmc.log(f"[open_video_folder] Erro: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok('Erro', f"Erro ao abrir o conteúdo: {str(e)}")

    xbmcplugin.endOfDirectory(handle, cacheToDisc=True)



