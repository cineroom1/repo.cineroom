import urllib.request
import urllib.parse
import json
import xbmcplugin
import xbmcgui
import sys
import os
import xbmcaddon
import time
import base64

from resources.lib.encryption_utils import obfuscate_string, deobfuscate_string
from urllib.parse import urlencode, parse_qsl
from resources.action.donation_window import DonationDialog
from resources.action.telegram_window import TelegramDialog
from resources.lib.configs.urls import data_feed
from resources.lib.utils import get_all_videos, VIDEO_CACHE, FILTERED_CACHE
from resources.lib.counter import (
    get_firebase_counters,
    update_firebase_counter,
    get_decayed_counters,
)

# Configurações do plugin
URL = sys.argv[0]
HANDLE = int(sys.argv[1])

# --- Estrutura Padrão dos Contadores ---
DEFAULT_COUNTERS = {
    "Filmes": 5,
    "Séries": 5,
    "Explorar": 5,
    "Visitas_menu": 1,
    "last_updated": ""
}

def get_url(**kwargs):
    """
    Cria uma URL para chamar o plugin recursivamente a partir dos argumentos fornecidos.
    """
    return '{}?{}'.format(URL, urlencode(kwargs))

def check_maintenance_status(menu):
    """
    Verifica se o addon está em manutenção.
    Retorna True se o status for "off", caso contrário, retorna False.
    """
    if menu and isinstance(menu, list) and len(menu) > 0:
        first_item = menu[0]
        if isinstance(first_item, dict) and first_item.get("status", "").lower() == "off":
            return True
    return False

import xbmc
import xbmcgui

