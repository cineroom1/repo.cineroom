import xbmc
import xbmcaddon
import time

from firebase import sync_cache, load_search_cache_from_disk

ADDON = xbmcaddon.Addon()

SYNC_INTERVAL_MINUTES = 10
MAX_TERMS_PER_BATCH = 5

class MyService(xbmc.Monitor):
    def run(self):
        while not self.abortRequested():
            xbmc.log("[SERVICE] Verificando caches pendentes...", xbmc.LOGINFO)

            for video_type in ["movie", "tvshow"]:
                buffer_data = load_search_cache_from_disk(video_type)
                if not buffer_data or not buffer_data["terms"]:
                    continue

                cache_age_minutes = (time.time() - buffer_data["timestamp"]) / 60
                if cache_age_minutes >= SYNC_INTERVAL_MINUTES or len(buffer_data["terms"]) >= MAX_TERMS_PER_BATCH:
                    sync_cache(video_type)  # envia ao Firebase em lote

            # Espera 1 minuto antes da próxima verificação
            if self.waitForAbort(60):
                xbmc.log("[SERVICE] Serviço encerrado.", xbmc.LOGINFO)
                break


if __name__ == "__main__":
    service = MyService()
    service.run()
