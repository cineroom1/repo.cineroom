import sys
import time
import json
import urllib.request
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from urllib.parse import urlencode

from resources.lib.encryption_utils import obfuscate_string, deobfuscate_string
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
ADDON = xbmcaddon.Addon()

CACHE_KEY_MAIN_MENU = "main_menu_data"
CACHE_EXPIRY_HOURS = 24

DEFAULT_COUNTERS = {
    "Filmes": 5,
    "Séries": 5,
    "Explorar": 5,
    "Visitas_menu": 1,
    "last_updated": ""
}

def get_url(**kwargs):
    """Cria uma URL para chamar o plugin recursivamente a partir dos argumentos fornecidos."""
    return '{}?{}'.format(URL, urlencode(kwargs, doseq=True))

def try_load_expired_cache(key):
    """Tenta carregar do cache expirado e desserializar JSON."""
    expired = VIDEO_CACHE.get(key, ignore_expiry=True)
    if expired:
        try:
            return json.loads(expired)
        except json.JSONDecodeError:
            xbmc.log(f"[ERROR] Cache expirado corrompido para a chave {key}", xbmc.LOGERROR)
    return None

def check_maintenance_status(menu):
    """Verifica se o addon está em manutenção (status == 'off' no primeiro item)."""
    if menu and isinstance(menu, list) and len(menu) > 0:
        first_item = menu[0]
        if isinstance(first_item, dict) and first_item.get("status", "").lower() == "off":
            return True
    return False

def get_menu(force_refresh=False):
    """Obtém o menu principal com sistema de cache (validade padrão)."""
    if not force_refresh:
        cached_data_string = VIDEO_CACHE.get(CACHE_KEY_MAIN_MENU)
        if cached_data_string:
            try:
                menu_list = json.loads(cached_data_string)
                xbmc.log("[CACHE] Menu carregado do cache", xbmc.LOGDEBUG)
                return menu_list
            except json.JSONDecodeError as e:
                xbmc.log(f"[ERROR] JSON inválido no cache do menu: {e}. Deletando cache corrompido.", xbmc.LOGERROR)
                VIDEO_CACHE.delete(CACHE_KEY_MAIN_MENU)
            except Exception as e:
                xbmc.log(f"[ERROR] Erro ao carregar menu do cache: {e}. Deletando cache.", xbmc.LOGERROR)
                VIDEO_CACHE.delete(CACHE_KEY_MAIN_MENU)

    try:
        xbmc.log("[NETWORK] Buscando dados do menu...", xbmc.LOGDEBUG)
        req = urllib.request.Request(data_feed, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:

            if response.status == 429:
                xbmcgui.Dialog().notification('Aviso', 'Muitas requisições. Tente novamente mais tarde.', xbmcgui.NOTIFICATION_WARNING)
                return try_load_expired_cache(CACHE_KEY_MAIN_MENU) or []

            if response.status != 200:
                xbmc.log(f"[ERROR] Status code: {response.status}", xbmc.LOGERROR)
                return try_load_expired_cache(CACHE_KEY_MAIN_MENU) or []

            raw_data = response.read().decode('utf-8')
            if not raw_data:
                xbmc.log("[ERROR] Resposta vazia do servidor", xbmc.LOGERROR)
                return try_load_expired_cache(CACHE_KEY_MAIN_MENU) or []

            menu = json.loads(raw_data)
            if not isinstance(menu, list):
                xbmc.log("[ERROR] Estrutura de dados inválida (esperava lista)", xbmc.LOGERROR)
                return try_load_expired_cache(CACHE_KEY_MAIN_MENU) or []

            VIDEO_CACHE.set(CACHE_KEY_MAIN_MENU, json.dumps(menu, ensure_ascii=False), expiry_hours=CACHE_EXPIRY_HOURS)
            xbmc.log("[CACHE] Menu armazenado com sucesso", xbmc.LOGDEBUG)
            return menu

    except Exception as e:
        xbmc.log(f"[ERROR] {e.__class__.__name__}: {e}", xbmc.LOGERROR)
        return try_load_expired_cache(CACHE_KEY_MAIN_MENU) or []

def create_list_item(label, art=None, info=None):
    """Cria um ListItem do Kodi com arte e info (opcional)."""
    li = xbmcgui.ListItem(label=label)
    if art:
        li.setArt(art)
    if info:
        li.setInfo('video', info)
    return li

def list_menu():
    """Exibe o menu principal com contadores atualizados."""
    xbmcplugin.setPluginCategory(HANDLE, 'Menu Principal')
    menu = get_menu()
    if not menu:
        return

    counters = get_firebase_counters()
    last_access = ADDON.getSetting('last_menu_access')
    current_date = time.strftime('%Y-%m-%d')

    if last_access != current_date:
        new_count = update_firebase_counter("Visitas_menu")
        if new_count is not None:
            counters["Visitas_menu"] = new_count
            ADDON.setSetting('last_menu_access', current_date)

    settings_map = {
        "Filmes": ADDON.getSettingBool('mostrar_filmes'),
        "Séries": ADDON.getSettingBool('mostrar_series'),
        "Pesquisar": ADDON.getSettingBool('mostrar_pesquisar'),
        "Explorar": ADDON.getSettingBool('mostrar_explorar'),
        "Minha_Lista": ADDON.getSettingBool('mostrar_favoritos')
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
            info = {'title': f'{title} - Indisponível', 'plot': 'Em manutenção'}
        else:
            label = title
            info = {'title': title, 'plot': plot}

        art = {
            'icon': menu_info.get('poster', ''),
            'fanart': menu_info.get('fanart', ''),
            'thumb': menu_info.get('poster', '')
        }
        list_item = create_list_item(label, art=art, info=info)

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
    """Lista subcategorias com cache."""
    menu = get_menu()
    if not menu or menu_index >= len(menu):
        return
    
    subcategories = menu[menu_index].get('subcategorias', [])
    if not subcategories:
        xbmcgui.Dialog().ok('Erro', 'Subcategorias não encontradas!')
        return
    
    category_key = menu[menu_index].get("menu_key", "")
    
    if category_key in ["Filmes", "Séries", "Explorar"]:
        new_count = update_firebase_counter(category_key)
    
    xbmcplugin.setPluginCategory(HANDLE, menu[menu_index].get("menu_title", "Subcategorias"))
    xbmcplugin.setContent(HANDLE, "files")

    for subcategory in subcategories:
        label = subcategory['categories']
            
        art = {
            'icon': subcategory.get('poster', ''),
            'fanart': subcategory.get('backdrop', menu[menu_index].get('fanart', ''))
        }
        
        info = {
            'title': label,
            'plot': subcategory.get('description', '')
        }
        
        if subcategory.get('year'):
            info['year'] = subcategory['year']
        
        list_item = create_list_item(label, art=art, info=info)
        
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


def show_donation():
    dialog = DonationDialog("DonationDialog.xml", ADDON.getAddonInfo("path"), "Default", "720p")
    dialog.doModal()
    del dialog

def show_telegram():
    dialog = TelegramDialog("TelegramDialog.xml", ADDON.getAddonInfo("path"), "Default", "720p")
    dialog.doModal()
    del dialog
