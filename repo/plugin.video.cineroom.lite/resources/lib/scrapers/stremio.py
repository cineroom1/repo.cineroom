# Em: resources/lib/scrapers/stremio.py
import requests
import json
import xbmc

# --- Imports do Pacote ---
from .session import USER_AGENT
from .utils import get_anime_search_patterns

# --- Scraper Stremio ---
# ####################################################################
# (✅ REFATORADO: Agora usa a função helper get_anime_search_patterns)
# ####################################################################
# Nota: Renomeado de _scrape_stremio_sources para 'scrape'
def scrape(provider_url, is_configurable, imdb_id, media_type, season, episode):
    """
    Busca fontes Stremio, agora com lógica de "split-cour" centralizada.
    """
    if not provider_url: return []
    if not imdb_id and "animezey" not in provider_url.lower(): return []
    
    url_paths_to_try = []

    if media_type == 'movie':
        if imdb_id: url_paths_to_try.append(f"/stream/movie/{imdb_id}.json")
    
    elif media_type == 'tvshow' and season is not None and episode is not None:
        
        # ✅ LÓGICA CENTRALIZADA (Importada de utils.py)
        # Gera os padrões: Ex: [(1, 21), (2, 9), (2, 8)]
        search_patterns = get_anime_search_patterns(season, episode)
        
        for s, e in search_patterns:
            if imdb_id:
                new_path = f"/stream/series/{imdb_id}:{s}:{e}.json"
                url_paths_to_try.append(new_path)
                xbmc.log(f"[stremio.scrape] Adicionando busca: {new_path}", xbmc.LOGDEBUG)

    
    if not url_paths_to_try:
        xbmc.log(f"[stremio.scrape] Nenhum URL path válido gerado.", xbmc.LOGWARNING)
        return []

    # Tenta obter a config do Torrentio (se aplicável)
    torrentio_config = ""
    if is_configurable:
        try:
            # Esta função deve estar definida em outro lugar do seu addon (ex: settings.py ou no __init__.py principal)
            # Se não estiver, esta exceção NameError irá tratar disso.
            torrentio_config = build_torrentio_config_string() 
        except NameError:
             xbmc.log("[stremio.scrape] build_torrentio_config_string() não encontrada, usando URL direta.", xbmc.LOGWARNING)
             torrentio_config = ""

    all_streams = []
    seen_stream_ids = set() # Para desduplicar (baseado em URL ou infoHash)

    # Loop por cada path (ex: ":1:21.json" e ":2:9.json")
    for url_path in url_paths_to_try:
        if is_configurable:
            full_url = f"{provider_url}/{torrentio_config}{url_path}"
        else:
            full_url = f"{provider_url}{url_path}"

        xbmc.log(f"[stremio.scrape] Fazendo requisição para: {full_url}", xbmc.LOGINFO)
        try:
            response = requests.get(full_url, headers={'User-Agent': USER_AGENT}, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            streams = data.get('streams', [])
            if streams:
                xbmc.log(f"[stremio.scrape] ✅ Encontrados {len(streams)} streams de {full_url}", xbmc.LOGINFO)
                for stream in streams:
                    # Desduplicar baseado na URL (links magnet/http) ou infoHash
                    stream_id = stream.get('url') or stream.get('infoHash')
                    if stream_id and stream_id not in seen_stream_ids:
                        all_streams.append(stream)
                        seen_stream_ids.add(stream_id)
                    elif not stream_id:
                        # Se não tiver ID, adiciona de qualquer forma (pode ser link desprotegido)
                         all_streams.append(stream)
            
        except requests.exceptions.RequestException as e:
            # Não é um ERRO fatal, apenas uma das tentativas falhou.
            xbmc.log(f"[{provider_url}] Erro Stremio (Ignorado): {e}", xbmc.LOGWARNING)
        except json.JSONDecodeError:
            xbmc.log(f"[{provider_url}] Erro Stremio (Ignorado): Resposta JSON inválida.", xbmc.LOGWARNING)

    xbmc.log(f"[stremio.scrape] Total de streams únicos encontrados: {len(all_streams)}", xbmc.LOGINFO)
    # Retorna os streams brutos. A normalização é feita no navigation.py
    return all_streams