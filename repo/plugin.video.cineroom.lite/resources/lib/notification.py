# -*- coding: utf-8 -*-
"""
notification.py — Sistema de notificações em cards via GitHub JSON.
"""

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import os
import time
from datetime import datetime, timezone

import traceback
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

ADDON      = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')

NOTIFICATIONS_URL = 'https://raw.githubusercontent.com/Gael1303/flixroom/refs/heads/main/cineroom/jsons/notify.json'
CACHE_FILE        = 'notifications_cache.json'
SHOWN_FILE        = 'notifications_shown.json'
CHECK_INTERVAL    = 6 * 3600  # 6 horas


# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────

def _profile_dir():
    path = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def _cache_path():
    return os.path.join(_profile_dir(), CACHE_FILE)

def _shown_path():
    return os.path.join(_profile_dir(), SHOWN_FILE)


# ─────────────────────────────────────────────────────────────
# IDs já exibidos
# ─────────────────────────────────────────────────────────────

def _load_shown():
    try:
        with open(_shown_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _mark_shown(notif_id):
    shown = _load_shown()
    shown[notif_id] = time.time()
    try:
        with open(_shown_path(), 'w', encoding='utf-8') as f:
            json.dump(shown, f)
    except Exception:
        pass

def _was_shown(notif_id):
    return notif_id in _load_shown()


# ─────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────

def _save_cache(data):
    try:
        data['_cached_at'] = time.time()
        with open(_cache_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass

def _load_cache():
    try:
        with open(_cache_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _cache_is_fresh():
    data = _load_cache()
    return (time.time() - data.get('_cached_at', 0)) < CHECK_INTERVAL


# ─────────────────────────────────────────────────────────────
# HTTP
# ─────────────────────────────────────────────────────────────

def _parse_json_safe(raw_bytes):
    """
    Workaround para bug no json.decoder do Python embutido no Kodi,
    onde ValueError não está no escopo do módulo interno do decoder.
    Usa ast.literal_eval como fallback se json.loads falhar.
    """
    text = raw_bytes.decode('utf-8')
    try:
        return json.loads(text)
    except Exception:
        pass
    # Fallback: ast consegue parsear JSON válido na maioria dos casos
    try:
        import ast
        # JSON usa true/false/null — converte para Python antes do ast
        text_py = text.replace('true', 'True').replace('false', 'False').replace('null', 'None')
        return ast.literal_eval(text_py)
    except Exception as e:
        xbmc.log(f'[Notification] Falha no parse JSON: {e}', xbmc.LOGERROR)
        return None


def _fetch_notifications():
    try:
        req = Request(NOTIFICATIONS_URL)
        req.add_header('Cache-Control', 'no-cache')
        req.add_header('User-Agent', 'CineroomLite/1.0')
        with urlopen(req, timeout=8) as resp:
            raw = resp.read()
        return _parse_json_safe(raw)
    except HTTPError as e:
        xbmc.log(f'[Notification] HTTP {e.code}: {e.reason}', xbmc.LOGWARNING)
    except URLError as e:
        xbmc.log(f'[Notification] URL error: {e.reason}', xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f'[Notification] Erro inesperado: {e}\n{traceback.format_exc()}', xbmc.LOGERROR)
    return None


# ─────────────────────────────────────────────────────────────
# Validações
# ─────────────────────────────────────────────────────────────

def _is_expired(notif):
    expires_at = notif.get('expires_at')
    if not expires_at:
        return False
    try:
        dt_str = expires_at.replace('Z', '+00:00')
        try:
            exp_dt = datetime.fromisoformat(dt_str)
        except AttributeError:
            exp_dt = datetime.strptime(dt_str[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= exp_dt
    except Exception:
        return False

def _matches_target(notif):
    target = notif.get('target', 'all')
    if target == 'all':
        return True
    try:
        from resources.lib.vip_auth import is_session_valid
        is_vip = is_session_valid()
        if target == 'vip':
            return is_vip
        if target == 'free':
            return not is_vip
    except Exception:
        pass
    return True

def _is_valid(notif):
    if not notif.get('active', False):
        return False
    if _is_expired(notif):
        return False
    if _was_shown(notif.get('id', '')):
        return False
    if not _matches_target(notif):
        return False
    return True


# ─────────────────────────────────────────────────────────────
# FIX 1: Alias para compatibilidade com service.py
# service.py chama check_and_cache_notification (sem 's')
# ─────────────────────────────────────────────────────────────

def check_and_cache_notifications():
    """Busca o JSON do GitHub e salva localmente. Chamado pelo service.py a cada 6h."""
    if _cache_is_fresh():
        return
    data = _fetch_notifications()
    if data:
        _save_cache(data)
        xbmc.log('[Notification] Cache atualizado.', xbmc.LOGINFO)

# Alias para compatibilidade — service.py usa o nome sem 's'
check_and_cache_notification = check_and_cache_notifications


# ─────────────────────────────────────────────────────────────
# Ponto de entrada principal (chamado pelo router.py)
# ─────────────────────────────────────────────────────────────

def show_notifications_panel():
    """
    Verifica notificações pendentes e exibe o painel de cards.
    Retorna lista de actions clicadas (pode ser vazia).
    """
    check_and_cache_notifications()

    cache = _load_cache()

    notifications = cache.get('notifications') or []
    if not notifications and cache.get('notification'):
        notifications = [cache.get('notification')]

    pending = [n for n in notifications if _is_valid(n)]

    if not pending:
        return []

    cards = pending[:3]
    return _show_panel(cards)


# ─────────────────────────────────────────────────────────────
# Cores por tipo
# ─────────────────────────────────────────────────────────────

_BADGE_COLORS = {
    'promo':  'FFFFCC00',
    'update': 'FF88BBFF',
    'info':   'FFAAAAAA',
}

_DEFAULT_BADGES = {
    'promo':  'PROMOÇÃO',
    'update': 'NOVIDADE',
    'info':   'AVISO',
}

_CARD_IDS = [
    (9101, 9102, 9103, 9104, 9111, 9112, 9105),  # badge, título, msg, btn, borda, linha, ícone
    (9201, 9202, 9203, 9204, 9121, 9122, 9205),
    (9301, 9302, 9303, 9304, 9131, 9132, 9305),
]

# Ícone padrão por tipo
_DEFAULT_ICONS = {
    'promo':  'resources/medias/icons/promo.png',
    'update': 'resources/medias/icons/update.png',
    'info':   'resources/medias/icons/info.png',
}


# ─────────────────────────────────────────────────────────────
# Dialog
# ─────────────────────────────────────────────────────────────

class NotificationsPanelDialog(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        self.cards   = kwargs.pop('cards', [])  # FIX 2: pop antes de passar ao super
        self.actions = []
        super().__init__(*args, **kwargs)

    def onInit(self):
        for i, card in enumerate(self.cards):
            self._populate_card(i, card)

        for i in range(len(self.cards), 3):
            self._hide_card(i)

        # Contador no rodapé
        try:
            count = len(self.cards)
            label = f'{count} {"Novo Aviso" if count == 1 else "Novos Avisos"}'
            self.getControl(9500).setLabel(label)
        except Exception:
            pass

        if self.cards:
            self.setFocusId(_CARD_IDS[0][3])

    def _populate_card(self, index, notif):
        ids = _CARD_IDS[index]
        id_badge, id_title, id_msg, id_btn, _id_borda, _id_linha, id_icon = ids

        notif_type  = notif.get('type', 'info')
        badge       = notif.get('badge') or _DEFAULT_BADGES.get(notif_type, 'AVISO')
        badge_color = _BADGE_COLORS.get(notif_type, 'FFAAAAAA')

        try:
            self.getControl(id_badge).setLabel(f'[COLOR {badge_color}][B]{badge}[/B][/COLOR]')
        except Exception:
            pass

        try:
            self.getControl(id_title).setLabel(f'[B]{notif.get("title", "")}[/B]')
        except Exception:
            pass

        try:
            self.getControl(id_msg).setLabel(notif.get('message', ''))
        except Exception:
            pass

        try:
            btn_label = notif.get('btn_label') or notif.get('btn_primary') or 'Ver mais'
            self.getControl(id_btn).setLabel(f'[B]{btn_label}[/B]')
        except Exception:
            pass

        # Ícone: usa campo 'icon' do JSON ou fallback por tipo
        try:
            icon = notif.get('icon')
            if icon:
                icon_path = xbmcvfs.translatePath(
                    f'special://home/addons/plugin.video.cineroom.lite/{icon}')
            else:
                default = _DEFAULT_ICONS.get(notif_type, 'resources/medias/icons/info.png')
                icon_path = xbmcvfs.translatePath(
                    f'special://home/addons/plugin.video.cineroom.lite/{default}')
            self.getControl(id_icon).setImage(icon_path)
        except Exception:
            pass

    def _hide_card(self, index):
        ids = _CARD_IDS[index]
        for ctrl_id in ids[:4]:
            try:
                self.getControl(ctrl_id).setLabel('')
            except Exception:
                pass
        try:
            self.getControl(ids[3]).setVisible(False)
        except Exception:
            pass

    def onClick(self, control_id):
        btn_ids = [ids[3] for ids in _CARD_IDS]
        if control_id in btn_ids:
            idx = btn_ids.index(control_id)
            if idx < len(self.cards):
                notif    = self.cards[idx]
                action   = notif.get('btn_action')
                notif_id = notif.get('id', '')

                # Sempre marca como visto ao clicar, independente da action
                _mark_shown(notif_id)

                if action == 'show_detail':
                    # Exibe o detalhe e depois remove o card
                    title  = notif.get('title', 'Detalhe')
                    detail = notif.get('detail', notif.get('message', ''))
                    xbmcgui.Dialog().textviewer(title, detail)
                else:
                    if action:
                        plugin_url = f'plugin://plugin.video.cineroom.lite/?action={action}'
                        xbmc.executebuiltin(f'RunPlugin({plugin_url})')

                self.cards.pop(idx)
                if self.cards:
                    self._refresh_panel()
                else:
                    self.close()
            return

        if control_id == 9400:
            self.close()

    def _refresh_panel(self):
        """Redesenha os cards após remoção de um item."""
        for i, card in enumerate(self.cards):
            self._populate_card(i, card)
        for i in range(len(self.cards), 3):
            self._hide_card(i)
        try:
            count = len(self.cards)
            label = f'{count} {"Novo Aviso" if count == 1 else "Novos Avisos"}'
            self.getControl(9500).setLabel(label)
        except Exception:
            pass
        if self.cards:
            self.setFocusId(_CARD_IDS[0][3])

    def onAction(self, action):
        if action.getId() in (
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_STOP,
        ):
            self.close()


def _show_panel(cards):
    XML_NAME = 'NotificationDialog.xml'

    try:
        dlg = NotificationsPanelDialog(
            XML_NAME,
            ADDON_PATH,
            'Default',
            '1080i',
            cards=cards,
        )
        dlg.doModal()
        actions = dlg.actions
        del dlg
        return actions
    except Exception as e:
        xbmc.log(f'[Notification] Erro ao exibir painel: {e}', xbmc.LOGERROR)
        return []