# -*- coding: utf-8 -*-
"""
Profile Indicator - Indicador Visual de Perfil

Adiciona ao menu principal:
- Nome do perfil atual
- Ícone kids/adulto
- Informações de filtros ativos
"""

import xbmc
import xbmcgui
import os


def add_profile_indicator_to_menu(menu_items, profile_manager, addon_path):
    """
    Adiciona item visual do perfil atual no TOPO do menu.
    
    Args:
        menu_items: Lista de itens do menu
        profile_manager: Instância do ProfileManager
        addon_path: Caminho do addon
    
    Returns:
        list: Menu com indicador de perfil adicionado
    """
    try:
        if not profile_manager:
            return menu_items
        
        current_profile = profile_manager.get_current_profile()
        if not current_profile:
            return menu_items
        
        # Cria item indicador
        indicator = _create_profile_indicator_item(current_profile, addon_path)
        
        # Adiciona no topo do menu
        return [indicator] + menu_items
        
    except Exception as e:
        return menu_items


def _create_profile_indicator_item(profile, addon_path):
    """
    Cria item de menu com informações do perfil atual.
    
    Returns:
        dict: Item de menu formatado
    """
    name = profile.get('name', 'Perfil')
    is_kids = profile.get('is_kids', False)
    age_range = profile.get('preferences', {}).get('age_range', 'livre')
    
    # Formata título com cor
    if is_kids:
        title = f"[COLOR yellow]👶 Perfil: {name} (Kids {age_range})[/COLOR]"
        plot = f"Perfil infantil ativo. Conteúdo filtrado para {age_range}."
        icon_name = 'kids_profile.png'
    else:
        title = f"[COLOR cyan]👤 Perfil: {name}[/COLOR]"
        plot = "Perfil adulto ativo. Todo conteúdo disponível."
        icon_name = 'profiles.png'
    
    # Caminho do ícone
    icon_path = os.path.join(addon_path, 'resources', 'medias', 'icons', icon_name)
    
    return {
        'title': title,
        'action': 'profile_info',  # Mostra detalhes do perfil
        'icon': icon_path,
        'plot': plot,
        'is_indicator': True  # Flag especial
    }


def show_profile_info_dialog(profile_manager):
    """
    Mostra dialog com informações detalhadas do perfil atual.
    
    Inclui:
    - Nome e tipo (kids/adulto)
    - Configurações de filtro
    - Estatísticas
    - Opção de trocar perfil
    """
    try:
        if not profile_manager:
            return
        
        current_profile = profile_manager.get_current_profile()
        if not current_profile:
            xbmcgui.Dialog().ok('Erro', 'Nenhum perfil ativo.')
            return
        
        # Monta informações
        info_lines = _build_profile_info_text(current_profile, profile_manager)
        
        # Mostra dialog
        dialog = xbmcgui.Dialog()
        
        # Menu de opções
        options = [
            'Ver Estatísticas 📊',
            'Trocar de Perfil',
            'Gerenciar Perfis',
            'Fechar'
        ]

        selected = dialog.select(
            f"Perfil Atual: {current_profile.get('name', 'Perfil')}",
            options
        )

        # Processa escolha
        if selected == 0:  # Ver Estatísticas
            try:
                from resources.lib.profile_stats import show_stats_dialog
                show_stats_dialog(
                    current_profile['id'],
                    current_profile.get('name', 'Perfil')
                )
            except Exception as e:
                xbmc.log(f"[ProfileIndicator] Erro ao abrir stats: {e}", xbmc.LOGERROR)

        elif selected == 1:  # Trocar perfil
            profile_manager.show_profile_selector()
            from resources.lib.profile.profile_refresh import refresh_after_profile_change
            refresh_after_profile_change(profile_manager)

        elif selected == 2:  # Gerenciar
            profile_manager.manage_profiles()
        
    except Exception as e:
        xbmc.log(f"[ProfileIndicator] Erro ao mostrar info: {e}", xbmc.LOGERROR)


