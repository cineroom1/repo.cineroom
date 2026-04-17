# -*- coding: utf-8 -*-
"""
Handler PLUS — fluxo:
  1. PLUSInfoDialog.xml  → apresentação dos benefícios (clicáveis) + Fazer Login / Cancelar
  2. PLUSBenefitPanel.xml → detalhes de cada benefício (ao clicar)
  3. PLUSLoginDialog.xml → formulário de usuário/senha

XMLs em: skins/Default/1080i/
"""

import xbmc
import xbmcgui
import xbmcaddon
import json
import time
import os

from resources.lib.vip_auth import (
    authenticate,
    requires_vip,
    get_current_vip_user,
    get_vip_expiry_str,
    is_session_valid,
    logout,
    _profile_dir,
    get_saved_username,
    get_saved_password,
)

ADDON_PATH = xbmcaddon.Addon().getAddonInfo('path')

# ============================================================
# CONFIGURAÇÕES DE BLOQUEIO
# ============================================================
MAX_ATTEMPTS   = 9999  # desativado (rate limit é tratado em vip_auth + servidor)
BLOCK_DURATION = 0     # desativado


# ============================================================
# CONTROLE DE BLOQUEIO LOCAL
# ============================================================

def _lockout_path():
    return os.path.join(_profile_dir(), 'plus_lockout.json')


def _load_lockout():
    try:
        with open(_lockout_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'attempts': 0, 'blocked_until': 0}


