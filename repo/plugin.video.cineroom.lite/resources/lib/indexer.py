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
from datetime import datetime, timezone

from .db import db
from .tmdb_api import update_local_popularity

SOURCES = {
    'movies':  'https://cdn.jsdelivr.net/gh/Gael1303/flixroom@main/cineroom/jsons/all_movies.json',
    'tvshows': 'https://cdn.jsdelivr.net/gh/Gael1303/flixroom@main/cineroom/jsons/all_tvshows.json',
}


def _fetch_json_source(url):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data if isinstance(data, list) else None
    except urllib.error.HTTPError:
        pass
    except urllib.error.URLError:
        pass
    except Exception as e:
        xbmc.log(f"[Indexer] Erro inesperado: {e}", xbmc.LOGERROR)
    return None


def check_for_updates_silently(addon_object):
    """
    Verifica novos itens, notifica o usuário e reconstrói o banco completo.
    SEMPRE faz sincronização total para garantir que removidos sejam deletados.
    """

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
    movies_data  = _fetch_json_source(SOURCES['movies'])
    tvshows_data = _fetch_json_source(SOURCES['tvshows'])


    if movies_data is None and tvshows_data is None:
        return 0

    # ← GUARDA AQUI, antes do or []
    if movies_data is None or tvshows_data is None:
        xbmc.log(
            '[Indexer] Download incompleto — uma das listas falhou. '
            'Abortando reconstrução para preservar o banco atual.',
            xbmc.LOGWARNING
        )
        return 0


    movies_data  = movies_data  or []
    tvshows_data = tvshows_data or []

    # 3. Buscar IDs já existentes no banco ANTES de limpar
    try:
        existing_movie_ids  = db.get_all_movie_ids_set()
        existing_tvshow_ids = db.get_all_tvshow_ids_set()
    except Exception as e:
        xbmc.log(f"[Indexer] Falha ao buscar IDs existentes: {e}", xbmc.LOGERROR)
        existing_movie_ids  = set()
        existing_tvshow_ids = set()

    # 4. Identificar itens NOVOS (não existem no banco E adicionados após última verificação)
    new_movies  = []
    new_tvshows = []

    for movie in movies_data:
        tmdb_id = movie.get('tmdb_id')
        if not tmdb_id or tmdb_id in existing_movie_ids:
            continue
        try:
            date_str = movie.get('date_added')
            if not date_str:
                continue
            item_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if item_dt.tzinfo is None:
                item_dt = item_dt.replace(tzinfo=timezone.utc)
            if item_dt >= last_check_dt:
                new_movies.append(movie)
        except (ValueError, TypeError):
            pass

    for show in tvshows_data:
        tmdb_id = show.get('tmdb_id')
        if not tmdb_id or tmdb_id in existing_tvshow_ids:
            continue
        try:
            date_str = show.get('date_added')
            if not date_str:
                continue
            item_dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if item_dt.tzinfo is None:
                item_dt = item_dt.replace(tzinfo=timezone.utc)
            if item_dt >= last_check_dt:
                new_tvshows.append(show)
        except (ValueError, TypeError):
            pass

    # 5. Notificar apenas novos
    new_movies_count  = len(new_movies)
    new_tvshows_count = len(new_tvshows)
    total_new         = new_movies_count + new_tvshows_count

    if total_new > 0:
        itens = []
        if new_movies_count > 0:
            itens.append(f"{new_movies_count} {'Filme' if new_movies_count == 1 else 'Filmes'}")
        if new_tvshows_count > 0:
            itens.append(f"{new_tvshows_count} {'Série' if new_tvshows_count == 1 else 'Séries'}")

        texto = " e ".join(itens) + " encontrado" + ("s" if total_new > 1 else "")

        try:
            icon_path = xbmcvfs.translatePath(addon_object.getAddonInfo('path') + '/icon.png')
        except Exception:
            icon_path = ""

        xbmc.executebuiltin(f'Notification("Cineroom Lite", "{texto}. Atualizando...", 5000, "{icon_path}")')

    

    try:
        db.clear_database()

        if movies_data:
            db.add_movies_bulk(movies_data)

        if tvshows_data:
            db.add_tvshows_bulk(tvshows_data)

            try:
                update_local_popularity()
            except Exception:
                pass

    except Exception as e:
        xbmc.log(f"[Indexer] Erro ao reconstruir banco: {e}", xbmc.LOGERROR)

    # 7. Salvar timestamp da verificação atual
    addon_object.setSetting('last_update_check', current_check_dt.isoformat())

    return total_new


def run_indexer(batch_size=100):
    """
    Atualiza o banco de dados completamente com feedback visual (chamado pelo menu).
    """
    progress = xbmcgui.DialogProgress()
    addon    = xbmcaddon.Addon()

    try:
        progress.create('Cineroom Lite', 'Iniciando atualização do catálogo...')

        # Etapa 1: Limpeza
        progress.update(2, 'Limpando banco de dados antigo...')
        db.clear_database()
        if progress.iscanceled():
            return

        # Etapa 2: Download
        progress.update(5, 'Baixando listas de conteúdo...')
        movies_to_add  = _fetch_json_source(SOURCES['movies'])  or []
        tvshows_to_add = _fetch_json_source(SOURCES['tvshows']) or []

        total_movies  = len(movies_to_add)
        total_tvshows = len(tvshows_to_add)
        total_items   = total_movies + total_tvshows

        if total_items == 0:
            xbmcgui.Dialog().ok("Aviso", "Nenhum item encontrado nas fontes de dados.")
            return

        # Etapa 3: Filmes
        movies_processed = 0
        for i in range(0, total_movies, batch_size):
            if progress.iscanceled():
                return
            batch = movies_to_add[i:i + batch_size]
            db.add_movies_bulk(batch)
            movies_processed += len(batch)
            percent = int(10 + (movies_processed / total_items) * 80)
            progress.update(percent, f"Adicionando filmes: {movies_processed}/{total_movies}")

        # Etapa 4: Séries
        tvshows_processed = 0
        for i in range(0, total_tvshows, batch_size):
            if progress.iscanceled():
                return
            batch = tvshows_to_add[i:i + batch_size]
            db.add_tvshows_bulk(batch)
            tvshows_processed += len(batch)
            total_done = movies_processed + tvshows_processed
            percent = int(10 + (total_done / total_items) * 80)
            progress.update(percent, f"Adicionando séries: {tvshows_processed}/{total_tvshows}")

        # Etapa 5: TMDB
        if not progress.iscanceled():
            progress.update(92, "Sincronizando capas e tendências (TMDB)...")
            try:
                update_local_popularity()
            except Exception:
                pass

        # Etapa 6: Finalização
        if not progress.iscanceled():
            progress.update(100, "Catalogação concluída com sucesso!")
            addon.setSetting('last_update_check', datetime.now(timezone.utc).isoformat())
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
        except Exception:
            pass

        xbmc.executebuiltin("Dialog.Close(busydialog)")