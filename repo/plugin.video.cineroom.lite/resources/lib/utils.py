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


def create_video_item(item_data, media_type, show_data=None):
    label = item_data.get('title', 'Título Desconhecido')
    ep_number = 0
    season_number = 0

    if media_type == 'episode':
        season_number = int(item_data.get('season_number', 0))
        ep_number_str = item_data.get('number', '0')
        ep_number = int(ep_number_str) if ep_number_str.isdigit() else 0
        label = f"{season_number}x{ep_number:02d}. {item_data.get('title', '')}"

    li = xbmcgui.ListItem(label=label)

    # --- 1. setInfo simplificado ---
    info = {
        'title': label,
        'plot': item_data.get('synopsis', ''),
        'premiered': item_data.get('premiered'),
        'mediatype': media_type
    }

    if media_type == 'movie':
        info['year'] = int(item_data.get('year', 0))
        info['duration'] = int(item_data.get('runtime', 0)) * 60
        info['rating'] = float(item_data.get('rating', 0))
    elif media_type in ['tvshow', 'season', 'episode']:
        info['year'] = int(item_data.get('year', 0))
        info['rating'] = float(item_data.get('rating', 0)) if media_type == 'tvshow' else None

    li.setInfo('video', {k: v for k, v in info.items() if v is not None})

    # --- 2. Arte (pode remover fanart/clearlogo para acelerar) ---
    art = {
        'poster': item_data.get('poster') or (show_data and show_data.get('poster')),
        'thumb': item_data.get('poster') or (show_data and show_data.get('poster')),
        'fanart': item_data.get('backdrop') or (show_data and show_data.get('backdrop')),
        'clearlogo': item_data.get('clearlogo') or (show_data and show_data.get('clearlogo'))
    }
    li.setArt({k: v for k, v in art.items() if v})

    # --- 3. Marcável como reproduzível ---
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
    Define o View Mode do Kodi de forma robusta, aguardando o container estar pronto.
    
    :param content_type: O tipo de conteúdo esperado (ex: 'movies', 'tvshows', 'genres').
    :param view_setting_key: O ID da configuração a ser lida para o view mode.
    :param default: O view mode padrão caso a configuração falhe.
    """
    try:
        view_mode_setting = ADDON.getSetting(view_setting_key)
        view_mode_id = VIEW_MODE_MAP.get(view_mode_setting, VIEW_MODE_MAP.get(default, 500))

        # Dá ao Kodi um momento inicial para começar a processar a lista
        xbmc.sleep(150)
        
        timeout = 0
        # Loop de espera: Continua até o conteúdo do container ser o que esperamos
        while xbmc.getInfoLabel('Container.Content') != content_type:
            xbmc.sleep(20) # Espera 20ms antes de checar de novo
            timeout += 20
            if timeout >= 3000: # Desiste após 3 segundos
                xbmc.log(f"[ViewUtils] Timeout! Container.Content não se tornou '{content_type}'.", xbmc.LOGWARNING)
                return

        # Agora que temos certeza de que a lista está na tela, definimos a visualização
        xbmc.executebuiltin(f'Container.SetViewMode({view_mode_id})')
        xbmc.log(f"[ViewUtils] View Mode '{view_mode_setting}' ({view_mode_id}) definido para o conteúdo '{content_type}'.", xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f"[ViewUtils] Erro ao tentar setar o view mode: {e}", xbmc.LOGERROR)


# Em: resources/lib/utils.py

def with_view_mode(content, is_menu=False):
    """
    Decorator que define o view_mode DEPOIS que a função termina de popular a lista.
    
    :param content: O tipo de conteúdo que a função está listando (ex: 'movies', 'genres').
    :param is_menu: Se True, força o modo 'list'.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 1. Executa a função original que adiciona os itens
            func(*args, **kwargs)
            
            # 2. Chama nossa nova e robusta função set_view_mode
            if is_menu:
                set_view_mode(content, view_setting_key='view_mode', default='list') # Usa 'list' como padrão para menus
            else:
                set_view_mode(content) # Usa as configurações do addon
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