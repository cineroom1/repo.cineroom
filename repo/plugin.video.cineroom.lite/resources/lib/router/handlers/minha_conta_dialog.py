# -*- coding: utf-8 -*-
"""
minha_conta_dialog.py — Tela "Minha Conta" PLUS
Salvar em: resources/lib/router/handlers/minha_conta_dialog.py
"""

import os
import time
import threading
from datetime import datetime, timezone

import xbmc
import xbmcgui
import xbmcaddon

from resources.lib.vip_auth import (
    get_current_vip_user,
    get_vip_expiry_str,
    is_session_valid,
    logout,
    change_password,
)

ADDON      = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
ADDON_ID   = ADDON.getAddonInfo('id')


# ─────────────────────────────────────────────
# HELPERS — perfil ativo
# ─────────────────────────────────────────────

def _get_pm():
    try:
        from resources.lib.profile_manager import ProfileManager
        return ProfileManager()
    except Exception as e:
        xbmc.log(f'[MinhaConta] ProfileManager indisponível: {e}', xbmc.LOGWARNING)
        return None


def _get_active_profile():
    pm = _get_pm()
    return pm.get_current_profile() if pm else None


def _resolve_avatar(profile) -> str:
    if not profile:
        return ''
    rel = profile.get('avatar', '')
    if not rel:
        return ''
    if os.path.isabs(rel) and os.path.exists(rel):
        return rel
    full = os.path.join(ADDON_PATH, 'resources', 'medias', rel)
    return full if os.path.exists(full) else ''


# ─────────────────────────────────────────────
# VARIÁVEIS DE SKIN
# ─────────────────────────────────────────────

def _set_skin_vars(username: str, expiry: str, profile_name: str = ''):
    xbmc.executebuiltin(f'Skin.SetString(VIPUsername,{username})')
    xbmc.executebuiltin(f'Skin.SetString(VIPExpiry,{expiry})')
    if profile_name:
        xbmc.executebuiltin(f'Skin.SetString(VIPProfile,{profile_name})')
    else:
        xbmc.executebuiltin('Skin.Reset(VIPProfile)')


# ─────────────────────────────────────────────
# DADOS DA SESSÃO
# ─────────────────────────────────────────────

