# -*- coding: utf-8 -*-
"""
rating_dialog.py — Overlay de avaliação durante a reprodução

Exibe um dialog no canto inferior direito quando o usuário atinge 80% do filme/série.
O vídeo continua tocando (WindowDialog é não-bloqueante).
O dialog fecha automaticamente em 10 segundos ou ao clicar em Gostei/Não Gostei.

Fluxo:
  service.py (_PlayerMonitor.onAVStarted)
      → lê item_info do addon setting '_now_playing'
      → inicia start_progress_monitor() em thread daemon
      → ao atingir 80% → abre RatingOverlay (WindowDialog)
      → usuário vota ou timer fecha
      → salva resultado em user_ratings (SQLite)
"""

import xbmc
import xbmcgui
import xbmcaddon
import threading
import time

ADDON = xbmcaddon.Addon()

TRIGGER_PERCENT = 80.0   # % para exibir o overlay
AUTO_CLOSE_SEC  = 10     # segundos até fechar sozinho
CHECK_INTERVAL  = 5      # segundos entre cada checagem de progresso

# ── Layout (referência 1280×720 — Kodi escala para a resolução real) ──────────
_W  = 400
_H  = 120
_SW = 1280
_SH = 720
_MG = 40

_X = _SW - _W - _MG
_Y = _SH - _H - _MG

# ── Cores ─────────────────────────────────────────────────────────────────────
_BG    = '0xDD0D0D0D'
_WHITE = '0xFFFFFFFF'
_GRAY  = '0xFFAAAAAA'
_GREEN = '0xFF2ECC71'
_RED   = '0xFFE74C3C'


# ══════════════════════════════════════════════════════════════════════════════
# WindowDialog — não bloqueia o player
# ══════════════════════════════════════════════════════════════════════════════

class RatingOverlay(xbmcgui.WindowDialog):
    """
    Overlay flutuante sobre o player.
    Layout:
    ┌────────────────────────────────────────┐
    │  O que achou?                          │
    │  Título do Conteúdo                    │
    │  [ 👍 Gostei ]    [ 👎 Não Gostei ]   │
    └────────────────────────────────────────┘
    """

    _ID_LIKE    = 1
    _ID_DISLIKE = 2

    def __init__(self, item_info: dict):
        super().__init__()
        self._item_info  = item_info
        self.choice      = None        # 'like' | 'dislike' | None
        self._dismissed  = False
        self._timer      = None
        self._build_ui()

    def _build_ui(self):
        # Fundo escuro semi-transparente
        self._bg = xbmcgui.ControlImage(_X, _Y, _W, _H, '', colorDiffuse=_BG)
        self.addControl(self._bg)

        # "O que achou?"
        self.addControl(xbmcgui.ControlLabel(
            _X + 14, _Y + 10, _W - 28, 28,
            '[B]O que achou?[/B]',
            font='font13', textColor=_WHITE,
        ))

        # Título (com S##E## para séries)
        raw = self._item_info.get('title', '')
        if self._item_info.get('media_type') == 'tvshow':
            s = self._item_info.get('season')
            e = self._item_info.get('episode')
            if s and e:
                raw = f'{raw}  S{int(s):02d}E{int(e):02d}'
        short = (raw[:34] + '…') if len(raw) > 34 else raw
        self.addControl(xbmcgui.ControlLabel(
            _X + 14, _Y + 38, _W - 28, 22,
            short,
            font='font12', textColor=_GRAY,
        ))

        # Botão Gostei
        self._btn_like = xbmcgui.ControlButton(
            _X + 14, _Y + 72, 178, 36,
            '[COLOR FF2ECC71]  👍  Gostei[/COLOR]',
            font='font12', focusedColor=_WHITE,
        )
        self.addControl(self._btn_like)

        # Botão Não Gostei
        self._btn_dislike = xbmcgui.ControlButton(
            _X + 206, _Y + 72, 178, 36,
            '[COLOR FFE74C3C]  👎  Não Gostei[/COLOR]',
            font='font12', focusedColor=_WHITE,
        )
        self.addControl(self._btn_dislike)

        # Navegação esquerda/direita entre botões
        self._btn_like.setNavigation(
            self._btn_like, self._btn_like,
            self._btn_like, self._btn_dislike,
        )
        self._btn_dislike.setNavigation(
            self._btn_dislike, self._btn_dislike,
            self._btn_like, self._btn_dislike,
        )

    def onInit(self):
        self.setFocus(self._btn_like)
        # Timer de fechamento automático
        self._timer = threading.Timer(AUTO_CLOSE_SEC, self._auto_close)
        self._timer.daemon = True
        self._timer.start()

    def onClick(self, control_id):
        if self._dismissed:
            return
        if control_id == self._ID_LIKE:
            self.choice = 'like'
        elif control_id == self._ID_DISLIKE:
            self.choice = 'dislike'
        self._dismiss()

    def onAction(self, action):
        if action.getId() in (
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_STOP,
        ):
            self._dismiss()

    def _auto_close(self):
        try:
            self.close()
        except Exception:
            pass

    def _dismiss(self):
        if self._dismissed:
            return
        self._dismissed = True
        if self._timer:
            self._timer.cancel()
        try:
            self.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# Monitor de progresso — roda em thread daemon dentro do service.py
# ══════════════════════════════════════════════════════════════════════════════

