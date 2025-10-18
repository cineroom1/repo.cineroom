# Em: resources/lib/scraper.py

import requests
import json
import xbmc
from .utils import build_torrentio_config_string

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Esta é a definição CORRETA da função, que aceita 6 argumentos.
def scrape_provider_sources(provider_url, imdb_id, is_configurable, media_type='movie', season=None, episode=None):
    """
    Busca fontes em um provedor, aplicando configuração apenas se o provedor suportar.
    """
    if not imdb_id:
        xbmc.log(f"[{provider_url}] Erro: IMDB ID não fornecido.", xbmc.LOGERROR)
        return []

    # Define o caminho base do stream
    if media_type == 'movie':
        url_path = f"/stream/movie/{imdb_id}.json"
    elif media_type == 'series' and season is not None and episode is not None:
        url_path = f"/stream/series/{imdb_id}:{season}:{episode}.json"
    else:
        xbmc.log(f"[{provider_url}] Dados insuficientes para a busca.", xbmc.LOGERROR)
        return []

    # Só monta a URL com a config se o provedor permitir
    if is_configurable:
        torrentio_config = build_torrentio_config_string()
        full_url = f"{provider_url}/{torrentio_config}{url_path}"
    else:
        # Para provedores não configuráveis, usa a URL limpa
        full_url = f"{provider_url}{url_path}"

    xbmc.log(f"Fazendo requisição para: {full_url}", xbmc.LOGINFO)

    try:
        response = requests.get(full_url, headers={'User-Agent': USER_AGENT}, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get('streams', [])
    except requests.exceptions.RequestException as e:
        xbmc.log(f"[{provider_url}] Erro ao buscar fontes: {e}", xbmc.LOGERROR)
        return []
    except json.JSONDecodeError:
        xbmc.log(f"[{provider_url}] Erro: A resposta não era um JSON válido.", xbmc.LOGERROR)
        return []