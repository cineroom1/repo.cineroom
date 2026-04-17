# -*- coding: utf-8 -*-
"""
History Backup/Restore — Exportar e Importar Histórico
✅ Pasta padrão configurável — não pede pasta toda vez
✅ Backup automático silencioso chamado pelo service.py (VIP)
✅ Rotação automática: mantém apenas os N backups mais recentes
✅ Exportação manual com UI interativa (VIP)
✅ Importação disponível para todos (free e VIP)
✅ Inclui favoritos e watchlist
✅ Compatível com Free (sem profile_id) e VIP (com profile_id)
"""

import os
import json
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
from datetime import datetime

ADDON      = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')

# Versão do schema — permite detectar incompatibilidades no futuro
BACKUP_VERSION = 1

# Quantos arquivos de backup manter na rotação automática
MAX_AUTO_BACKUPS = 5

# Setting IDs usados no settings.xml
SETTING_BACKUP_FOLDER = 'backup.folder'
SETTING_BACKUP_AUTO   = 'backup.auto_enabled'
SETTING_BACKUP_LAST   = 'backup.last_auto'   # hidden/interno


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[CR Backup] {msg}', level)


def _notify(msg, icon=xbmcgui.NOTIFICATION_INFO, ms=3000):
    xbmcgui.Dialog().notification(ADDON_NAME, msg, icon, ms)


def _is_vip():
    """Verifica se o usuário tem sessão VIP ativa."""
    try:
        from resources.lib.vip_auth import is_session_valid
        return is_session_valid()
    except Exception:
        return False


def _should_use_profiles():
    try:
        return ADDON.getSettingBool('use_profile_isolation')
    except Exception:
        return False


def _get_active_profile_id():
    if not _should_use_profiles():
        return None
    try:
        from resources.lib.profile_manager import ProfileManager
        profile = ProfileManager().get_current_profile()
        return profile.get('id') if profile else None
    except Exception:
        return None


def _get_backup_folder():
    """
    Retorna a pasta de backup configurada, ou None se não configurada.
    Garante que termina com '/'.
    """
    folder = ADDON.getSetting(SETTING_BACKUP_FOLDER)
    if not folder or not folder.strip():
        return None
    folder = folder.strip()
    if not folder.endswith('/') and not folder.endswith('\\'):
        folder += '/'
    return folder


def _browse_folder(heading='Selecionar pasta', default=''):
    """Abre o browser de pastas do Kodi."""
    path = xbmcgui.Dialog().browse(
        3, heading, 'files', '', False, False, default
    )
    return path if path and path.strip() else None


def _rotate_backups(folder, profile_id=None):
    """
    Mantém apenas MAX_AUTO_BACKUPS arquivos mais recentes na pasta.
    Remove os mais antigos silenciosamente.
    """
    try:
        pid_token = f'_{profile_id}' if profile_id else ''
        prefix    = f'cineroom_backup{pid_token}_'

        _, files = xbmcvfs.listdir(folder)
        backup_files = sorted(
            [f for f in files if f.startswith(prefix) and f.endswith('.json')]
        )

        while len(backup_files) >= MAX_AUTO_BACKUPS:
            old = backup_files.pop(0)
            xbmcvfs.delete(folder + old)
            _log(f'Rotação: removido backup antigo {old}')
    except Exception as e:
        _log(f'Erro na rotação de backups: {e}', xbmc.LOGWARNING)


# ── CORE: montar payload de backup ────────────────────────────────────────────

