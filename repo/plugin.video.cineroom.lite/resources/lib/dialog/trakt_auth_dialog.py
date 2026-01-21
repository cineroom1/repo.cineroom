# -*- coding: utf-8 -*-
import xbmcgui
import xbmc

class TraktAuthDialog(xbmcgui.WindowXMLDialog):
    """Diálogo customizado para autenticação Trakt"""
    
    # IDs dos controles
    CODE_LABEL_ID = 2001
    BUTTON_CONFIRM = 9002
    BUTTON_CANCEL = 9003
    
    def __init__(self, *args, **kwargs):
        self.url = kwargs.get("url", "")
        self.user_code = kwargs.get("user_code", "")
        self.confirmed = False
        super(TraktAuthDialog, self).__init__(*args)

    def onInit(self):
        """Inicializa o diálogo com as informações de autenticação"""
        
        # Define o código diretamente no label
        try:
            code_label = self.getControl(self.CODE_LABEL_ID)
            code_label.setLabel(f"[B]{self.user_code}[/B]")
            xbmc.log(f"[Trakt Auth Dialog] Código definido: {self.user_code}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[Trakt Auth Dialog] Erro ao definir código: {e}", xbmc.LOGERROR)
        
        # Define o foco inicial no botão de confirmar
        self.setFocusId(self.BUTTON_CONFIRM)
        
        xbmc.log(f"[Trakt Auth Dialog] URL: {self.url}", xbmc.LOGINFO)
        xbmc.log(f"[Trakt Auth Dialog] Code: {self.user_code}", xbmc.LOGINFO)

    def onAction(self, action):
        """Trata ações do controle remoto/teclado"""
        action_id = action.getId()
        
        # Fecha o diálogo ao pressionar ESC ou Voltar
        if action_id in (xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK):
            self.confirmed = False
            self.close()

    def onClick(self, controlId):
        """Trata cliques nos botões"""
        if controlId == self.BUTTON_CONFIRM:
            self.confirmed = True
            self.close()
        elif controlId == self.BUTTON_CANCEL:
            self.confirmed = False
            self.close()
    
    def get_result(self):
        """Retorna True se o usuário confirmou, False se cancelou"""
        return self.confirmed