def _save_lockout(data):
    try:
        with open(_lockout_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


def _reset_lockout():
    return


def _register_failed_attempt():
    """Lockout local desativado."""
    return 0, 0


def _check_lockout():
    """Lockout local desativado (use rate limit do vip_auth + servidor)."""
    return False, 0


# ── Rate limiting para device_limit_reached ───────────────────────────────────

def _device_limit_rl_path():
    return os.path.join(_profile_dir(), 'device_limit_rl.json')


def _device_limit_load():
    try:
        with open(_device_limit_rl_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'attempts': 0, 'blocked_until': 0}


def _device_limit_save(data):
    try:
        with open(_device_limit_rl_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass


def _device_limit_is_blocked():
    data = _device_limit_load()
    now  = time.time()
    blocked_until = data.get('blocked_until', 0)
    if blocked_until and now < blocked_until:
        return True, int(blocked_until - now)
    return False, 0


def _device_limit_register():
    """Registra tentativa com device_limit_reached. Bloqueia por 1h apos 3 tentativas."""
    data     = _device_limit_load()
    attempts = data.get('attempts', 0) + 1
    blocked_until = time.time() + (60 * 60) if attempts >= 3 else 0
    _device_limit_save({'attempts': attempts, 'blocked_until': blocked_until})
    return attempts, blocked_until


def _dialog_blocked(seconds_left):
    minutes = seconds_left // 60
    seconds = seconds_left % 60
    xbmcgui.Dialog().ok(
        'Acesso Bloqueado',
        'Muitas tentativas incorretas.\n'
        'Tente novamente em [B]' + str(minutes) + 'm ' + str(seconds) + 's[/B].'
    )


# ============================================================
# TELA DE BOAS-VINDAS (primeiro acesso)
# ============================================================

class WelcomeDialog(xbmcgui.WindowXMLDialog):
    """
    Tela de boas-vindas com dois cards: Free e PLUS.
    Abre WelcomeDialog.xml.

    IDs:
        9201 — botão Fazer Login PLUS  → self.choice = 'vip'
        9202 — botão Continuar Free   → self.choice = 'anon'
        9001-9006 — benefícios PLUS clicáveis (abrem PLUSBenefitPanel)
    """

    BENEFITS = {
    9001: {
        'title': 'Perfis com PIN',
        'description': (
            'Perfis separados para cada usuário.\n\n'
            '• Avatar individual\n'
            '• Proteção por PIN\n'
            '• Histórico e favoritos independentes\n'
            '• Preferências salvas por perfil\n\n'
            'Cada pessoa usa o app do seu jeito.'
        )
    },

    9002: {
        'title': 'Perfil infantil',
        'description': (
            'Modo seguro para crianças.\n\n'
            '• Filtro automático por idade\n'
            '• Bloqueio de categorias adultas\n'
            '• Tempo limite de uso\n'
            '• Interface simplificada\n\n'
            'Controle total para os responsáveis.'
        )
    },

    9003: {
        'title': 'Sugestões inteligentes',
        'description': (
            'Organização automática baseada no seu uso.\n\n'
            '• Analisa histórico e preferências\n'
            '• Destaca itens relacionados\n'
            '• Prioriza o que você mais assiste\n'
            '• Atualiza automaticamente\n\n'
            'Facilita encontrar algo para assistir.'
        )
    },

    9004: {
        'title': 'Filtros avançados',
        'description': (
            'Mais opções para organizar e navegar.\n\n'
            '• Qualidade: filtre por resolução\n'
            '• Temas: categorias especiais\n'
            '• Tendências: itens populares\n'
            '• Avaliação: ordem por nota\n\n'
            'Mais controle sobre os resultados.'
        )
    },

    9005: {
        'title': 'Sincronização com Trakt',
        'description': (
            'Integração completa com sua conta.\n\n'
            '• Histórico sincronizado\n'
            '• Watchlist compartilhada\n'
            '• Listas e coleções\n'
            '• Progresso salvo na nuvem\n\n'
            'Acesse seus dados em qualquer dispositivo.'
        )
    },

    9006: {
        'title': 'Biblioteca integrada',
        'description': (
            'Integração com a biblioteca do Kodi.\n\n'
            '• Metadados automáticos\n'
            '• Pôster, sinopse e elenco\n'
            '• Organização por gênero/ano\n'
            '• Compatível com skins\n\n'
            'Tudo organizado no padrão do Kodi.'
        )
    },

    9007: {
        'title': 'Backup automático',
        'description': (
            'Seus dados sempre seguros.\n\n'
            '• Backup automático periódico\n'
            '• Escolha onde salvar\n'
            '• Mantém versões recentes\n'
            '• Exportação manual completa\n\n'
            'Recupere tudo quando precisar.'
        )
    },
}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.choice = 'anon'

    def onInit(self):
        self.setFocusId(9201)

    def onClick(self, control_id):
        if control_id == 9201:
            self.choice = 'vip'
            self.close()
        elif control_id == 9202:
            self.choice = 'anon'
            self.close()
        elif control_id in self.BENEFITS:
            self._show_benefit(control_id)

    def onAction(self, action):
        if action.getId() in (
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_STOP,
        ):
            self.choice = 'anon'
            self.close()

    def _show_benefit(self, benefit_id):
        benefit = self.BENEFITS.get(benefit_id)
        if not benefit:
            return
        panel = PLUSBenefitPanel(
            'Plusbenefitpanel.xml',
            ADDON_PATH,
            'Default',
            '1080i',
            title=benefit['title'],
            description=benefit['description'],
        )
        panel.doModal()
        del panel


# ============================================================
# PAINEL DE DETALHES DO BENEFÍCIO
# ============================================================

class PLUSBenefitPanel(xbmcgui.WindowXMLDialog):
    """
    Mini-painel que mostra detalhes de um benefício específico.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title       = kwargs.get('title', '')
        self.description = kwargs.get('description', '')

    def onInit(self):
        try:
            self.getControl(9100).setLabel(self.title)
            self.getControl(9101).setText(self.description)
        except Exception as e:
            xbmc.log('[PLUS] Erro ao definir painel: ' + str(e), xbmc.LOGERROR)
        self.setFocusId(9999)

    def onClick(self, control_id):
        if control_id == 9999:
            self.close()

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_PREVIOUS_MENU,
                               xbmcgui.ACTION_NAV_BACK,
                               xbmcgui.ACTION_STOP,
                               xbmcgui.ACTION_SELECT_ITEM):
            self.close()


# ============================================================
# DIALOG 1 — Apresentação PLUS (benefícios clicáveis)
# ============================================================

class PLUSInfoDialog(xbmcgui.WindowXMLDialog):
    """
    Tela de apresentação dos benefícios PLUS.
    IDs:
        9001-9005 — botões de benefícios (clicáveis para detalhes)
        9201 — botão Fazer Login
        9202 — botão Cancelar
    """

    BENEFITS = {
        9001: {
            'title': 'Perfis personalizados',
            'description': (
                'Crie perfis individuais para cada pessoa da casa.\n\n'
                '• Avatar personalizado para cada perfil\n'
                '• Proteção com PIN de 4 dígitos\n'
                '• Preferências individuais (favoritos, histórico)\n'
                '• Recomendações baseadas no perfil ativo\n\n'
                'Cada membro da família tem sua própria experiência personalizada.'
            )
        },
        9002: {
            'title': 'Perfil infantil',
            'description': (
                'Controle parental completo para crianças.\n\n'
                '• Filtro automático por faixa etária\n'
                '• Limite de tempo de uso diário\n'
                '• Bloqueio de conteúdo adulto\n'
                '• Relatório de uso para os pais\n\n'
                'Garanta que as crianças acessem apenas conteúdo apropriado.'
            )
        },
        9003: {
            'title': 'Categorias extras',
            'description': (
                'Acesso a categorias exclusivas do PLUS.\n\n'
                '• Mais Buscados: conteúdo popular\n'
                '• Temas: filmes organizados por tema\n'
                '• 4K: conteúdo em ultra-alta definição\n'
                '• Coleções: séries de filmes e franquias\n\n'
                'Descubra conteúdo de forma mais organizada e inteligente.'
            )
        },
        9004: {
            'title': 'Trakt integrado',
            'description': (
                'Sincronização completa com Trakt.tv.\n\n'
                '• Watchlist: lista de filmes/séries para assistir\n'
                '• Histórico: acompanhe o que já assistiu\n'
                '• Sincronização: dados salvos na nuvem\n'
                '• Recomendações: baseadas no seu gosto\n'
                '• Múltiplos dispositivos: acesse de qualquer lugar\n\n'
                'Nunca perca o controle do que você assiste.'
            )
        },
        9005: {
            'title': 'Biblioteca do Kodi',
            'description': (
                'Adicione conteúdo à Biblioteca nativa do Kodi.\n\n'
                '• Integração total com scrapers do Kodi\n'
                '• Metadados automáticos (sinopse, pôster, atores)\n'
                '• Organização por gênero e ano\n'
                '• Compatível com skins do Kodi\n'
                '• Widgets e favoritos funcionam perfeitamente\n\n'
                'Transforme o Cineroom em sua biblioteca pessoal.'
            )
        },
        9006: {
            'title': 'Backup automático do histórico',
            'description': (
                'Nunca perca seu histórico, mesmo reinstalando o addon.\n\n'
                '• Backup automático a cada 24h via serviço em segundo plano\n'
                '• Pasta configurável: USB, rede (SMB/NFS) ou armazenamento local\n'
                '• Rotação automática: mantém os 5 backups mais recentes\n'
                '• Exportação manual completa: histórico + favoritos + watchlist\n'
                '• Importação com mesclagem ou substituição\n\n'
                'Seus dados ficam seguros mesmo sem o Trakt.'
            )
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proceed = False

    def onInit(self):
        self.setFocusId(9201)

    def onClick(self, control_id):
        if control_id == 9201:
            self.proceed = True
            self.close()
        elif control_id == 9202:
            self.proceed = False
            self.close()
        elif control_id in self.BENEFITS:
            self._show_benefit_details(control_id)

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_PREVIOUS_MENU,
                               xbmcgui.ACTION_NAV_BACK,
                               xbmcgui.ACTION_STOP):
            self.proceed = False
            self.close()

    def _show_benefit_details(self, benefit_id):
        benefit = self.BENEFITS.get(benefit_id)
        if not benefit:
            return
        panel = PLUSBenefitPanel(
            'PLUSBenefitPanel.xml',
            ADDON_PATH,
            'Default',
            '1080i',
            title=benefit['title'],
            description=benefit['description']
        )
        panel.doModal()
        del panel


# ============================================================
# DIALOG 2 — Formulário de login
# ============================================================

class PLUSLoginDialog(xbmcgui.WindowXMLDialog):
    """
    Formulário de login PLUS.
    IDs:
        9101 — edit usuário
        9102 — edit senha
        9103 — botão Entrar
        9104 — botão Cancelar
        9110 — label de erro (hidden por padrão)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username          = ''
        self.password          = ''
        self.confirmed         = False
        self._error            = kwargs.get('error_msg', '')
        self._prefill_username = kwargs.get('prefill_username', '')
        self._prefill_password = kwargs.get('prefill_password', '')

    def onInit(self):
        # Exibe mensagem de erro se veio de tentativa anterior
        if self._error:
            try:
                lbl = self.getControl(9110)
                lbl.setLabel(self._error)
                lbl.setVisible(True)
            except Exception:
                pass

        if self._prefill_username:
            try:
                self.getControl(9101).setText(self._prefill_username)
            except Exception:
                pass

        if self._prefill_password:
            try:
                self.getControl(9102).setText(self._prefill_password)
            except Exception:
                pass

        # Foca na senha se usuário já está preenchido, senão foca no usuário
        if self._prefill_username:
            self.setFocusId(9103 if self._prefill_password else 9102)
        else:
            self.setFocusId(9101)

    def onClick(self, control_id):
        if control_id == 9103:
            self._do_login()
        elif control_id == 9104:
            self.confirmed = False
            self.close()

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (xbmcgui.ACTION_PREVIOUS_MENU,
                         xbmcgui.ACTION_NAV_BACK,
                         xbmcgui.ACTION_STOP):
            self.confirmed = False
            self.close()
            return
        if action_id in (xbmcgui.ACTION_SELECT_ITEM,
                         xbmcgui.ACTION_MOVE_RIGHT):
            if self.getFocusId() in (9101, 9102):
                self._do_login()

    def _do_login(self):
        try:
            username = self.getControl(9101).getText().strip().lower()
            password = self.getControl(9102).getText().strip()
        except Exception:
            username, password = '', ''

        if not username or not password:
            self._show_error('Preencha usuário e senha.')
            return

        self.username  = username
        self.password  = password
        self.confirmed = True
        self.close()

    def _show_error(self, msg):
        try:
            lbl = self.getControl(9110)
            lbl.setLabel(msg)
            lbl.setVisible(True)
        except Exception:
            pass


# ============================================================
# MENSAGENS DE ERRO
# ============================================================

_ERROR_MESSAGES = {
    'wrong_password': 'Usuário ou senha incorretos.',
    'not_found':      'Usuário não encontrado ou inativo.',
    'vip_expired': 'Seu acesso PLUS expirou. Renove para continuar.',
    'offline':        'Sem conexão. Tente mais tarde.',
    'empty_fields':   'Preencha usuário e senha.',
    'rate_limited':   'Muitas tentativas. Aguarde alguns minutos.',
    'device_limit_reached': 'Limite de dispositivos atingido para esta conta.',
    'missing_device_id': 'Erro interno: device_id ausente. Atualize o addon.',
    'invalid_token': 'Sessão inválida. Faça login novamente.',
    'device_revoked': 'Este dispositivo foi revogado. Faça login novamente.',
}


# ============================================================
# GATE PRINCIPAL — fluxo info → login → autenticação
# ============================================================

def handle_vip_gate(action: str) -> bool:
    """
    Verifica acesso PLUS antes de executar a action.
    Fluxo: sessão válida → ok direto
           sem sessão → PLUSLoginDialog direto (WelcomeDialog só no primeiro acesso via router)
    Retorna True para prosseguir, False para bloquear.
    """
    if not requires_vip(action):
        return True

    if is_session_valid():
        return True

    # ── Verifica bloqueio antes de mostrar qualquer tela ─────────────────────
    blocked, seconds_left = _check_lockout()
    if blocked:
        _dialog_blocked(seconds_left)
        return False

    # ── Loop de login direto ──────────────────────────────────────────────────
    error_msg = ''

    while True:
        # Re-verifica bloqueio no início de cada tentativa
        blocked, seconds_left = _check_lockout()
        if blocked:
            _dialog_blocked(seconds_left)
            return False

        saved_username = get_saved_username()
        saved_password = get_saved_password()

        # Abre o dialog de login (com mensagem de erro da tentativa anterior, se houver)
        login = PLUSLoginDialog(
            'PLUSLoginDialog.xml',
            ADDON_PATH,
            'Default',
            '1080i',
            error_msg=error_msg,
            prefill_username=saved_username,
            prefill_password=saved_password,
        )
        login.doModal()

        if not login.confirmed:
            del login
            return False

        username = login.username
        password = login.password
        del login

        # Autenticação com indicador de progresso
        pDialog = xbmcgui.DialogProgress()
        pDialog.create('Cineroom PLUS', 'Verificando credenciais...')
        pDialog.update(50)
        ok, reason = authenticate(username, password)
        pDialog.close()

        # ── Login bem-sucedido ────────────────────────────────────────────────
        if ok:
            _reset_lockout()
            user = get_current_vip_user()
            xbmcgui.Dialog().notification(
                'Cineroom PLUS',
                'Bem-vindo, ' + user + '!',
                xbmcgui.NOTIFICATION_INFO,
                3000,
            )
            return True

        # ── Erros que contam como tentativa falha ─────────────────────────────
        if reason in ('wrong_password', 'not_found', 'empty_fields'):
            attempts, blocked_until = _register_failed_attempt()

            if blocked_until:
                xbmcgui.Dialog().ok(
                    'Acesso Bloqueado',
                    'Limite de ' + str(MAX_ATTEMPTS) + ' tentativas atingido.\n'
                    'Aguarde 10 minutos para tentar novamente.'
                )
                return False

            remaining = MAX_ATTEMPTS - attempts
            error_msg = (
                'Senha incorreta. '
                + str(remaining) + ' tentativa(s) restante(s).'
            )
            continue   # volta ao topo do while → reabre PLUSLoginDialog

        # ── Erros que NÃO contam como tentativa (problema externo) ────────────

        if reason == 'device_limit_reached':
            blocked, seconds_left = _device_limit_is_blocked()
            if blocked:
                minutes = seconds_left // 60
                xbmcgui.Dialog().ok(
                    'Acesso Temporariamente Bloqueado',
                    'Muitas tentativas com limite de dispositivos atingido.\n'
                    'Tente novamente em [B]' + str(minutes) + ' minuto(s)[/B].\n\n'
                    'Entre em contato com o desenvolvedor via Telegram.'
                )
                return False

            attempts, blocked_until = _device_limit_register()
            from resources.lib.dialog.device_limit_dialog import show_device_limit_dialog
            show_device_limit_dialog()
            return False

        msg = _ERROR_MESSAGES.get(reason, 'Falha na autenticação.')
        xbmcgui.Dialog().ok('[COLOR red]Acesso Negado[/COLOR]', msg)
        return False


# ============================================================
# LOGOUT PLUS
# ============================================================

def handle_vip_logout() -> bool:
    user   = get_current_vip_user()
    dialog = xbmcgui.Dialog()

    if not user:
        dialog.notification('PLUS', 'Nenhum usuário PLUS conectado.',
                            xbmcgui.NOTIFICATION_INFO, 3000)
        return True

    if dialog.yesno('Sair do PLUS', 'Desconectar [COLOR gold]' + user + '[/COLOR]?'):
        logout()
        dialog.notification('PLUS', 'Sessão PLUS encerrada.',
                            xbmcgui.NOTIFICATION_INFO, 2500)
    return True


# ============================================================
# ITEM DE STATUS PLUS PARA MENUS
# ============================================================

def get_plus_status_item() -> dict:
    user = get_current_vip_user()
    if user:
        expiry = get_vip_expiry_str()
        return {
            'title': '[COLOR gold]★ PLUS — ' + user + '[/COLOR]',
            'action': 'vip_menu',
            'icon':   'DefaultUser.png',
            'plot':   'Área PLUS ativa.\nUsuário: ' + user + '\nPlano válido até: ' + expiry,
        }
    return {
        'title': '[COLOR gold]★ Área PLUS[/COLOR]',
        'action': 'vip_menu',
        'icon':   'DefaultUser.png',
        'plot':   'Faça login para desbloquear recursos de organização PLUS e categorias adicionais.',
    }