
# -*- coding: utf-8 -*-
import sys
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
import json
import re
from .db import db
from .utils import create_video_item
from . import scrapers
from .dialogs import DialogSelecaoFontes
from .resolver import CineroomResolverWindow
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
    

    for item in menu_structure:

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

def show_my_list_menu():
    xbmcplugin.setPluginCategory(HANDLE, "Minha Lista")
    xbmcplugin.setContent(HANDLE, 'folder')

    items = [
        ("Filmes", get_url(action="favorites_movies")),
        ("Séries", get_url(action="favorites_tvshows"))
    ]

    for label, url in items:
        li = xbmcgui.ListItem(label=label)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def show_favorite_movies():
    xbmcplugin.setPluginCategory(HANDLE, "Minha Lista • Filmes")
    xbmcplugin.setContent(HANDLE, 'movies')

    favorites = db.get_favorites_by_type('movie')

    for item in favorites:
        li = create_video_item(item, 'movie')
        url = get_url(
            action='find_sources',
            media_type='movie',
            tmdb_id=item['tmdb_id'],
            imdb_id=item.get('imdb_id'),
            title=item.get('title'),
            year=item.get('year'),
            original_title=item.get('original_title', ''),
            clearlogo=item.get('clearlogo', ''),
            fanart=item.get('fanart', ''),
            backdrop=item.get('backdrop', ''),
            poster=item.get('poster', '')
        )
        li.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)

def show_favorite_tvshows():
    xbmcplugin.setPluginCategory(HANDLE, "Minha Lista • Séries")
    xbmcplugin.setContent(HANDLE, 'tvshows')

    favorites = db.get_favorites_by_type('tvshow')

    for item in favorites:
        li = create_video_item(item, 'tvshow')
        url = get_url(
            action='list_seasons',
            tvshow_tmdb_id=item['tmdb_id']
        )
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


