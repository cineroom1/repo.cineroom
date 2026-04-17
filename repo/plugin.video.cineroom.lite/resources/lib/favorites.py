# -*- coding: utf-8 -*-
"""
Favorites Module - Sistema de Favoritos com Perfil OPCIONAL
✅ Retrocompatível com sistema antigo (sem perfis)
✅ Suporta perfis quando habilitado
✅ Resolve profile_id AUTOMATICAMENTE do perfil ativo
✅ Configurável via settings
"""

import xbmcgui
import xbmcaddon
import xbmc

ADDON = xbmcaddon.Addon()


def _should_use_profiles():
    try:
        return ADDON.getSettingBool('use_profile_isolation')
    except:
        return False


def _resolve_profile_id(profile_id=None):
    """
    Garante que o profile_id correto seja usado:
    - Se perfis não estão ativos → sempre None (pool global)
    - Se o chamador passou profile_id explícito → usa ele
    - Se não passou (None) → resolve AUTOMATICAMENTE do perfil ativo

    Isso evita o bug onde o chamador esquece de passar profile_id e
    o favorito vai para o pool global, aparecendo em Kids e Adultos.
    """
    if not _should_use_profiles():
        return None

    if profile_id is not None:
        return profile_id

    # Resolve automaticamente do perfil ativo — ponto crítico do isolamento
    try:
        from resources.lib.profile_manager import ProfileManager
        pm = ProfileManager()
        profile = pm.get_current_profile()
        if profile:
            pid = profile.get('id')
            return pid
    except Exception as e:
        pass

    return None


FREE_FAVORITES_LIMIT = 50

def add_item_to_favorites(tmdb_id, media_type, profile_id=None):
    from resources.lib.db.favorites_db import favorites_db
    from resources.lib.vip_auth import is_session_valid

    resolved_id = _resolve_profile_id(profile_id)

    # ── Gate Free ────────────────────────────────────────────────────────────
    if not is_session_valid():
        count = favorites_db.get_favorites_count(profile_id=resolved_id)
        if count['total'] >= FREE_FAVORITES_LIMIT:
            xbmcgui.Dialog().ok(
                '[COLOR gold]Limite Atingido[/COLOR]',
                f'Usuários Free podem salvar até {FREE_FAVORITES_LIMIT} itens.\n\n'
                'Faça upgrade para [COLOR gold]PLUS[/COLOR] e salve sem limites.'
            )
            return
    # ─────────────────────────────────────────────────────────────────────────

    favorites_db.add_to_favorites(tmdb_id, media_type, profile_id=resolved_id)

    xbmcgui.Dialog().notification(
        "Minha Lista",
        "Adicionado à sua lista!",
        xbmcgui.NOTIFICATION_INFO
    )


def remove_item_from_favorites(tmdb_id, media_type, profile_id=None):
    """
    Remove item dos favoritos do perfil ativo.
    profile_id é opcional — se não informado, usa o perfil ativo automaticamente.
    """
    from resources.lib.db.favorites_db import favorites_db

    resolved_id = _resolve_profile_id(profile_id)
    favorites_db.remove_from_favorites(tmdb_id, media_type, profile_id=resolved_id)

    xbmcgui.Dialog().notification(
        "Minha Lista",
        "Removido da sua lista.",
        xbmcgui.NOTIFICATION_INFO
    )


def is_favorite(tmdb_id, media_type, profile_id=None):
    """
    Verifica se item é favorito no perfil ativo.
    profile_id é opcional — se não informado, usa o perfil ativo automaticamente.
    """
    from resources.lib.db.favorites_db import favorites_db

    resolved_id = _resolve_profile_id(profile_id)
    return favorites_db.is_favorite(tmdb_id, media_type, profile_id=resolved_id)


def get_all_favorites(profile_id=None):
    """
    Retorna todos os favoritos do perfil ativo.
    profile_id é opcional — se não informado, usa o perfil ativo automaticamente.
    """
    from resources.lib.db.favorites_db import favorites_db

    resolved_id = _resolve_profile_id(profile_id)
    return favorites_db.get_all_favorites(profile_id=resolved_id)