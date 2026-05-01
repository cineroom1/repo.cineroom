# -*- coding: utf-8 -*-
"""
Cineroom Burst - Router
========================
Roteia requisições para os scrapers com threading gerenciado.

Responsabilidades deste módulo:
  - Gerenciar threads (quantidade e timeout vêm das settings via config.py)
  - Aplicar timeout por provider
  - Retornar resultados com prioridade embutida (o chamador não precisa buscá-la)
"""

import xbmc
from concurrent.futures import ThreadPoolExecutor, as_completed


def scrape_provider_sources(provider_name, provider_data, item_data):
    """
    Scrape individual de um provider (modo compatibilidade / uso direto).

    Args:
        provider_name (str): Nome do provider.
        provider_data (dict): Dados do provider (url, configurable, priority…).
        item_data (dict): Dados do item (imdb_id, media_type, season, episode…).

    Returns:
        list[dict]: Lista de fontes encontradas.
    """
    xbmc.log(f"[Burst] Roteando para: {provider_name}", xbmc.LOGINFO)

    season  = item_data.get('season')
    episode = item_data.get('episode')
    sources = []

    try:
        # ── NETCINE ──────────────────────────────────────────────────────────
        if provider_name == "NetCine":
            from ..scrapers import netcine
            sources = netcine.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )
            
        # ── ASSISTIRFILME ──────────────────────────────────────────────────────────
        elif provider_name == "Assistirfilme":
            from ..scrapers import assistirfilme
            sources = assistirfilme.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )      
            
        # ── ANIMESUP ────────────────────────────────────────────────────────────
        elif provider_name == "AnimeSup":
            from ..scrapers import animesup
            sources = animesup.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )    

        # ── STREMIO (link direto) ────────────────────────────────────────────
        elif provider_name in ("Brazuca", "Torrentio", "Fenixflix", "Mico-Leão", "FrostStream", "NebulaStreams"):
            from ..scrapers import stremio
            sources = stremio.scrape(
                provider_url=provider_data.get('url'),
                is_configurable=provider_data.get('configurable', False),
                imdb_id=item_data.get('imdb_id'),
                media_type=item_data.get('media_type'),
                season=season,
                episode=episode,
                item_data=item_data
            )

        # ── ANIMEZEY ────────────────────────────────────────────────────────
        elif provider_name == "AnimeZey":
            from ..scrapers import animezey
            sources = animezey.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data
            )
            
        # ── GOFLIXY ────────────────────────────────────────────────────────
        elif provider_name == "GoFlixy":
            from ..scrapers import goflixy
            sources = goflixy.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data
            )    

        # ── COMANDO TOP ─────────────────────────────────────────────────────
        elif provider_name == "ComandoTop":
            from ..scrapers import comando
            sources = comando.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )

        # ── APACHE TORRENT ──────────────────────────────────────────────────
        elif provider_name == "ApacheTorrent":
            from ..scrapers import apachetorrent
            sources = apachetorrent.scrape_apache(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )

        # ── FILMES MASTER ───────────────────────────────────────────────────
        elif provider_name == "Filmesmaster":
            from ..scrapers import filmesmaster
            sources = filmesmaster.scrape_filmesmaster(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )

        # ── STARCK FILMES ───────────────────────────────────────────────────
        elif provider_name == "StarckFilmes":
            from ..scrapers import starckfilmes
            sources = starckfilmes.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )

        # ── CMD1 ────────────────────────────────────────────────────────────
        elif provider_name == "CMD1":
            from ..scrapers import cmd1
            sources = cmd1.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )

        else:
            xbmc.log(f"[Burst] Provider '{provider_name}' não reconhecido", xbmc.LOGWARNING)
            return []

    except Exception as e:
        import traceback
        xbmc.log(f"[Burst] Erro ao chamar scraper '{provider_name}': {e}", xbmc.LOGERROR)
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        return []

    xbmc.log(f"[Burst] {provider_name}: {len(sources)} fontes encontradas", xbmc.LOGINFO)
    return sources


def scrape_all_sources(item_data, progress_callback=None, max_workers=None):
    """
    Scrape paralelo de todos os providers habilitados.

    Timeout e max_workers são lidos das settings do Burst.
    O parâmetro max_workers pode sobrescrever a setting (retrocompatibilidade),
    mas o ideal é deixá-lo None para usar o valor configurado pelo usuário.

    Args:
        item_data (dict): Dados do item.
        progress_callback (callable): fn(completed, total, provider_name) — opcional.
        max_workers (int | None): Override de threads. None = usa a setting.

    Returns:
        dict[str, dict]: {
            provider_name: {
                "sources":  [list de fontes],
                "priority": int   ← prioridade efetiva (da setting ou default)
            }
        }
    """
    from ..config import get_enabled_providers, get_scraper_timeout, get_max_workers

    active_providers = get_enabled_providers()
    timeout          = get_scraper_timeout()
    workers          = max_workers if max_workers is not None else get_max_workers()

    if not active_providers:
        xbmc.log("[Burst] Nenhum provider habilitado", xbmc.LOGWARNING)
        return {}

    # Filtra providers que precisam de IMDB ID e não o têm
    imdb_id = item_data.get('imdb_id')
    valid_providers = [
        (name, data) for name, data in active_providers
        if name == 'AnimeZey' or imdb_id
    ]

    if not valid_providers:
        xbmc.log("[Burst] Nenhum provider válido após filtro de IMDB", xbmc.LOGWARNING)
        return {}

    total      = len(valid_providers)
    workers    = min(workers, total)  # nunca mais threads que providers

    xbmc.log(
        f"[Burst] Scrape paralelo: {total} providers | "
        f"workers={workers} | timeout={timeout}s",
        xbmc.LOGINFO
    )

    results   = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="BurstScraper") as executor:
        futures = {
            executor.submit(_safe_scrape, name, data, item_data, timeout): (name, data)
            for name, data in valid_providers
        }

        for future in as_completed(futures, timeout=timeout + 5):
            completed += 1
            name, data = futures[future]

            if progress_callback:
                try:
                    progress_callback(completed, total, name)
                except Exception:
                    pass

            try:
                sources = future.result(timeout=timeout + 10)  # margem para encerrar a thread
                results[name] = {
                    "sources":  sources or [],
                    "priority": data.get('priority', 999)
                }
                count = len(sources) if sources else 0
                level = xbmc.LOGINFO if count > 0 else xbmc.LOGDEBUG
                xbmc.log(f"[Burst] {'✅' if count else '⚠️'} {name}: {count} fontes", level)

            except Exception as e:
                xbmc.log(f"[Burst] ❌ {name}: {e}", xbmc.LOGERROR)
                results[name] = {"sources": [], "priority": data.get('priority', 999)}

    success = sum(1 for v in results.values() if v["sources"])
    xbmc.log(f"[Burst] Concluído: {success}/{total} providers com fontes", xbmc.LOGINFO)
    return results


# ────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ────────────────────────────────────────────────────────────────────────────

def _safe_scrape(provider_name, provider_data, item_data, timeout):
    """
    Wrapper de scrape com tratamento de erros.

    NOTA: signal.SIGALRM foi removido pois só funciona na thread principal.
    O ThreadPoolExecutor já aplica timeout via future.result(timeout=...) no
    chamador (scrape_all_sources). Usar signal em threads secundárias lança
    ValueError silencioso que impede o scraper de retornar resultados.
    """
    try:
        sources = scrape_provider_sources(provider_name, provider_data, item_data)
        return sources

    except Exception as e:
        import traceback
        xbmc.log(f"[Burst] Erro em {provider_name}: {e}", xbmc.LOGERROR)
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        return []