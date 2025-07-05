import os
import json
import time
import xbmc
import xbmcvfs
from xbmcaddon import Addon

ADDON_PATH = xbmcvfs.translatePath(Addon().getAddonInfo('path'))  # Caminho do addon
CACHE_DIR = xbmcvfs.translatePath("special://temp/addon_cache/")  # Diretório do cache
CACHE_TIME = 3600  # Tempo de expiração em segundos (1 hora)


def _get_cache_path(filename):
    """Retorna o caminho completo do arquivo de cache"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)  # Cria o diretório se não existir
    return os.path.join(CACHE_DIR, filename)


def get_cached_json(url, cache_name):
    """Retorna o JSON do cache ou faz o download se estiver expirado"""
    cache_file = _get_cache_path(cache_name)

    # Verifica se o cache existe e se ainda é válido
    if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file)) < CACHE_TIME:
        with open(cache_file, "r", encoding="utf-8") as file:
            return json.load(file)

    # Se o cache expirou, baixa novamente
    json_data = download_json(url)

    if json_data:
        with open(cache_file, "w", encoding="utf-8") as file:
            json.dump(json_data, file, ensure_ascii=False, indent=4)

    return json_data


def download_json(url):
    """Baixa o JSON da URL"""
    import requests

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        xbmc.log(f"Erro ao baixar JSON: {str(e)}", xbmc.LOGERROR)
        return None

def clear_cache():
    """Remove todos os arquivos do diretório de cache"""
    if os.path.exists(CACHE_DIR):
        for arquivo in os.listdir(CACHE_DIR):
            caminho_arquivo = os.path.join(CACHE_DIR, arquivo)
            try:
                os.remove(caminho_arquivo)
            except Exception as e:
                xbmc.log(f"Erro ao remover {caminho_arquivo}: {str(e)}", xbmc.LOGERROR)
        xbmc.executebuiltin("Notification(Clean Cache, Cache limpo com sucesso!, 3000)")
