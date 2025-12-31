# -*- coding: utf-8 -*-
import xbmcgui
import xbmc
import xbmcplugin
import sys
import threading
import time
from urllib.parse import quote_plus
from typing import Callable, Optional

USER_AGENT = 'Mozilla/50 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# =======================================================
# 1. CLASSE PLAYER PARA LIDAR COM EVENTOS (CALLBACKS)
# =======================================================
class CineroomPlayer(xbmc.Player):
    """Player customizado que chama um callback assim que a reprodução começa."""
    def __init__(self, callback: Callable[[], None]):
        xbmc.Player.__init__(self)
        self.callback = callback

    def onPlayBackStarted(self):
        xbmc.log("[CineroomPlayer] Playback iniciado. Fechando resolvedor...", xbmc.LOGINFO)
        self.callback()


# =======================================================
# 2. CLASSE RESOLVEDOR/LOADING WINDOW
# =======================================================
class CineroomResolverWindow(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_url = kwargs.get('source_url')
        self.item_data = kwargs.get('item_data')
        self.resolved_url = None
        self.handle = kwargs.get('handle', int(sys.argv[1]))
        self.is_torrent_source = False
        self.player: Optional[CineroomPlayer] = None  # Mantém referência do player

        # Propriedades dinâmicas para XML
        self.setProperty("enable_busy_spinner", "true")
        self.setProperty("resolve_status", "Iniciando...")

        if self.item_data:
            self.setProperty("info.title", self.item_data.get('title', 'Resolvendo Fonte...'))
            # definir fanart/backdrop como propriedade da janela
            self.setProperty("info.fanart", self.item_data.get('backdrop', ''))
            self.setProperty("info.poster", self.item_data.get('poster', ''))
            self.setProperty("info.clearlogo", self.item_data.get('clearlogo', ''))

    def onInit(self):
        threading.Thread(target=self.start_resolution_process, daemon=True).start()

    # ---------------------------------------------------
    # Processo principal de resolução
    # ---------------------------------------------------
    def start_resolution_process(self):
        time.sleep(1.5)  # Tempo mínimo de tela
        try:
            self.setProperty("resolve_status", "Buscando informações...")
            xbmc.log(f"[CineroomResolver] Iniciando resolução para URL: {self.source_url[:50]}...", xbmc.LOGINFO)
            final_url, item_info = self.resolve_url_logic(self.source_url, self.item_data)

            self.setProperty("resolve_status", "Resolvendo link...")
            if not final_url:
                raise Exception("Falha ao resolver a URL final.")

            self.resolved_url = final_url
            self.setProperty("resolve_status", "Carregando player...")
            self.play_resolved_source(final_url, item_info)

        except Exception as e:
            self.setProperty("resolve_status", "Erro ao resolver")
            if self.is_torrent_source and self.resolved_url:
                xbmc.log(f"[CineroomResolver] ERRO TORRENT. Fechando silenciosamente: {e}", xbmc.LOGWARNING)
                xbmc.sleep(1000)
                self.close()
            else:
                xbmc.log(f"[CineroomResolver] ERRO CRÍTICO: {e}", xbmc.LOGERROR)
                xbmcgui.Dialog().ok("Erro de Resolução", "Ocorreu um erro ao tentar resolver a fonte de vídeo. Verifique os logs.")
                self.setProperty("enable_busy_spinner", "false")
                time.sleep(1)
                self.close()

    # ---------------------------------------------------
    # Lógica de resolução da URL
    # ---------------------------------------------------
    def resolve_url_logic(self, url, item_info):
        final_url = url
        is_torrent = False

        # --- Torrent / Elementum ---
        if url.startswith('magnet:') or (len(url) == 40 and not url.startswith('http')):
            is_torrent = True
            self.is_torrent_source = True
            magnet_uri = url if url.startswith('magnet:') else f"magnet:?xt=urn:btih:{url}"
            encoded_uri = quote_plus(magnet_uri)
            tmdb_id = item_info.get('tmdb_id')
            media_type = item_info.get('media_type')
            final_url = f"plugin://plugin.video.elementum/play?uri={encoded_uri}"
            if tmdb_id:
                final_url += f"&tmdb={tmdb_id}"
            if media_type == 'tvshow':
                season = item_info.get('season')
                episode = item_info.get('episode')
                if season is not None and episode is not None:
                    final_url += f"&season={season}&episode={episode}"
        else:
            animezey_domains = ['animezey23112022.workers.dev', 'animezey16082023.workers.dev', '1.animezeydl.workers.dev']
            if any(domain in final_url.lower() for domain in animezey_domains):
                xbmc.log("[CineroomResolver] Link AnimeZey detectado.", xbmc.LOGDEBUG)

        return final_url, item_info

    # ---------------------------------------------------
    # Criação do ListItem
    # ---------------------------------------------------
    def _create_listitem(self, final_url, item_info):
        play_item = xbmcgui.ListItem(path=final_url)

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
            'clearlogo': item_info.get('clearlogo') or '',
        })

        animezey_domains = ['animezey23112022.workers.dev', 'animezey16082023.workers.dev', '1.animezeydl.workers.dev']
        if any(domain in final_url.lower() for domain in animezey_domains):
            play_item.setProperty('inputstream', 'inputstream.ffmpegdirect')
            play_item.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
            play_item.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')
            referer_url = final_url.split('?')[0] if "?" in final_url else final_url
            headers_str = f"Referer={referer_url}\r\nUser-Agent={USER_AGENT}\r\n"
            play_item.setProperty('inputstream.ffmpegdirect.headers', headers_str)

        play_item.setProperty('IsPlayable', 'true')
        play_item.setContentLookup(False)
        return play_item

    # ---------------------------------------------------
    # Reprodução com monitoramento de início
    # ---------------------------------------------------
    def play_resolved_source(self, final_url, item_info):
        play_item = self._create_listitem(final_url, item_info)
        xbmcplugin.setResolvedUrl(handle=self.handle, succeeded=True, listitem=play_item)
        xbmc.log("[CineroomResolver] setResolvedUrl chamado, monitorando playback...", xbmc.LOGINFO)

        # Desliga spinner quando o player iniciar
        def monitor():
            player = xbmc.Player()
            while not player.isPlaying():
                xbmc.sleep(100)
            xbmc.log("[CineroomResolver] Playback detectado pelo monitor. Fechando resolvedor...", xbmc.LOGINFO)
            self.setProperty("enable_busy_spinner", "false")
            self.close()

        threading.Thread(target=monitor, daemon=True).start()

    # ---------------------------------------------------
    # Tratamento de ações do usuário
    # ---------------------------------------------------
    def onAction(self, action):
        action_id = action.getId()
    
        # Voltar, parar ou cancelar buffer
        if action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PARENT_DIR, xbmcgui.ACTION_STOP):
            xbmc.log("[CineroomResolver] Ação de cancelamento detectada. Fechando resolvedor...", xbmc.LOGINFO)
        
            # Para o player, caso já tenha sido iniciado
            if self.player and self.player.isPlaying():
                self.player.stop()
        
            # Marca spinner como falso para parar qualquer animação
            self.setProperty("enable_busy_spinner", "false")
        
            # Fecha a janela
            self.close()

