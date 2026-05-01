# -*- coding: utf-8 -*-
# resources/lib/scrapers/stremio.py - VERSÃO OTIMIZADA

import requests
import xbmc
from .session import USER_AGENT
from .utils import get_anime_search_patterns

def scrape(provider_url, is_configurable, imdb_id, media_type, season, episode, item_data=None):
    """
    Scraper Stremio unificado e otimizado.
    
    Melhorias:
    - Validação centralizada de parâmetros
    - Construção inteligente de URLs
    - Deduplicação eficiente
    - Logs concisos
    """
    
    # ========================================
    # 1. VALIDAÇÃO E NORMALIZAÇÃO
    # ========================================
    if not provider_url:
        return []
    
    # Normaliza season/episode APENAS se não forem None
    season = _safe_int(season)
    episode = _safe_int(episode)
    
    # Valida requisitos mínimos
    if not imdb_id and "animezey" not in provider_url.lower():
        xbmc.log(f"[Stremio] Sem IMDB ID para {provider_url}", xbmc.LOGDEBUG)
        return []
    
    # ========================================
    # 2. CONSTRUÇÃO DE ENDPOINTS
    # ========================================
    endpoints = _build_endpoints(media_type, imdb_id, season, episode)
    
    if not endpoints:
        xbmc.log(f"[Stremio] Nenhum endpoint válido para {media_type}", xbmc.LOGWARNING)
        return []
    
    # ========================================
    # 3. CONFIGURAÇÃO TORRENTIO
    # ========================================
    config_prefix = ""
    if is_configurable:
        try:
            from ..utils import build_torrentio_config_string
            config_prefix = build_torrentio_config_string()
        except Exception as e:
            xbmc.log(f"[Stremio] Config error: {e}", xbmc.LOGDEBUG)
    
    # ========================================
    # 4. BUSCA E DEDUPLICAÇÃO
    # ========================================
    streams = []
    seen_ids = set()
    
    for endpoint in endpoints:
        url = f"{provider_url}/{config_prefix}{endpoint}" if config_prefix else f"{provider_url}{endpoint}"
        
        found = _fetch_streams(url)
        if not found:
            continue
        
        # Deduplica e adiciona release_title
        for stream in found:
            stream_id = stream.get('url') or stream.get('infoHash')
            
            if stream_id and stream_id in seen_ids:
                continue
            
            # Adiciona título de lançamento se não existir
            if 'release_title' not in stream:
                stream['release_title'] = _generate_release_title(
                    item_data, media_type, season, episode
                )
            
            streams.append(stream)
            
            if stream_id:
                seen_ids.add(stream_id)
    
    xbmc.log(f"[Stremio] {len(streams)} streams de {provider_url.split('/')[2]}", xbmc.LOGINFO)
    return streams


# ============================================
# FUNÇÕES AUXILIARES (INTERNAS)
# ============================================

def _safe_int(value):
    """Converte para int de forma segura."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        xbmc.log(f"[Stremio] Conversão inválida: {value}", xbmc.LOGDEBUG)
        return None


def _build_endpoints(media_type, imdb_id, season, episode):
    """
    Constrói lista de endpoints para tentar.
    
    Retorna:
        list: URLs relativas (ex: ["/stream/movie/tt1234.json"])
    """
    endpoints = []
    
    if media_type == 'movie':
        if imdb_id:
            endpoints.append(f"/stream/movie/{imdb_id}.json")
    
    elif media_type == 'tvshow':
        if season is None or episode is None:
            return []
        
        if not imdb_id:
            return []
        
        # Usa padrões de busca de anime (ex: S01:E01, S1:E1)
        patterns = get_anime_search_patterns(season, episode)
        
        for s, e in patterns:
            endpoints.append(f"/stream/series/{imdb_id}:{s}:{e}.json")
    
    return endpoints


def _fetch_streams(url):
    """
    Faz request e retorna lista de streams.
    
    Returns:
        list: Streams encontrados ou lista vazia
    """
    try:
        response = requests.get(
            url, 
            headers={'User-Agent': USER_AGENT}, 
            timeout=60  # Reduzido de 15s para 10s
        )
        response.raise_for_status()
        
        data = response.json()
        streams = data.get('streams', [])
        
        if streams:
            xbmc.log(f"[Stremio] ✓ {len(streams)} em {url.split('/')[-1]}", xbmc.LOGDEBUG)
        
        return streams
        
    except requests.Timeout:
        xbmc.log(f"[Stremio] Timeout: {url}", xbmc.LOGWARNING)
    except requests.RequestException as e:
        xbmc.log(f"[Stremio] Erro HTTP: {e}", xbmc.LOGDEBUG)
    except ValueError:
        xbmc.log(f"[Stremio] JSON inválido: {url}", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"[Stremio] Erro inesperado: {e}", xbmc.LOGERROR)
    
    return []


def _generate_release_title(item_data, media_type, season, episode):
    """
    Gera título de lançamento padrão.
    
    Ex: "Breaking Bad S01E05" ou "Interstellar"
    """
    if not item_data:
        if media_type == 'tvshow' and season is not None and episode is not None:
            return f"S{season:02d}E{episode:02d}"
        return "Desconhecido"
    
    title = item_data.get('title', 'Desconhecido')
    
    if media_type == 'tvshow' and season is not None and episode is not None:
        return f"{title} S{season:02d}E{episode:02d}"
    
    return title