# Em: resources/lib/indexer.py
# -*- coding: utf-8 -*-

import xbmcgui
import xbmc
import xbmcaddon
import xbmcplugin
import xbmcvfs
import sys
import urllib.request
import json
import base64
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from .db import db
from .tmdb_api import update_local_popularity

SECRET_KEYS = {
    'movies_a': "bm9zai5zZWl2b21fbGxhL3Nub3NqL21vb3JlbmljL3RzZXRhbEBtb29y",
    'movies_b': "eGlsZi8zMDMxbGVhRy9oZy90ZW4ucnZpbGVkc2oubmRjLy86c3B0dGg=",
    'tvshows_a': "bm9zai5zd29oc3Z0X3RzZXQvc25vc2ovbW9vcmVuaWMvdHNldGFsQG1vb3",
    'tvshows_b': "J4aWxmLzMwMzFsZWFHL2hnL3Rlbi5ydmlsZWRzai5uZGMvLzpzcHR0aA=="
}

def _get_source_url(item_type):
    try:
        part_a = SECRET_KEYS.get(f'{item_type}_a')
        part_b = SECRET_KEYS.get(f'{item_type}_b')
        if not part_a or not part_b: return None
        encoded_string = part_a + part_b
        inverted_url_bytes = base64.b64decode(encoded_string)
        inverted_url = inverted_url_bytes.decode('utf-8')
        final_url = inverted_url[::-1]
        return final_url
    except Exception as e:
        xbmc.log(f"[Indexer] Falha ao decodificar a URL secreta para {item_type}: {e}", xbmc.LOGERROR)
        return None

def _fetch_json_source(url):
    if not url: return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data if isinstance(data, list) else None
    except urllib.error.HTTPError as e:
        xbmc.log(f"[Indexer] Servidor offline ou lista removida (Erro {e.code})", xbmc.LOGWARNING)
    except urllib.error.URLError:
        xbmc.log("[Indexer] Sem conexão com o servidor de dados.", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"[Indexer] Erro inesperado: {e}", xbmc.LOGERROR)
    return None

