# Em: service.py

import xbmc
import xbmcaddon
import time
# ✅ 1. ADICIONE ESTAS IMPORTAÇÕES NO TOPO
from datetime import datetime, timezone
from resources.lib.indexer import check_for_updates_silently

# Pega as informações do nosso addon
ADDON = xbmcaddon.Addon()
MONITOR = xbmc.Monitor()

def log(msg):
    """Função auxiliar para logs, para facilitar a leitura."""
    xbmc.log(f"[CR Lite Service] {msg}", level=xbmc.LOGINFO)

def _parse_interval_setting(setting_value):
    # ... (esta função já está perfeita, sem alterações)
    value_map = {
        "Desativado": 0, "A cada 3 horas": 3, "A cada 5 horas": 5,
        "A cada 12 horas": 12, "A cada 24 horas (Diariamente)": 24
    }
    return value_map.get(setting_value, 3)

def run_update_check():
    """Executa a verificação e o timestamp será atualizado pela própria função."""
    log('Iniciando verificação de novo conteúdo...')
    try:
        check_for_updates_silently(ADDON)
        log('Verificação concluída.')
    except Exception as e:
        log(f'Ocorreu um erro durante a verificação: {e}')

if __name__ == '__main__':
    log('Serviço de atualização automática iniciado.')

    # --- Verificação na Inicialização ---
    initial_interval_setting = ADDON.getSetting('update_interval')
    initial_check_hours = _parse_interval_setting(initial_interval_setting)
    if initial_check_hours > 0:
        log('Verificação na inicialização está ativada. Aguardando 2 minutos...')
        if not MONITOR.waitForAbort(120):
            run_update_check()

    # --- Loop Principal do Serviço ---
    while not MONITOR.abortRequested():
        interval_setting = ADDON.getSetting('update_interval')
        check_interval_hours = _parse_interval_setting(interval_setting)

        if check_interval_hours > 0:
            
            # ✅ 2. SUBSTITUA A LÓGICA DE TEMPO ANTIGA POR ESTA
            last_update_str = ADDON.getSetting('last_update_check')
            last_update_dt = None

            if not last_update_str:
                last_update_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
            else:
                try:
                    # Tenta ler o formato moderno (ISO)
                    last_update_dt = datetime.fromisoformat(last_update_str)
                except ValueError:
                    # Se falhar, tenta ler o formato antigo (timestamp) para retrocompatibilidade
                    try:
                        last_update_dt = datetime.fromtimestamp(int(last_update_str), tz=timezone.utc)
                    except (ValueError, TypeError):
                        last_update_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)

            interval_seconds = check_interval_hours * 60 * 60
            current_time_dt = datetime.now(timezone.utc)
            
            # Compara a diferença de tempo em segundos
            time_since_last_check = (current_time_dt - last_update_dt).total_seconds()
            
            log(f"Última checagem há {int(time_since_last_check / 60)} minutos. Próxima em {check_interval_hours} horas.")

            if time_since_last_check >= interval_seconds:
                log(f'Intervalo de {check_interval_hours}h atingido. Executando a verificação.')
                run_update_check()

        # O serviço acorda a cada 15 minutos para reavaliar
        wait_time_seconds = 15 * 60
        if MONITOR.waitForAbort(wait_time_seconds):
            break

    log('Serviço de atualização automática finalizado.')