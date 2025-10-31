# -*- coding: utf-8 -*-
import sys
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
import json
import re
from .db import db
from .utils import create_video_item
from . import scrapers
from .dialogs import DialogSelecaoFontes
from urllib.parse import urlencode, unquote_plus, quote_plus
import urllib.request
import re
import threading
import time



# --- Configurações Essenciais ---
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
ADDON = xbmcaddon.Addon()
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"

# --- Mapeamento de Idiomas (se ainda precisar) ---
FLAG_TO_LANG = { '🇧🇷': 'BR', '🇵🇹': 'PT', '🇺🇸': 'EN', '🇬🇧': 'EN', '🇪🇸': 'ES' }
def extract_languages_from_title(title: str):
    languages = []
    flags = re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', title)
    for flag in flags:
        lang = FLAG_TO_LANG.get(flag)
        if lang and lang not in languages:
            languages.append(lang)
    return languages if languages else ['N/A']

def parse_stream_title(title):
    """Extrai detalhes do título da fonte do Torrentio."""
    details = {}
    details['release_title'] = title.split('\n')[0].strip()
    size_match = re.search(r'\[\s*(\d+\.?\d*\s*(GB|MB))\s*\]', title, re.IGNORECASE)
    if size_match: details['size'] = size_match.group(1)
    peers_match = re.search(r'👤\s*(\d+)', title)
    if peers_match: details['peers'] = peers_match.group(1)
    provider_match = re.search(r'⚙️\s*([^\n]+)', title)
    if provider_match: details['provider'] = provider_match.group(1).strip()
    return details
    
