# Built-in
import sys
import time
import json
import urllib.parse
import urllib.request
import hashlib

# Kodi
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

# Internos
from urllib.parse import urlencode, parse_qsl
from resources.action.favorites import load_favorites, add_to_favorites, remove_from_favorites
from resources.lib.utils import get_all_videos, VIDEO_CACHE
from resources.lib.utils_view import set_view_mode


# As variáveis globais HANDLE e URL foram removidas da parte superior.
# Elas serão definidas apenas no momento da execução do plugin.

def get_url(**kwargs) -> str:
    """
    Cria uma URL para chamar o plugin recursivamente.
    Otimizado para serialização automática de objetos.
    Usa sys.argv[0] para obter a URL base de forma segura.
    """
    params = {}
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            params[key] = json.dumps(value)
        else:
            params[key] = value
    return f"{sys.argv[0]}?{urlencode(params)}"


MEDIA_TYPES = {
    'movie': {'content_type': 'movies', 'playable': True, 'folder': False},
    'tvshow': {'content_type': 'tvshows', 'playable': False, 'folder': True},
    'set': {'content_type': 'movies', 'playable': False, 'folder': True}
}

def load_videos(external_link):
    """Carrega os vídeos a partir de uma URL externa."""
    try:
        with urllib.request.urlopen(external_link) as response:
            return json.load(response)
    except Exception as e:
        xbmcgui.Dialog().ok('Erro', f'Erro ao carregar vídeos: {e}')
        return None

def check_maintenance(data):
    """Verifica se a lista está em manutenção."""
    if isinstance(data[0], dict) and data[0].get("status", "").lower() == "off":
        xbmcgui.Dialog().notification("Aguarde...", "A lista está em manutenção!", xbmcgui.NOTIFICATION_WARNING, 3000)
        return True
    return False

def set_content_type(handle, videos):
    """Define o tipo de conteúdo com base nos vídeos."""
    types = {video['type'] for video in videos}
    if types == {'movie'}:
        xbmcplugin.setContent(handle, 'movies')
    elif types == {'tvshow'}:
        xbmcplugin.setContent(handle, 'tvshows')
    elif types == {'set'}:
        xbmcplugin.setContent(handle, 'movies')
    else:
        xbmcplugin.setContent(handle, 'movies')


