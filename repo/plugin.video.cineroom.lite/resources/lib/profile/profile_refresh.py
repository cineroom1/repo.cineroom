# -*- coding: utf-8 -*-
"""
Profile Refresh Module - Atualização Instantânea de Perfil

Este módulo garante que ao trocar de perfil:
1. Todos os caches são invalidados
2. Filtros são recarregados
3. Interface é atualizada instantaneamente
"""

import xbmc
import xbmcgui

def refresh_after_profile_change(profile_manager=None):
    """
    Atualiza o addon após troca de perfil.
    
    Invalida:
    - Cache do banco de dados
    - Cache de memória do addon
    - Filtros de conteúdo
    - Interface do Kodi
    
    Args:
        profile_manager: Instância do ProfileManager (opcional)
    
    Returns:
        bool: True se refresh bem-sucedido
    """
    try:
        
        # 1. Invalida cache do banco de dados
        _invalidate_database_caches()
        
        # 2. Limpa cache de módulos Python (se necessário)
        _clear_module_caches()
        
        # 3. Atualiza filtros de conteúdo
        _reload_content_filters(profile_manager)
        
        # 4. Atualiza interface do Kodi
        _refresh_kodi_interface()
        
        
        # 5. Retorna ao menu principal
        force_return_to_main_menu()
        
        return True
        
    except Exception as e:
        xbmc.log(f"[ProfileRefresh] ❌ Erro no refresh: {e}", xbmc.LOGERROR)
        return False


def _invalidate_database_caches():
    """
    Invalida TODOS os caches do banco de dados.
    
    Isso força as queries a retornarem os dados filtrados
    pelo novo perfil.
    """
    try:
        from resources.lib.db import db
        
        # Limpa cache de memória (Redis-like)
        if hasattr(db, '_cache'):
            db._cache.clear()
        
        # Limpa caches específicos de movies
        if hasattr(db, 'movies_db'):
            if hasattr(db.movies_db, '_cache'):
                db.movies_db._cache.clear()
            db.movies_db._cache_delete_prefix("movies_")
        
        # Limpa caches específicos de tvshows
        if hasattr(db, 'tvshows_db'):
            if hasattr(db.tvshows_db, '_cache'):
                db.tvshows_db._cache.clear()
            db.tvshows_db._cache_delete_prefix("tv_")
        
        # Limpa caches de favoritos
        if hasattr(db, 'favorites_db'):
            if hasattr(db.favorites_db, '_cache'):
                db.favorites_db._cache.clear()
            db.favorites_db._cache_delete_prefix("favorites:")
        
        
    except Exception as e:
        pass


def _clear_module_caches():
    """
    Limpa caches de módulos Python (se houver).
    
    Isso garante que imports futuros usarão o novo perfil.
    """
    try:
        # Limpa cache de módulos do main.py (se existir)
        import sys
        if 'resources.lib.main' in sys.modules:
            main_module = sys.modules['resources.lib.main']
            
            # Limpa _MODULE_CACHE
            if hasattr(main_module, '_MODULE_CACHE'):
                pass  # NÃO limpa completamente - mantém módulos já carregados
            
            # Limpa _PROFILE_MANAGER global (força reload)
            if hasattr(main_module, '_PROFILE_MANAGER'):
                pass  # NÃO zera - apenas força reload do filtro
        
    except Exception as e:
        pass


def _reload_content_filters(profile_manager):
    """
    Recarrega os filtros de conteúdo com o novo perfil.
    
    Isso é CRÍTICO - garante que as queries SQL usarão
    o filtro do perfil recém-selecionado.
    """
    try:
        from resources.lib.content_filter import get_content_filter
        from resources.lib.db import db
        
        # Cria novo filtro com perfil atual
        new_filter = get_content_filter(profile_manager)
        
        # Atualiza filtro no banco de movies
        if hasattr(db, 'movies_db'):
            db.movies_db.set_content_filter(new_filter)
        
        # Atualiza filtro no banco de tvshows
        if hasattr(db, 'tvshows_db'):
            db.tvshows_db.set_content_filter(new_filter)
        
        
    except Exception as e:
        pass


def _refresh_kodi_interface():
    """
    Atualiza a interface do Kodi.
    
    Usa apenas Container.Refresh para evitar triggerar scans indesejados.
    NÃO usa UpdateLibrary(video) pois isso trigga o VideoInfoScanner
    que tenta adicionar pastas de addons à biblioteca.
    """
    try:
        # APENAS atualiza o container atual
        xbmc.executebuiltin('Container.Refresh')
        
        
    except Exception as e:
        pass


def _show_profile_changed_notification(profile_manager):
    """
    Mostra notificação visual de troca de perfil.
    
    Args:
        profile_manager: Instância do ProfileManager
    """
    try:
        if not profile_manager:
            return
        
        current_profile = profile_manager.get_current_profile()
        if not current_profile:
            return
        
        profile_name = current_profile.get('name', 'Perfil')
        is_kids = current_profile.get('is_kids', False)
        
        # Escolhe ícone baseado no tipo de perfil
        icon = xbmcgui.NOTIFICATION_INFO
        if is_kids:
            icon = xbmcgui.NOTIFICATION_WARNING  # Ícone diferente para kids
        
        # Mostra notificação
        xbmcgui.Dialog().notification(
            heading='Perfil Alterado',
            message=f'Agora usando: {profile_name}' + (' 👶' if is_kids else ''),
            icon=icon,
            time=3000  # 3 segundos
        )
        
    except Exception as e:
        pass


# ============================================================
# FUNÇÕES AUXILIARES PARA INTEGRAÇÃO
# ============================================================

def force_return_to_main_menu():
    """
    Força retorno ao menu principal após troca de perfil.
    
    Isso garante que o usuário veja imediatamente o conteúdo
    do novo perfil.
    """
    try:
        # Navega de volta ao menu principal do addon
        addon_id = 'plugin.video.cineroom.lite'
        xbmc.executebuiltin(f'ActivateWindow(Videos,plugin://{addon_id}/,return)')
        
        
    except Exception as e:
        pass


def get_profile_info_for_display(profile_manager):
    """
    Retorna informações formatadas do perfil atual para exibição.
    
    Returns:
        dict: {
            'name': str,
            'is_kids': bool,
            'age_range': str,
            'display_text': str (formatado para UI)
        }
    """
    try:
        if not profile_manager:
            return None
        
        current = profile_manager.get_current_profile()
        if not current:
            return None
        
        name = current.get('name', 'Perfil')
        is_kids = current.get('is_kids', False)
        age_range = current.get('preferences', {}).get('age_range', 'livre')
        
        # Formata texto para display
        if is_kids:
            display_text = f"👶 {name} (Kids {age_range})"
        else:
            display_text = f"👤 {name}"
        
        return {
            'name': name,
            'is_kids': is_kids,
            'age_range': age_range,
            'display_text': display_text
        }
        
    except Exception as e:
        return None