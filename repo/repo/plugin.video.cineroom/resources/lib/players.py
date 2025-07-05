import sys
import os
import subprocess
import xbmc
import xbmcgui
import xbmcplugin
import re
import xbmcaddon
import re
from datetime import datetime
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote_plus
from datetime import datetime
from urllib.parse import quote
from resources.lib.elementum_rajada import play_elementum, is_elementum_installed, process_elementum_choice

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
MEDIA_PATH = os.path.join(ADDON_PATH, 'resources', 'media')
HANDLE = int(sys.argv[1])

def adicionar_trackers(magnet_link):
    """
    Adiciona trackers públicos ao final de um link magnet.
    """
    trackers = [
        "udp://tracker.openbittorrent.com:80/announce",
        "udp://tracker.trackerfix.com:83/announce",
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://tracker.trackerfix.com:80/announce",
        "udp://tracker.coppersurfer.tk:6969/announce",
        "udp://tracker.leechers-paradise.org:6969/announce",
        "udp://eddie4.nl:6969/announce",
        "udp://p4p.arenabg.com:1337/announce",
        "udp://explodie.org:6969/announce",
        "udp://zer0day.ch:1337/announce",
        "udp://glotorrents.pw:6969/announce",
        "udp://torrent.gresille.org:80/announce",
        "udp://p4p.arenabg.ch:1337",
        "udp://tracker.internetwarriors.net:1337",
        "http://tracker.opentrackr.org:1337/announce",
        "udp://open.stealth.si:80/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.cyberia.is:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.birkenwald.de:6969/announce",
        "udp://tracker.moeking.me:6969/announce",
        "udp://ipv4.tracker.harry.lu:80/announce",
        "udp://tracker.tiny-vps.com:6969/announce"
    ]

    for tracker in trackers:
        encoded = quote(tracker, safe='')
        if encoded not in magnet_link:
            magnet_link += f"&tr={encoded}"
    return magnet_link

def get_player_choice(path):
    # Se a plataforma for Android, SEMPRE reproduz automaticamente no player padrão do Kodi
    if xbmc.getCondVisibility("System.Platform.Android"):
        return "kodi", path
    
    # Para outras plataformas (NÃO Android), mantém a lógica de escolha de player
    dialog = xbmcgui.Dialog()
    players = []

    # Se o link for do tipo 'workers.dev', priorize o Kodi Player
    if "workers.dev/download.aspx" in path:
        players.append(("Player Padrão (Kodi) - Recomendado", "kodi"))

    # Adiciona VLC para Windows se disponível
    if xbmc.getCondVisibility("System.Platform.Windows"):
        vlc_path = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
        if not os.path.exists(vlc_path):
            vlc_path = r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
        if os.path.exists(vlc_path):
            players.append(("VLC", "vlc"))

    # Adicione o Player Padrão se não for a primeira opção já (para não-Android)
    if not any(p[1] == "kodi" for p in players):
        players.append(("Player Padrão (Kodi)", "kodi"))

    # Exibe o diálogo de escolha para o usuário (APENAS se não for Android)
    choices = [player[0] for player in players]
    index = dialog.select("Escolha o player", choices)

    if index == -1:
        return None, None

    return players[index][1], path

def play_with_vlc(path):
    vlc_path = r"C:\Program Files\VideoLAN\VLC\vlc.exe"
    if not os.path.exists(vlc_path):
        vlc_path = r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
    if os.path.exists(vlc_path):
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        command = [vlc_path, "--http-user-agent", user_agent, path]
        try:
            subprocess.Popen(command, shell=False)
            xbmc.log(f"Comando VLC executado: {command}", xbmc.LOGINFO)
        except Exception as e:
            xbmcgui.Dialog().ok("Erro", f"Falha ao abrir no VLC: {str(e)}")
            xbmc.log(f"Erro ao executar VLC: {str(e)}", xbmc.LOGERROR)
    else:
        xbmcgui.Dialog().ok("Erro", "VLC não encontrado. Por favor, instale o VLC.")