def create_video_item(handle, video):
    """Cria um ListItem para exibir na interface do Kodi, aproveitando cache de vídeos."""
    from resources.action.search import open_video_folder
    try:
        list_item = xbmcgui.ListItem(label=video['title'])
        list_item.setArt({
            'poster': video.get('poster', ''),
            'thumb': video.get('poster', ''),
            'fanart': video.get('backdrop', ''),
            'clearlogo': video.get('clearlogo', '')
        })

        mediatype = video['type']
        media_info = MEDIA_TYPES.get(mediatype, {})
        is_folder = media_info.get('folder', False)
        list_item.setProperty('IsPlayable', 'true' if media_info.get('playable', False) else 'false')

        # ---------- START: Otimização com cache ----------
        if mediatype == 'movie':
            tmdb_id = str(video.get('tmdb_id'))
            cache_key = f"video_{tmdb_id}"

            # Tenta usar cache
            main_video_json = VIDEO_CACHE.get(cache_key)
            if main_video_json:
                try:
                    main_video = json.loads(main_video_json)
                except Exception:
                    main_video = None
                    VIDEO_CACHE.delete(cache_key)
            else:
                main_video = None

            # Se não existir no cache, usa o vídeo atual e salva no cache
            if not main_video:
                main_video = video
                if VIDEO_CACHE.enabled:
                    try:
                        VIDEO_CACHE.set(cache_key, json.dumps(main_video), expiry_hours=12)
                    except Exception:
                        pass

            # URL chama a função 'open_video_folder'
            url = get_url(action='open_video_folder', tmdb_id=tmdb_id)
            is_folder = True

        elif mediatype == 'set':
            url = get_url(action='list_collection', collection=json.dumps(video))
        elif mediatype == 'tvshow':
            url = get_url(action='list_seasons', serie=video)
        else:
            url = ''

        # ---------- Informações do vídeo ----------
        info = {
            'title': video['title'],
            'mediatype': mediatype,
            'plot': video.get('synopsis', ''),
            'premiered': video.get("premiered", "Ano não disponível"),
            'dateadded': video.get('date_added', ''),
        }

        try:
            info['rating'] = float(video.get('rating', 0))
        except (ValueError, TypeError):
            info['rating'] = 0
        try:
            info['votes'] = int(video.get('vote_count', 0))
        except (ValueError, TypeError):
            info['votes'] = 0
        try:
            info['year'] = int(video.get('year', 0))
        except (ValueError, TypeError):
            info['year'] = 0

        genres = video.get('genres', [])
        info['genre'] = genres if isinstance(genres, list) else [genres]

        raw_director_data = video.get("director")
        directors = []
        if isinstance(raw_director_data, list):
            directors = [str(d).strip() for d in raw_director_data if d]
        elif isinstance(raw_director_data, str) and raw_director_data.strip():
            directors = [raw_director_data.strip()]
        if directors:
            info['director'] = directors

        studio_data = video.get('studio', [])
        if isinstance(studio_data, list):
            info['studio'] = ', '.join([str(s).strip() for s in studio_data if s])
        elif isinstance(studio_data, str):
            info['studio'] = studio_data.strip()

        info['duration'] = video.get("runtime", 0)

        # Bilheteria
        plot_extra = ""
        revenue = video.get('revenue', 0)
        if revenue:
            formatted_revenue = f"\n[COLOR gold]Bilheteria[/COLOR]: ${revenue:,.0f}".replace(",", ".")
            plot_extra += f"\n{formatted_revenue}"

        # IMDb
        imdb_id = video.get('imdb_id', '')
        if imdb_id:
            info['imdbnumber'] = imdb_id
            list_item.setProperty('imdb_id', imdb_id)
            try:
                list_item.setUniqueIDs({'imdb': imdb_id})
            except Exception as e:
                xbmc.log(f"Erro ao definir UniqueIDs: {e}", xbmc.LOGDEBUG)

        if plot_extra:
            info['plot'] += plot_extra

        list_item.setInfo('video', info)

        # Subtitles
        subtitles = video.get('subtitles')
        if subtitles:
            if isinstance(subtitles, str):
                subtitles = [subtitles]
            list_item.setSubtitles(subtitles)

        list_item.setProperty('mediatype', mediatype)
        if revenue:
            list_item.setProperty('revenue', str(revenue))

        # Favoritos
        favorites = load_favorites()
        if any(fav['title'] == video['title'] for fav in favorites):
            list_item.addContextMenuItems([(
                'Remover da sua lista',
                f'RunPlugin({get_url(action="remove_from_favorites", video=json.dumps(video))})'
            )])
        else:
            list_item.addContextMenuItems([(
                'Adicionar à sua lista',
                f'RunPlugin({get_url(action="add_to_favorites", video=json.dumps(video))})'
            )])

        xbmc.log(f"DEBUG: create_video_item - Valor final de is_folder: {is_folder} (Tipo: {type(is_folder)})", xbmc.LOGDEBUG)
        return list_item, url, is_folder

    except Exception as e:
        xbmc.log(f"Erro ao criar item de vídeo: {e}", xbmc.LOGERROR)
        return None, None, False



