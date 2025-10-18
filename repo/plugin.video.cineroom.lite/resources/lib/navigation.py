# -*- coding: utf-8 -*-
import sys
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
import json
import re
from .db import db
from .utils import create_video_item
from . import scraper
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


PROVIDERS = {
    "Torrentio": {"url": "https://torrentio.strem.fun", "configurable": True},
    "Brazuca": {"url": "https://torrentio.strem.fun/brazuca", "configurable": True},
    "MyCine": {"url": "https://mycine.alwaysdata.net", "configurable": False}
}

def find_and_play_sources(item_data, autoplay=False, season=None, episode=None):
    """
    Função aprimorada que recebe os dados do item diretamente...
    """
    # ✅ ADICIONE ESTA LINHA PARA VER O QUE ESTÁ CHEGANDO
    xbmc.log(f"[DEBUG] Dados recebidos em find_and_play_sources: {item_data}", xbmc.LOGINFO)

    # Extrai as informações necessárias do dicionário recebido
    media_type = item_data.get('media_type')
    imdb_id = item_data.get('imdb_id')

    # Verificação de segurança
    if not all([media_type, imdb_id]):
         xbmcgui.Dialog().ok("Erro", "Dados insuficientes para buscar fontes (media_type ou imdb_id ausente).")
         return

    # ======================================================================
    # == LISTAS SEPARADAS PARA ORDENAÇÃO ==
    # ======================================================================
    local_streams = []
    provider_streams_to_process = []  # Lista temporária para as threads

    # --- FUNÇÃO AUXILIAR PARA EXTRAIR IDIOMAS ---
    def extrair_idiomas_do_titulo(titulo, extras=None, provider=None):
        xbmc.log(f"[Cineroom] Analisando título stream: {titulo}", xbmc.LOGINFO)
        xbmc.log(f"[Cineroom] Extras: {extras}", xbmc.LOGINFO)
        xbmc.log(f"[Cineroom] Provider: {provider}", xbmc.LOGINFO)

        titulo_lower = titulo.lower()
        idiomas = set()

        mapa_idiomas = {
            'dual': 'DUAL', 'multi': 'MULTI',

            # Português
            'dublado': 'PT-BR', 'portugues': 'PT-BR', 'portuguese': 'PT-BR',
            'pt': 'PT-BR', 'pt-br': 'PT-BR', 'br': 'PT-BR', 'port': 'PT-BR',
            '.DUAL': 'PT-BR', 'DUAL': 'PT-BR',

            # Legenda
            'legendado': 'LEG', 'leg': 'LEG', 'sub': 'LEG', 'subs': 'LEG', 'subbed': 'LEG',

            # Inglês
            'ingles': 'EN', 'english': 'EN', 'ing': 'EN', 'eng': 'EN',

            # Espanhol
            'espanhol': 'ES', 'spanish': 'ES', 'esp': 'ES', 'lat': 'LAT',

            # Francês
            'frances': 'FR', 'french': 'FR', 'fre': 'FR',

            # Japonês
            'japones': 'JP', 'japanese': 'JP', 'jpn': 'JP',

            # Italiano
            'italiano': 'IT', 'italian': 'IT', 'ita': 'IT',

            # Alemão
            'aleman': 'DE', 'german': 'DE', 'ger': 'DE',

            # Polonês
            'pl': 'PL', 'polish': 'PL', 'plsub': 'PL', 'napisy pl': 'PL',

            # Russo
            'russo': 'RU', 'russian': 'RU', 'rus': 'RU', 'mvo': 'RU', 'закадры': 'RU',
        }

        for termo, sigla in mapa_idiomas.items():
            if termo in titulo_lower:
                idiomas.add(sigla)
            if extras and any(termo in x.lower() for x in extras):
                idiomas.add(sigla)
            if provider and termo in provider.lower():
                idiomas.add(sigla)

        # Normalização: se detectar PT-BR e EN juntos → vira DUAL
        if 'PT-BR' in idiomas and 'EN' in idiomas:
            idiomas.discard('PT-BR')
            idiomas.discard('EN')
            idiomas.add('DUAL')

        # --------- FONTES LOCAIS EM 'DUAL' FICAM PT-BR/EN ----------
        if provider and 'local' in provider.lower():
            if 'DUAL' in idiomas or ('PT-BR' in idiomas and 'EN' in idiomas):
                return 'PT-BR / EN'

        resultado = ' / '.join(sorted(idiomas)) or 'N/A'
        return resultado

    # ======================================================================
    # == BLOCO DAS FONTES LOCAIS (JSON) ==
    # ======================================================================
    fontes_locais_raw = item_data.get('streams', [])
    if fontes_locais_raw:
        for stream in fontes_locais_raw:
            is_torrent = "elementum" in stream.get('url', '') or stream.get('server_name', '').upper() == 'TORRENT'
            stream_type = 'Torrent' if is_torrent else 'Direto'
            provider = stream.get('server_name', 'Fonte Local')

            titulo_local = f"{item_data.get('title')} {stream.get('quality', '')} {' '.join(stream.get('extras', []))}"
            languages = extrair_idiomas_do_titulo(titulo_local, stream.get('extras', []), provider)

            local_streams.append({
                'url': stream.get('url'), 'quality': stream.get('quality', 'N/A'),
                'type': stream_type, 'release_title': item_data.get('title'),
                'size': 'N/A', 'peers': 'N/A', 'seeders': 'N/A', 'provider': provider,
                'languages': languages
            })

    # ======================================================================
    # == BLOCO DE BUSCA PARALELA NOS PROVEDORES ==
    # ======================================================================
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
    threads = []
    lock = threading.Lock()

    def fetch_sources(provider_name, provider_data):
        provider_url = provider_data['url']
        is_configurable = provider_data['configurable']

        streams = scraper.scrape_provider_sources(
            provider_url, imdb_id, is_configurable,
            media_type, season, episode
        )
        if streams:
            with lock:
                for stream in streams:
                    stream['provider_name'] = provider_name
                provider_streams_to_process.extend(streams)

    for name, data in PROVIDERS.items():
        setting_id = f"provider.{name.lower()}.enabled"
        if ADDON.getSettingBool(setting_id):
            thread = threading.Thread(target=fetch_sources, args=(name, data))
            threads.append(thread)
            thread.start()

    for thread in threads:
        thread.join()
    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')

    # ======================================================================
    # == PROCESSAMENTO DAS FONTES DOS PROVEDORES ==
    # ======================================================================
    provider_streams_formatted = []
    if provider_streams_to_process:
        seen_urls = {stream['url'] for stream in local_streams}

        for stream in provider_streams_to_process:
            url_fonte = stream.get('url') or stream.get('infoHash')
            if not url_fonte or url_fonte in seen_urls:
                continue
            seen_urls.add(url_fonte)

            full_title = stream.get('title', 'Título desconhecido')
            release_title = full_title.split('\n')[0]

            size_str, peers, seeders, real_provider = "N/A", "0", "0", stream.get('provider_name', 'N/A')

            info_line_match = re.search(r'👤\s*([\d,]+)\s*💾\s*(.*?)\s*⚙️\s*(.*)', full_title)
            if info_line_match:
                peers = info_line_match.group(1).replace(',', '').strip()
                size_str = info_line_match.group(2).strip()
                real_provider = info_line_match.group(3).strip()
                real_provider = re.sub(r'[\U0001F1E6-\U0001F1FF]+$', '', real_provider).strip()
                seeders = peers

            quality_match = re.search(r'(4K|2160p|1080p|720p)', release_title, re.IGNORECASE)
            quality = quality_match.group(1).upper() if quality_match else 'HD'

            languages = extrair_idiomas_do_titulo(release_title, stream.get('extras', []), stream.get('provider_name', ''))

            hints = stream.get('behaviorHints', {})
            api_langs = hints.get('videoLanguages', [])
            if api_langs:
                languages_str_api = ' / '.join([lang.upper() for lang in api_langs])
                if languages != 'N/A' and languages not in languages_str_api:
                    languages = f"{languages} / {languages_str_api}"
                else:
                    languages = languages_str_api

            provider_streams_formatted.append({
                'url': url_fonte, 'quality': quality, 'type': 'Torrent',
                'release_title': release_title, 'size': size_str, 'peers': peers,
                'seeders': seeders, 'provider': real_provider, 'languages': languages
            })

    # ======================================================================
    # == BLOCO FINAL (ORDENAÇÃO, JUNÇÃO E EXIBIÇÃO) ==
    # ======================================================================

    # 1. Ordena APENAS a lista de fontes dos provedores
    provider_streams_formatted.sort(key=lambda x: int(x['seeders']) if str(x.get('seeders')).isdigit() else 0, reverse=True)

    # 2. Junta as listas, colocando as locais PRIMEIRO
    final_streams = local_streams + provider_streams_formatted

    if not final_streams:
        xbmcgui.Dialog().ok("Aviso", "Nenhuma fonte foi encontrada.")
        return
        
        
    url_escolhida = None


    if autoplay:
        # Se autoplay for True, pega a primeira URL da lista (que já é a melhor)
        best_source = final_streams[0]
        url_escolhida = best_source.get('url')
        xbmc.log(f"[Cineroom] Autoplay: selecionando a melhor fonte: {url_escolhida}", xbmc.LOGINFO)
    else:    

        # 3. Exibe o diálogo com a lista final e ordenada
        try:
            xml_filename = 'dialog_cineroom_fullscreen.xml'
            addon_path = ADDON.getAddonInfo('path')
            dialog = DialogSelecaoFontes(xml_filename, addon_path, fontes=final_streams, item_data=item_data)
            dialog.doModal()
            url_escolhida = dialog.escolha
            del dialog
        except Exception as e:
            xbmc.log(f"Erro ao mostrar dialog fullscreen: {e}", xbmc.LOGERROR)
            return

    if url_escolhida:
        time.sleep(1)
        play_url(url_escolhida, item_data)