def search(query=None, page=1):
    page = int(page)
    PAGE_SIZE = 20
    offset = (page - 1) * PAGE_SIZE

    # 1. Input de busca
    if not query:
        keyboard = xbmc.Keyboard('', 'Pesquisar Filme ou Série')
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            query = keyboard.getText().strip()
        else:
            return

    if not query:
        return

    xbmcplugin.setPluginCategory(HANDLE, f'Pesquisando: {query}')
    xbmcplugin.setContent(HANDLE, 'movies')

    from .tmdb_api import search_tmdb
    from .movies import _create_movie_item_tuple
    from .tvshows import _create_show_tuple
    from .db import db

    items = []
    used_tmdb_ids = set()

    # 2. BUSCA LOCAL (sem quebrar assinatura)
    try:
        local_results = db.search_items(query)
    except Exception as e:
        xbmc.log(f"[Cineroom] Erro search local: {e}", xbmc.LOGERROR)
        local_results = []

    # paginação manual local
    local_page = local_results[offset: offset + PAGE_SIZE]

    for item in local_page:
        tmdb_id = item.get('tmdb_id')
        if tmdb_id:
            used_tmdb_ids.add(str(tmdb_id))

        if item.get('media_type') == 'movie':
            items.append(_create_movie_item_tuple(item))
        else:
            items.append(_create_show_tuple(item))

    # 3. BUSCA TMDB (complementar)
    tmdb_results = search_tmdb(query, page=page) or []

    for item in tmdb_results:
        tmdb_id = str(item.get('id'))
        if tmdb_id in used_tmdb_ids:
            continue

        if item.get('media_type') == 'movie':
            items.append(_create_movie_item_tuple(item))
        else:
            items.append(_create_show_tuple(item))

    if not items:
        xbmcgui.Dialog().notification("Busca", f'Nada encontrado para "{query}"')
        xbmcplugin.endOfDirectory(HANDLE)
        return

    xbmcplugin.addDirectoryItems(HANDLE, items, len(items))

    # 4. Próxima página
    if len(items) >= PAGE_SIZE:
        next_url = get_url(
            action='search',
            query=query,
            page=page + 1
        )
        li = xbmcgui.ListItem(label='[COLOR yellow]Próxima Página >>[/COLOR]')
        li.setArt({'thumb': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(HANDLE, next_url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)



# --- Providers com Ordem Prioritária ---
PROVIDERS = {
    "Brazuca": {
        "url": "https://94c8cb9f702d-brazuca-torrents.baby-beamup.club",
        "configurable": False,
        "priority": 1  # 🥇 PRIMEIRO - Brazuca
    },
    "AnimeZey": {
        "url": "https://1.animezey23112022.workers.dev", 
        "configurable": False, 
        "priority": 3  # 🥇 PRIMEIRO - AnimeZey
    },
    "CDFlix": {
        "url": "https://cdflix.cdteam.xyz/%7B%22language%22%3A%22pt_br%22%7D",
        "configurable": False,
        "priority": 1  # 🥈 SEGUNDO - CDFlix
    },
    "SkyFlix": {
        "url": "https://da5f663b4690-skyflixfork16.baby-beamup.club",
        "configurable": False, 
        "priority": 1  # 🥈 SEGUNDO - SkyFlix
    },
    "Torrentio": {
        "url": "https://torrentio.strem.fun/providers=comando,bludv,micoleaodublado,yts,nyaasi,1337x%7Clanguage=portuguese,english,japanese",
        "configurable": False,
        "priority": 2  # 🥈 SEGUNDO - Torrentio
    },
    "ComandoTop": {
        "url": "https://comandofilmestop.site",
        "configurable": False,
        "priority": 3  # 🥉 TERCEIRO - ComandoTop
    },
    "ApacheTorrent": {
        "url": "https://apachetorrent.com",
        "configurable": False,
        "priority": 3  # 🥉 TERCEIRO - ApacheTorrent
    },
    "Filmesmaster": {
        "url": "https://filmesmaster.org/",
        "configurable": False,
        "priority": 4  # QUARTO - Filmesmaster
    },
    "Mico-Leão": {
        "url": "https://27a5b2bfe3c0-stremio-brazilian-addon.baby-beamup.club",
        "configurable": False,
        "priority": 5  
    }
}





# --- 1. FUNÇÕES DE SUPORTE (DEVEM VIR ANTES) ---

def extrair_idiomas_do_titulo(titulo, extras=None, provider=None):
    # 1. Tratamento para Provedores 100% Brasileiros (SkyFlix, Brazuca, CDFlix, etc)
    # Se o provedor for um desses, não importa o nome, marcamos como PT-BR
    provedores_br = ['SkyFlix', 'Brazuca', 'CDFlix', 'ComandoTop', 'Mico-Leão', 'AnimeZey', 'Fonte Local']
    if provider in provedores_br:
        # Se mesmo sendo BR ele detectar "Dual" no título, marcamos DUAL
        if titulo and any(x in titulo.lower() for x in ['dual', 'multi']):
            return 'DUAL'
        return 'PT-BR'

    if not titulo: return 'LEG'
    t = titulo.lower()
    
    # 2. Detecção de DUAL (Prioridade antes do LEG)
    if any(x in t for x in ['dual', 'multi', 'dublado', 'dub', 'portugues', 'pt-br', ' pt ']):
        if 'dual' in t or 'multi' in t:
            return 'DUAL'
        return 'PT-BR'
    
    # 3. Detecção de LEG
    # Se tiver termos de legenda ou se for de um provedor internacional (Torrentio)
    # e não caiu na regra de dublagem acima, marcamos como LEG.
    if any(x in t for x in ['legendado', 'leg', 'sub', 'subs', 'subtitled', 'eng', 'english', 'original']):
        return 'LEG'
    
    # 4. Fallback: Padrão para Torrentio/Internacionais sem info de dublagem
    return 'LEG'

def get_color_seeders(val, stream_type):
    if stream_type == 'Direto' or val == 999:
        return "[COLOR cyan]LINK DIRETO[/COLOR]", 999
    try:
        v = int(val)
        color = "green" if v >= 10 else ("yellow" if v >= 5 else "red")
        return f"[COLOR {color}]{v}[/COLOR]", v
    except:
        return "[COLOR grey]S:0[/COLOR]", 0

def get_color_quality(q):
    q = q.upper()
    if '4K' in q or '2160P' in q: return f"[COLOR gold]{q}[/COLOR]", 4
    if '1080P' in q: return f"[COLOR blue]{q}[/COLOR]", 3
    if '720P' in q: return f"[COLOR orange]{q}[/COLOR]", 2
    return f"[COLOR grey]{q}[/COLOR]", 1

def extrair_codec_hdr(raw_title):
    t = raw_title.lower()

    source = ""
    if any(x in t for x in ['web-dl', 'webdl', 'webrip']):
        source = "web-dl"
    elif any(x in t for x in ['bluray', 'blu-ray', 'bdrip', 'bdremux']):
        source = "bluray"
    elif 'hdrip' in t:
        source = "hdrip"
    elif 'dvdrip' in t:
        source = "dvdrip"
    elif '3d' in t:
        source = "3d"
    elif 'cam' in t:
        source = "cam"
    elif re.search(r'\bts\b', t):
        source = "ts"

    codec = ""
    if any(x in t for x in ('h265', 'x265', 'hevc')):
        codec = "HEVC"
    elif any(x in t for x in ('h264', 'x264', 'avc')):
        codec = "AVC"

    hdr = ""
    if 'hdr' in t:
        hdr = "HDR"
    elif '10bit' in t or '10-bit' in t:
        hdr = "10bit"

    return codec, hdr, source



def extrair_audio(raw_title):
    t = raw_title.lower()

    canais = ""
    if re.search(r'7[\.\s]?1', t):
        canais = "7.1"
    elif re.search(r'5[\.\s]?1', t):
        canais = "5.1"
    elif re.search(r'2[\.\s]?0', t):
        canais = "2.0"

    codec = ""
    if 'atmos' in t:
        codec = "Atmos"
    elif 'truehd' in t:
        codec = "TrueHD"
    elif 'dts-hd' in t or 'dtshd' in t:
        codec = "DTS-HD"
    elif 'dts' in t:
        codec = "DTS"
    elif 'eac3' in t or 'dd+' in t:
        codec = "DD+"
    elif 'ac3' in t:
        codec = "AC3"
    elif 'aac' in t:
        codec = "AAC"

    return " ".join(x for x in (codec, canais) if x)


# --- 2. FUNÇÃO PRINCIPAL ---

def find_and_play_sources(item_data, autoplay=False, season=None, episode=None):
    import time

    media_type = item_data.get('media_type')
    imdb_id = item_data.get('imdb_id')

    if not media_type:
        xbmcgui.Dialog().ok("Erro", "Dados insuficientes.")
        return

    # ==========================================================
    # 1. PROCESSAMENTO DE STREAM (INALTERADO)
    # ==========================================================
    def process_single_stream(stream, is_local=False, p_name='Fonte Local', p_priority=999):
        url = stream.get('url') or stream.get('infoHash')
        if not url:
            return None

        # ✅ AGORA USAMOS O NOME REAL DO ARQUIVO COMO DISPLAY TITLE
        raw_title = stream.get('title') or stream.get('name') or ""
    
        # Limpa o título para remover informações redundantes
        # Remove o que já vamos mostrar separadamente (seeders, size, etc.)
        display_title = raw_title
    
        # Remove tags de seeders/peers se existirem
        display_title = re.sub(r'👤\s*\d+', '', display_title)
        display_title = re.sub(r'S:\s*\d+', '', display_title)
    
        # Remove tags de tamanho entre colchetes
        display_title = re.sub(r'\[\s*\d+\.?\d*\s*(?:GB|MB)\s*\]', '', display_title, flags=re.IGNORECASE)
    
        # Remove provedor se estiver no final com emoji ⚙️
        display_title = re.sub(r'⚙️\s*[^\n]+$', '', display_title)
    
        # Limpa espaços extras e caracteres de nova linha
        display_title = ' '.join(display_title.split()).strip()
    
        # Se ainda estiver muito longo, trunca
        if len(display_title) > 80:
            display_title = display_title[:77] + '...'
    
        # Fallback se ficar vazio
        if not display_title:
            nome_base = item_data.get('title') or 'Vídeo'
            ano = item_data.get('year') or ''
            if item_data.get('season') and item_data.get('episode'):
                s = str(item_data['season']).zfill(2)
                e = str(item_data['episode']).zfill(2)
                display_title = f"{nome_base} S{s}E{e}"
            else:
                display_title = f"{nome_base} ({ano})" if ano else nome_base

        # Resto do processamento permanece igual...
        if is_local:
            is_torrent = "elementum" in url or stream.get('server_name', '').upper() == 'TORRENT'
            stype = 'Torrent' if is_torrent else 'Direto'
        else:
            stype = stream.get('type', 'Direto')
            if re.match(r'^[a-fA-F0-9]{40}$', url) or url.startswith('magnet:'):
                stype = 'Torrent'

        seed_match = re.search(r'(?:👤|S:)\s*(\d+)', raw_title)
        s_val = seed_match.group(1) if seed_match else stream.get('seeders', 0)
        if stype == 'Direto':
            s_val = 999

        size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', raw_title, re.IGNORECASE)
        size_str = size_match.group(1) if size_match else stream.get('size', 'N/A')

        q_match = re.search(r'(4K|2160p|1080p|720p)', raw_title, re.IGNORECASE)
        q_str = q_match.group(1).upper() if q_match else str(stream.get('quality', 'HD')).upper()

        codec, hdr, source = extrair_codec_hdr(raw_title)
        audio = extrair_audio(raw_title)
    
        video_info = " ".join(x for x in (codec, hdr, audio) if x)

        seed_label, seed_score = get_color_seeders(s_val, stype)
        qual_label, qual_score = get_color_quality(q_str)

        return {
            'url': url,
            # ✅ AGORA É O NOME REAL DO ARQUIVO
            'display_title': display_title,
            # Guarda o título original também para referência
            'raw_title': raw_title,

            # UI
            'quality_label': qual_label,
            'seeders_label': seed_label,
            'size': size_str,
            'provider': p_name,
            'languages': extrair_idiomas_do_titulo(
                raw_title, stream.get('extras', []), p_name
            ),

            # PNG PROPERTIES
            'codec': codec.lower() if codec else '',
            'hdr': hdr.lower() if hdr else '',
            'audio': audio.lower() if audio else '',
            'source': source,

            # fallback texto
            'video_info': video_info,

            # ordenação
            'p_priority': p_priority,
            'q_score': qual_score,
            's_score': int(s_val)
        }

    # ==========================================================
    # 2. BUSY DIALOG + THREADS INTELIGENTE
    # ==========================================================
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')

    provider_results = {}
    completed = 0
    lock = threading.Lock()

    start_time = time.time()
    pDialog = None

    def fetch_thread(name, data):
        nonlocal completed
        try:
            found = scrapers.scrape_provider_sources(name, data, item_data)
            if found:
                with lock:
                    provider_results[name] = found
        except:
            pass
        finally:
            with lock:
                completed += 1

    active_providers = [
        (n, d) for n, d in PROVIDERS.items()
        if ADDON.getSettingBool(f"provider.{n.lower()}.enabled")
    ]

    threads = []
    total_threads = len(active_providers)
    

    for name, data in active_providers:
        if name != 'AnimeZey' and not imdb_id:
            with lock:
                completed += 1
            continue

        t = threading.Thread(target=fetch_thread, args=(name, data))
        t.start()
        threads.append(t)

    # Loop de monitoramento
    while completed < total_threads:
        elapsed = time.time() - start_time

        # Cria progress BG apenas se demorar
        if elapsed > 0.7 and not pDialog:
            pDialog = xbmcgui.DialogProgressBG()
            pDialog.create("CR [COLOR cyan]Lite[/COLOR]", "Buscando fontes...")

        if pDialog:
            percent = int((completed / total_threads) * 100)
            pDialog.update(
                percent,
                message=f"Consultando providers ({completed}/{total_threads})"
            )

        xbmc.sleep(100)

    for t in threads:
        t.join()

    if pDialog:
        pDialog.close()

    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')

    # ==========================================================
    # 3. CONSOLIDAÇÃO (INALTERADO)
    # ==========================================================
    final_list = []
    seen_urls = set()

    for s in item_data.get('streams', []):
        p = process_single_stream(s, is_local=True)
        if p:
            final_list.append(p)
            seen_urls.add(p['url'])

    for name, data in active_providers:
        if name in provider_results:
            for s in provider_results[name]:
                p = process_single_stream(s, False, name, data.get('priority', 999))
                if p and p['url'] not in seen_urls:
                    final_list.append(p)
                    seen_urls.add(p['url'])

    if not final_list:
        xbmcgui.Dialog().ok("Aviso", "Nenhuma fonte encontrada.")
        return

    final_list.sort(key=lambda x: (x['p_priority'], -x['q_score'], -x['s_score']))

    # ==========================================================
    # 4. DIÁLOGO / AUTOPLAY (INALTERADO)
    # ==========================================================
    url_escolhida = None

    if ADDON.getSettingBool('playback.autoplay'):
        url_escolhida = final_list[0]['url']
    else:
        labels = [
            f"{s['quality_label']} | {s['seeders_label']} | {s['size']} | {s['provider']}"
            for s in final_list
        ]

        try:
            from resources.lib.dialogs import DialogSelecaoFontes
            dialog = DialogSelecaoFontes(
                'dialog_cineroom_fullscreen.xml',
                ADDON.getAddonInfo('path'),
                fontes=final_list,
                item_data=item_data
            )
            dialog.doModal()
            url_escolhida = dialog.escolha
            del dialog
        except:
            sel = xbmcgui.Dialog().select(
                f"Fontes: {final_list[0]['display_title']}", labels
            )
            if sel >= 0:
                url_escolhida = final_list[sel]['url']

    # ==========================================================
    # 5. RESOLVER
    # ==========================================================
    if url_escolhida:
        resolver = CineroomResolverWindow(
            "resolver_window.xml",
            ADDON.getAddonInfo('path'),
            source_url=url_escolhida,
            item_data=item_data,
            handle=int(sys.argv[1])
        )
        resolver.doModal()


def play_url(url, item_info):
    """
    Função para reproduzir uma URL, tratando Torrents (Elementum) com seleção
    automática de episódio e links diretos com headers (AnimeZey).
    """
    if not url:
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
    
    # --- ✅ 6. SCROBBLE AUTOMÁTICO TRAKT ---
    if ADDON.getSettingBool('trakt_auto_scrobble'):
        threading.Thread(
            target=_delayed_trakt_scrobble,
            args=(item_info,),
            daemon=True
        ).start()


def play_url(url, item_info):
    """
    Função para reproduzir uma URL, tratando Torrents (Elementum) com seleção
    automática de episódio e links diretos com headers (AnimeZey).
    """
    if not url:
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
    
    # --- ✅ 6. SCROBBLE AUTOMÁTICO TRAKT ---
    if ADDON.getSettingBool('trakt_auto_scrobble'):
        threading.Thread(
            target=_delayed_trakt_scrobble,
            args=(item_info,),
            daemon=True
        ).start()


def _delayed_trakt_scrobble(item_info):
    """
    Monitora playback e scrobla quando terminar (compatível com Elementum)
    """
    import time
    
    xbmc.log("[Trakt Scrobble] Iniciando monitoramento...", xbmc.LOGINFO)
    
    # Aguarda player iniciar (máx 30s)
    player_started = False
    for i in range(30):
        if xbmc.Player().isPlaying():
            player_started = True
            xbmc.log(f"[Trakt Scrobble] Player detectado após {i}s", xbmc.LOGINFO)
            break
        time.sleep(1)
    
    if not player_started:
        xbmc.log("[Trakt Scrobble] Timeout: player não iniciou em 30s", xbmc.LOGWARNING)
        return
    
    player = xbmc.Player()
    media_type = item_info.get('media_type')
    tmdb_id = item_info.get('tmdb_id')
    
    if not tmdb_id:
        xbmc.log("[Trakt Scrobble] Sem TMDB ID, abortando", xbmc.LOGWARNING)
        return
    
    # Aguarda término do playback
    start_time = time.time()
    total_time = 0
    last_position = 0
    
    try:
        # Monitora enquanto está tocando
        while player.isPlaying():
            try:
                total_time = player.getTotalTime()
                last_position = player.getTime()
            except:
                pass
            time.sleep(5)
        
        # Calcula progresso real
        elapsed = time.time() - start_time
        
        if total_time > 0:
            # Usa a maior posição alcançada
            progress = (max(last_position, elapsed) / total_time) * 100
        else:
            # Fallback: se assistiu mais de 5 minutos, considera válido
            progress = 100 if elapsed > 300 else 0
        
        xbmc.log(f"[Trakt Scrobble] Progresso: {progress:.1f}% (tempo: {elapsed:.0f}s, duração: {total_time:.0f}s)", xbmc.LOGINFO)
        
        # Só marca se assistiu pelo menos 80% OU mais de 15 minutos
        if progress < 80 and elapsed < 900:
            xbmc.log(f"[Trakt Scrobble] Progresso insuficiente ({progress:.0f}%), não marcando", xbmc.LOGINFO)
            return
        
        # Marca como assistido no Trakt
        from resources.lib.trakt_sync import trakt_request
        
        if media_type == 'movie':
            payload = {
                'movies': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'watched_at': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
                }]
            }
            desc = item_info.get('title', 'Filme')
            
        elif media_type == 'tvshow':
            season = item_info.get('season')
            episode = item_info.get('episode')
            
            if not season or not episode:
                xbmc.log("[Trakt Scrobble] Série sem S/E, abortando", xbmc.LOGWARNING)
                return
            
            payload = {
                'shows': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'seasons': [{
                        'number': int(season),
                        'episodes': [{
                            'number': int(episode),
                            'watched_at': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
                        }]
                    }]
                }]
            }
            desc = f"{item_info.get('title', 'Série')} S{str(season).zfill(2)}E{str(episode).zfill(2)}"
        else:
            xbmc.log(f"[Trakt Scrobble] Tipo desconhecido: {media_type}", xbmc.LOGWARNING)
            return
        
        # Envia para Trakt
        response = trakt_request('POST', '/sync/history', payload)
        
        if response:
            xbmc.log(f"[Trakt Scrobble] ✅ Marcado como assistido: {desc}", xbmc.LOGINFO)
            xbmcgui.Dialog().notification("Trakt", f"✅ {desc}", xbmcgui.NOTIFICATION_INFO, 2000)
        else:
            xbmc.log(f"[Trakt Scrobble] ❌ Falha ao marcar: {desc}", xbmc.LOGERROR)
        
    except Exception as e:
        xbmc.log(f"[Trakt Scrobble] Erro durante monitoramento: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)

