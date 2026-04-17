# -*- coding: utf-8 -*-
"""
Janela de resolução visual - Delega playback para player.py
"""
import sys
import threading
import time
import xbmc
import xbmcgui


class CineroomSearchWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self._last_percent = -1

    def onInit(self):
        self.setProperty("search.status", "Buscando fontes...")
        self.setProperty("search.percent", "0")
        try:
            self.getControl(202).setWidth(0)
        except Exception:
            pass

    def set_art(self, fanart="", clearlogo="", title=""):
        if fanart:
            self.setProperty("info.fanart", fanart)
        if clearlogo:
            self.setProperty("info.clearlogo", clearlogo)
        if title:
            self.setProperty("info.title", title)

    def update_progress(self, completed, total, provider_name):
        if total <= 0:
            percent = 0
        else:
            percent = int((completed / float(total)) * 100)

        # Evita spam de UI
        if percent == self._last_percent:
            return
        self._last_percent = percent

        self.setProperty("search.status", f"[B]BUSCANDO[/B]... ({completed} / {total})")
        self.setProperty("search.percent", str(percent))

        try:
            total_width = 900  # Deve bater com o width definido no XML
            fill_width = int((percent / 100.0) * total_width)
            self.getControl(202).setWidth(fill_width)
        except Exception:
            pass


class CineroomResolverWindow(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        self.source_url  = kwargs.pop('source_url', None)
        self.item_data   = kwargs.pop('item_data',  None)
        self.handle      = kwargs.pop('handle', int(sys.argv[1]))
        self._is_closing = False

        super().__init__(*args, **kwargs)

        self.setProperty("enable_busy_spinner", "true")
        self.setProperty("resolve_status", "Iniciando...")

        if self.item_data:
            self.setProperty("info.title",     self.item_data.get('title', 'Resolvendo Fonte...'))
            self.setProperty("info.fanart",    self.item_data.get('backdrop', ''))
            self.setProperty("info.poster",    self.item_data.get('poster', ''))
            self.setProperty("info.clearlogo", self.item_data.get('clearlogo', ''))

    def onInit(self):
        threading.Thread(target=self.start_resolution_process, daemon=True).start()

    def start_resolution_process(self):
        time.sleep(0.8)

        try:
            self._update_status("Analisando fonte...")

            try:
                from resources.lib.playback.player import play_url_with_retry
            except ImportError:
                try:
                    from resources.lib.player import play_url_with_retry
                except ImportError:
                    from player import play_url_with_retry

            self._update_status("Resolvendo link...")
            time.sleep(0.5)

            self._update_status("Preparando reprodução...")
            time.sleep(0.3)

            success = play_url_with_retry(
                self.source_url,
                self.item_data,
                max_retries=2
            )

            if not success:
                raise Exception("Player retornou falha na reprodução")

            self._monitor_playback_start()

        except Exception as e:
            self._handle_error(e)

    def _monitor_playback_start(self):
        player   = xbmc.Player()
        max_wait = 30
        waited   = 0

        while waited < max_wait and not self._is_closing:
            if player.isPlaying():
                self.setProperty("enable_busy_spinner", "false")
                time.sleep(0.3)
                self._safe_close()
                return
            time.sleep(0.2)
            waited += 0.2

        if not self._is_closing:
            self._safe_close()

    def _update_status(self, message: str):
        self.setProperty("resolve_status", message)

    def _handle_error(self, error: Exception):
        import traceback
        self._update_status("Erro ao resolver")
        xbmc.log(f"[Resolver] ERRO: {error}", xbmc.LOGERROR)
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        self.setProperty("enable_busy_spinner", "false")
        xbmcgui.Dialog().notification(
            "Erro de Resolução",
            "Não foi possível resolver a fonte de vídeo",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )
        time.sleep(1)
        self._safe_close()

    def onAction(self, action):
        if action.getId() in (
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_PARENT_DIR,
            xbmcgui.ACTION_STOP,
            xbmcgui.ACTION_PREVIOUS_MENU,
        ):
            player = xbmc.Player()
            if player.isPlaying():
                player.stop()
            self._safe_close()

    def _safe_close(self):
        if self._is_closing:
            return
        self._is_closing = True
        self.setProperty("enable_busy_spinner", "false")
        try:
            self.close()
        except Exception as e:
            xbmc.log(f"[Resolver] Erro ao fechar janela: {e}", xbmc.LOGERROR)