def check_for_updates_silently(addon_object):
    """
    Verifica novos itens, notifica o usuário e atualiza o banco completo.
    """
    xbmc.log("[Indexer] Iniciando verificação de atualizações...", xbmc.LOGINFO)
    
    # 1. Buscar timestamp da última verificação
    last_check_str = addon_object.getSetting('last_update_check')
    if not last_check_str:
        last_check_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
    else:
        try:
            last_check_dt = datetime.fromisoformat(last_check_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                last_check_dt = datetime.fromtimestamp(int(last_check_str), tz=timezone.utc)
            except (ValueError, TypeError):
                last_check_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)

    current_check_dt = datetime.now(timezone.utc)

    # 2. Baixar as listas completas
    movies_url = _get_source_url('movies')
    tvshows_url = _get_source_url('tvshows')
    movies_data = _fetch_json_source(movies_url) 
    tvshows_data = _fetch_json_source(tvshows_url) 
    
    if movies_data is None and tvshows_data is None:
        xbmc.log("[Indexer] Fontes indisponíveis. Abortando verificação.", xbmc.LOGINFO)
        return
    
    movies_data = movies_data or []
    tvshows_data = tvshows_data or []

    # 3. Buscar IDs já existentes no banco usando as classes específicas
    try:
        from resources.lib.db.movies_db import movies_db
        from resources.lib.db.tvshows_db import tvshows_db
        
        existing_movie_ids = movies_db.get_all_movie_ids_set()
        existing_tvshow_ids = tvshows_db.get_all_tvshow_ids_set()
        
        xbmc.log(f"[Indexer] Banco atual: {len(existing_movie_ids)} filmes, {len(existing_tvshow_ids)} séries", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Indexer] Falha ao buscar IDs existentes: {e}", xbmc.LOGERROR)
        existing_movie_ids = set()
        existing_tvshow_ids = set()

    # 4. Identificar itens NOVOS (não existem no banco E foram adicionados após última verificação)
    new_movies = []
    new_tvshows = []

    # Processar filmes
    for movie in movies_data:
        tmdb_id = movie.get('tmdb_id')
        if not tmdb_id:
            continue
            
        # Se NÃO existe no banco, verificar data
        if tmdb_id not in existing_movie_ids:
            try:
                date_str = movie.get('date_added')
                if not date_str:
                    # Se não tem data, considerar como novo
                    new_movies.append(movie)
                    continue
                
                # Normalizar para UTC
                item_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if item_dt.tzinfo is None:
                    item_dt = item_dt.replace(tzinfo=timezone.utc)
                
                # Verificar se foi adicionado após última verificação
                if item_dt >= last_check_dt:
                    new_movies.append(movie)
                    xbmc.log(f"[Indexer] Novo filme detectado: {movie.get('title', 'Unknown')} (ID: {tmdb_id})", xbmc.LOGDEBUG)
                    
            except (ValueError, TypeError) as e:
                xbmc.log(f"[Indexer] Erro ao processar data do filme {tmdb_id}: {e}", xbmc.LOGDEBUG)
                # Em caso de erro na data, considerar como novo se não está no banco
                new_movies.append(movie)

    # Processar séries
    for show in tvshows_data:
        tmdb_id = show.get('tmdb_id')
        if not tmdb_id:
            continue
            
        if tmdb_id not in existing_tvshow_ids:
            try:
                date_str = show.get('date_added')
                if not date_str:
                    new_tvshows.append(show)
                    continue
                
                item_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if item_dt.tzinfo is None:
                    item_dt = item_dt.replace(tzinfo=timezone.utc)
                
                if item_dt >= last_check_dt:
                    new_tvshows.append(show)
                    xbmc.log(f"[Indexer] Nova série detectada: {show.get('name', 'Unknown')} (ID: {tmdb_id})", xbmc.LOGDEBUG)
                    
            except (ValueError, TypeError) as e:
                xbmc.log(f"[Indexer] Erro ao processar data da série {tmdb_id}: {e}", xbmc.LOGDEBUG)
                new_tvshows.append(show)

    # 5. Contar e NOTIFICAR
    new_movies_count = len(new_movies)
    new_tvshows_count = len(new_tvshows)
    total_new = new_movies_count + new_tvshows_count
    
    xbmc.log(f"[Indexer] Resultado da verificação: {new_movies_count} novos filmes, {new_tvshows_count} novas séries", xbmc.LOGINFO)
    
    if total_new > 0:
        itens = []
        if new_movies_count > 0:
            itens.append(f"{new_movies_count} {'Filme' if new_movies_count == 1 else 'Filmes'}")
        if new_tvshows_count > 0:
            itens.append(f"{new_tvshows_count} {'Série' if new_tvshows_count == 1 else 'Séries'}")
        
        texto = " e ".join(itens) + " encontrado" + ("s" if total_new > 1 else "")
        
        try:
            icon_path = xbmcvfs.translatePath(addon_object.getAddonInfo('path') + '/icon.png')
        except:
            icon_path = ""
            
        xbmc.log(f"[Indexer] {texto}. Adicionando ao banco...", xbmc.LOGINFO)
        xbmc.executebuiltin(f'Notification("Cineroom Lite", "{texto}. Atualizando...", 5000, "{icon_path}")')
    else:
        xbmc.log("[Indexer] Nenhum conteúdo novo encontrado.", xbmc.LOGINFO)

    # 6. ATUALIZAR BANCO: Adicionar apenas os novos (sem limpar tudo)
    try:
        if new_movies:
            xbmc.log(f"[Indexer] Adicionando {len(new_movies)} novos filmes ao banco...", xbmc.LOGINFO)
            db.add_movies_bulk(new_movies)
        
        if new_tvshows:
            xbmc.log(f"[Indexer] Adicionando {len(new_tvshows)} novas séries ao banco...", xbmc.LOGINFO)
            db.add_tvshows_bulk(new_tvshows)
        
        # Sincronizar popularidade do TMDB apenas se houver novos itens
        if total_new > 0:
            xbmc.log("[Indexer] Sincronizando com TMDB...", xbmc.LOGINFO)
            try:
                update_local_popularity()
            except Exception as e_tmdb:
                xbmc.log(f"[Indexer] Erro ao sincronizar TMDB: {e_tmdb}", xbmc.LOGWARNING)
        
        xbmc.log("[Indexer] Verificação concluída com sucesso!", xbmc.LOGINFO)
        
    except Exception as e:
        xbmc.log(f"[Indexer] Erro ao atualizar banco: {e}", xbmc.LOGERROR)

    # 7. Salvar timestamp da verificação atual
    addon_object.setSetting('last_update_check', current_check_dt.isoformat())