def play_with_resolveurl(path):
    try:
        import resolveurl as urlresolver
    except ImportError:
        xbmcgui.Dialog().ok("Erro", "ResolveURL não está instalado.")
        xbmc.log("ResolveURL não encontrado", xbmc.LOGERROR)
        return

    resolved = urlresolver.resolve(path)
    if resolved:
        play_item = xbmcgui.ListItem(path=resolved)
        xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)
        xbmc.log(f"Reproduzido com ResolveURL: {resolved}", xbmc.LOGINFO)
    else:
        xbmcgui.Dialog().ok("Erro", "Não foi possível resolver o link.")
        xbmc.log(f"ResolveURL falhou: {path}", xbmc.LOGERROR)

def play_with_kodi(path):
    play_item = xbmcgui.ListItem(path=path)
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)
    xbmc.log(f"Reproduzindo no player do Kodi: {path}", xbmc.LOGINFO)

def clean_url(url):
    """
    Remove qualquer texto entre parênteses e o próprio parêntese da URL.
    Exemplo: https://example.com/video(DUAL AUDIO) -> https://example.com/video
    """
    print(f"URL antes da limpeza: {url}")
    cleaned_url = re.sub(r"\([^)]*\)", "", url)
    print(f"URL depois da limpeza: {cleaned_url}")
    return cleaned_url

def select_source(paths, movie_poster=None, movie_synopsis=None):
    """Exibe diálogo padrão do Kodi para seleção da fonte de reprodução"""
    dialog = xbmcgui.Dialog()
    items = []

    for path in paths:
        if path == "search_sources":
            label = "[COLOR gold]BUSCAR FONTES[/COLOR]"
        else:
            source_type = 'TORRENT' if 'magnet:?xt=urn:btih:' in path else 'LINK DIRETO'
            extra_info = extract_extra_info(path) if 'extract_extra_info' in globals() else ''
            label = f"{source_type}{extra_info}"

        items.append(label)

    ret = dialog.select("Escolha uma fonte para assistir", items)
    return paths[ret] if ret != -1 else None

    
def get_jacktook_search_link(is_movie=True, title='', tmdb_id='', tvdb_id='None', imdb_id='', season=None, episode=None, showname=''):
    import urllib.parse
    import json

    ids = {
        "tmdb_id": tmdb_id or "",
        "tvdb_id": tvdb_id or "",
        "imdb_id": imdb_id or ""
    }
    ids_str = urllib.parse.quote(json.dumps(ids))

    if is_movie:
        query = urllib.parse.quote(title.strip())
        return f"plugin://plugin.video.jacktook/?action=search&mode=movies&rescrape=True&query={query}&ids={ids_str}"
    else:
        query = urllib.parse.quote(showname.strip() or title.strip())
        tv_data = {
            "name": title.strip(),
            "episode": str(episode or ""),
            "season": str(season or "")
        }
        tv_data_str = urllib.parse.quote(json.dumps(tv_data))
        return (
            f"plugin://plugin.video.jacktook/?action=search&mode=tv&rescrape=True&query={query}"
            f"&ids={ids_str}&tv_data={tv_data_str}"
        )


def is_jacktook_installed():
    return xbmc.getCondVisibility('System.HasAddon(plugin.video.jacktook)') == 1

