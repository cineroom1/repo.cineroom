# -*- coding: utf-8 -*-
# Em: resources/lib/utils.py

import xbmcaddon
import xbmc
import xbmcgui
import re
import sys
import json
import urllib.parse
from urllib.parse import urlencode, unquote_plus, quote_plus


ADDON = xbmcaddon.Addon()
BASE_URL = sys.argv[0]

def get_url(**kwargs):
    """Cria uma URL de plugin a partir de um dicionário de parâmetros."""
    return f"{BASE_URL}?{urlencode(kwargs)}"


import xbmcgui

def create_video_item(item_data, media_type, show_data=None):
    # 1. TRATAMENTO DO LABEL
    
    # O TMDB usa 'name' para o título da temporada/episódio, e 'title' para o título do filme.
    # Usamos um fallback robusto.
    label = item_data.get('title') or item_data.get('name', 'Título Desconhecido')
    ep_number = 0
    season_number = item_data.get('season_number', item_data.get('number', 0))

    if media_type == 'episode':
        ep_number = item_data.get('episode_number', 0)
        # Formato de label específico para episódio (Ex: 1x02. Título do Episódio)
        label = f"{season_number}x{ep_number:02d}. {item_data.get('name', '')}"
    
    # Se for temporada (season), o label já foi definido acima (Ex: "Temporada 1")

    li = xbmcgui.ListItem(label=label)

    # --- 2. setInfo com Mapeamento de Chaves TMDB ---
    
    # O TMDB usa 'overview' para sinopse em todos os níveis.
    info = {
        'title': label,
        'plot': item_data.get('synopsis', item_data.get('overview', '')), # Prioriza 'synopsis' (local), senão usa 'overview' (TMDB)
        'premiered': item_data.get('premiered', item_data.get('air_date')), # TMDB usa air_date para série/temporada/episódio
        'mediatype': media_type
    }

    if media_type == 'movie':
        info['year'] = int(item_data.get('year', 0))
        info['duration'] = int(item_data.get('runtime', 0)) * 60
        info['rating'] = float(item_data.get('rating', 0))
        
    elif media_type == 'tvshow':
        info['year'] = int(item_data.get('year', 0))
        info['rating'] = float(item_data.get('rating', 0))
        info['seasoncount'] = item_data.get('season_count', 0)
        info['episodecount'] = item_data.get('episodes_count', 0)
        info['status'] = item_data.get('status')
        info['playcount'] = int(item_data.get('playcount', 0))
        
    elif media_type == 'season':
        # ✅ CORREÇÃO CHAVE: Temporadas usam chaves de avaliação do TMDB
        info['rating'] = float(item_data.get('rating', item_data.get('vote_average', 0.0)))
        info['season'] = season_number
        
    elif media_type == 'episode':
        # ✅ CORREÇÃO CHAVE: Episódios usam chaves de avaliação do TMDB
        info['rating'] = float(item_data.get('rating', item_data.get('vote_average', 0.0)))
        info['season'] = season_number
        info['episode'] = ep_number
        # 'runtime' (do TMDB) é o que define a duração do episódio
        info['duration'] = int(item_data.get('runtime', 0)) * 60

    li.setInfo('video', {k: v for k, v in info.items() if v is not None})

    item_poster_url = item_data.get('poster') or (
        f"https://image.tmdb.org/t/p/w500{item_data.get('poster_path')}" if item_data.get('poster_path') else None
    )
    
    item_backdrop_url = item_data.get('backdrop') or (
        f"https://image.tmdb.org/t/p/w780{item_data.get('backdrop_path')}" if item_data.get('backdrop_path') else None
    )

    art = {
        # Prioridade 1: Poster do item atual (seja série ou temporada)
        'poster': item_poster_url,
        # Prioridade 2: Fanart (geralmente backdrop) do item atual
        'fanart': item_backdrop_url,
        'clearlogo': item_data.get('clearlogo'),
        # Prioridade 3: Se o item for Season/Episode, use a arte da série mãe
        'tvshow.poster': show_data and show_data.get('poster'),
        'tvshow.fanart': show_data and show_data.get('backdrop'),
        'tvshow.clearlogo': show_data and show_data.get('clearlogo')
    }
    
    # Remove entradas vazias antes de setar
    li.setArt({k: v for k, v in art.items() if v})

    # --- 4. Marcável como reproduzível ---
    if media_type in ['movie', 'episode']:
        li.setProperty('IsPlayable', 'true')
        
    return li

    