def list_videos(handle, external_link, is_vip=False, sort_method=None, page=1, items_per_page=100):
    """Lista os vídeos com cache otimizado e tratamento de erros robusto"""
    if is_vip == 'true':
        if not verify_vip_access():
            return

    progress = xbmcgui.DialogProgressBG()
    progress.create('Carregando vídeos', 'Otimizando...')
    
    try:
        try:
            page = max(1, int(page))
            items_per_page = max(10, min(int(items_per_page), 200))
        except (ValueError, TypeError):
            page = 1
            items_per_page = 100

        def get_system_memory():
            mem_str = xbmc.getInfoLabel('System.Memory(total)')
            if 'MB' in mem_str:
                return int(mem_str.replace('MB', '').strip())
            elif 'GB' in mem_str:
                return int(float(mem_str.replace('GB', '').strip()) * 1024)
            return 1024

        cache_key = f"v4_{hashlib.md5(external_link.encode()).hexdigest()}_{sort_method or 'none'}"
        videos = []
        ram_cache_active = False
        
        if get_system_memory() > 1024:
            ram_cache_active = True
            if hasattr(list_videos, '_ram_cache'):
                cached = list_videos._ram_cache.get(cache_key)
                if cached and time.time() - cached['time'] < 300:
                    videos = cached['data']
                    progress.update(30, 'Dados da RAM')

        if not videos and VIDEO_CACHE.enabled:
            progress.update(20, 'Verificando cache...')
            try:
                cached = VIDEO_CACHE.get(cache_key)
                if cached:
                    videos = json.loads(cached)
                    if ram_cache_active:
                        if not hasattr(list_videos, '_ram_cache'):
                            list_videos._ram_cache = {}
                        list_videos._ram_cache[cache_key] = {
                            'data': videos,
                            'time': time.time()
                        }
            except Exception as e:
                xbmc.log(f"[CACHE] Limpando cache corrompido: {str(e)}", xbmc.LOGWARNING)
                VIDEO_CACHE.delete(cache_key)

        if not videos:
            progress.update(40, 'Carregando dados...')
            videos = load_videos(external_link)
            
            if videos:
                if VIDEO_CACHE.enabled:
                    progress.update(60, 'Armazenando cache...')
                    try:
                        VIDEO_CACHE.set(cache_key, json.dumps(videos), expiry_hours=12)
                    except Exception as e:
                        xbmc.log(f"[ERRO] Cache não salvo: {str(e)}", xbmc.LOGERROR)
                
                if ram_cache_active:
                    if not hasattr(list_videos, '_ram_cache'):
                        list_videos._ram_cache = {}
                    list_videos._ram_cache[cache_key] = {
                        'data': videos,
                        'time': time.time()
                    }

        if not videos:
            progress.close()
            xbmcgui.Dialog().ok('Erro', 'Nenhum vídeo encontrado')
            return

        if check_maintenance(videos):
            progress.close()
            return

        progress.update(70, 'Processando...')
        video_items = videos[1:] if isinstance(videos[0], dict) and "status" in videos[0] else videos
        set_content_type(handle, video_items)

        sort_options = {
            'year': lambda x: int(x.get('year', 0)),
            'rating': lambda x: float(x.get('rating', 0)),
            'label': lambda x: str(x.get('title', '')).lower(),
            'genre': lambda x: ', '.join(str(g) for g in x.get('genres', [])).lower()
        }
        
        if sort_method in sort_options:
            try:
                video_items.sort(key=sort_options[sort_method],
                                 reverse=sort_method in ['year', 'rating'])
            except Exception as e:
                xbmc.log(f"[ERRO] Ordenação falhou: {str(e)}", xbmc.LOGWARNING)

        total_items = len(video_items)
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        
        progress.update(80, 'Preparando exibição...')
        added_items = 0
        
        for i in range(start_index, min(end_index, total_items)):
            video = video_items[i]
            
            if i % 5 == 0 or i == end_index - 1:
                progress.update(80 + int((i-start_index)/items_per_page*20),
                                f'Item {i+1}/{total_items}')
            
            if not isinstance(video, dict):
                continue
                
            try:
                list_item, url, is_folder = create_video_item(handle, video)
                if list_item and url:
                    xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=is_folder)
                    added_items += 1
            except Exception as e:
                xbmc.log(f"[ERRO] Item inválido: {str(e)}", xbmc.LOGDEBUG)

        if end_index < total_items and added_items > 0:
            next_page_item = xbmcgui.ListItem(label='Próxima Página >>')
            next_page_url = get_url(
                action='list_videos',
                external_link=external_link,
                sort_method=sort_method,
                page=page + 1,
                items_per_page=items_per_page
            )
            xbmcplugin.addDirectoryItem(handle, next_page_url, next_page_item, isFolder=True)

        xbmcplugin.endOfDirectory(handle)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"[ERRO CRÍTICO] list_videos: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Erro', 'Verifique os logs', xbmcgui.NOTIFICATION_ERROR)
    finally:
        progress.close()


