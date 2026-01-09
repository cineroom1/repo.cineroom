# -*- coding: utf-8 -*-
"""
Janela de resolução visual - Delega playback para player.py
"""
import xbmcgui
import xbmc
import sys
import threading
import time

class CineroomResolverWindow(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_url = kwargs.get('source_url')
        self.item_data = kwargs.get('item_data')
        self.handle = kwargs.get('handle', int(sys.argv[1]))
        self._is_closing = False

        # Propriedades dinâmicas para XML
        self.setProperty("enable_busy_spinner", "true")
        self.setProperty("resolve_status", "Iniciando...")

        if self.item_data:
            self.setProperty("info.title", self.item_data.get('title', 'Resolvendo Fonte...'))
            self.setProperty("info.fanart", self.item_data.get('backdrop', ''))
            self.setProperty("info.poster", self.item_data.get('poster', ''))
            self.setProperty("info.clearlogo", self.item_data.get('clearlogo', ''))

    def onInit(self):
        """Inicia o processo de resolução em thread separada"""
        threading.Thread(target=self.start_resolution_process, daemon=True).start()

    def start_resolution_process(self):
        """
        Fluxo simplificado:
        1. Mostra tela de loading
        2. Delega TUDO para player.py (detecção, config, reprodução)
        3. Monitora início do playback
        4. Fecha janela automaticamente
        """
        time.sleep(0.8)  # Tempo mínimo para mostrar a tela
        
        try:
            self._update_status("Analisando fonte...")
            xbmc.log(f"[Resolver] Delegando para player.py: {self.source_url[:80]}...", xbmc.LOGINFO)
            
            # ✅ IMPORTAÇÃO CORRETA - do seu __init__.py
            # Se resolver.py está em resources/lib/ e player.py está em resources/lib/playback/
            # Então importa de playback (que tem o __init__.py configurado)
            
            # Opção 1: Importação relativa
            try:
                from ..playback import play_url_with_retry
                xbmc.log("[Resolver] Importação relativa bem-sucedida", xbmc.LOGDEBUG)
            except (ImportError, ValueError):
                # Opção 2: Importação absoluta
                from resources.lib.playback import play_url_with_retry
                xbmc.log("[Resolver] Importação absoluta bem-sucedida", xbmc.LOGDEBUG)
            
            # Etapa de resolução visual
            self._update_status("Resolvendo link...")
            time.sleep(0.5)
            
            self._update_status("Preparando reprodução...")
            time.sleep(0.3)
            
            # ✅ DELEGA TUDO PARA PLAYER.PY
            success = play_url_with_retry(
                self.source_url,
                self.item_data,
                max_retries=2
            )
            
            if not success:
                raise Exception("Player retornou falha na reprodução")
            
            # ✅ Monitora início do playback para fechar a janela
            xbmc.log("[Resolver] Aguardando playback iniciar...", xbmc.LOGDEBUG)
            self._monitor_playback_start()

        except Exception as e:
            self._handle_error(e)

    def _monitor_playback_start(self):
        """
        Monitora quando o playback realmente inicia
        Fecha a janela automaticamente quando detectar
        """
        player = xbmc.Player()
        max_wait = 30  # 30 segundos de timeout
        waited = 0
        
        while waited < max_wait and not self._is_closing:
            if player.isPlaying():
                xbmc.log("[Resolver] ✓ Playback detectado! Fechando janela...", xbmc.LOGINFO)
                self.setProperty("enable_busy_spinner", "false")
                time.sleep(0.3)  # Pequeno delay antes de fechar
                self._safe_close()
                return
            
            time.sleep(0.2)
            waited += 0.2
        
        # Timeout
        if not self._is_closing:
            xbmc.log("[Resolver] ⚠ Timeout aguardando playback", xbmc.LOGWARNING)
            self._safe_close()

    def _update_status(self, message: str):
        """Atualiza o status exibido na tela"""
        self.setProperty("resolve_status", message)
        xbmc.log(f"[Resolver] Status: {message}", xbmc.LOGDEBUG)

    def _handle_error(self, error: Exception):
        """Trata erros durante a resolução"""
        self._update_status("Erro ao resolver")
        xbmc.log(f"[Resolver] ERRO: {error}", xbmc.LOGERROR)
        
        # Mostra diálogo de erro
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
        """Handler de ações (voltar, ESC, etc)"""
        action_id = action.getId()
        
        # Ações de cancelamento
        if action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PARENT_DIR, 
                         xbmcgui.ACTION_STOP, xbmcgui.ACTION_PREVIOUS_MENU):
            xbmc.log("[Resolver] Ação de cancelamento detectada pelo usuário", xbmc.LOGINFO)
            
            # Para o player se estiver rodando
            player = xbmc.Player()
            if player.isPlaying():
                player.stop()
            
            self._safe_close()

    def _safe_close(self):
        """Fecha a janela de forma segura (evita múltiplos closes)"""
        if self._is_closing:
            return
        
        self._is_closing = True
        self.setProperty("enable_busy_spinner", "false")
        
        try:
            self.close()
        except Exception as e:
            xbmc.log(f"[Resolver] Erro ao fechar janela: {e}", xbmc.LOGERROR)