# Em: resources/lib/indexer.py

import xbmcgui
import xbmc
import xbmcaddon
import urllib.request
import json
import base64
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from .db import db

SECRET_KEYS = {
    'movies_a': "bm9zai5zZWl2b21fbGxhL3Nub3NqL21vb3JlbmljL3RzZXRhbEBtb29y",
    'movies_b': "eGlsZi8zMDMxbGVhRy9oZy90ZW4ucnZpbGVkc2oubmRjLy86c3B0dGg=",
    'tvshows_a': "bm9zai5zd29oc3Z0X2xsYS9zbm9zai9tb29yZW5pYy90c2V0YWxAbW9v",
    'tvshows_b': "cnhpbGYvMzAzMWxlYUcvaGcvdGVuLnJ2aWxlZHNqLm5kYy8vOnNwdHRo"
}

def _get_source_url(item_type):
    """Decodifica e monta a URL real a partir das nossas chaves secretas."""
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
    """Baixa e decodifica um arquivo JSON de uma URL, garantindo que é uma lista."""
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, list):
                    return data
                else:
                    xbmc.log(f"[Indexer] ERRO: O JSON da fonte não contém uma lista.", xbmc.LOGERROR)
    except Exception as e:
        xbmc.log(f"[Indexer] ERRO CRÍTICO ao baixar o JSON: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro de Indexação", f"Falha ao baixar os dados.\n\nErro: {e}")
    return None

