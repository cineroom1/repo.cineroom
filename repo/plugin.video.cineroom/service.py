import xbmc
import xbmcaddon
import time
import json
import xbmcgui
import urllib.request

from firebase import sync_cache, load_search_cache_from_disk

ADDON = xbmcaddon.Addon()
# Chave para armazenar o ID da última notificação vista
LAST_NOTIFICATION_ID_KEY = "last_notification_id"
FIREBASE_NOTIFICATIONS_URL = "https://notify-313a5-default-rtdb.firebaseio.com/notificacoes_app/.json"
SYNC_INTERVAL_MINUTES = 15
MAX_TERMS_PER_BATCH = 2

class MyService(xbmc.Monitor):
    def check_for_notifications(self):
        """Busca e exibe novas notificações do Firebase."""
        try:
            # Obtém o ID da última notificação vista, se existir
            last_id_seen = ADDON.getSetting(LAST_NOTIFICATION_ID_KEY)
            
            req = urllib.request.Request(FIREBASE_NOTIFICATIONS_URL)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.getcode() == 200:
                    notifications_data = json.loads(response.read().decode('utf-8'))
                    
                    if not notifications_data:
                        return
                    
                    # Encontra o ID da última notificação
                    latest_notification_id = max(int(id) for id in notifications_data.keys())

                    # Se a última notificação for diferente da que o usuário viu
                    if str(latest_notification_id) != last_id_seen:
                        latest_data = notifications_data[str(latest_notification_id)]
                        
                        dialog = xbmcgui.Dialog()
                        dialog.notification(
                            heading=latest_data.get('titulo', 'Notificação'),
                            message=latest_data.get('mensagem', ''),
                            sound=True
                        )
                        # Salva o novo ID para que a notificação não seja exibida novamente
                        ADDON.setSetting(LAST_NOTIFICATION_ID_KEY, str(latest_notification_id))
        
        except Exception as e:
            xbmc.log(f"[SERVICE] Erro ao verificar notificações: {str(e)}", xbmc.LOGERROR)

    def run(self):
        while not self.abortRequested():
            xbmc.log("[SERVICE] Verificando caches e notificações pendentes...", xbmc.LOGINFO)

            # Lógica existente para sincronizar o cache de buscas
            for video_type in ["movie", "tvshow"]:
                buffer_data = load_search_cache_from_disk(video_type)
                if not buffer_data or not buffer_data["terms"]:
                    continue

                cache_age_minutes = (time.time() - buffer_data["timestamp"]) / 60
                if cache_age_minutes >= SYNC_INTERVAL_MINUTES or len(buffer_data["terms"]) >= MAX_TERMS_PER_BATCH:
                    sync_cache(video_type)

            # --- Adiciona a verificação de notificações aqui ---
            self.check_for_notifications()

            # Espera 1 minuto antes da próxima verificação
            if self.waitForAbort(60):
                xbmc.log("[SERVICE] Serviço encerrado.", xbmc.LOGINFO)
                break


if __name__ == "__main__":
    service = MyService()
    service.run()