def _build_backup_payload(profile_id, export_favorites=True, export_watchlist=True,
                          progress_cb=None):
    """
    Coleta todos os dados e retorna o dict de backup pronto para serializar.
    progress_cb(pct, msg) é chamado durante a coleta (opcional).
    """
    def _prog(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    backup = {
        'version':     BACKUP_VERSION,
        'addon':       ADDON.getAddonInfo('id'),
        'profile_id':  profile_id,
        'exported_at': datetime.now().isoformat(),
        'history':     [],
        'favorites':   [],
        'watchlist':   [],
    }

    _prog(10, 'Lendo histórico...')
    from resources.lib.db.history_db import history_db
    for item in history_db.get_history(profile_id=profile_id, limit=99999):
        backup['history'].append({
            'tmdb_id':    item.get('tmdb_id'),
            'media_type': item.get('media_type'),
            'season':     item.get('season'),
            'episode':    item.get('episode'),
            'progress':   item.get('progress', 0.0),
            'watched_at': item.get('watched_at'),
            '_title':     item.get('title'),
            '_year':      item.get('year'),
        })

    _prog(45, 'Lendo favoritos...')
    if export_favorites:
        try:
            from resources.lib.db.favorites_db import favorites_db
            for item in favorites_db.get_all_favorites(profile_id=profile_id):
                backup['favorites'].append({
                    'tmdb_id':    item.get('tmdb_id'),
                    'media_type': item.get('media_type'),
                    '_title':     item.get('title'),
                })
        except Exception as e:
            _log(f'Favoritos indisponíveis: {e}', xbmc.LOGWARNING)

    _prog(70, 'Lendo watchlist...')
    if export_watchlist:
        try:
            from resources.lib.db.watchlist_db import watchlist_db
            for item in watchlist_db.get_all_watchlist(profile_id=profile_id):
                backup['watchlist'].append({
                    'tmdb_id':    item.get('tmdb_id'),
                    'media_type': item.get('media_type'),
                    '_title':     item.get('title'),
                })
        except Exception as e:
            _log(f'Watchlist indisponível: {e}', xbmc.LOGWARNING)

    return backup


def _save_backup_to_folder(backup, folder, profile_id=None):
    """
    Serializa e salva o backup na pasta indicada.
    Retorna o filepath completo ou levanta exceção.
    """
    timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')
    pid_suffix = f'_{profile_id}' if profile_id else ''
    filename   = f'cineroom_backup{pid_suffix}_{timestamp}.json'
    filepath   = folder + filename

    f  = xbmcvfs.File(filepath, 'w')
    ok = f.write(json.dumps(backup, ensure_ascii=False, indent=2))
    f.close()

    if not ok:
        raise IOError(f'Falha ao escrever arquivo: {filepath}')

    return filepath


# ── BACKUP SILENCIOSO (chamado pelo service) ───────────────────────────────────

def run_auto_backup():
    """
    Executa backup automático silencioso.
    Chamado pelo service.py a cada ciclo (24h).

    Requisitos:
      - Usuário VIP
      - backup.auto_enabled = true
      - backup.folder configurada e acessível

    Não exibe diálogos — apenas notificação discreta no final.
    Aplica rotação automática de arquivos.
    """
    if not _is_vip():
        _log('Auto-backup ignorado: usuário não é VIP.')
        return

    if ADDON.getSetting(SETTING_BACKUP_AUTO) != 'true':
        _log('Auto-backup desativado nas configurações.')
        return

    folder = _get_backup_folder()
    if not folder:
        _log('Auto-backup: pasta não configurada, ignorando.', xbmc.LOGWARNING)
        return

    if not xbmcvfs.exists(folder):
        _log(f'Auto-backup: pasta inacessível: {folder}', xbmc.LOGWARNING)
        return

    profile_id = _get_active_profile_id()

    try:
        _log(f'Iniciando auto-backup (perfil: {profile_id or "global"})...')

        _rotate_backups(folder, profile_id)
        backup   = _build_backup_payload(profile_id)
        filepath = _save_backup_to_folder(backup, folder, profile_id)

        h_count = len(backup['history'])
        ADDON.setSetting(SETTING_BACKUP_LAST, datetime.now().isoformat())

        _log(f'Auto-backup concluído: {h_count} itens → {filepath}')
        _notify(f'Backup automático salvo ({h_count} itens)', ms=2500)

    except Exception as e:
        _log(f'Erro no auto-backup: {e}', xbmc.LOGERROR)


# ── EXPORTAÇÃO MANUAL (VIP) ───────────────────────────────────────────────────

def export_history(profile_id=None):
    """
    Exporta histórico manualmente com UI interativa.
    Exclusivo VIP.
    """
    if not _is_vip():
        xbmcgui.Dialog().ok(
            ADDON_NAME,
            'O backup manual do histórico é uma [B]funcionalidade VIP[/B].\n\n'
            'Faça login com sua conta VIP para utilizar este recurso.'
        )
        return

    if profile_id is None:
        profile_id = _get_active_profile_id()

    dialog = xbmcgui.Dialog()

    # ── Pasta de destino ──────────────────────────────────────────────────────
    saved_folder = _get_backup_folder()

    if saved_folder:
        use_saved = dialog.yesno(
            'Pasta de backup',
            f'Pasta configurada:\n[B]{saved_folder}[/B]\n\nUsar esta pasta?',
            nolabel='Escolher outra',
            yeslabel='Usar esta',
        )
        if use_saved:
            folder = saved_folder
        else:
            folder = _browse_folder('Onde salvar o backup?', saved_folder)
            if not folder:
                return
            if dialog.yesno(ADDON_NAME, 'Definir esta pasta como padrão para backups futuros?'):
                ADDON.setSetting(SETTING_BACKUP_FOLDER, folder)
    else:
        folder = _browse_folder('Onde salvar o backup?')
        if not folder:
            return
        if dialog.yesno(ADDON_NAME, 'Definir esta pasta como padrão para backups futuros?'):
            ADDON.setSetting(SETTING_BACKUP_FOLDER, folder)

    # ── O que exportar ────────────────────────────────────────────────────────
    choice = dialog.select('O que deseja exportar?', [
        'Histórico + Favoritos + Watchlist',
        'Somente Histórico',
    ])
    if choice < 0:
        return

    export_favorites = (choice == 0)
    export_watchlist = (choice == 0)

    # ── Progresso ─────────────────────────────────────────────────────────────
    pbar = xbmcgui.DialogProgress()
    pbar.create(ADDON_NAME, 'Preparando backup...')

    try:
        backup = _build_backup_payload(
            profile_id, export_favorites, export_watchlist,
            progress_cb=lambda pct, msg: pbar.update(pct, msg)
        )
        pbar.update(85, 'Salvando arquivo...')
        _rotate_backups(folder, profile_id)
        filepath = _save_backup_to_folder(backup, folder, profile_id)
        pbar.update(100, 'Concluído!')

    except Exception as e:
        pbar.close()
        _log(f'Erro ao exportar: {e}', xbmc.LOGERROR)
        _notify(f'Erro ao exportar: {e}', xbmcgui.NOTIFICATION_ERROR)
        return

    pbar.close()

    h_count  = len(backup['history'])
    fv_count = len(backup['favorites'])
    wl_count = len(backup['watchlist'])

    lines = ['✔ Backup salvo com sucesso!', '', f'📂 {filepath}', '',
             f'🎬 Histórico:  {h_count} itens']
    if export_favorites:
        lines.append(f'⭐ Favoritos:  {fv_count} itens')
    if export_watchlist:
        lines.append(f'📋 Watchlist:  {wl_count} itens')

    ADDON.setSetting(SETTING_BACKUP_LAST, datetime.now().isoformat())
    dialog.ok(ADDON_NAME, '\n'.join(lines))


# ── IMPORTAÇÃO (free e VIP) ───────────────────────────────────────────────────

def import_history(profile_id=None):
    """
    Importa um arquivo JSON de backup. Disponível para todos.
    O browser já abre na pasta padrão, se configurada.
    """
    if profile_id is None:
        profile_id = _get_active_profile_id()

    default_folder = _get_backup_folder() or ''
    filepath = xbmcgui.Dialog().browse(
        1, 'Selecionar arquivo de backup (.json)',
        'files', '.json', False, False, default_folder
    )
    if not filepath or not filepath.strip():
        return

    # ── Ler e validar ─────────────────────────────────────────────────────────
    try:
        f   = xbmcvfs.File(filepath, 'r')
        raw = f.read()
        f.close()
        backup = json.loads(raw)
    except Exception as e:
        _notify(f'Não foi possível ler o arquivo: {e}', xbmcgui.NOTIFICATION_ERROR)
        return

    if not isinstance(backup, dict) or 'history' not in backup:
        _notify('Arquivo inválido ou incompatível.', xbmcgui.NOTIFICATION_ERROR)
        return

    if backup.get('version', 0) > BACKUP_VERSION:
        _notify('Backup criado em versão mais nova. Atualize o addon.',
                xbmcgui.NOTIFICATION_ERROR)
        return

    h_count     = len(backup.get('history',   []))
    fv_count    = len(backup.get('favorites', []))
    wl_count    = len(backup.get('watchlist', []))
    exported_at = backup.get('exported_at', 'desconhecido')

    dialog   = xbmcgui.Dialog()
    info_msg = (
        f'Arquivo: {os.path.basename(filepath)}\n'
        f'Exportado em: {exported_at}\n\n'
        f'🎬 Histórico:  {h_count} itens\n'
        f'⭐ Favoritos:  {fv_count} itens\n'
        f'📋 Watchlist:  {wl_count} itens\n\n'
        f'Como deseja importar?'
    )

    mode = dialog.select(info_msg, [
        'Mesclar  (mantém histórico atual + adiciona novos)',
        'Substituir  (apaga histórico atual e importa tudo)',
    ])
    if mode < 0:
        return

    replace_mode = (mode == 1)

    if replace_mode and not dialog.yesno(
        ADDON_NAME,
        'Tem certeza? O histórico atual será [B]apagado[/B] antes de importar.',
        nolabel='Cancelar', yeslabel='Substituir',
    ):
        return

    # ── Importar ──────────────────────────────────────────────────────────────
    pbar = xbmcgui.DialogProgress()
    pbar.create(ADDON_NAME, 'Importando backup...')

    imported_h = imported_fv = imported_wl = errors = 0

    try:
        from resources.lib.db.history_db import history_db

        if replace_mode:
            pbar.update(5, 'Limpando histórico atual...')
            history_db.clear_history(profile_id=profile_id)

        history_items = backup.get('history', [])
        total = max(len(history_items), 1)

        for i, item in enumerate(history_items):
            if pbar.iscanceled():
                break
            pbar.update(10 + int((i / total) * 60), f'Histórico: {i + 1}/{total}...')

            tmdb_id    = item.get('tmdb_id')
            media_type = item.get('media_type')
            if not tmdb_id or not media_type:
                errors += 1
                continue
            try:
                history_db.add_to_history(
                    tmdb_id=int(tmdb_id), media_type=media_type,
                    profile_id=profile_id,
                    season=item.get('season'), episode=item.get('episode'),
                    progress=float(item.get('progress', 0.0)),
                )
                imported_h += 1
            except Exception as e:
                _log(f'Erro item {tmdb_id}: {e}', xbmc.LOGWARNING)
                errors += 1

        pbar.update(72, 'Importando favoritos...')
        if fv_count > 0:
            try:
                from resources.lib.db.favorites_db import favorites_db
                if replace_mode:
                    favorites_db.clear_all_favorites(profile_id=profile_id)
                for item in backup.get('favorites', []):
                    if item.get('tmdb_id') and item.get('media_type'):
                        favorites_db.add_to_favorites(
                            int(item['tmdb_id']), item['media_type'], profile_id=profile_id)
                        imported_fv += 1
            except Exception as e:
                _log(f'Erro favoritos: {e}', xbmc.LOGWARNING)

        pbar.update(88, 'Importando watchlist...')
        if wl_count > 0:
            try:
                from resources.lib.db.watchlist_db import watchlist_db
                if replace_mode:
                    watchlist_db.clear_watchlist(profile_id=profile_id)
                for item in backup.get('watchlist', []):
                    if item.get('tmdb_id') and item.get('media_type'):
                        watchlist_db.add_to_watchlist(
                            int(item['tmdb_id']), item['media_type'], profile_id=profile_id)
                        imported_wl += 1
            except Exception as e:
                _log(f'Erro watchlist: {e}', xbmc.LOGWARNING)

        pbar.update(100, 'Concluído!')

    except Exception as e:
        pbar.close()
        _log(f'Erro geral na importação: {e}', xbmc.LOGERROR)
        _notify(f'Erro durante a importação: {e}', xbmcgui.NOTIFICATION_ERROR)
        return

    pbar.close()

    mode_label = 'substituição' if replace_mode else 'mesclagem'
    lines = [f'✔ Importação por {mode_label} concluída!', '',
             f'🎬 Histórico importado:  {imported_h} itens']
    if fv_count > 0:
        lines.append(f'⭐ Favoritos importados: {imported_fv} itens')
    if wl_count > 0:
        lines.append(f'📋 Watchlist importada:  {imported_wl} itens')
    if errors > 0:
        lines.append(f'\n⚠ {errors} itens ignorados (dados inválidos)')

    dialog.ok(ADDON_NAME, '\n'.join(lines))
    xbmc.executebuiltin('Container.Refresh')


# ── CONFIGURAR PASTA PADRÃO (VIP) ────────────────────────────────────────────

def configure_backup_folder():
    """
    Abre browser para o usuário escolher/alterar a pasta padrão.
    Exclusivo VIP. Chamado pela action 'backup_configure'.
    """
    if not _is_vip():
        xbmcgui.Dialog().ok(ADDON_NAME,
            'A configuração de pasta é uma [B]funcionalidade VIP[/B].')
        return

    current = _get_backup_folder() or ''
    folder  = _browse_folder('Escolha a pasta padrão para backups', default=current)
    if not folder:
        return

    ADDON.setSetting(SETTING_BACKUP_FOLDER, folder)
    _notify('Pasta de backup definida!', ms=2500)
    xbmc.executebuiltin('Container.Refresh')


def toggle_auto_backup():
    """
    Alterna o backup automático on/off.
    Exclusivo VIP. Chamado pela action 'backup_toggle_auto'.
    Se estiver ativando e não houver pasta configurada, pede agora.
    """
    if not _is_vip():
        xbmcgui.Dialog().ok(ADDON_NAME, 'Funcionalidade [B]VIP[/B].')
        return

    current = ADDON.getSetting(SETTING_BACKUP_AUTO) == 'true'
    new_val = not current

    if new_val and not _get_backup_folder():
        folder = _browse_folder('Escolha a pasta para os backups automáticos')
        if not folder:
            return
        ADDON.setSetting(SETTING_BACKUP_FOLDER, folder)

    ADDON.setSetting(SETTING_BACKUP_AUTO, 'true' if new_val else 'false')
    _notify(f'Backup automático {"ativado" if new_val else "desativado"}!', ms=2500)
    xbmc.executebuiltin('Container.Refresh')


# ── MENU ──────────────────────────────────────────────────────────────────────

def show_backup_menu():
    """
    Menu de Backup/Restore exibido dentro do histórico.
    VIP: exportar, configurar pasta, ligar auto-backup.
    Free: somente importar (com aviso sobre VIP).
    """
    import sys
    import xbmcplugin
    from urllib.parse import urlencode

    HANDLE   = int(sys.argv[1])
    BASE_URL = sys.argv[0]

    def _url(**kw):
        return f'{BASE_URL}?{urlencode(kw)}'

    vip = _is_vip()

    xbmcplugin.setPluginCategory(HANDLE, 'Backup do Histórico')
    xbmcplugin.setContent(HANDLE, 'files')

    if not vip:
        li = xbmcgui.ListItem(
            label='[COLOR yellow]💎 Exportar e Backup Automático são recursos VIP[/COLOR]')
        li.setInfo('video', {'plot':
            'Faça login com sua conta VIP para desbloquear o backup automático e a exportação manual.'})
        xbmcplugin.addDirectoryItem(HANDLE, '', li, isFolder=False)

    if vip:
        auto_on    = ADDON.getSetting(SETTING_BACKUP_AUTO) == 'true'
        auto_label = '[COLOR green]✔ Ativado[/COLOR]' if auto_on else '[COLOR gray]Desativado[/COLOR]'
        last_bk    = ADDON.getSetting(SETTING_BACKUP_LAST) or 'nunca'
        folder_lbl = _get_backup_folder() or 'Não configurada'

        vip_items = [
            (
                'Exportar Agora',
                f'Salva histórico, favoritos e watchlist.\nPasta: {folder_lbl}',
                'backup_export',
            ),
            (
                f'Backup Automático: {auto_label}',
                f'Backup feito automaticamente a cada 24h pelo serviço.\nÚltimo: {last_bk}',
                'backup_toggle_auto',
            ),
            (
                'Alterar Pasta Padrão',
                f'Pasta atual: {folder_lbl}',
                'backup_configure',
            ),
        ]
        for label, plot, action in vip_items:
            li = xbmcgui.ListItem(label=label)
            li.setInfo('video', {'plot': plot})
            li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(HANDLE, _url(action=action), li, isFolder=False)

    # Importar: disponível para todos
    li = xbmcgui.ListItem(label='⬇  Importar / Restaurar')
    li.setInfo('video', {'plot': 'Restaura a partir de um arquivo .json. Disponível para todos.'})
    li.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(HANDLE, _url(action='backup_import'), li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)