def show_main_menu(menu_structure):
    """Cria e exibe os itens do menu principal na tela."""
    xbmcplugin.setPluginCategory(HANDLE, 'Menu Principal')
    
    xbmc.log(f"[DEBUG] 'show_main_menu' em navigation.py foi EXECUTADA. Estrutura recebida: {menu_structure}", xbmc.LOGINFO)

    for item in menu_structure:
        xbmc.log(f"[DEBUG] Adicionando item ao menu: {item['title']}", xbmc.LOGINFO)

        li = xbmcgui.ListItem(label=item['title'])
        
        # --- BLOCO ADICIONADO PARA MOSTRAR O ÍCONE ---
        # Pega o ícone do dicionário. Usar .get() é mais seguro pois não dá erro se a chave 'icon' não existir.
        icon = item.get('icon')
        if icon:
            # Define a arte do item da lista. 'thumb' é a chave para o ícone principal.
            li.setArt({'thumb': icon})
        # ----------------------------------------------
        
        # Adiciona Plot/Descrição se existir
        plot = item.get('plot', '')
        if plot:
            li.setInfo('video', {'plot': plot})
            
        url = get_url(action=item['action'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
        
    # Finaliza o diretório para que os itens apareçam na tela.
    xbmcplugin.endOfDirectory(HANDLE)
    
# Em navigation.py

def show_my_list():
    """Exibe todos os filmes e séries da lista de favoritos."""
    xbmcplugin.setPluginCategory(HANDLE, "Minha Lista")
    xbmcplugin.setContent(HANDLE, 'videos')
    
    favorites = db.get_all_favorites()
    
    if not favorites:
        xbmcgui.Dialog().ok(
            "Sua lista está vazia.",
            "Use o menu de contexto (clique direito ou segure 'OK')"
        )

        xbmcplugin.endOfDirectory(HANDLE)
        return
        
    for item in favorites:
        media_type = item['item_type']
        li = create_video_item(item, media_type)
        
        # Monta a URL correta para cada tipo de item
        if media_type == 'movie':
            streams_json = json.dumps(item.get('streams', []))
            url = get_url(action='find_sources', 
                        media_type='movie',
                        tmdb_id=item.get('tmdb_id'),
                        imdb_id=item.get('imdb_id'))
            li.setProperty('IsPlayable', 'true')
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
        elif media_type == 'tvshow':
            url = get_url(action='list_seasons', tvshow_tmdb_id=item['tmdb_id'])
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
            
    xbmcplugin.endOfDirectory(HANDLE)    
    
def _fetch_json_from_url(url):
    """Função auxiliar para baixar um JSON de uma URL."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        xbmc.log(f"[ERROR] Falha ao buscar JSON de {url}: {e}", xbmc.LOGERROR)
    return None


def search(query=None):
    """
    Função de busca unificada. Se não houver 'query', abre o teclado.
    Se houver 'query', mostra os resultados.
    """
    # Cenário 1: O usuário acabou de clicar em "Pesquisar"
    if not query:
        keyboard = xbmc.Keyboard('', 'Pesquisar no Cineroom')
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            query = keyboard.getText()
        else:
            # Usuário cancelou, então não fazemos nada
            return

    # Se chegamos aqui, temos uma 'query' para pesquisar (seja do teclado ou do re-carregamento)
    if not query: return # Segurança extra caso o texto seja vazio
    
    # A partir daqui, o código é o mesmo da sua antiga 'show_search_results'
    results = db.search_items(query)
    
    # É crucial definir um category que inclua a query.
    # Isso ajuda o Kodi a entender o "contexto" da lista.
    xbmcplugin.setPluginCategory(HANDLE, f'Resultados para: "{query}"')
    xbmcplugin.setContent(HANDLE, 'videos')
        
    if results:
        for item in results:
            media_type = item['item_type']
            li = create_video_item(item, media_type)
            
            if media_type == 'movie':
                streams_json = json.dumps(item.get('streams', []))
                # ✅ MUDANÇA SUTIL: A URL de play agora precisa preservar a query
                # para o Kodi saber onde voltar ao apertar "Back".
                url = get_url(action='find_sources', 
                        media_type='movie',
                        tmdb_id=item.get('tmdb_id'),
                        imdb_id=item.get('imdb_id'))
                li.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
            elif media_type == 'tvshow':
                url = get_url(action='list_seasons', tvshow_tmdb_id=item['tmdb_id'])
                xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    else:
        xbmcgui.Dialog().notification("Pesquisa", f'Nenhum resultado encontrado para "{query}"')

    xbmcplugin.endOfDirectory(HANDLE)  


# --- Providers com Ordem Prioritária ---
PROVIDERS = {
    "StarckFilmes": {
        "url": "https://starckfilmes-v2.com", 
        "configurable": False,
        "priority": 1  # 🥇 PRIMEIRO - Fontes diretas BR, mais rápidas
    },
    "AnimeZey": {
        "url": "https://1.animezey23112022.workers.dev", 
        "configurable": False, 
        "priority": 1  # 🥇 PRIMEIRO - Especializado em animes
    },
    "Brazuca": {
        "url": "https://94c8cb9f702d-brazuca-torrents.baby-beamup.club",
        "configurable": False,
        "priority": 2  # 🥈 SEGUNDO - Torrents BR organizados
    },
    "MyCine": {
        "url": "https://mycine.alwaysdata.net",
        "configurable": False, 
        "priority": 3  # 🥉 TERCEIRO - Backup BR
    },
    "Torrentio": {
        "url": "https://torrentio.strem.fun/providers=comando,bludv,micoleaodublado,yts,nyaasi,1337x%7Clanguage=portuguese,english,japanese",
        "configurable": False,
        "priority": 4  # 🏅 QUARTO - Internacional (fallback)
    }    
}

def find_and_play_sources(item_data, autoplay=False, season=None, episode=None):
    """
    (VERSÃO OTIMIZADA COM ORDEM PRIORITÁRIA)
    Busca fontes na ordem prioritária definida para melhor UX e performance.
    """
    xbmc.log(f"[DEBUG] Dados recebidos em find_and_play_sources: {item_data}", xbmc.LOGINFO)

    media_type = item_data.get('media_type')
    imdb_id = item_data.get('imdb_id')

    if not media_type:
        xbmcgui.Dialog().ok("Erro", "Dados insuficientes (media_type ausente).")
        return

    # AnimeZey não precisa de IMDB ID, mas outros provedores sim
    if not imdb_id and not ADDON.getSettingBool("provider.animezey.enabled"):
        xbmc.log(f"IMDB ID ausente para {media_type} '{item_data.get('title')}' e AnimeZey está desativado.", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", "IMDB ID ausente, não é possível buscar em provedores Stremio.")
        return

    local_streams = []
    provider_streams_to_process = []

    # --- Função Auxiliar Interna: Extrair Idiomas ---
    def extrair_idiomas_do_titulo(titulo, extras=None, provider=None):
        titulo_lower = titulo.lower()
        idiomas = set()
        mapa_idiomas = {
            'dual': 'DUAL', 'multi': 'MULTI', 'dublado': 'PT-BR', 'portugues': 'PT-BR', 
            'portuguese': 'PT-BR', 'pt': 'PT-BR', 'pt-br': 'PT-BR', 'br': 'PT-BR', 
            'port': 'PT-BR', '.DUAL': 'PT-BR', 'DUAL': 'PT-BR', 'legendado': 'LEG', 
            'leg': 'LEG', 'sub': 'LEG', 'subs': 'LEG', 'subbed': 'LEG', 'ingles': 'EN', 
            'english': 'EN', 'ing': 'EN', 'eng': 'EN', 'espanhol': 'ES', 'spanish': 'ES', 
            'esp': 'ES', 'lat': 'LAT', 'frances': 'FR', 'french': 'FR', 'fre': 'FR', 
            'japones': 'JP', 'japanese': 'JP', 'jpn': 'JP', 'italiano': 'IT', 
            'italian': 'IT', 'ita': 'IT', 'aleman': 'DE', 'german': 'DE', 'ger': 'DE', 
            'pl': 'PL', 'polish': 'PL', 'plsub': 'PL', 'napisy pl': 'PL', 'russo': 'RU', 
            'russian': 'RU', 'rus': 'RU', 'mvo': 'RU', 'закадры': 'RU',
        }
        for termo, sigla in mapa_idiomas.items():
            if termo in titulo_lower: 
                idiomas.add(sigla)
            if extras and any(termo in str(x).lower() for x in extras): 
                idiomas.add(sigla)
            if provider and termo in provider.lower(): 
                idiomas.add(sigla)
        
        if 'PT-BR' in idiomas and 'EN' in idiomas:
            idiomas.discard('PT-BR')
            idiomas.discard('EN')
            idiomas.add('DUAL')
            
        if provider and 'local' in provider.lower():
            if 'DUAL' in idiomas or ('PT-BR' in idiomas and 'EN' in idiomas):
                return 'PT-BR / EN'
                
        return ' / '.join(sorted(idiomas)) or 'N/A'

    # --- Bloco Fontes Locais ---
    fontes_locais_raw = item_data.get('streams', [])
    if isinstance(fontes_locais_raw, list):
        for stream in fontes_locais_raw:
            if isinstance(stream, dict) and stream.get('url'):
                is_torrent = "elementum" in stream.get('url', '') or stream.get('server_name', '').upper() == 'TORRENT'
                stream_type = 'Torrent' if is_torrent else 'Direto'
                provider = stream.get('server_name', 'Fonte Local')
                titulo_local = f"{item_data.get('title')} {stream.get('quality', '')} {' '.join(stream.get('extras', []))}"
                languages = extrair_idiomas_do_titulo(titulo_local, stream.get('extras', []), provider)
                local_streams.append({
                    'url': stream.get('url'), 
                    'quality': stream.get('quality', 'N/A'),
                    'type': stream_type, 
                    'release_title': item_data.get('title', 'N/A'),
                    'size': stream.get('size', 'N/A'), 
                    'peers': 'N/A', 
                    'seeders': 'N/A', 
                    'provider': provider, 
                    'languages': languages
                })

    # --- Bloco Busca Paralela nos Provedores - COM ORDEM PRIORITÁRIA ---
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
    threads = []
    lock = threading.Lock()
    provider_results = {}  # Dicionário para manter ordem

    def fetch_sources(provider_name, provider_data, priority):
        """Função interna da thread para chamar o scraper."""
        try:
            streams_found = scrapers.scrape_provider_sources(
                provider_name=provider_name,
                provider_data=provider_data,
                item_data=item_data
            )
            if streams_found and isinstance(streams_found, list): 
                with lock:
                    valid_streams = []
                    for stream in streams_found:
                        if isinstance(stream, dict): 
                            stream['provider_name'] = provider_name
                            stream['provider_priority'] = priority
                            valid_streams.append(stream)
                    provider_results[provider_name] = valid_streams
                    xbmc.log(f"[SCRAPER] {provider_name} encontrou {len(valid_streams)} fontes", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[SCRAPER] Erro em {provider_name}: {e}", xbmc.LOGERROR)

    # Ordena providers por prioridade antes de iniciar threads
    sorted_providers = sorted(
        [(name, data) for name, data in PROVIDERS.items() 
         if ADDON.getSettingBool(f"provider.{name.lower()}.enabled")],
        key=lambda x: x[1].get('priority', 999)
    )

    xbmc.log(f"[SCRAPER] Providers ativos (ordenados): {[name for name, _ in sorted_providers]}", xbmc.LOGINFO)

    # Inicia as threads para cada provedor (agora ordenados)
    for name, data in sorted_providers:
        # Verificação IMDB ID
        if name != 'AnimeZey' and not imdb_id:
            xbmc.log(f"Pulando provedor {name} (não-AnimeZey) por falta de IMDB ID.", xbmc.LOGWARNING)
            continue

        thread = threading.Thread(
            target=fetch_sources, 
            args=(name, data, data.get('priority', 999))
        )
        threads.append(thread)
        thread.start()

    # Aguarda todas as threads
    for thread in threads:
        thread.join()

    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    
    # Reconstroi a lista na ORDEM PRIORITÁRIA
    provider_streams_to_process = []
    for name, _ in sorted_providers:
        if name in provider_results:
            provider_streams_to_process.extend(provider_results[name])
    
    xbmc.log(f"[SCRAPER] Total de fontes de providers: {len(provider_streams_to_process)}", xbmc.LOGINFO)

    # --- Bloco Processamento das Fontes ---
    provider_streams_formatted = []
    if provider_streams_to_process:
        seen_urls = {stream['url'] for stream in local_streams if stream.get('url')}

        for stream in provider_streams_to_process:
            url_fonte = stream.get('url') or stream.get('infoHash') 
            
            if not url_fonte or url_fonte in seen_urls:
                continue
            seen_urls.add(url_fonte)

            # Determina o tipo
            stream_type = stream.get('type', 'Desconhecido')
            if stream_type == 'Desconhecido':
                if re.match(r'^[a-fA-F0-9]{40}$', url_fonte) or url_fonte.startswith('magnet:'):
                    stream_type = 'Torrent'
                elif url_fonte.startswith(('http:', 'https:')):
                    stream_type = 'Direto'

            # Extração de informações
            full_title = stream.get('title') or stream.get('name') or stream.get('release_title', 'Título desconhecido')
            release_title = full_title.split('\n')[0].strip()

            size_str = stream.get('size', 'N/A')
            peers_str = str(stream.get('peers', stream.get('seeders', 0)))
            seeders_str = str(stream.get('seeders', stream.get('peers', 0)))
            real_provider = stream.get('provider_name', 'N/A')
            
            quality = stream.get('quality')
            if not quality:
                quality_match = re.search(r'(4K|2160p|1080p|720p)', release_title, re.IGNORECASE)
                quality = quality_match.group(1).upper() if quality_match else 'HD'

            # Extração de idiomas
            languages = extrair_idiomas_do_titulo(release_title, stream.get('extras', []), real_provider)
            hints = stream.get('behaviorHints', {})
            api_langs = hints.get('videoLanguages', [])
            if api_langs:
                languages_str_api = ' / '.join([lang.upper() for lang in api_langs])
                if languages != 'N/A' and languages not in languages_str_api and languages_str_api not in languages:
                    languages = f"{languages} / {languages_str_api}"
                elif languages == 'N/A':
                    languages = languages_str_api

            provider_streams_formatted.append({
                'url': url_fonte,
                'quality': quality,
                'type': stream_type,
                'release_title': release_title,
                'size': size_str,
                'peers': peers_str,
                'seeders': seeders_str,
                'provider': real_provider,
                'languages': languages,
                'provider_priority': stream.get('provider_priority', 999)  # Mantém prioridade para ordenação
            })

    # --- Ordenação Final e Exibição ---
    # Ordena por prioridade do provider primeiro, depois por seeders
    provider_streams_formatted.sort(key=lambda x: (
        x.get('provider_priority', 999),
        int(x['seeders']) if str(x.get('seeders')).isdigit() else 0
    ), reverse=False)  # False porque prioridade menor = melhor

    final_streams = local_streams + provider_streams_formatted

    if not final_streams:
        xbmcgui.Dialog().ok("Aviso", "Nenhuma fonte foi encontrada.")
        return

    url_escolhida = None

    # Verifica configuração de autoplay
    try:
        is_autoplay_enabled = ADDON.getSettingBool('playback.autoplay')
    except Exception:
        is_autoplay_enabled = False

    if is_autoplay_enabled and final_streams:
        # MODO AUTOPLAY - pega a primeira fonte (já ordenada por prioridade)
        best_source = final_streams[0]
        url_escolhida = best_source.get('url')
        xbmc.log(f"[Cineroom] Autoplay: selecionando fonte prioritária: {best_source['provider']}", xbmc.LOGINFO)

    else:
        # MODO SELEÇÃO DE FONTE
        try:
            # Tenta usar diálogo customizado
            from resources.lib.dialogs import DialogSelecaoFontes  # Ajuste o import conforme necessário
            xml_filename = 'dialog_cineroom_fullscreen.xml'
            addon_path = ADDON.getAddonInfo('path')
            dialog = DialogSelecaoFontes(xml_filename, addon_path, fontes=final_streams, item_data=item_data)
            dialog.doModal()
            url_escolhida = dialog.escolha
            del dialog
        except Exception as e:
            xbmc.log(f"Erro ao mostrar dialog fullscreen: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
            try:
                # Fallback para diálogo nativo
                labels = [f"[{s['provider']}] {s['release_title']} ({s['quality']}) - {s['languages']}" for s in final_streams]
                urls = [s['url'] for s in final_streams]
                dialog_native = xbmcgui.Dialog()
                selected_index = dialog_native.select('Selecione uma fonte (Ordenadas por Prioridade):', labels)
                if selected_index >= 0:
                    url_escolhida = urls[selected_index]
            except Exception as e2:
                xbmc.log(f"Erro ao mostrar diálogo nativo fallback: {e2}", xbmc.LOGERROR)
                return

    if url_escolhida:
        xbmc.log(f"[Cineroom] Fonte selecionada: {url_escolhida}", xbmc.LOGINFO)
        time.sleep(0.5)
        play_url(url_escolhida, item_data)
    else:
        xbmc.log("[Cineroom] Nenhuma fonte selecionada ou diálogo cancelado.", xbmc.LOGINFO)

def play_url(url, item_info):
    """
    Função para reproduzir uma URL, tratando Torrents (Elementum) com seleção
    automática de episódio e links diretos com headers (AnimeZey).
    """
    if not url:
        xbmc.log("[Cineroom] Tentativa de tocar uma URL vazia.", xbmc.LOGWARNING)
        return

    try:
        handle = int(sys.argv[1])
    except (IndexError, ValueError) as e:
        xbmc.log(f"[Cineroom] Erro: Script chamado sem um handle válido: {e}", xbmc.LOGERROR)
        return

    final_url = url
    is_torrent = False

    # --- 1. Lógica de Torrent ---
    if url.startswith('magnet:'):
        is_torrent = True
        magnet_uri = url
    elif len(url) == 40 and not url.startswith('http') and ' ' not in url:
        is_torrent = True
        magnet_uri = f"magnet:?xt=urn:btih:{url}"
    elif 'elementum' in url:
        is_torrent = True
        magnet_uri = url

    if is_torrent:
        if magnet_uri.startswith('plugin://'):
            final_url = magnet_uri
            xbmc.log(f"[Cineroom] Resolvendo link Elementum (local): {final_url}", xbmc.LOGINFO)
        else:
            encoded_uri = urllib.parse.quote_plus(magnet_uri)
            media_type = item_info.get('media_type')
            tmdb_id = item_info.get('tmdb_id')
            
            final_url = f"plugin://plugin.video.elementum/play?uri={encoded_uri}"
            
            if tmdb_id:
                final_url += f"&tmdb={tmdb_id}"

            # Lógica para séries
            if media_type == 'tvshow':
                season = item_info.get('season')
                episode = item_info.get('episode')
                
                if season is not None and episode is not None:
                    final_url += f"&season={season}&episode={episode}"
                    xbmc.log(f"[Cineroom] Construindo link Elementum (Série S/E): {final_url}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[Cineroom] Construindo link Elementum (Série): {final_url}", xbmc.LOGINFO)
            else:
                xbmc.log(f"[Cineroom] Construindo link Elementum (Filme): {final_url}", xbmc.LOGINFO)
    else:
        xbmc.log(f"[Cineroom] Resolvendo link direto: {final_url}", xbmc.LOGINFO)

    # --- 2. Cria o ListItem ---
    play_item = xbmcgui.ListItem(path=final_url)

    # --- 3. Metadados ---
    info_labels = {
        'title': item_info.get('episode_title', item_info.get('title', 'Playback')),
        'originaltitle': item_info.get('original_title'),
        'year': item_info.get('year'),
        'plot': item_info.get('plot', item_info.get('overview', '')),
        'season': item_info.get('season'),
        'episode': item_info.get('episode'),
        'tvshowtitle': item_info.get('title') if item_info.get('media_type') == 'tvshow' else '',
        'mediatype': item_info.get('media_type', 'video'),
        'imdbnumber': item_info.get('imdb_id'),
        'duration': int(item_info.get('runtime', 0)) * 60,
        'genre': " / ".join(item_info.get('genres', [])),
    }
    play_item.setInfo('video', info_labels)
    
    play_item.setArt({
        'thumb': item_info.get('episode_poster') or item_info.get('poster') or '',
        'poster': item_info.get('poster') or '',
        'fanart': item_info.get('backdrop') or '',
    })

    # --- 4. Lógica de Headers para AnimeZey ---
    animezey_domains = ['animezey23112022.workers.dev', 'animezey16082023.workers.dev', '1.animezeydl.workers.dev']
    if not is_torrent and any(domain in final_url.lower() for domain in animezey_domains):
        xbmc.log("[Cineroom] Link AnimeZey detectado. Configurando inputstream e headers.", xbmc.LOGDEBUG)
        
        play_item.setProperty('inputstream', 'inputstream.ffmpegdirect')
        play_item.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
        play_item.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')

        referer_header = final_url
        headers_str = (
            f"Referer={referer_header}\r\n"
            f"User-Agent={USER_AGENT}\r\n"
        )
        play_item.setProperty('inputstream.ffmpegdirect.headers', headers_str)

    # --- 5. Resolve a URL ---
    play_item.setProperty('IsPlayable', 'true')
    play_item.setContentLookup(False)

    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=play_item)


        
def show_sources_dialog(streams_list):
    """
    Exibe a lista de fontes em uma janela de diálogo nativa do Kodi.
    Para cada episódio, mostra as duas opções disponíveis (4K DUAL AUDIO e normal).
    """
    if not streams_list:
        return None
    
    # Se só tem um link, retorna automaticamente
    if len(streams_list) == 1:
        return streams_list[0].get('url', '')
    
    # Para múltiplos links, identifica qual é 4K e qual é normal
    options = []
    url_map = {}  # Mapeia opções para URLs
    
    for i, stream in enumerate(streams_list):
        url = stream.get('url', '')
        
        # Detecta se é 4K DUAL AUDIO pela URL
        if '(4K - DUAL AUDIO)' in url:
            quality = '4K DUAL AUDIO'
            # Remove o texto da qualidade da URL para ficar limpa
            clean_url = url.replace('(4K - DUAL AUDIO)', '').strip()
        else:
            quality = 'HD'
            clean_url = url
        
        # Cria label descritivo
        label = f"Opção {i+1}: [{quality}]"
        
        options.append(label)
        url_map[label] = clean_url  # Usa a URL limpa
    
    # Mostra diálogo de seleção
    dialog = xbmcgui.Dialog()
    selected_index = dialog.select('Selecione a qualidade do vídeo:', options)
    
    if selected_index < 0:
        xbmc.log("Seleção de qualidade cancelada pelo usuário.", xbmc.LOGINFO)
        return None
    
    selected_label = options[selected_index]
    selected_url = url_map[selected_label]
    
    xbmc.log(f"Qualidade selecionada: {selected_label}", xbmc.LOGINFO)
    return selected_url

def play_movie(streams, tmdb_id=None, season=None, episode=None, show_title=None, 
               episode_title=None, episode_plot=None, episode_duration=0, episode_tmdb_id=None):
    """
    Função para reproduzir links diretos (HTTP, M3U8, etc.)
    Recebe uma lista de fontes, exibe a janela de seleção simples
    e toca o link escolhido.
    """
    from urllib.parse import unquote_plus
    
    if not streams:
        xbmcgui.Dialog().ok("Erro", "Nenhuma fonte encontrada")
        return

    # 1. Decodifica e carrega a lista de fontes da URL
    try:
        streams_list = json.loads(unquote_plus(streams))
    except (json.JSONDecodeError, TypeError):
        xbmcgui.Dialog().ok("Erro", "Falha ao processar a lista de fontes.")
        return

    # 2. Chama a janela de seleção simples
    url_escolhida = show_sources_dialog(streams_list)
    
    if not url_escolhida:
        xbmc.log("Nenhuma fonte selecionada pelo usuário.", xbmc.LOGINFO)
        return
        
    # 3. Lógica de playback para links diretos
    # Se for magnet, ainda converte para Elementum (fallback)
    if url_escolhida.startswith('magnet:'):
        url_para_tocar = f"plugin://plugin.video.elementum/play?uri={quote_plus(url_escolhida)}"
    else:
        url_para_tocar = url_escolhida

    
    # Cria o ListItem final COM METADADOS PARA MARCAÇÃO ASSISTIDO
    play_item = xbmcgui.ListItem(path=url_para_tocar)
    
    # ✅✅✅ METADADOS CRÍTICOS PARA MARCAÇÃO ASSISTIDO ✅✅✅
    if tmdb_id and season is not None and episode is not None:
        info_tag = play_item.getVideoInfoTag()
        info_tag.setTitle(episode_title or '')
        info_tag.setTvShowTitle(show_title or '')
        info_tag.setSeason(int(season))
        info_tag.setEpisode(int(episode))
        info_tag.setMediaType('episode')
        info_tag.setPlot(episode_plot or '')
        info_tag.setDuration(int(episode_duration))
        
        unique_ids = {'tmdb': str(tmdb_id)}
        if episode_tmdb_id:
            unique_ids['tmdb_episode'] = str(episode_tmdb_id)
            
        info_tag.setUniqueIDs(unique_ids, 'tmdb')
    
    play_item.setProperty('IsPlayable', 'true')
    play_item.setContentLookup(False)
    
    xbmcplugin.setResolvedUrl(handle=HANDLE, succeeded=True, listitem=play_item)