def run_indexer(batch_size=100):
    """
    Atualiza o banco de dados completamente com feedback visual (chamado pelo menu).
    """
    progress = xbmcgui.DialogProgress()
    addon = xbmcaddon.Addon()
    
    try:
        progress.create('Cineroom Lite', 'Iniciando atualização do catálogo...')
        
        # --- ETAPA 1: LIMPEZA ---
        progress.update(2, 'Limpando banco de dados antigo...')
        db.clear_database()
        if progress.iscanceled(): return

        # --- ETAPA 2: DOWNLOAD ---
        progress.update(5, 'Baixando listas de conteúdo...')
        movies_url = _get_source_url('movies')
        tvshows_url = _get_source_url('tvshows')

        movies_to_add = _fetch_json_source(movies_url) or []
        tvshows_to_add = _fetch_json_source(tvshows_url) or []

        total_movies = len(movies_to_add)
        total_tvshows = len(tvshows_to_add)
        total_items = total_movies + total_tvshows

        if total_items == 0:
            xbmcgui.Dialog().ok("Aviso", "Nenhum item encontrado nas fontes de dados.")
            return

        # --- ETAPA 3: PROCESSAMENTO DE FILMES ---
        movies_processed = 0
        if movies_to_add:
            for i in range(0, total_movies, batch_size):
                if progress.iscanceled(): return
                batch = movies_to_add[i:i+batch_size]
                db.add_movies_bulk(batch)
                movies_processed += len(batch)
                
                percent = int(10 + (movies_processed / total_items) * 80)
                progress.update(percent, f"Adicionando filmes: {movies_processed}/{total_movies}")

        # --- ETAPA 4: PROCESSAMENTO DE SÉRIES ---
        tvshows_processed = 0
        if tvshows_to_add:
            for i in range(0, total_tvshows, batch_size):
                if progress.iscanceled(): return
                batch = tvshows_to_add[i:i+batch_size]
                db.add_tvshows_bulk(batch)
                tvshows_processed += len(batch)
                
                total_done = movies_processed + tvshows_processed
                percent = int(10 + (total_done / total_items) * 80)
                progress.update(percent, f"Adicionando séries: {tvshows_processed}/{total_tvshows}")

        # --- ETAPA 5: SINCRONIZAÇÃO TMDB ---
        if not progress.iscanceled():
            progress.update(92, "Sincronizando capas e tendências (TMDB)...")
            try:
                update_local_popularity()
            except Exception as e:
                xbmc.log(f"[Indexer] Erro TMDB: {e}", xbmc.LOGWARNING)

        # --- ETAPA 6: FINALIZAÇÃO ---
        if not progress.iscanceled():
            progress.update(100, "Catalogação concluída com sucesso!")
            
            current_check_dt = datetime.now(timezone.utc)
            addon.setSetting('last_update_check', current_check_dt.isoformat())
            
            xbmc.sleep(800)
            xbmcgui.Dialog().notification("Cineroom Lite", "Catálogo Atualizado!", xbmcgui.NOTIFICATION_INFO, 5000)

    except Exception as e:
        xbmc.log(f"[Indexer] Erro crítico: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro na Atualização", f"Detalhes: {e}")
    
    finally:
        if progress:
            progress.close()
        
        try:
            handle = int(sys.argv[1])
            xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=True)
        except:
            pass

        xbmc.executebuiltin("Dialog.Close(busydialog)")