def list_collection(handle, collection_data):
    """Lista os filmes de uma coleção, com estrutura semelhante à de temporadas de séries."""
    try:
        if isinstance(collection_data, str):
            collection = json.loads(collection_data)
        else:
            collection = collection_data

        if not isinstance(collection, dict) or not collection.get('movies'):
            raise ValueError("Dados da coleção inválidos ou 'movies' ausentes.")

        collection_title = collection.get('title', 'Coleção')
        xbmcplugin.setPluginCategory(handle, collection_title)
        xbmcplugin.setContent(handle, 'movies')

        for movie in collection.get('movies', []):
            movie['type'] = 'movie'
            list_item, url, is_folder = create_video_item(handle, movie)
            if list_item and url:
                xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=is_folder)

        xbmcplugin.endOfDirectory(handle)

    except Exception as e:
        xbmc.log(f"Erro ao listar coleção: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Erro', 'Não foi possível exibir a coleção.', xbmcgui.NOTIFICATION_ERROR, 3000)


def list_seasons(handle, serie_data):
    """Lista temporadas com número correto da temporada"""
    try:
        if isinstance(serie_data, str):
            serie = json.loads(serie_data)
        else:
            serie = serie_data

        clearlogo = serie.get('clearlogo', '')
        if clearlogo:
            xbmcplugin.setPluginCategory(handle, '{}'.format(serie.get('title', '')))
            xbmcplugin.setProperty(handle, 'clearlogo', clearlogo)
        
        xbmcplugin.setContent(handle, 'seasons')
        
        for index, temp in enumerate(serie['temporadas'], start=1):
            if not temp.get('title'):
                continue

            temp_number = temp.get('number', index)
            
            has_episodes = bool(temp.get('episodios_link') or temp.get('episodios', []))
            title = temp['title'] + (' (Indisponível)' if not has_episodes else '')

            li = xbmcgui.ListItem(label=title)
            li.setArt({
                'poster': temp.get('poster', serie.get('poster', '')),
                'fanart': serie.get('backdrop', ''),
                'clearlogo': clearlogo
            })
            
            li.setInfo('video', {
                'title': title,
                'tvshowtitle': serie['title'],
                'season': temp_number,
                'plot': temp.get('synopsis', ''),
                'rating': temp.get('rating', 0),
                'mediatype': 'season'
            })

            if has_episodes:
                url = get_url(
                    action='list_episodes',
                    season_title=title,
                    serie=json.dumps({
                        'serie_title': serie['title'],
                        'serie_clearlogo': clearlogo,
                        'season_title': temp['title'],
                        'season_number': temp_number,
                        'episodios_link': temp.get('episodios_link', ''),
                        'episodios': temp.get('episodios', []),
                        'poster': temp.get('poster', serie.get('poster', '')),
                        'fanart': serie.get('backdrop', '')
                    })
                )
                xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
            else:
                li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, '', li, isFolder=False)

        xbmcplugin.endOfDirectory(handle)
        return True

    except Exception as e:
        xbmc.log(f"Erro em list_seasons: {str(e)}", xbmc.LOGERROR)
        return False


