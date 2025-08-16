import sys
import time
import json
import urllib.request
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import hashlib


from urllib.parse import urlencode

from resources.lib.encryption_utils import obfuscate_string, deobfuscate_string
from resources.action.donation_window import DonationDialog
from resources.action.telegram_window import TelegramDialog
from resources.lib.configs.urls import data_feed
from resources.lib.utils import get_all_videos, VIDEO_CACHE


# Configurações do plugin
URL = sys.argv[0]
HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()

CACHE_KEY_MAIN_MENU = "main_menu_data"
CACHE_EXPIRY_HOURS = 24


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


    settings_map = {
        "Filmes": ADDON.getSettingBool('mostrar_filmes'),
        "Séries": ADDON.getSettingBool('mostrar_series'),
        "Exclusivo": ADDON.getSettingBool('mostrar_Exclusivo'),
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
    """Lista subcategorias marcando as VIP e bloqueia acesso se subcategoria estiver off."""
    menu = get_menu()
    if not menu or menu_index >= len(menu):
        return
    
    subcategories = menu[menu_index].get('subcategorias', [])
    if not subcategories:
        xbmcgui.Dialog().ok('Erro', 'Subcategorias não encontradas!')
        return

    xbmcplugin.setPluginCategory(HANDLE, menu[menu_index].get("menu_title", "Subcategorias"))
    xbmcplugin.setContent(HANDLE, "files")

    for subcategory in subcategories:
        # Bloqueia subcategoria com status off
        if subcategory.get("status", "on").lower() == "off":
            label = f"[COLOR red]•[/COLOR] {subcategory.get('categories', 'Indisponível')} - (Manutenção)"
            info = {'title': f"{subcategory.get('categories', 'Indisponível')} - Indisponível", 'plot': 'Em manutenção'}
            art = {
                'icon': subcategory.get('poster', ''),
                'fanart': subcategory.get('backdrop', menu[menu_index].get('fanart', '')),
                'thumb': subcategory.get('poster', '')
            }
            list_item = create_list_item(label, art=art, info=info)
            # Coloca como item não clicável (isFolder=False)
            xbmcplugin.addDirectoryItem(HANDLE, "", list_item, isFolder=False)
            continue

        # Subcategoria ativa - lista normalmente
        label = subcategory.get('categories', 'Sem título')
        if subcategory.get('is_vip', False):
            label = f"{label} [COLOR gold]★[/COLOR]"

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
        
        url_params = {
            'action': subcategory.get('action', 'list_videos'),
            'is_vip': 'true' if subcategory.get('is_vip', False) else 'false',
            'content_name': subcategory['categories']
        }
        
        if 'externallink' in subcategory:
            url_params['external_link'] = subcategory['externallink']
        if 'sort_method' in subcategory:
            url_params['sort_method'] = subcategory['sort_method']
        
        url = get_url(**url_params)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)



FIREBASE_URL = "https://vipacess-7ddc2-default-rtdb.firebaseio.com/vip_accesses"

def get_today_date():
    return time.strftime('%Y-%m-%d')

def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        xbmc.log(f"[VIP] Erro no GET: {e}", xbmc.LOGERROR)
        return None

def http_put(url, data):
    try:
        req = urllib.request.Request(url, data=data.encode('utf-8'), method='PUT')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception as e:
        xbmc.log(f"[VIP] Erro no PUT: {e}", xbmc.LOGERROR)
        return False

def get_access_count_for_today():
    today = get_today_date()
    url = f"{FIREBASE_URL}/{today}.json"
    data = http_get(url)
    if data is None or data == "null":
        return 0
    try:
        return int(json.loads(data))
    except:
        return 0

def increment_access_count():
    today = get_today_date()
    count = get_access_count_for_today()
    count += 1
    url = f"{FIREBASE_URL}/{today}.json"
    success = http_put(url, json.dumps(count))
    
    # Verifica se foi bloqueado pelo Firebase
    if not success and get_access_count_for_today() >= 1:
        xbmcgui.Dialog().ok("Limite diário", "Limite Diario Atingido! (20 Usuarios)")
    return success

def generate_session_token():
    secret_key = ADDON.getSetting('secret_key') or "DEFAULT_KEY_ALTERAR_NO_SETTINGS"
    timestamp = str(int(time.time()) // 86400)
    return hashlib.sha256((secret_key + timestamp).encode()).hexdigest()

def validate_session_token(token):
    return token == generate_session_token()

def verify_vip_access():
    today = get_today_date()

    # Bloqueio local após 3 tentativas erradas
    blocked_day = ADDON.getSetting('vip_blocked_day')
    if blocked_day == today:
        xbmcgui.Dialog().ok("Acesso Bloqueado", "Muitas tentativas incorretas. Tente novamente amanhã.")
        return False

    # Token válido existente
    saved_token = ADDON.getSetting('vip_session_token')
    if saved_token and validate_session_token(saved_token):
        return True

    # Usa teclado numérico
    senha_digitada = xbmcgui.Dialog().numeric(0, "Acesso VIP\nDigite a senha:")
    if senha_digitada:
        senha_hash = hashlib.sha256(senha_digitada.encode()).hexdigest()
        correct_hash = ADDON.getSetting('vip_password_hash')

        if senha_hash == correct_hash:
            if increment_access_count():
                token = generate_session_token()
                ADDON.setSetting('vip_session_token', token)
                ADDON.setSetting('vip_failed_attempts', "0")
                ADDON.setSetting('vip_blocked_day', "")
                return True
        else:
            tentativas = int(ADDON.getSetting('vip_failed_attempts') or "0") + 1
            ADDON.setSetting('vip_failed_attempts', str(tentativas))

            if tentativas >= 3:
                ADDON.setSetting('vip_blocked_day', today)
                xbmcgui.Dialog().ok("Acesso Bloqueado", "3 tentativas incorretas. Tente novamente amanhã.")
            else:
                xbmcgui.Dialog().ok("Senha incorreta", "Senha VIP inválida.")
    return False




def show_donation():
    dialog = DonationDialog("DonationDialog.xml", ADDON.getAddonInfo("path"), "Default", "720p")
    dialog.doModal()
    del dialog

def show_telegram():
    dialog = TelegramDialog("TelegramDialog.xml", ADDON.getAddonInfo("path"), "Default", "720p")
    dialog.doModal()
    del dialog