def play_video(paths, title='', tmdb_id='', tvdb_id='', imdb_id='', year=None, movie_poster='', movie_synopsis='', 
               season=None, episode=None, showname=''):
    try:
        if not paths:
            raise ValueError("Nenhum path fornecido para reprodução")

        paths = [paths] if isinstance(paths, str) else list(paths)

        # Adiciona opção única de pesquisa
        if tmdb_id or title:
            paths.append("search_sources")

        selected_path = select_source(paths, movie_poster=movie_poster, movie_synopsis=movie_synopsis)
        if not selected_path:
            return False

        selected_path = clean_url(selected_path)

        if selected_path == "search_sources":
            provider = ADDON.getSetting('default_search_provider')
            if provider == "0":  # Elementum
                result = handle_elementum_playback(tmdb_id, title, year)
            else:  # JackTook
                if not is_jacktook_installed():
                    xbmcgui.Dialog().notification(
                        "JackTook não instalado",
                        "Instale o plugin JackTook para usar esta função.",
                        xbmcgui.NOTIFICATION_ERROR
                    )
                    return False

                is_movie = episode is None
                search_link = get_jacktook_search_link(
                    is_movie=is_movie,
                    title=title,
                    tmdb_id=tmdb_id,
                    tvdb_id=tvdb_id,
                    imdb_id=imdb_id,
                    season=season,
                    episode=episode,
                    showname=showname
                )
                if search_link:
                    play_with_kodi(search_link)
                    result = True
                else:
                    result = False

        elif selected_path.startswith("plugin://plugin.video.elementum"):
            result = handle_elementum_link(selected_path)
        else:
            result = handle_standard_playback(selected_path)

        xbmc.executebuiltin('Container.Update')
        return result

    except Exception as e:
        xbmc.log(f"Erro ao reproduzir vídeo: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().notification("Erro", "Falha ao reproduzir o conteúdo", xbmcgui.NOTIFICATION_ERROR)
        return False
    finally:
        xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)




def extract_extra_info(path):
    """Extrai informações adicionais entre parênteses no path."""
    match = re.search(r'\s*\(([^)]+)\)\s*$', path)
    return f" - {match.group(1)}" if match else ""

def handle_elementum_playback(tmdb_id, title, year):
    """Lida com a reprodução via Elementum (busca ou play direto)."""
    if not is_elementum_installed():
        xbmcgui.Dialog().notification('Elementum não instalado', 'Instale o Elementum para continuar.', xbmcgui.NOTIFICATION_ERROR)
        return

    if tmdb_id:
        play_elementum(tmdb_id, title)
    else:
        show_elementum_burst_search_from_title(title, year)

def handle_elementum_link(path):
    """Processa links do Elementum, adicionando trackers a magnet links e limpando links HTTPS com parênteses e 'DUAL AUDIO'."""
    parsed = urlparse(path)
    query = parse_qs(parsed.query)
    uri = query.get('uri', [''])[0]
    
    # Limpa os parênteses e "DUAL AUDIO" do link HTTPS e também dos magnet links
    uri = re.sub(r'\s*\([^)]*\)\s*$', '', uri)
    uri = re.sub(r'\s*\(.*DUAL AUDIO.*\)\s*$', '', uri)
    uri = re.sub(r'%28DUAL%20AUDIO%29', '', uri)
    
    if uri.startswith("magnet:?"):
        uri = adicionar_trackers(uri)
        query['uri'] = [uri]
        new_query = urlencode(query, doseq=True)
        path = urlunparse(parsed._replace(query=new_query))

    xbmc.log(f"URL após limpeza: {uri}", xbmc.LOGINFO)
    play_with_kodi(path)

def handle_standard_playback(path):
    """Lida com reprodução padrão (URLs ou paths locais)."""
    if path.startswith(('http://', 'https://')):
        player, _ = get_player_choice(path)
        if not player:
            return

        if player == "vlc":
            play_with_vlc(path)
        elif player == "resolveurl":
            play_with_resolveurl(path)
        else: # player == "kodi"
            if "workers.dev/download.aspx" in path:
                pDialog = xbmcgui.DialogProgressBG()
                pDialog.create("Conectando ao Servidor", "Aguarde, preparando o stream de vídeo...")
                play_with_kodi(path)
                time.sleep(5)
                pDialog.close()
            else:
                play_with_kodi(path)
    else:
        play_with_kodi(path)