def play_url(url, item_info):
    """
    Função CORRIGIDA para reproduzir uma URL usando o método nativo do Kodi,
    que é mais estável e evita race conditions.
    """
    if not url:
        xbmc.log("[Cineroom] Tentativa de tocar uma URL vazia.", xbmc.LOGWARNING)
        return

    # A lógica de montar a URL do Elementum está perfeita.
    if url.startswith('magnet:'):
        # Para setResolvedUrl, o infoHash não precisa do prefixo magnet:.
        # O Elementum espera a URL completa.
        url_para_tocar = f"plugin://plugin.video.elementum/play?uri={quote_plus(url)}"
    else:
        url_para_tocar = url

    xbmc.log(f"[Cineroom] Preparando para resolver URL com setResolvedUrl: {url_para_tocar}", xbmc.LOGINFO)

    # Criando o ListItem com todos os metadados ricos.
    play_item = xbmcgui.ListItem(path=url_para_tocar)

    info_labels = {
        'title': item_info.get('title', 'Playback'),
        'plot': item_info.get('plot', item_info.get('overview', '')),
        'year': item_info.get('year'),
        'genre': " / ".join(item_info.get('genres', [])),
        'duration': int(item_info.get('runtime', 0)) * 60,
        'mediatype': 'movie'
    }
    play_item.setInfo('video', info_labels)
    
    # Esta é a mudança crucial.
    # Obtemos o 'handle' do plugin que foi passado quando o script iniciou.
    # E dizemos ao Kodi: "este script terminou, aqui está o link final para você tocar".
    try:
        handle = int(sys.argv[1])
        xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=play_item)
    except (IndexError, ValueError) as e:
        # Se não for possível obter o handle (ex: script rodado de forma diferente),
        # usamos o método antigo como um fallback, embora seja menos estável.
        xbmc.log(f"[Cineroom] Não foi possível usar setResolvedUrl ({e}), usando player como fallback.", xbmc.LOGWARNING)
        xbmc.Player().play(item=url_para_tocar, listitem=play_item)

        
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