def start_progress_monitor(item_info: dict):
    """
    Ponto de entrada chamado pelo service.py via _PlayerMonitor.onAVStarted.
    Inicia a thread de monitoramento.
    """
    t = threading.Thread(
        target=_progress_monitor,
        args=(item_info,),
        daemon=True,
    )
    t.start()


def _progress_monitor(item_info: dict):
    """
    Verifica o progresso a cada CHECK_INTERVAL segundos.
    Dispara o overlay uma única vez ao atingir TRIGGER_PERCENT.
    """
    player  = xbmc.Player()
    tmdb_id = item_info.get('tmdb_id')

    if not tmdb_id:
        return

    # Aguarda player iniciar (até 30s)
    for _ in range(30):
        if player.isPlaying():
            break
        time.sleep(1)
    else:
        return

    time.sleep(5)  # estabiliza

    while player.isPlaying():
        try:
            pos   = player.getTime()
            total = player.getTotalTime()

            if total > 60:
                pct = (pos / total) * 100.0
                xbmc.log(f'[RatingOverlay] Progresso: {pct:.1f}%', xbmc.LOGDEBUG)

                if pct >= TRIGGER_PERCENT:
                    if not _already_rated(tmdb_id, item_info.get('media_type', 'movie')):
                        _show_overlay(item_info)
                    return  # encerra o monitor, overlay exibido ou já avaliado

        except Exception:
            pass

        time.sleep(CHECK_INTERVAL)


def _show_overlay(item_info: dict):
    """Exibe o RatingOverlay e salva a escolha."""
    try:
        overlay = RatingOverlay(item_info)
        overlay.doModal()
        choice = overlay.choice
        del overlay

        if choice in ('like', 'dislike'):
            _save_rating(
                tmdb_id    = item_info.get('tmdb_id'),
                media_type = item_info.get('media_type', 'movie'),
                rating     = choice,
                profile_id = _get_profile_id(),
            )
            xbmc.log(
                f'[RatingOverlay] "{choice}" salvo — tmdb_id={item_info.get("tmdb_id")}',
                xbmc.LOGINFO,
            )

    except Exception as e:
        xbmc.log(f'[RatingOverlay] Erro ao exibir: {e}', xbmc.LOGERROR)


# ══════════════════════════════════════════════════════════════════════════════
# Persistência
# ══════════════════════════════════════════════════════════════════════════════

def _get_profile_id():
    try:
        from resources.lib.vip_auth import is_session_valid
        if not is_session_valid():
            return None
        from resources.lib.profile_manager import ProfileManager
        profile = ProfileManager().get_current_profile()
        return profile.get('id') if profile else None
    except Exception:
        return None


def _ensure_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_ratings (
            tmdb_id    INTEGER  NOT NULL,
            media_type TEXT     NOT NULL,
            profile_id TEXT,
            rating     TEXT     NOT NULL,
            rated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (tmdb_id, media_type, profile_id)
        )
    """)


def _already_rated(tmdb_id, media_type) -> bool:
    """Retorna True se este item já foi avaliado — evita repetir o overlay."""
    try:
        from resources.lib.db.history_db import history_db
        conn   = history_db._get_conn()
        cursor = conn.cursor()
        try:
            _ensure_table(cursor)
            cursor.execute(
                "SELECT 1 FROM user_ratings "
                "WHERE tmdb_id=? AND media_type=? AND profile_id IS ? LIMIT 1",
                (int(tmdb_id), media_type, _get_profile_id()),
            )
            return cursor.fetchone() is not None
        finally:
            history_db._release_conn(conn)
    except Exception:
        return False


def _save_rating(tmdb_id, media_type, rating, profile_id=None):
    try:
        from resources.lib.db.history_db import history_db
        conn   = history_db._get_conn()
        cursor = conn.cursor()
        try:
            _ensure_table(cursor)
            cursor.execute(
                "INSERT OR REPLACE INTO user_ratings "
                "(tmdb_id, media_type, profile_id, rating, rated_at) "
                "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (int(tmdb_id), media_type, profile_id, rating),
            )
            conn.commit()
        finally:
            history_db._release_conn(conn)
    except Exception as e:
        xbmc.log(f'[RatingOverlay] Erro ao salvar: {e}', xbmc.LOGERROR)


# ── Helpers para o módulo de recomendações ────────────────────────────────────

def get_liked_items(media_type='movie', profile_id=None, limit=200):
    """tmdb_ids curtidos — consumido por recommendations.py."""
    try:
        from resources.lib.db.history_db import history_db
        conn   = history_db._get_conn()
        cursor = conn.cursor()
        try:
            _ensure_table(cursor)
            cursor.execute(
                "SELECT tmdb_id FROM user_ratings "
                "WHERE media_type=? AND profile_id IS ? AND rating='like' "
                "ORDER BY rated_at DESC LIMIT ?",
                (media_type, profile_id, limit),
            )
            return [r[0] for r in cursor.fetchall()]
        finally:
            history_db._release_conn(conn)
    except Exception:
        return []


def get_disliked_items(media_type='movie', profile_id=None):
    """tmdb_ids não curtidos — consumido por recommendations.py."""
    try:
        from resources.lib.db.history_db import history_db
        conn   = history_db._get_conn()
        cursor = conn.cursor()
        try:
            _ensure_table(cursor)
            cursor.execute(
                "SELECT tmdb_id FROM user_ratings "
                "WHERE media_type=? AND profile_id IS ? AND rating='dislike'",
                (media_type, profile_id),
            )
            return [r[0] for r in cursor.fetchall()]
        finally:
            history_db._release_conn(conn)
    except Exception:
        return []