# Em: resources/lib/indexer.py
# -*- coding: utf-8 -*-

import xbmcgui
import xbmc
import xbmcaddon
import xbmcplugin # Necessário para fechar o loading do Kodi
import sys # Necessário para pegar o ID do plugin
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
    Verifica e adiciona apenas o novo conteúdo de forma silenciosa.
    """
    last_check_str = addon_object.getSetting('last_update_check')

    if not last_check_str:
        last_check_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)
    else:
        try:
            last_check_dt = datetime.fromisoformat(last_check_str)
        except ValueError:
            try:
                last_check_dt = datetime.fromtimestamp(int(last_check_str), tz=timezone.utc)
            except (ValueError, TypeError):
                last_check_dt = datetime(2000, 1, 1, tzinfo=timezone.utc)

    current_check_dt = datetime.now(timezone.utc)
    last_check_date_only = last_check_dt.date()

    movies_url = _get_source_url('movies')
    tvshows_url = _get_source_url('tvshows')
    movies_data = _fetch_json_source(movies_url) 
    tvshows_data = _fetch_json_source(tvshows_url) 
    
    if movies_data is None and tvshows_data is None:
        xbmc.log("[Indexer] Fontes indisponíveis. Abortando verificação silenciosa.", xbmc.LOGINFO)
        return
    
    movies_data = movies_data or []
    tvshows_data = tvshows_data or []

    xbmc.log("[Indexer] Buscando IDs existentes no banco de dados...", level=xbmc.LOGINFO)
    try:
        existing_movie_ids = db.get_all_movie_ids_set()
        existing_tvshow_ids = db.get_all_tvshow_ids_set()
    except Exception as e:
        xbmc.log(f"[Indexer] Falha grave ao buscar IDs existentes: {e}", xbmc.LOGERROR)
        existing_movie_ids = set()
        existing_tvshow_ids = set()

    new_movies = []
    for movie in movies_data:
        try:
            date_str = movie.get('date_added')
            if not isinstance(date_str, str) or not date_str:
                continue

            item_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if item_dt.tzinfo is None:
                item_dt = item_dt.replace(tzinfo=timezone.utc)

            is_new_by_date = False
            if 'T' in date_str:
                if item_dt > last_check_dt:
                    is_new_by_date = True
            else:
                if item_dt.date() >= last_check_date_only:
                    is_new_by_date = True

            tmdb_id = movie.get('tmdb_id')
            if is_new_by_date and tmdb_id not in existing_movie_ids:
                new_movies.append(movie)

        except (ValueError, TypeError):
            continue

    new_tvshows = []
    for show in tvshows_data:
        try:
            date_str = show.get('date_added')
            if not isinstance(date_str, str) or not date_str:
                continue

            item_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if item_dt.tzinfo is None:
                item_dt = item_dt.replace(tzinfo=timezone.utc)

            is_new_by_date = False
            if 'T' in date_str:
                if item_dt > last_check_dt:
                    is_new_by_date = True
            else:
                if item_dt.date() >= last_check_date_only:
                    is_new_by_date = True

            tmdb_id = show.get('tmdb_id')
            if is_new_by_date and tmdb_id not in existing_tvshow_ids:
                new_tvshows.append(show)

        except (ValueError, TypeError):
            continue

    total_new_items = len(new_movies) + len(new_tvshows)

    if total_new_items > 0:
        xbmc.log(f"[Indexer] Adicionando {len(new_movies)} novos filmes e {len(new_tvshows)} novas séries.", level=xbmc.LOGINFO)
        if new_movies:
            db.add_movies_bulk(new_movies)
        if new_tvshows:
            db.add_tvshows_bulk(new_tvshows)

        message = f"{total_new_items} novos itens adicionados ao catálogo."
        xbmcgui.Dialog().notification("Cineroom Lite", message, xbmcgui.NOTIFICATION_INFO, 5000)
    else:
        xbmc.log("[Indexer] Nenhum conteúdo novo encontrado.", level=xbmc.LOGINFO)

    addon_object.setSetting('last_update_check', current_check_dt.isoformat())


def run_indexer(batch_size=100):
    """
    Atualiza o banco de dados completamente com feedback visual.
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
                
                # Ocupa de 10% a 45% da barra
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
                
                # Continua de onde parou até ~90%
                total_done = movies_processed + tvshows_processed
                percent = int(10 + (total_done / total_items) * 80)
                progress.update(percent, f"Adicionando séries: {tvshows_processed}/{total_tvshows}")

        # --- ETAPA 5: SINCRONIZAÇÃO TMDB (O Toque Final) ---
        if not progress.iscanceled():
            progress.update(92, "Sincronizando capas e tendências (TMDB)...")
            try:
                # Agora que o banco tem IDs, podemos buscar popularidade
                update_local_popularity()
            except Exception as e:
                xbmc.log(f"[Indexer] Erro TMDB: {e}", xbmc.LOGWARNING)

        # --- ETAPA 6: FINALIZAÇÃO ---
        if not progress.iscanceled():
            progress.update(100, "Catalogação concluída com sucesso!")
            
            # Atualiza data da última verificação
            current_check_dt = datetime.now(timezone.utc)
            addon.setSetting('last_update_check', current_check_dt.isoformat())
            
            xbmc.sleep(800)
            xbmcgui.Dialog().notification("Cineroom Lite", "Catálogo Atualizado!", xbmcgui.NOTIFICATION_INFO, 5000)

    except Exception as e:
        xbmc.log(f"[Indexer] Erro crítico: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro na Atualização", f"Detalhes: {e}")
    
    finally:
        # Fecha a barra de progresso
        if progress:
            progress.close()
        
        # Finaliza o handle do plugin para o Kodi parar de "girar" o loading
        try:
            handle = int(sys.argv[1])
            xbmcplugin.endOfDirectory(handle, succeeded=True, updateListing=True)
        except:
            pass

        # Garante que qualquer diálogo de espera do sistema seja fechado
        xbmc.executebuiltin("Dialog.Close(busydialog)")