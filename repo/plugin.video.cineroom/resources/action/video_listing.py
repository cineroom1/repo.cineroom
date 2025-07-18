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

# Internos
from urllib.parse import urlencode, parse_qsl
from resources.action.favorites import load_favorites
from resources.lib.utils import get_all_videos, VIDEO_CACHE, FILTERED_CACHE
from resources.lib.utils_view import set_view_mode


# No final da função, depois de xbmcplugin.endOfDirectory(HANDLE)




HANDLE = int(sys.argv[1])
URL = sys.argv[0]

def get_url(**kwargs) -> str:
    """
    Cria uma URL para chamar o plugin recursivamente.
    Otimizado para serialização automática de objetos.
    """
    params = {}
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            params[key] = json.dumps(value)
        else:
            params[key] = value
    return f"{URL}?{urlencode(params)}"


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

def set_content_type(videos):
    """Define o tipo de conteúdo com base nos vídeos."""
    types = {video['type'] for video in videos}
    if types == {'movie'}:
        xbmcplugin.setContent(HANDLE, 'movies')
    elif types == {'tvshow'}:
        xbmcplugin.setContent(HANDLE, 'tvshows')
    elif types == {'set'}:
        xbmcplugin.setContent(HANDLE, 'movies')
    else:
        xbmcplugin.setContent(HANDLE, 'movies')


def create_video_item(video):
    """Cria um ListItem para exibir na interface do Kodi."""
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

        if mediatype == 'movie':
            urls = video.get('url', [])
            if isinstance(urls, str):
                urls = [urls]
            url = get_url(
                action='play',
                video=','.join(urls),
                tmdb_id=video.get('tmdb_id', ''),
                imdb_id=video.get('imdb_id', ''),
                title=video.get('title', ''),
                movie_poster=video.get('poster', ''),
                movie_synopsis=video.get('synopsis', ''),
                is_series='false'
            )
        elif mediatype == 'set':
            url = get_url(action='list_collection', collection=json.dumps(video))
        elif mediatype == 'tvshow':
            url = get_url(action='list_seasons', serie=video)
        else:
            url = ''

        # Montando dicionário de informações para o Kodi
        info = {
            'title': video['title'],
            'mediatype': mediatype,
            'plot': video.get('synopsis', ''),
            'premiered': video.get("premiered", "Ano não disponível"),
            'dateadded': video.get('date_added', ''),
        }

        # Rating
        try:
            info['rating'] = float(video.get('rating', 0))
        except (ValueError, TypeError):
            info['rating'] = 0

        # Vote count
        try:
            info['votes'] = int(video.get('vote_count', 0))
        except (ValueError, TypeError):
            info['votes'] = 0

        # Ano
        try:
            info['year'] = int(video.get('year', 0))
        except (ValueError, TypeError):
            info['year'] = 0

        # Gêneros
        genres = video.get('genres', [])
        if isinstance(genres, list):
            info['genre'] = genres
        elif isinstance(genres, str):
            info['genre'] = [genres]

        # Diretores
        raw_director_data = video.get("director")
        directors = []
        if isinstance(raw_director_data, list):
            directors = [str(d).strip() for d in raw_director_data if d is not None and str(d).strip()]
        elif isinstance(raw_director_data, str) and raw_director_data.strip():
            directors = [raw_director_data.strip()]
        if directors:
            info['director'] = directors

        # Estúdios
        studio_data = video.get('studio', [])
        if isinstance(studio_data, list):
            info['studio'] = ', '.join([str(s).strip() for s in studio_data if s is not None and str(s).strip()])
        elif isinstance(studio_data, str):
            info['studio'] = studio_data.strip()

        # Runtime
        info['duration'] = video.get("runtime", 0)

        # Adicionar bilheteria e IMDb ID ao plot
        plot_extra = ""
        revenue = video.get('revenue', 0)
        if revenue:
            formatted_revenue = f"\n[COLOR gold]Bilheteria[/COLOR]: ${revenue:,.0f}".replace(",", ".")
            plot_extra += f"\n{formatted_revenue}"

        imdb_id = video.get('imdb_id', '')
        if imdb_id:
            info['imdbnumber'] = imdb_id
            list_item.setProperty('imdb_id', imdb_id)
            try:
                list_item.setUniqueIDs({'imdb': imdb_id})  # Padrão moderno do Kodi
            except Exception as e:
                xbmc.log(f"Erro ao definir UniqueIDs: {e}", xbmc.LOGDEBUG)

        if plot_extra:
            info['plot'] += plot_extra

        # Define as informações no ListItem
                # Define as informações no ListItem
        list_item.setInfo('video', info)

        # 🎯 NOVO: Adicionar legendas, se existirem
        subtitles = video.get('subtitles')
        if subtitles:
            if isinstance(subtitles, str):
                subtitles = [subtitles]
            list_item.setSubtitles(subtitles)

        # Define como propriedade adicional
        list_item.setProperty('mediatype', mediatype)
        if revenue:
            list_item.setProperty('revenue', str(revenue))

        # Menu de favoritos
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

        xbmc.log(f"DEBUG: create_video_item - Valor final de is_folder antes do retorno: {is_folder} (Tipo: {type(is_folder)})", xbmc.LOGDEBUG)
        return list_item, url, is_folder

    except Exception as e:
        xbmc.log(f"Erro ao criar item de vídeo: {e}", xbmc.LOGERROR)
        return None, None, False