# Mapeamento das opções de view do Kodi
VIEW_MODE_MAP = {
    'list': 50,
    'poster': 51,
    'iconwall': 52,
    'shift': 53,
    'infowall': 54,
    'widelist': 55,
    'wall': 500,
    'banner': 56,
    'fanart': 502
}

def set_view_mode(content_type, view_setting_key='view_mode', default='wall'):
    """
    Define o View Mode do Kodi de forma robusta e imediata.
    (Versão Corrigida para Performance)
    """
    try:
        view_mode_setting = ADDON.getSetting(view_setting_key)
        
        # Mapeamento do nome para o ID numérico (seu código está correto)
        view_mode_id = VIEW_MODE_MAP.get(view_mode_setting, VIEW_MODE_MAP.get(default, 500))

        # Define o tipo de conteúdo do container (necessário para o Kodi)
        # É importante setar o Content Type ANTES de chamar SetViewMode
        xbmcplugin.setContent(int(sys.argv[1]), content_type) # Certifique-se de que isso é feito em outro lugar, se possível.

        # Apenas executa o comando de View Mode. O Kodi lida com o resto.
        xbmc.executebuiltin(f'Container.SetViewMode({view_mode_id})')
        
        xbmc.log(f"[ViewUtils] View Mode '{view_mode_setting}' ({view_mode_id}) definido para o conteúdo '{content_type}'.", xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f"[ViewUtils] Erro ao tentar setar o view mode: {e}", xbmc.LOGERROR)


# Em: resources/lib/utils.py

def with_view_mode(content, is_menu=False):
    """
    Decorator que define o view_mode DEPOIS que a função termina de popular a lista.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 1. Executa a função original que adiciona os itens
            func(*args, **kwargs)
            
            # 2. Chama a função set_view_mode
            if is_menu:
                set_view_mode(content, view_setting_key='view_mode', default='list')
            else:
                set_view_mode(content) 
        return wrapper
    return decorator


def build_torrentio_config_string():
    """
    Lê as configurações do usuário no settings.xml e monta a string de 
    configuração para a URL do Torrentio.
    """
    config_parts = []

    # --- Filtro de Qualidade ---
    qualities = []
    if ADDON.getSettingBool('filter.quality.4k'): qualities.append('4k')
    if ADDON.getSettingBool('filter.quality.1080p'): qualities.append('1080p')
    if ADDON.getSettingBool('filter.quality.720p'): qualities.append('720p')
    if ADDON.getSettingBool('filter.quality.sd'): qualities.append('sd')
    
    # Se nenhuma qualidade for selecionada, não aplica filtro (mostra tudo)
    if qualities:
        config_parts.append(f"qualityfilter={','.join(qualities)}")

    # --- Critério de Ordenação ---
    # 0=Qualidade (padrão), 1=Seeders, 2=Tamanho
    sort_options = ['quality', 'seeders', 'size']
    sort_index = ADDON.getSettingInt('sort.type')
    sort_type = sort_options[sort_index] if 0 <= sort_index < len(sort_options) else 'quality'
    config_parts.append(f"sort={sort_type}")

    # --- Idiomas ---
    # Supondo que você tenha uma configuração de texto para idiomas, separada por vírgula
    langs = ADDON.getSetting('filter.lang')
    if langs:
        config_parts.append(f"lang={langs.strip()}")

    # --- Excluir Qualidades/Termos ---
    # Supondo que você tenha uma configuração de texto para termos a excluir
    exclude = ADDON.getSetting('filter.exclude')
    if exclude:
        config_parts.append(f"exclude={exclude.strip()}")

    # --- Limite de Resultados ---
    limit = ADDON.getSettingInt('filter.limit')
    if limit > 0:
        config_parts.append(f"limit={limit}")

    # Junta todas as partes com '|'
    # Exemplo de resultado: "qualityfilter=4k,1080p|sort=seeders|lang=dubbed"
    return "|".join(config_parts)