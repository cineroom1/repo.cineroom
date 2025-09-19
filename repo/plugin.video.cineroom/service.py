# -*- coding: utf-8 -*-
# Python 3.x
import xbmc
import xbmcaddon
import time

# Importa as funções para cache e sincronização com Supabase
# Certifique-se de que o arquivo "firebase.py" esteja no mesmo diretório
# do seu serviço.
from firebase import load_search_cache_from_disk, sync_cache as sync_cache_supabase

# Configurações do Addon
ADDON = xbmcaddon.Addon()

# As variáveis originais do seu script
SYNC_INTERVAL_MINUTES = 15
MAX_TERMS_PER_BATCH = 2

class MyService(xbmc.Monitor):
    def run(self):
        """Loop principal do serviço."""
        while not self.abortRequested():
            xbmc.log("[SERVICE] Verificando caches pendentes para Supabase...", xbmc.LOGINFO)

            # Lógica para sincronizar o cache de buscas para o Supabase
            for video_type in ["movie", "tvshow"]:
                buffer_data = load_search_cache_from_disk(video_type)
                if not buffer_data or not buffer_data.get("terms"):
                    continue

                cache_age_minutes = (time.time() - buffer_data["timestamp"]) / 60
                if cache_age_minutes >= SYNC_INTERVAL_MINUTES or len(buffer_data["terms"]) >= MAX_TERMS_PER_BATCH:
                    # Chamar a função de sincronização do Supabase
                    sync_cache_supabase(video_type)

            # Espera 1 minuto antes da próxima verificação
            # Ajustei o tempo para 15 minutos (SYNC_INTERVAL_MINUTES * 60)
            # para corresponder ao intervalo de sincronização
            if self.waitForAbort(SYNC_INTERVAL_MINUTES * 60):
                xbmc.log("[SERVICE] Serviço encerrado.", xbmc.LOGINFO)
                break

if __name__ == "__main__":
    service = MyService()
    service.run()