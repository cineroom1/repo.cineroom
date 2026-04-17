# -*- coding: utf-8 -*-
import xbmcgui
import xbmc
from xbmcaddon import Addon
import xbmcvfs


ADDON = Addon('plugin.video.cineroom.lite')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))


class CineroomHomeMenu(xbmcgui.WindowXMLDialog):
    """Home Menu customizado do Cineroom - 8 botões em grid 2x4"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile_name = kwargs.get('profile_name', 'Usuário')
        self.is_kids = kwargs.get('is_kids', False)
        self.age_range = kwargs.get('age_range', '')
    
    def onInit(self):
        """Inicialização do dialog"""
        # Define nome do perfil
        if self.is_kids:
            self.setProperty("ProfileName", f"{self.profile_name}")
            self.setProperty("ProfileColor", "FFFF9800")  # Laranja para kids
            
            # Adiciona indicador de modo infantil
            age_text = f"Modo Infantil" if self.age_range else "Modo Infantil"
            self.setProperty("KidsMode", age_text)
            
            # 🔒 OCULTA BOTÃO TRAKT PARA PERFIS KIDS
            try:
                trakt_btn = self.getControl(104)
                trakt_btn.setVisible(False)
            except:
                pass
            
            # 🔒 OCULTA BOTÃO TOOLS PARA PERFIS KIDS
            try:
                tools_btn = self.getControl(107)
                tools_btn.setVisible(False)
            except:
                pass
        else:
            self.setProperty("ProfileName", f"{self.profile_name}")
            self.setProperty("ProfileColor", "FFFFFFFF")  # Branco para adulto
            
            # Garante que TRAKT e TOOLS estão visíveis para adultos
            try:
                trakt_btn = self.getControl(104)
                trakt_btn.setVisible(True)
            except:
                pass
            
            try:
                tools_btn = self.getControl(107)
                tools_btn.setVisible(True)
            except:
                pass
        
        # Foca no botão Filmes por padrão
        try:
            self.setFocusId(101)
        except:
            pass
    
    def onClick(self, controlID):
        """Handler de cliques nos botões"""
        try:
            # BOTÃO SAIR (108) - Fecha sem animação e volta pro Kodi
            if controlID == 108:
                self.close()
                xbmc.executebuiltin('ActivateWindow(home)')
                return
            
            # Animação de saída para outros botões
            self.setProperty('closing', 'true')
            xbmc.sleep(250)  # Aguarda fade out
            
            # Fecha dialog
            self.close()
            
            # MAPEAMENTO DE ROTAS
            routes = {
                101: 'movies_menu',           # Filmes → Abre submenu
                102: 'tvshows_menu',          # Séries → Abre submenu
                103: 'favorites_menu',        # Minha Lista
                104: 'trakt_main_menu',       # Trakt → Abre submenu (oculto para kids)
                105: 'search',                # Pesquisa
                106: 'profile_select',        # Perfil → Abre menu de perfis
                107: 'tools_menu',            # Tools → Abre menu ferramentas (oculto para kids)
            }
            
            action = routes.get(controlID)
            
            if action:
                # USA CONTAINER.UPDATE em vez de ActivateWindow
                # Isso mantém o histórico correto de navegação
                xbmc.executebuiltin(
                    f'Container.Update('
                    f'plugin://plugin.video.cineroom.lite/?action={action})'
                )
        
        except Exception as e:
            xbmc.log(f"[CINEROOM HOME] onClick error: {e}", xbmc.LOGERROR)
            self.close()
    
    def onAction(self, action):
        """Handler de ações (back, esc)"""
        action_id = action.getId()
        
        # Fecha ao pressionar back/esc e vai pro Kodi Home
        if action_id in (10, 92, xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()
            xbmc.executebuiltin('ActivateWindow(home)')
    
    def __del__(self):
        """Cleanup"""
        pass


def show_home_menu(profile_name="Usuário", is_kids=False, age_range=""):
    """
    Mostra o Home Menu customizado
    
    Args:
        profile_name: Nome do perfil atual
        is_kids: Se é perfil infantil (True/False)
        age_range: Faixa etária do perfil infantil (ex: "3-7 anos")
    """
    win = CineroomHomeMenu(
        "CineroomHomeMenu.xml",
        ADDON_PATH,
        "Default",
        "1080i",
        profile_name=profile_name,
        is_kids=is_kids,
        age_range=age_range
    )
    win.doModal()
    del win