def check_for_updates_silently(addon_object):
    """
    Verifica e adiciona apenas o novo conteúdo de forma silenciosa.
    Esta versão checa se o ID já existe antes de notificar.
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

    # Armazena a hora exata que esta verificação começou
    current_check_dt = datetime.now(timezone.utc)

    # Extrai apenas a DATA da última checagem (ex: 2025-10-18)
    last_check_date_only = last_check_dt.date()

    movies_url = _get_source_url('movies')
    tvshows_url = _get_source_url('tvshows')
    movies_data = _fetch_json_source(movies_url) or []
    tvshows_data = _fetch_json_source(tvshows_url) or []

    # --- ✅ NOVA ETAPA: Buscar IDs existentes PRIMEIRO ---
    xbmc.log("[Indexer] Buscando IDs existentes no banco de dados...", level=xbmc.LOGINFO)
    try:
        existing_movie_ids = db.get_all_movie_ids_set()
        existing_tvshow_ids = db.get_all_tvshow_ids_set()
    except Exception as e:
        xbmc.log(f"[Indexer] Falha grave ao buscar IDs existentes: {e}", xbmc.LOGERROR)
        # Se falhar, usamos sets vazios. O pior que pode acontecer é notificar de novo.
        existing_movie_ids = set()
        existing_tvshow_ids = set()

    xbmc.log(f"[Indexer] Encontrados {len(existing_movie_ids)} IDs de filmes e {len(existing_tvshow_ids)} IDs de séries.", level=xbmc.LOGINFO)

    new_movies = []
    for movie in movies_data:
        try:
            date_str = movie.get('date_added')
            if not isinstance(date_str, str) or not date_str:
                continue

            item_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if item_dt.tzinfo is None:
                item_dt = item_dt.replace(tzinfo=timezone.utc)

            # --- ✅ NOVA LÓGICA DE COMPARAÇÃO (DUAS ETAPAS) ---
            is_new_by_date = False

            # 1. O item é novo baseado na data?
            if 'T' in date_str:
                # Comparação precisa (com hora)
                if item_dt > last_check_dt:
                    is_new_by_date = True
            else:
                # Comparação de "dia inteiro" (com >= para pegar itens de hoje)
                if item_dt.date() >= last_check_date_only:
                    is_new_by_date = True

            # 2. O item já existe no banco?
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

            # --- ✅ NOVA LÓGICA DE COMPARAÇÃO (DUAS ETAPAS) ---
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

    # --- ESTE BLOCO AGORA SÓ RODA SE HOUVER ITENS GENUINAMENTE NOVOS ---
    total_new_items = len(new_movies) + len(new_tvshows)

    if total_new_items > 0:
        xbmc.log(f"[Indexer] Adicionando {len(new_movies)} novos filmes e {len(new_tvshows)} novas séries.", level=xbmc.LOGINFO)
        if new_movies:
            db.add_movies_bulk(new_movies)
        if new_tvshows:
            db.add_tvshows_bulk(new_tvshows)

        # A notificação agora só aparece para itens realmente novos
        message = f"{total_new_items} novos itens adicionados ao catálogo."
        xbmcgui.Dialog().notification("Cineroom Lite", message, xbmcgui.NOTIFICATION_INFO, 5000)
    else:
        xbmc.log("[Indexer] Nenhum conteúdo novo encontrado.", level=xbmc.LOGINFO)

    # Sempre salva a data desta verificação (current_check_dt)
    addon_object.setSetting('last_update_check', current_check_dt.isoformat())


def run_indexer(batch_size=150):
    """
    Atualiza o banco de dados com um feedback de progresso e salva o timestamp.
    """
    progress = xbmcgui.DialogProgress()
    try:
        progress.create('Cineroom Lite', 'Iniciando atualização...')
        progress.update(2, 'Limpando dados antigos...')
        db.clear_database()
        if progress.iscanceled(): return

        progress.update(5, 'Baixando listas de conteúdo...')
        
        movies_url = _get_source_url('movies')
        tvshows_url = _get_source_url('tvshows')

        movies_to_add = _fetch_json_source(movies_url) or []
        if progress.iscanceled(): return
        
        tvshows_to_add = _fetch_json_source(tvshows_url) or []
        if progress.iscanceled(): return

        total_movies = len(movies_to_add)
        total_tvshows = len(tvshows_to_add)
        total_items = total_movies + total_tvshows

        if total_items == 0:
            xbmcgui.Dialog().ok("Aviso", "Nenhum item encontrado nas fontes de dados.")
            return
            
        # Lógica de processamento em lotes (seu código original, sem alterações)
        movies_processed = 0
        if movies_to_add:
            for i in range(0, total_movies, batch_size):
                if progress.iscanceled(): break
                batch = movies_to_add[i:i+batch_size]
                db.add_movies_bulk(batch)
                movies_processed += len(batch)
                percent = int(10 + (movies_processed / total_items) * 85)
                progress.update(percent, f"Adicionando filmes: {movies_processed}/{total_movies}")

        tvshows_processed = 0
        if tvshows_to_add and not progress.iscanceled():
            for i in range(0, total_tvshows, batch_size):
                if progress.iscanceled(): break
                batch = tvshows_to_add[i:i+batch_size]
                db.add_tvshows_bulk(batch)
                tvshows_processed += len(batch)
                total_processed = movies_processed + tvshows_processed
                percent = int(10 + (total_processed / total_items) * 85)
                progress.update(percent, f"Adicionando séries: {tvshows_processed}/{total_tvshows}")

        if not progress.iscanceled():
            progress.update(100, "Finalizando...")
            
            # ✅ CORREÇÃO CRÍTICA: Salva a data e hora após a indexação manual bem-sucedida.
            # Isso sincroniza o serviço automático com a última atualização completa.
            current_check_dt = datetime.now(timezone.utc)
            addon = xbmcaddon.Addon()
            addon.setSetting('last_update_check', current_check_dt.isoformat())
            
            xbmc.sleep(500)
            xbmcgui.Dialog().notification("Sucesso!", "Banco de dados atualizado.", xbmcgui.NOTIFICATION_INFO, 5000)

    except Exception as e:
        xbmc.log(f"[Indexer] Erro durante a indexação: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Ocorreu um erro durante a indexação:\n{e}")
    finally:
        # Garante que a barra de progresso sempre feche
        if 'progress' in locals() and not progress.iscanceled():
            progress.close()