# -*- coding: utf-8 -*-
"""
Profile Stats — Estatísticas de visualização por perfil (VIP)

Estatísticas disponíveis:
- Gêneros mais assistidos
- Minutos/horas assistidos
- Filmes e séries concluídos
- Streak (dias seguidos assistindo)
"""

import xbmc
import xbmcgui
import xbmcaddon
import json
from .db.history_db import history_db

ADDON = xbmcaddon.Addon()

# Progresso mínimo para considerar "concluído"
MIN_PROGRESS_COMPLETED = 85.0


def get_profile_stats(profile_id):
    """
    Retorna todas as estatísticas do perfil em um único dict.

    Args:
        profile_id: ID do perfil VIP

    Returns:
        dict com todas as estatísticas, ou None em caso de erro
    """
    if not profile_id:
        return None

    try:
        stats = {}
        stats['completed']     = history_db.get_completed_count(profile_id)
        stats['watch_time']    = history_db.get_total_watch_time(profile_id)
        stats['top_genres']    = history_db.get_top_genres(profile_id, limit=5)
        stats['streak']        = history_db.get_streak(profile_id)
        stats['formatted']     = _format_stats(stats)
        return stats

    except Exception as e:
        xbmc.log(f"[ProfileStats] Erro ao calcular stats: {e}", xbmc.LOGERROR)
        return None


def _format_stats(stats):
    """
    Formata as estatísticas para exibição na UI.

    Returns:
        dict com strings prontas para exibir
    """
    # Tempo assistido
    total_min = stats['watch_time'].get('total_minutes', 0)
    if total_min >= 60:
        hours = total_min // 60
        mins  = total_min % 60
        time_str = f"{hours}h {mins}min" if mins else f"{hours}h"
    else:
        time_str = f"{total_min}min"

    # Concluídos
    completed = stats['completed']
    completed_str = (
        f"{completed.get('movies', 0)} filmes · "
        f"{completed.get('tvshows', 0)} séries"
    )

    # Streak
    streak = stats['streak']
    streak_days = streak.get('current', 0)
    if streak_days == 0:
        streak_str = "Nenhuma sequência ativa"
    elif streak_days == 1:
        streak_str = "1 dia seguido 🔥"
    else:
        streak_str = f"{streak_days} dias seguidos 🔥"

    # Gêneros top 3 para resumo
    genres = stats['top_genres']
    genres_str = " · ".join(g['genre'] for g in genres[:3]) if genres else "Nenhum ainda"

    return {
        'watch_time':  time_str,
        'completed':   completed_str,
        'streak':      streak_str,
        'top_genres':  genres_str,
    }


def show_stats_dialog(profile_id, profile_name):
    """
    Exibe dialog de estatísticas do perfil.

    Args:
        profile_id: ID do perfil
        profile_name: Nome do perfil (para o título do dialog)
    """
    try:
        from resources.lib.vip_auth import is_session_valid
        if not is_session_valid():
            xbmcgui.Dialog().ok(
                "VIP Necessário",
                "Estatísticas de perfil são exclusivas para membros VIP."
            )
            return
    except Exception:
        pass

    stats = get_profile_stats(profile_id)

    if not stats:
        xbmcgui.Dialog().notification(
            "Estatísticas",
            "Nenhuma visualização registrada ainda.",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return

    fmt      = stats['formatted']
    genres   = stats['top_genres']
    streak   = stats['streak']
    watchtime = stats['watch_time']

    # ── Monta texto do dialog ──────────────────────────────────────────────
    lines = []

    lines.append(f"[B]⏱ Tempo assistido[/B]")
    lines.append(f"  {fmt['watch_time']}")
    lines.append(f"  Filmes: {watchtime.get('movies_minutes', 0) // 60}h {watchtime.get('movies_minutes', 0) % 60}min")
    lines.append(f"  Séries: {watchtime.get('tvshows_minutes', 0) // 60}h {watchtime.get('tvshows_minutes', 0) % 60}min")
    lines.append("")

    lines.append(f"[B]✅ Concluídos[/B]")
    lines.append(f"  {fmt['completed']}")
    lines.append("")

    lines.append(f"[B]🔥 Sequência atual[/B]")
    lines.append(f"  {fmt['streak']}")
    if streak.get('best', 0) > 0:
        lines.append(f"  Recorde: {streak['best']} dias")
    lines.append("")

    lines.append(f"[B]🎬 Gêneros favoritos[/B]")
    if genres:
        for i, g in enumerate(genres, 1):
            bar = "█" * min(g['count'], 10)
            lines.append(f"  {i}. {g['genre']}  {bar} ({g['count']}x)")
    else:
        lines.append("  Nenhum dado ainda")

    text = "\n".join(lines)

    xbmcgui.Dialog().textviewer(
        f"📊 Estatísticas — {profile_name}",
        text
    )