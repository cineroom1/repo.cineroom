# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import xbmcvfs
from datetime import datetime, timezone

ADDON = xbmcaddon.Addon()
MONITOR = xbmc.Monitor()

def log(msg):
    xbmc.log(f"[CR Lite Service] {msg}", level=xbmc.LOGINFO)

def _parse_interval_setting(setting_value):
    value_map = {
        "Desativado": 0, "A cada 3 horas": 3, "A cada 5 horas": 5,
        "A cada 12 hours": 12, "A cada 24 horas (Diariamente)": 24
    }
    return value_map.get(setting_value, 0)

def run_update_check():
    log('Iniciando verificação de novo conteúdo...')
    try:
        # 1. Verifica novos filmes/séries nos seus JSONs (Atualiza o DB local)
        from resources.lib.indexer import check_for_updates_silently
        check_for_updates_silently(ADDON)
        
        # 2. Sincroniza o DB local com a Biblioteca do Kodi (arquivos .strm)
        # Respeita a nova configuração de ativação automática
        if ADDON.getSetting('sync_auto_library') == 'true':
            try:
                from resources.lib.library import sync_library_silently
                log('Sincronização automática ativa. Verificando arquivos .strm...')
                sync_library_silently()
                
                # Avisa o Kodi para escanear novas artes e arquivos
                xbmc.executebuiltin('UpdateLibrary(video)')
            except Exception as e_lib:
                log(f'Erro na sincronização da biblioteca: {e_lib}')
        else:
            log('Sincronização automática ignorada (desativada nas configurações).')

        # 3. Atualiza popularidade (TMDB)
        try:
            from resources.lib.tmdb_api import update_local_popularity
            log('Iniciando sincronização de popularidade...')
            update_local_popularity() 
        except Exception as e_pop:
            log(f'Erro ao atualizar popularidade: {e_pop}')

        # 4. MANUTENÇÃO E NOTIFICAÇÃO
        try:
            from resources.lib.db import db 
            conn = db._get_conn()
            cursor = conn.cursor()
            
            # Limpa cache antigo
            cursor.execute("DELETE FROM api_cache WHERE timestamp < datetime('now', '-48 hours')")
            conn.commit()
            
            # Notificação de Itens Novos
            hoje = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT COUNT(*) FROM movies WHERE date_added LIKE ?", (f"{hoje}%",))
            novos_filmes = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM tvshows WHERE date_added LIKE ?", (f"{hoje}%",))
            novas_series = cursor.fetchone()[0]
            conn.close()

            if novos_filmes > 0 or novas_series > 0:
                itens = []
                if novos_filmes > 0: itens.append(f"+{novos_filmes} Filmes")
                if novas_series > 0: itens.append(f"+{novas_series} Séries")
                texto = "Novidades: " + " e ".join(itens)
                icon_path = xbmcvfs.translatePath(ADDON.getAddonInfo('path') + '/icon.png')
                xbmc.executebuiltin(f'Notification("Cineroom Lite", "{texto}", 7000, "{icon_path}")')
        except Exception as e_maint:
            log(f'Erro na manutenção: {e_maint}')

        # Salva o sucesso da operação
        ADDON.setSetting('last_update_check', datetime.now(timezone.utc).isoformat())
        log('Verificação concluída com sucesso.')

    except Exception as e:
        log(f'Ocorreu um erro geral: {e}')
        
def run_trakt_service():
    """Executa sincronização automática do Trakt"""
    try:
        from resources.lib.trakt_sync import TraktSyncService, get_trakt_settings
        
        settings = get_trakt_settings()
        if not settings.get('access_token'):
            return
        
        service = TraktSyncService()
        service.start()
        
        # Monitora por 5 minutos
        monitor = xbmc.Monitor()
        for i in range(300):  # 5 minutos
            if monitor.waitForAbort(1):  # Verifica a cada segundo
                break
        
        service.stop()
        
    except Exception as e:
        xbmc.log(f"[Trakt Service] Erro: {e}", xbmc.LOGERROR)        

if __name__ == '__main__':
    log('Serviço iniciado.')
    
    # Espera inicial para rede estabilizar
    if not MONITOR.waitForAbort(30):
        interval = _parse_interval_setting(ADDON.getSetting('update_interval'))
        if interval > 0:
            run_update_check()

    while not MONITOR.abortRequested():
        if MONITOR.waitForAbort(1800): # Checa a cada 30min se já deu o horário
            break
            
        interval_hours = _parse_interval_setting(ADDON.getSetting('update_interval'))
        if interval_hours == 0: continue

        last_update_str = ADDON.getSetting('last_update_check')
        current_time_dt = datetime.now(timezone.utc)
        
        try:
            if not last_update_str:
                last_update_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
            else:
                try:
                    last_update_dt = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
                except:
                    last_update_dt = datetime.fromtimestamp(int(float(last_update_str)), tz=timezone.utc)
            
            if (current_time_dt - last_update_dt).total_seconds() >= (interval_hours * 3600):
                run_update_check()
                
        except Exception as e:
            log(f"Erro no loop de tempo: {e}")

    log('Serviço finalizado.')