def get_menu(force_refresh=False):
    """
    Obtém o menu principal com sistema de cache (validade de 7 dias)
    """
    cache_key = "main_menu_data"
    
    # Verificar cache primeiro (se não for force_refresh)
    if not force_refresh:
        cached_data_string = VIDEO_CACHE.get(cache_key)
        if cached_data_string:
            try:
                # DESERIALIZE a string de volta para uma lista Python
                menu_list = json.loads(cached_data_string)
                xbmc.log("[CACHE] Menu carregado do cache (validade: 7 dias)", xbmc.LOGDEBUG)
                return menu_list
            except json.JSONDecodeError as e:
                xbmc.log(f"[ERROR] JSON inválido no cache do menu: {str(e)}. Deletando cache corrompido.", xbmc.LOGERROR)
                VIDEO_CACHE.delete(cache_key) # Deleta cache corrompido para tentar buscar novamente
            except Exception as e:
                xbmc.log(f"[ERROR] Erro ao carregar menu do cache: {str(e)}. Deletando cache.", xbmc.LOGERROR)
                VIDEO_CACHE.delete(cache_key) # Deleta cache em caso de outros erros

    try:
        xbmc.log("[NETWORK] Buscando dados do menu...", xbmc.LOGDEBUG)
        
        req = urllib.request.Request(
            data_feed,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        
        with urllib.request.urlopen(req) as response:
            # --- Lógica de tratamento de resposta da rede ---
            # (Mantenha seu código existente para status 429, 200, resposta vazia, etc.)
            
            if response.status == 429:
                xbmcgui.Dialog().notification('Aviso', 'Muitas requisições. Tente novamente mais tarde.', xbmcgui.NOTIFICATION_WARNING)
                # Tenta obter do cache expirado como fallback, mas ainda precisa deserializar
                expired_cache_string = VIDEO_CACHE.get(cache_key, ignore_expiry=True)
                if expired_cache_string:
                    try:
                        return json.loads(expired_cache_string)
                    except json.JSONDecodeError:
                        xbmc.log("[ERROR] Cache expirado do menu corrompido.", xbmc.LOGERROR)
                return None
            
            if response.status != 200:
                xbmc.log(f"[ERROR] Status code: {response.status}", xbmc.LOGERROR)
                expired_cache_string = VIDEO_CACHE.get(cache_key, ignore_expiry=True)
                if expired_cache_string:
                    try:
                        return json.loads(expired_cache_string)
                    except json.JSONDecodeError:
                        xbmc.log("[ERROR] Cache expirado do menu corrompido.", xbmc.LOGERROR)
                return []
                
            raw_data = response.read().decode('utf-8')
            if not raw_data:
                xbmc.log("[ERROR] Resposta vazia do servidor", xbmc.LOGERROR)
                expired_cache_string = VIDEO_CACHE.get(cache_key, ignore_expiry=True)
                if expired_cache_string:
                    try:
                        return json.loads(expired_cache_string)
                    except json.JSONDecodeError:
                        xbmc.log("[ERROR] Cache expirado do menu corrompido.", xbmc.LOGERROR)
                return []
                
            try:
                menu = json.loads(raw_data) # 'menu' é uma LISTA aqui
            except json.JSONDecodeError as e:
                xbmc.log(f"[ERROR] JSON inválido: {str(e)}", xbmc.LOGERROR)
                expired_cache_string = VIDEO_CACHE.get(cache_key, ignore_expiry=True)
                if expired_cache_string:
                    try:
                        return json.loads(expired_cache_string)
                    except json.JSONDecodeError:
                        xbmc.log("[ERROR] Cache expirado do menu corrompido.", xbmc.LOGERROR)
                return []
            
            if not isinstance(menu, list):
                xbmc.log("[ERROR] Estrutura de dados inválida (esperava lista)", xbmc.LOGERROR)
                expired_cache_string = VIDEO_CACHE.get(cache_key, ignore_expiry=True)
                if expired_cache_string:
                    try:
                        return json.loads(expired_cache_string)
                    except json.JSONDecodeError:
                        xbmc.log("[ERROR] Cache expirado do menu corrompido.", xbmc.LOGERROR)
                return []
            
            # --- PONTO CRÍTICO DE MUDANÇA: Serializar a lista para JSON string antes de salvar ---
            menu_json_string = json.dumps(menu, ensure_ascii=False)
            VIDEO_CACHE.set(cache_key, menu_json_string, expiry_hours=24) # Salva a STRING
            xbmc.log("[CACHE] Menu armazenado com sucesso", xbmc.LOGDEBUG) # Este log pode permanecer
            
            return menu # Retorna a LISTA para o chamador
            
    except Exception as e:
        xbmc.log(f"[ERROR] {str(e.__class__.__name__)}: {str(e)}", xbmc.LOGERROR)
        # Tenta obter do cache expirado como fallback, mas ainda precisa deserializar
        expired_cache_string = VIDEO_CACHE.get(cache_key, ignore_expiry=True)
        if expired_cache_string:
            try:
                return json.loads(expired_cache_string)
            except json.JSONDecodeError:
                xbmc.log("[ERROR] Cache expirado do menu corrompido.", xbmc.LOGERROR)
        return []

def list_menu():
    """Exibe o menu principal com contadores atualizados"""
    xbmcplugin.setPluginCategory(HANDLE, 'Menu Principal')
    menu = get_menu()
    if not menu:
        return

    counters = get_firebase_counters()

    addon = xbmcaddon.Addon()
    last_access = addon.getSetting('last_menu_access')
    current_date = time.strftime('%Y-%m-%d')

    if last_access != current_date:
        new_count = update_firebase_counter("Visitas_menu")
        if new_count is not None:
            counters["Visitas_menu"] = new_count
            addon.setSetting('last_menu_access', current_date)

    settings_map = {
        "Filmes": addon.getSettingBool('mostrar_filmes'),
        "Séries": addon.getSettingBool('mostrar_series'),
        "Pesquisar": addon.getSettingBool('mostrar_pesquisar'),
        "Canais": addon.getSettingBool('mostrar_canais'),
        "Explorar": addon.getSettingBool('mostrar_explorar'),
        "Minha_Lista": addon.getSettingBool('mostrar_favoritos')
    }

    for index, menu_info in enumerate(menu[1:], start=1):
        title = menu_info.get("menu_title", "")
        key = menu_info.get("menu_key", "")

        if not settings_map.get(key, True):
            continue

        status = menu_info.get("status", "").lower()
        plot = menu_info.get("description", "")

        if status == "off":
            label = f"[COLOR red]•[/COLOR] {title} - (Manutenção)"
            list_item = xbmcgui.ListItem(label=label)
            list_item.setInfo('video', {'title': f'{title} - Indisponível', 'plot': 'Em manutenção'})
        else:
            label = f"{title}"  # Texto simples sem formatação de cor
            list_item = xbmcgui.ListItem(label=label)
            list_item.setInfo('video', {'title': title, 'plot': plot})

        list_item.setArt({
            'icon': menu_info.get('poster', ''),
            'fanart': menu_info.get('fanart', ''),
            'thumb': menu_info.get('poster', '')
        })

        if 'subcategorias' in menu_info:
            url = get_url(action='list_subcategories', menu_index=index)
        elif isinstance(menu_info.get("externallink"), list):
            url = get_url(action='list_sub_external_links', menu_index=index)
        else:
            action = menu_info.get('action', '')
            external_link = menu_info.get('externallink', '')
            url = get_url(action=action, external_link=external_link) if external_link else get_url(action=action)

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def list_subcategories(menu_index):
    """Lista subcategorias com cache"""
    menu = get_menu()
    if not menu or menu_index >= len(menu):
        return
    
    subcategories = menu[menu_index].get('subcategorias', [])
    if not subcategories:
        xbmcgui.Dialog().ok('Erro', 'Subcategorias não encontradas!')
        return
    
    category_key = menu[menu_index].get("menu_key", "")
    
    # Atualiza contador no Firebase
    if category_key in ["Filmes", "Séries", "Explorar"]:
        new_count = update_firebase_counter(category_key)
    
    xbmcplugin.setPluginCategory(HANDLE, menu[menu_index].get("menu_title", "Subcategorias"))
    xbmcplugin.setContent(HANDLE, "files")

    for subcategory in subcategories:
        label = f"{subcategory['categories']}"
            
        list_item = xbmcgui.ListItem(label=label)
        list_item.setArt({
            'icon': subcategory.get('poster', ''),
            'fanart': subcategory.get('backdrop', menu[menu_index].get('fanart', ''))
        })
        
        info = {
            'title': subcategory['categories'],
            'plot': subcategory.get('description', '')
        }
        
        if subcategory.get('year'):
            info['year'] = subcategory['year']
            
        list_item.setInfo('video', info)
        
        if 'action' in subcategory:
            url = get_url(action=subcategory['action'])
        else:
            url = get_url(
                action='list_videos',
                external_link=subcategory.get('externallink'),
                sort_method=subcategory.get('sort_method', '')
            )

        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)