def _get_session_details() -> dict:
    import json
    import xbmcvfs

    try:
        import xbmcaddon as _addon_mod
        profile_dir    = xbmcvfs.translatePath(_addon_mod.Addon().getAddonInfo('profile'))
        session_path   = os.path.join(profile_dir, 'vip_session.json')
        device_id_path = os.path.join(profile_dir, 'device_id.txt')

        session = {}
        if os.path.exists(session_path):
            try:
                with open(session_path, 'r', encoding='utf-8') as f:
                    session = json.load(f)
            except Exception:
                pass

        device_id = ''
        if os.path.exists(device_id_path):
            try:
                with open(device_id_path, 'r', encoding='utf-8') as f:
                    device_id = f.read().strip()
            except Exception:
                pass

        def _fmt_ts(ts):
            try:
                return datetime.fromtimestamp(float(ts)).strftime('%d/%m/%Y  %H:%M')
            except Exception:
                return '—'

        def _fmt_iso(iso_str):
            if not iso_str:
                return 'Vitalício'
            try:
                dt_str = iso_str.replace('Z', '+00:00')
                try:
                    dt = datetime.fromisoformat(dt_str)
                except AttributeError:
                    dt = datetime.strptime(dt_str[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)

                dt_local = dt.astimezone()
                return dt_local.strftime('%d/%m/%Y  %H:%M')
            except Exception:
                return iso_str[:10] if len(iso_str) >= 10 else iso_str

        def _offline_until(session: dict) -> str:
            try:
                now = datetime.now().astimezone()

                iso = session.get('offline_expires_at')
                if iso:
                    dt_str = iso.replace('Z', '+00:00')
                    try:
                        exp = datetime.fromisoformat(dt_str)
                    except AttributeError:
                        exp = datetime.strptime(dt_str[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)

                    exp_local = exp.astimezone()
                    if now >= exp_local:
                        return f'Expirado em {exp_local.strftime("%d/%m/%Y  %H:%M")}'
                    return f'Ativo até {exp_local.strftime("%d/%m/%Y  %H:%M")}'

                ttl = session.get('offline_ttl')
                auth_ts = session.get('auth_ts')
                if ttl and auth_ts:
                    exp_local = datetime.fromtimestamp(float(auth_ts) + int(ttl)).astimezone()
                    if now >= exp_local:
                        return f'Expirado em {exp_local.strftime("%d/%m/%Y  %H:%M")}'
                    return f'Ativo até {exp_local.strftime("%d/%m/%Y  %H:%M")}'

            except Exception:
                pass

            return '—'

        vip_exp_raw = session.get('vip_expires_at')
        plan_label  = 'Vitalício' if not vip_exp_raw else 'PLUS com expiração'

        did = device_id
        if len(did) > 16:
            did_display = did[:8] + '…' + did[-4:]
        else:
            did_display = did or '—'

        return {
            'username':      session.get('username') or get_current_vip_user() or '—',
            'plan':          plan_label,
            'vip_expiry':    _fmt_iso(vip_exp_raw),
            'token_expiry':  _fmt_ts(session.get('token_exp', 0)),
            'last_login':    _fmt_ts(session.get('auth_ts', 0)),
            'offline_until': _offline_until(session),
            'device_name':   xbmc.getInfoLabel('System.FriendlyName') or 'Kodi',
            'device_id':     did_display,
        }

    except Exception as e:
        xbmc.log(f'[MinhaConta] Erro em _get_session_details: {e}', xbmc.LOGERROR)
        return {
            'username':      get_current_vip_user() or '—',
            'plan':          '—',
            'vip_expiry':    get_vip_expiry_str(),
            'token_expiry':  '—',
            'last_login':    '—',
            'offline_until': '—',
            'device_name':   xbmc.getInfoLabel('System.FriendlyName') or 'Kodi',
            'device_id':     '—',
        }


# ─────────────────────────────────────────────
# NAVEGAÇÃO ASSÍNCRONA
# ─────────────────────────────────────────────

def _run_after_close(builtin: str, delay_ms: int = 300):
    def _run():
        xbmc.sleep(delay_ms)
        xbmc.executebuiltin(builtin)
    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────
# DIALOG — Detalhes da Conta
# ─────────────────────────────────────────────

class ContaDetalhesDialog(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._details = kwargs.get('details', {})

    def onInit(self):
        d = self._details

        def _lbl(ctrl_id, text):
            try:
                self.getControl(ctrl_id).setLabel(str(text))
            except Exception:
                pass

        _lbl(8001, d.get('username', '—'))
        _lbl(8002, d.get('plan', '—'))
        _lbl(8003, d.get('vip_expiry', '—'))
        _lbl(8004, d.get('token_expiry', '—'))
        _lbl(8005, d.get('last_login', '—'))
        _lbl(8006, d.get('offline_until', '—'))
        _lbl(8007, d.get('device_name', '—'))
        _lbl(8008, d.get('device_id', '—'))

        try:
            self.setFocusId(8010)
        except Exception:
            pass

    def onClick(self, control_id):
        if control_id == 8010:
            self.close()

    def onAction(self, action):
        if action.getId() in (
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_STOP,
            xbmcgui.ACTION_SELECT_ITEM,
        ):
            self.close()


# ─────────────────────────────────────────────
# TROCAR SENHA (fluxo inline, sem XML extra)
# ─────────────────────────────────────────────

def open_trocar_senha():
    """
    Fluxo de troca de senha usando dialogs nativos do Kodi.
    Não precisa de XML extra.
    """
    dialog = xbmcgui.Dialog()

    senha_atual = dialog.input(
        'Senha Atual',
        type=xbmcgui.INPUT_ALPHANUM,
        option=xbmcgui.ALPHANUM_HIDE_INPUT,
    )
    if not senha_atual:
        return

    nova_senha = dialog.input(
        'Nova Senha',
        type=xbmcgui.INPUT_ALPHANUM,
        option=xbmcgui.ALPHANUM_HIDE_INPUT,
    )
    if not nova_senha:
        return

    confirmar = dialog.input(
        'Confirmar Nova Senha',
        type=xbmcgui.INPUT_ALPHANUM,
        option=xbmcgui.ALPHANUM_HIDE_INPUT,
    )
    if not confirmar:
        return

    if nova_senha != confirmar:
        dialog.notification(
            'Trocar Senha', 'As senhas não coincidem.',
            xbmcgui.NOTIFICATION_WARNING, 3000
        )
        return

    if len(nova_senha) < 6:
        dialog.notification(
            'Trocar Senha', 'A nova senha deve ter ao menos 6 caracteres.',
            xbmcgui.NOTIFICATION_WARNING, 3000
        )
        return

    # Chama a API
    pDialog = xbmcgui.DialogProgress()
    pDialog.create('Cineroom PLUS', 'Alterando senha...')
    pDialog.update(50)
    ok, err = change_password(senha_atual, nova_senha)
    pDialog.close()

    _ERROS = {
        'wrong_current_password': 'Senha atual incorreta.',
        'password_too_short':     'A nova senha é curta demais (mínimo 6 caracteres).',
        'same_password':          'A nova senha é igual à atual.',
        'offline':                'Sem conexão. Tente mais tarde.',
        'no_session':             'Sessão inválida. Faça login novamente.',
        'missing_fields':         'Preencha todos os campos.',
    }

    if ok:
        dialog.notification(
            'Trocar Senha', 'Senha alterada com sucesso!',
            xbmcgui.NOTIFICATION_INFO, 3000
        )
    else:
        msg = _ERROS.get(err, f'Erro ao alterar senha: {err}')
        dialog.ok('[COLOR red]Erro[/COLOR]', msg)


# ─────────────────────────────────────────────
# DIALOG — Minha Conta (principal)
# ─────────────────────────────────────────────

class MinhaContaDialog(xbmcgui.WindowXMLDialog):
    """
    Tela principal "Minha Conta".
    XML: MinhaConta.xml

    Botões:
        9040 — Trocar perfil
        9046 — Detalhes da conta
        9047 — Gerenciar Dispositivos   ← novo
        9048 — Trocar Senha             ← novo
        9041 — Histórico
        9042 — Biblioteca
        9043 — Trakt
        9044 — Sincronizar Trakt
        9045 — Sair do PLUS
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._avatar = kwargs.get('avatar', '')

    def onInit(self):
        if self._avatar:
            try:
                self.getControl(9050).setImage(self._avatar)
            except Exception:
                pass
        try:
            self.setFocusId(9040)
        except Exception:
            pass
   
    def onClick(self, control_id):
        if control_id == 9040:
            self._trocar_perfil()
        elif control_id == 9046:
            self._abrir_detalhes()
        elif control_id == 9048:
            self._trocar_senha()
        elif control_id == 9041:
            self._ir_para(f'plugin://{ADDON_ID}/?action=show_history_menu')
        elif control_id == 9042:
            self._ir_para(f'plugin://{ADDON_ID}/?action=library_menu')
        elif control_id == 9043:
            self._ir_para(f'plugin://{ADDON_ID}/?action=trakt_main_menu')
        elif control_id == 9044:
            self._ir_para(f'plugin://{ADDON_ID}/?action=trakt_auth')
        elif control_id == 9045:
            self._deslogar()

    def onAction(self, action):
        if action.getId() in (
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_STOP,
        ):
            self.close()

    # ── Ações ────────────────────────────────────────────────────────

    def _abrir_detalhes(self):
        details = _get_session_details()
        dlg = ContaDetalhesDialog(
            'ContaDetalhes.xml', ADDON_PATH, 'Default', '1080i',
            details=details,
        )
        dlg.doModal()
        del dlg

    def _trocar_senha(self):
        open_trocar_senha()

    def _trocar_perfil(self):
        pm = _get_pm()
        if not pm:
            xbmcgui.Dialog().notification(
                'Cineroom PLUS', 'Seletor de perfis indisponível.',
                xbmcgui.NOTIFICATION_WARNING, 3000
            )
            return

        try:
            profile = _get_active_profile()
            if profile and profile.get('is_kids', False):
                pin = ADDON.getSetting('parental_pin') or ''
                if pin:
                    entered = xbmcgui.Dialog().input(
                        'PIN Parental', type=xbmcgui.INPUT_NUMERIC
                    )
                    if entered != pin:
                        xbmcgui.Dialog().notification(
                            'Cineroom PLUS', 'PIN incorreto.',
                            xbmcgui.NOTIFICATION_WARNING, 2500
                        )
                        return
        except Exception as e:
            xbmc.log(f'[MinhaConta] Erro verificando PIN: {e}', xbmc.LOGWARNING)

        self.close()

        # Mostra seletor e aguarda a escolha antes de qualquer navegação
        novo_perfil = pm.show_profile_selector()

        if novo_perfil:
            # Dispositivos fracos precisam de mais tempo para o perfil ser persistido
            xbmc.sleep(400)
            xbmc.executebuiltin(
                f'Container.Update(plugin://{ADDON_ID}/,replace)'
            )

    def _ir_para(self, plugin_url: str):
        self.close()
        _run_after_close(f'ActivateWindow(Videos,{plugin_url},return)')

    def _deslogar(self):
        user = get_current_vip_user() or 'sua conta'
        if not xbmcgui.Dialog().yesno(
            'Sair do PLUS',
            f'Desconectar [COLOR gold]{user}[/COLOR] do Cineroom PLUS?'
        ):
            return
        self.close()
        _run_after_close(f'Container.Update(plugin://{ADDON_ID}/?action=vip_logout,replace)')


# ─────────────────────────────────────────────
# PONTO DE ENTRADA
# ─────────────────────────────────────────────

def open_minha_conta() -> bool:
    if not is_session_valid():
        xbmcgui.Dialog().notification(
            'Cineroom PLUS', 'Faça login para acessar sua conta.',
            xbmcgui.NOTIFICATION_WARNING, 3000
        )
        return False

    username     = get_current_vip_user()
    expiry       = get_vip_expiry_str()
    profile      = _get_active_profile()
    avatar       = _resolve_avatar(profile)
    profile_name = profile.get('name', '') if profile else ''

    _set_skin_vars(username, expiry, profile_name)

    dlg = MinhaContaDialog(
        'MinhaConta.xml', ADDON_PATH, 'Default', '1080i',
        avatar=avatar,
    )
    dlg.doModal()
    del dlg
    return True