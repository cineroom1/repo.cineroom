# -*- coding: utf-8 -*-
"""
Busca e seleção de fontes de vídeo
"""
import sys
import xbmc
import xbmcgui
import xbmcaddon
import threading
import time
from .processors import process_single_stream
from ..resolver import CineroomResolverWindow
from .. import scrapers

ADDON = xbmcaddon.Addon()

# Configuração de providers
PROVIDERS = {
    "Brazuca": {
        "url": "https://94c8cb9f702d-brazuca-torrents.baby-beamup.club",
        "configurable": False,
        "priority": 3
    },
    "AnimeZey": {
        "url": "https://1.animezey23112022.workers.dev", 
        "configurable": False, 
        "priority": 1
    },
    "CDFlix": {
        "url": "https://cdflix.cdteam.xyz/%7B%22language%22%3A%22pt_br%22%7D",
        "configurable": False,
        "priority": 2
    },
    "StarckFilmes": {
        "url": "https://www.starckfilmes-v8.com",
        "configurable": False,
        "priority": 1
    },
    "SkyFlix": {
        "url": "https://da5f663b4690-skyflixfork16.baby-beamup.club",
        "configurable": False, 
        "priority": 3
    },
    "Torrentio": {
        "url": "https://torrentio.strem.fun/providers=comando,bludv,micoleaodublado,yts,nyaasi,1337x%7Clanguage=portuguese,english,japanese",
        "configurable": False,
        "priority": 2
    },
    "ComandoTop": {
        "url": "https://comandofilmestop.site",
        "configurable": False,
        "priority": 3
    },
    "ApacheTorrent": {
        "url": "https://apachetorrent.com",
        "configurable": False,
        "priority": 3
    },
    "Filmesmaster": {
        "url": "https://filmesmaster.org/",
        "configurable": False,
        "priority": 4
    },
    "Mico-Leão": {
        "url": "https://27a5b2bfe3c0-stremio-brazilian-addon.baby-beamup.club",
        "configurable": False,
        "priority": 5  
    }
}


def find_and_play_sources(item_data, autoplay=False, season=None, episode=None):
    """
    Busca fontes e exibe diálogo de seleção ou autoplay
    """
    media_type = item_data.get('media_type')
    imdb_id = item_data.get('imdb_id')
    
    if not media_type:
        xbmcgui.Dialog().ok("Erro", "Dados insuficientes.")
        return

    # === BUSY DIALOG ===
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')

    provider_results = {}
    completed = 0
    lock = threading.Lock()
    start_time = time.time()
    pDialog = None

    # === THREAD WORKER ===
    def fetch_thread(name, data):
        nonlocal completed
        try:
            found = scrapers.scrape_provider_sources(name, data, item_data)
            if found:
                with lock:
                    provider_results[name] = found
        except:
            pass
        finally:
            with lock:
                completed += 1

    # === INICIA THREADS ===
    active_providers = [
        (n, d) for n, d in PROVIDERS.items()
        if ADDON.getSettingBool(f"provider.{n.lower()}.enabled")
    ]

    threads = []
    total_threads = len(active_providers)

    for name, data in active_providers:
        # AnimeZey não precisa IMDB, outros sim
        if name != 'AnimeZey' and not imdb_id:
            with lock:
                completed += 1
            continue

        t = threading.Thread(target=fetch_thread, args=(name, data))
        t.start()
        threads.append(t)

    # === MONITORA PROGRESSO ===
    while completed < total_threads:
        elapsed = time.time() - start_time

        # Mostra progress apenas se demorar
        if elapsed > 0.7 and not pDialog:
            pDialog = xbmcgui.DialogProgressBG()
            pDialog.create("CR [COLOR cyan]Lite[/COLOR]", "Buscando fontes...")

        if pDialog:
            percent = int((completed / total_threads) * 100)
            pDialog.update(percent, message=f"Consultando providers ({completed}/{total_threads})")

        xbmc.sleep(100)

    for t in threads:
        t.join()

    if pDialog:
        pDialog.close()

    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')

    # === CONSOLIDAÇÃO ===
    final_list = []
    seen_urls = set()

    # Streams locais primeiro
    for s in item_data.get('streams', []):
        p = process_single_stream(s, is_local=True, item_data=item_data)
        if p:
            final_list.append(p)
            seen_urls.add(p['url'])

    # Streams de providers
    for name, data in active_providers:
        if name in provider_results:
            for s in provider_results[name]:
                p = process_single_stream(s, False, name, data.get('priority', 999), item_data)
                if p and p['url'] not in seen_urls:
                    final_list.append(p)
                    seen_urls.add(p['url'])

    if not final_list:
        xbmcgui.Dialog().ok("Aviso", "Nenhuma fonte encontrada.")
        return

    # Ordena: prioridade > qualidade > seeders
    final_list.sort(key=lambda x: (x['p_priority'], -x['q_score'], -x['s_score']))

    # === SELEÇÃO/AUTOPLAY ===
    url_escolhida = None

    if ADDON.getSettingBool('playback.autoplay'):
        url_escolhida = final_list[0]['url']
    else:
        try:
            from resources.lib.dialog.dialogs import DialogSelecaoFontes
            dialog = DialogSelecaoFontes(
                'dialog_cineroom_fullscreen.xml',
                ADDON.getAddonInfo('path'),
                fontes=final_list,
                item_data=item_data
            )
            dialog.doModal()
            url_escolhida = dialog.escolha
            del dialog
        except:
            labels = [
                f"{s['quality_label']} | {s['seeders_label']} | {s['size']} | {s['provider']}"
                for s in final_list
            ]
            sel = xbmcgui.Dialog().select(f"Fontes: {final_list[0]['display_title']}", labels)
            if sel >= 0:
                url_escolhida = final_list[sel]['url']

    # === RESOLVER ===
    if url_escolhida:
        resolver = CineroomResolverWindow(
            "resolver_window.xml",
            ADDON.getAddonInfo('path'),
            source_url=url_escolhida,
            item_data=item_data,
            handle=int(sys.argv[1])
        )
        resolver.doModal()