def list_sub_external_links(menu_index):
    """
    Exibe sublistas de canais com base nos links múltiplos.
    Suporta também a opção 'search(Pesquisar Canal)'.
    """
    menu = get_menu()
    item = menu[menu_index]

    links = item.get('externallink', [])
    if not links:
        xbmcgui.Dialog().ok("Erro", "Nenhum link externo encontrado.")
        return

    for link in links:
        if "(" in link and ")" in link:
            base_url = link.split("(")[0].strip()
            nome = link.split("(")[-1].replace(")", "").strip()
        else:
            base_url = link.strip()
            nome = "Lista"

        if base_url.lower() == "search":
            search_url = f"{sys.argv[0]}?action=search_canais"
            search_item = xbmcgui.ListItem(label=f"[COLOR yellow]{nome}[/COLOR]")
            search_item.setArt({
                'icon': "https://archive.org/download/em_alta/search.png",
                'fanart': item.get('fanart', '')
            })
            xbmcplugin.addDirectoryItem(HANDLE, search_url, search_item, isFolder=True)
            continue
        # Só executa daqui pra baixo se não for 'search'
        quoted_url = urllib.parse.quote_plus(base_url)
    
       # Item para atualizar a lista
        refresh_url = f"{sys.argv[0]}?action=refresh&external_link={quoted_url}"
        refresh_item = xbmcgui.ListItem(label=f'[COLOR blue][B]- Atualizar Lista ({nome})[/B][/COLOR]')
        refresh_item.setArt({
            'icon': "https://archive.org/download/em_alta/ChatGPT%20Image%205%20de%20abr.%20de%202025%2C%2014_35_24.png",
            'fanart': item.get('fanart', '')
        })
        xbmcplugin.addDirectoryItem(HANDLE, refresh_url, refresh_item, isFolder=True)

        # Cria item normal
        list_item = xbmcgui.ListItem(label=nome)
        list_item.setArt({
            'icon': item.get('poster', ''),
            'fanart': item.get('fanart', '')
        })
        list_item.setInfo('video', {'title': nome})

        url = get_url(action='list_canais', external_link=base_url)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

def show_donation():
    dialog = DonationDialog("DonationDialog.xml", xbmcaddon.Addon().getAddonInfo("path"), "Default", "720p")
    dialog.doModal()
    del dialog
    
def show_telegram():
    dialog = TelegramDialog("TelegramDialog.xml", xbmcaddon.Addon().getAddonInfo("path"), "Default", "720p")
    dialog.doModal()
    del dialog    