def _build_profile_info_text(profile, profile_manager):
    """
    Constrói texto formatado com informações do perfil.
    
    Returns:
        list: Linhas de texto
    """
    lines = []
    
    # Nome e tipo
    name = profile.get('name', 'Perfil')
    is_kids = profile.get('is_kids', False)
    
    lines.append(f"Nome: {name}")
    lines.append(f"Tipo: {'Infantil 👶' if is_kids else 'Adulto 👤'}")
    
    # Configurações kids
    if is_kids:
        prefs = profile.get('preferences', {})
        age_range = prefs.get('age_range', 'livre')
        
        lines.append("")
        lines.append("Configurações de Filtro:")
        lines.append(f"  Faixa etária: {age_range}")
        lines.append(f"  Gêneros seguros: Animação, Família, Comédia")
        lines.append(f"  PG-13: Bloqueado")
        lines.append(f"  Ação/Terror: Bloqueado")
    
    # Whitelist/Blacklist
    whitelist_count = len(profile.get('content_whitelist', []))
    blacklist_count = len(profile.get('content_blacklist', []))
    
    if whitelist_count > 0 or blacklist_count > 0:
        lines.append("")
        lines.append("Listas personalizadas:")
        if whitelist_count > 0:
            lines.append(f"  ✅ Permitidos: {whitelist_count} itens")
        if blacklist_count > 0:
            lines.append(f"  ❌ Bloqueados: {blacklist_count} itens")
    
    # Estatísticas (se disponível)
    try:
        from resources.lib.db import db
        
        # Favoritos do perfil
        if hasattr(db, 'favorites_db'):
            count = db.favorites_db.get_favorites_count(profile['id'])
            if count and count['total'] > 0:
                lines.append("")
                lines.append("Favoritos:")
                lines.append(f"  Filmes: {count['movies']}")
                lines.append(f"  Séries: {count['tvshows']}")
                lines.append(f"  Total: {count['total']}")
    except:
        pass
    
    return lines


def create_profile_quick_switch_menu_item(addon_path):
    """
    Cria item de menu para troca rápida de perfil.
    
    Útil para adicionar em menus contextuais ou atalhos.
    
    Returns:
        dict: Item de menu
    """
    icon_path = os.path.join(addon_path, 'resources', 'medias', 'icons', 'profiles.png')
    
    return {
        'title': '[COLOR orange]⚡ Trocar Perfil Rápido[/COLOR]',
        'action': 'profile_quick_switch',
        'icon': icon_path,
        'plot': 'Troca rápida entre perfis com atualização instantânea.'
    }


def handle_profile_quick_switch(profile_manager):
    """
    Handler para troca rápida de perfil.
    
    Mostra lista de perfis e troca instantaneamente.
    """
    try:
        if not profile_manager:
            return
        
        # Mostra seletor
        new_profile = profile_manager.show_profile_selector()
        
        if new_profile:
            # Refresh instantâneo
            from resources.lib.profile.profile_refresh import (
                refresh_after_profile_change,
                force_return_to_main_menu
            )
            
            refresh_after_profile_change(profile_manager)
            force_return_to_main_menu()
            
    except Exception as e:
        xbmc.log(f"[ProfileIndicator] Erro na troca rápida: {e}", xbmc.LOGERROR)


# ============================================================
# INTEGRAÇÃO COM CONSTANTS.PY
# ============================================================

def get_menu_with_profile_indicator(menu_constant_name, profile_manager, addon_path):
    """
    Retorna menu com indicador de perfil adicionado.
    
    Use em navigation.py ou main.py ao mostrar menus.
    
    Example:
        # Em navigation.py:
        from resources.lib.profile_indicator import get_menu_with_profile_indicator
        
        def show_main_menu():
            pm = get_profile_manager()
            menu = get_menu_with_profile_indicator('MAIN_MENU', pm, ADDON_PATH)
            _show_menu_items(menu)
    
    Args:
        menu_constant_name: Nome do menu em constants (ex: 'MAIN_MENU')
        profile_manager: Instância do ProfileManager
        addon_path: Caminho do addon
    
    Returns:
        list: Menu com indicador
    """
    try:
        from resources.lib import constants
        
        # Pega menu original
        menu = getattr(constants, menu_constant_name, [])
        
        # Adiciona indicador
        return add_profile_indicator_to_menu(menu, profile_manager, addon_path)
        
    except Exception as e:
        return []