def list_videos(external_link, sort_method=None, page=1, items_per_page=100):
    """Lista os vídeos com cache otimizado e tratamento de erros robusto"""
    progress = xbmcgui.DialogProgressBG()
    progress.create('Carregando vídeos', 'Otimizando...')
    
    try:
        # 1. Configuração inicial segura
        try:
            page = max(1, int(page))
            items_per_page = max(10, min(int(items_per_page), 200))
        except (ValueError, TypeError):
            page = 1
            items_per_page = 100

        # 2. Função auxiliar para verificar memória
        def get_system_memory():
            mem_str = xbmc.getInfoLabel('System.Memory(total)')
            if 'MB' in mem_str:
                return int(mem_str.replace('MB', '').strip())
            elif 'GB' in mem_str:
                return int(float(mem_str.replace('GB', '').strip()) * 1024)
            return 1024  # Default seguro para 1GB se não puder detectar

        # 3. Cache inteligente com verificação de memória segura
        cache_key = f"v4_{hashlib.md5(external_link.encode()).hexdigest()}_{sort_method or 'none'}"
        videos = []
        ram_cache_active = False
        
        # Verifica se há memória suficiente para cache RAM (>1GB)
        if get_system_memory() > 1024:  # Mais de 1GB
            ram_cache_active = True
            if hasattr(list_videos, '_ram_cache'):
                cached = list_videos._ram_cache.get(cache_key)
                if cached and time.time() - cached['time'] < 300:  # 5 minutos
                    videos = cached['data']
                    progress.update(30, 'Dados da RAM')

        # Cache em disco se RAM não disponível ou vazio
        if not videos and VIDEO_CACHE.enabled:
            progress.update(20, 'Verificando cache...')
            try:
                cached = VIDEO_CACHE.get(cache_key)
                if cached:
                    videos = json.loads(cached)
                    # Atualiza cache RAM se disponível
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

        # 4. Carregamento dos dados se cache vazio
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

        # 5. Verificações de conteúdo
        if not videos:
            progress.close()
            xbmcgui.Dialog().ok('Erro', 'Nenhum vídeo encontrado')
            return

        if check_maintenance(videos):
            progress.close()
            return

        # 6. Processamento otimizado dos vídeos
        progress.update(70, 'Processando...')
        video_items = videos[1:] if isinstance(videos[0], dict) and "status" in videos[0] else videos
        set_content_type(video_items)

        # 7. Ordenação segura
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

        # 8. Paginação e exibição
        total_items = len(video_items)
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        
        progress.update(80, 'Preparando exibição...')
        added_items = 0
        
        for i in range(start_index, min(end_index, total_items)):
            video = video_items[i]
            
            # Atualização de progresso otimizada
            if i % 5 == 0 or i == end_index - 1:
                progress.update(80 + int((i-start_index)/items_per_page*20), 
                              f'Item {i+1}/{total_items}')
            
            if not isinstance(video, dict):
                continue
                
            try:
                list_item, url, is_folder = create_video_item(video)
                if list_item and url:
                    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)
                    added_items += 1
            except Exception as e:
                xbmc.log(f"[ERRO] Item inválido: {str(e)}", xbmc.LOGDEBUG)

        # 9. Próxima página se aplicável
        if end_index < total_items and added_items > 0:
            next_page_item = xbmcgui.ListItem(label='Próxima Página >>')
            next_page_url = get_url(
                action='list_videos',
                external_link=external_link,
                sort_method=sort_method,
                page=page + 1,
                items_per_page=items_per_page
            )
            xbmcplugin.addDirectoryItem(HANDLE, next_page_url, next_page_item, isFolder=True)

        xbmcplugin.endOfDirectory(HANDLE)
        set_view_mode()

    except Exception as e:
        xbmc.log(f"[ERRO CRÍTICO] list_videos: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Erro', 'Verifique os logs', xbmcgui.NOTIFICATION_ERROR)
    finally:
        progress.close()


def list_collection(collection_data):
    """Lista os filmes de uma coleção, com estrutura semelhante à de temporadas de séries."""

    try:
        # 1. Desserialização segura
        if isinstance(collection_data, str):
            collection = json.loads(collection_data)
        else:
            collection = collection_data

        # 2. Validação básica
        if not isinstance(collection, dict) or not collection.get('movies'):
            raise ValueError("Dados da coleção inválidos ou 'movies' ausentes.")

        # 3. Nome da coleção para exibição e organização
        collection_title = collection.get('title', 'Coleção')
        xbmcplugin.setPluginCategory(HANDLE, collection_title)
        xbmcplugin.setContent(HANDLE, 'movies')

        # 4. Itera pelos filmes da coleção
        for movie in collection.get('movies', []):
            movie['type'] = 'movie'  # Força o tipo correto
            list_item, url, is_folder = create_video_item(movie)
            if list_item and url:
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)

        # 5. Finaliza a listagem
        xbmcplugin.endOfDirectory(HANDLE)

    except Exception as e:
        xbmc.log(f"Erro ao listar coleção: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Erro', 'Não foi possível exibir a coleção.', xbmcgui.NOTIFICATION_ERROR, 3000)


def list_seasons(serie_data):
    """Lista temporadas com número correto da temporada"""
    try:
        if isinstance(serie_data, str):
            serie = json.loads(serie_data)
        else:
            serie = serie_data

        # Configurações iniciais
        clearlogo = serie.get('clearlogo', '')
        if clearlogo:
            xbmcplugin.setPluginCategory(HANDLE, '{}'.format(serie.get('title', '')))
            xbmcplugin.setProperty(HANDLE, 'clearlogo', clearlogo)
        
        xbmcplugin.setContent(HANDLE, 'seasons')
        
        # Processa cada temporada com seu número correto
        for index, temp in enumerate(serie['temporadas'], start=1):
            if not temp.get('title'):
                continue

            # Define o número da temporada (pega do JSON ou usa o índice)
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
                'season': temp_number,  # Usa o número correto aqui
                'plot': temp.get('synopsis', ''),
                'rating': temp.get('rating', 0),
                'mediatype': 'season'
            })

            if has_episodes:
                url = get_url(
                    action='list_episodes',
                    serie=json.dumps({
                        'serie_title': serie['title'],
                        'serie_clearlogo': clearlogo,
                        'season_title': temp['title'],
                        'season_number': temp_number,  # Passa o número correto
                        'episodios_link': temp.get('episodios_link', ''),
                        'episodios': temp.get('episodios', []),
                        'poster': temp.get('poster', serie.get('poster', '')),
                        'fanart': serie.get('backdrop', '')
                    })
                )
                xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
            else:
                li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(HANDLE, '', li, isFolder=False)

        xbmcplugin.endOfDirectory(HANDLE)
        return True

    except Exception as e:
        xbmc.log(f"Erro em list_seasons: {str(e)}", xbmc.LOGERROR)
        return False


def list_episodes(season_data, season_title):
    """Lista episódios com número correto da temporada"""
    try:
        if isinstance(season_data, str):
            season = json.loads(season_data)
        else:
            season = season_data

        # Configura cabeçalho
        clearlogo = season.get('serie_clearlogo', '')
        serie_title = season.get('serie_title', 'Série')
        season_number = season.get('season_number', 1)  # Agora vem correto da list_seasons
        
        header = f"{serie_title}"
        if clearlogo:
            xbmcplugin.setProperty(HANDLE, 'clearlogo', clearlogo)
            
        xbmcplugin.setPluginCategory(HANDLE, header)
        xbmcplugin.setContent(HANDLE, 'episodes')

        # Carrega episódios
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
                'season': season_number,  # Usa o número correto da temporada
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
                HANDLE,
                get_url(action='play', video=json.dumps(url), is_series='true'),
                li,
                isFolder=False
            )

        xbmcplugin.endOfDirectory(HANDLE)
        return True

    except Exception as e:
        xbmc.log(f"Erro em list_episodes: {str(e)}", xbmc.LOGERROR)
        return False