def list_episodes(handle, season_data, season_title):
    """Lista episódios com número correto da temporada"""
    try:
        if isinstance(season_data, str):
            season = json.loads(season_data)
        else:
            season = season_data

        clearlogo = season.get('serie_clearlogo', '')
        serie_title = season.get('serie_title', 'Série')
        season_number = season.get('season_number', 1)
        
        header = f"{serie_title}"
        if clearlogo:
            xbmcplugin.setProperty(handle, 'clearlogo', clearlogo)
            
        xbmcplugin.setPluginCategory(handle, header)
        xbmcplugin.setContent(handle, 'episodes')

        episodios = []
        if season.get('episodios_link'):
            try:
                with urllib.request.urlopen(season['episodios_link']) as response:
                    episodios = json.loads(response.read().decode()).get('episodios', [])
            except Exception as e:
                xbmc.log(f"Erro ao carregar episódios: {str(e)}", xbmc.LOGERROR)
        else:
            episodios = season.get('episodios', [])

        for ep in episodios:
            if not ep.get('url'):
                continue

            ep_num = ep.get('episode', '')
            ep_title = ep.get('title', 'Episódio Desconhecido')
            label = f"Ep. {ep_num} - {ep_title}" if ep_num else ep_title

            li = xbmcgui.ListItem(label=label)
            li.setInfo('video', {
                'title': ep_title,
                'tvshowtitle': serie_title,
                'season': season_number,
                'episode': int(ep_num) if str(ep_num).isdigit() else 0,
                'plot': ep.get('synopsis', ''),
                'aired': ep.get('air_date', ''),
                'rating': ep.get('rating', 0),
                'mediatype': 'episode'
            })

            li.setArt({
                'thumb': ep.get('poster', season.get('poster', '')),
                'fanart': season.get('fanart', ''),
                'clearlogo': clearlogo
            })
            li.setProperty('IsPlayable', 'true')

            url = ep['url'] if isinstance(ep['url'], list) else [ep['url']]
            xbmcplugin.addDirectoryItem(
                handle,
                get_url(action='play', video=json.dumps(url), is_series='true'),
                li,
                isFolder=False
            )

        xbmcplugin.endOfDirectory(handle)
        return True

    except Exception as e:
        xbmc.log(f"Erro em list_episodes: {str(e)}", xbmc.LOGERROR)
        return False


def handle_plugin_call():
    """
    Função principal que processa a chamada do plugin,
    isolando a lógica de inicialização de sys.argv.
    """
    try:
        # AQUI definimos as variáveis URL e HANDLE,
        # que só serão executadas quando o script for chamado diretamente
        URL = sys.argv[0]
        HANDLE = int(sys.argv[1])
        
        params = dict(parse_qsl(sys.argv[2][1:]))
        action = params.get('action')
        
        # Lógica de roteamento do plugin
        if action == 'list_videos':
            external_link = params.get('external_link', '')
            is_vip = params.get('is_vip', False)
            sort_method = params.get('sort_method')
            page = params.get('page', 1)
            items_per_page = params.get('items_per_page', 100)
            list_videos(HANDLE, external_link, is_vip, sort_method, page, items_per_page)
        elif action == 'list_collection':
            collection_data = params.get('collection')
            list_collection(HANDLE, collection_data)
        elif action == 'list_seasons':
            serie_data = params.get('serie')
            list_seasons(HANDLE, serie_data)
        elif action == 'list_episodes':
            season_data = params.get('season')
            season_title = params.get('season_title')
            list_episodes(HANDLE, season_data, season_title)
        elif action == 'add_to_favorites':
            video_data_str = params.get('video')
            if video_data_str:
                add_to_favorites(json.loads(video_data_str))
        elif action == 'remove_from_favorites':
            video_data_str = params.get('video')
            if video_data_str:
                remove_from_favorites(json.loads(video_data_str))
        else:
            xbmcgui.Dialog().notification('Erro', f'Ação desconhecida: {action}', xbmcgui.NOTIFICATION_ERROR)

    except IndexError:
        # Este é o bloco que será executado quando o script
        # for importado por outro módulo (como o service.py).
        # Ele não tenta acessar sys.argv[1] e, portanto, não falha.
        xbmc.log("video_listing.py importado, ignorando a execução do plugin.", xbmc.LOGDEBUG)
        pass


# Este bloco de código só será executado quando o script for o programa principal,
# ou seja, quando o Kodi o chamar diretamente.
if __name__ == '__main__':
    handle_plugin_call()