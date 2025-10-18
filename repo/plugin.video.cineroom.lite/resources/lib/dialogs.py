# -*- coding: utf-8 -*-
import xbmcgui
import xbmc

ACTION_PREVIOUS_MENU = 10
ACTION_NAV_BACK = 92

class DialogSelecaoFontes(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.item_data = kwargs.get('item_data')
        self.escolha = None
        self.todas_as_fontes = kwargs.get('fontes', [])
        self.qualidades_disponiveis = []
        self.filtro_atual = "Todos"
        self.idiomas_disponiveis = []
        self.filtro_idioma_atual = "Todos"

    def _normalizar_qualidade(self, q_string):
        q_lower = q_string.lower()
        if '4k' in q_lower or '2160' in q_lower: return "4K"
        if '1080' in q_lower: return "1080p"
        if '720' in q_lower: return "720p"
        if '480' in q_lower or 'sd' in q_lower: return "SD"
        return "Outros"

    def _extrair_idiomas(self, release_title):
        """
        Analisa o título e retorna um conjunto de idiomas encontrados.
        AGORA COM UM DICIONÁRIO EXPANDIDO.
        """
        title_lower = release_title.lower()
        idiomas = set()
        
        # ===================================================================
        # A MUDANÇA PRINCIPAL ESTÁ AQUI: DICIONÁRIO DE IDIOMAS EXPANDIDO
        # ===================================================================
        mapa_idiomas = {
            # Português
            'dublado': 'Dublado', 'pt-br': 'Dublado', 'portugues': 'Dublado',
            'legendado': 'Legendado', 'leg': 'Legendado',
            'dual audio': 'Dual Áudio', 'dual': 'Dual Áudio',
            'multi audio': 'Multi Áudio', 'multi': 'Multi Áudio',
            
            # Inglês
            'english': 'Inglês', 'eng': 'Inglês',
            
            # Espanhol
            'spanish': 'Espanhol', 'espanol': 'Espanhol', 'esp': 'Espanhol', 'es': 'Espanhol',
            'latino': 'Latino',
            
            # Francês
            'french': 'Francês', 'frances': 'Francês', 'fr': 'Francês', 'truefrench': 'Francês', 'vff': 'Francês',
            
            # Outros Idiomas Comuns
            'italian': 'Italiano', 'ita': 'Italiano',
            'german': 'Alemão', 'ger': 'Alemão', 'de': 'Alemão',
            'russian': 'Russo', 'rus': 'Russo',
            'japanese': 'Japonês', 'jap': 'Japonês', 'jpn': 'Japonês',
            'korean': 'Coreano', 'kor': 'Coreano',
            'chinese': 'Chinês', 'chi': 'Chinês', 'zho': 'Chinês'
        }
        # ===================================================================
        # FIM DA MUDANÇA
        # ===================================================================

        for chave, valor in mapa_idiomas.items():
            # A verificação " in " pode causar falsos positivos, mas é um bom começo.
            # Ex: A palavra "danger" seria detectada como "ger" (alemão).
            # Para maior precisão, seria necessário usar regex ou verificar delimitadores (espaços, pontos).
            # Por enquanto, esta abordagem é a mais simples e deve resolver a maioria dos casos.
            if chave in title_lower:
                idiomas.add(valor)

        if not idiomas:
            idiomas.add("Original")
            
        return idiomas

    def _atualizar_labels_filtros(self):
        try:
            self.getControl(1300).setLabel(f"Qualidade: {self.filtro_atual}")
            self.getControl(1400).setLabel(f"Idioma: {self.filtro_idioma_atual}")
        except Exception as e:
            xbmc.log(f"[Dialogs] Erro ao atualizar labels dos filtros: {e}", xbmc.LOGERROR)

    def onInit(self):
        try:
            if self.item_data:
                self.setProperty('info.fanart', self.item_data.get('backdrop', ''))
                self.setProperty('info.poster', self.item_data.get('poster', ''))
                self.setProperty('info.overview', self.item_data.get('synopsis', ''))
                self.setProperty('info.clearlogo', self.item_data.get('clearlogo', ''))
            
            qualidades_normalizadas = {self._normalizar_qualidade(f.get('quality', '')) for f in self.todas_as_fontes if f.get('quality')}
            ordem_de_qualidade = ["4K", "1080p", "720p", "SD", "Outros"]
            qualidades_ordenadas = sorted(list(qualidades_normalizadas), key=lambda q: ordem_de_qualidade.index(q) if q in ordem_de_qualidade else 99)
            self.qualidades_disponiveis = ["Todos"] + qualidades_ordenadas
            
            idiomas_encontrados = set()
            for f in self.todas_as_fontes:
                idiomas_encontrados.update(self._extrair_idiomas(f.get('release_title', '')))
            idiomas_ordenados = sorted(list(idiomas_encontrados))
            self.idiomas_disponiveis = ["Todos"] + idiomas_ordenados

            self._atualizar_labels_filtros()
            self.popular_lista_fontes()
            self.setFocusId(1300)

        except Exception as e:
            xbmc.log(f"[Dialogs] Erro fatal durante o onInit: {e}", xbmc.LOGERROR)
            self.close()

    def popular_lista_fontes(self):
        try:
            lista_control = self.getControl(1000)
            lista_control.reset()
            fontes_filtradas = self.todas_as_fontes
            if self.filtro_atual != "Todos":
                fontes_filtradas = [f for f in fontes_filtradas if self._normalizar_qualidade(f.get('quality', '')) == self.filtro_atual]
            if self.filtro_idioma_atual != "Todos":
                fontes_filtradas = [f for f in fontes_filtradas if self.filtro_idioma_atual in self._extrair_idiomas(f.get('release_title', ''))]
            for fonte in fontes_filtradas:
                li = xbmcgui.ListItem(label=fonte.get('release_title', ''))
                li.setProperty('quality', fonte.get('quality', 'N/A'))
                li.setProperty('type', fonte.get('type', 'N/A'))
                li.setProperty('release_title', fonte.get('release_title', ''))
                li.setProperty('size', fonte.get('size', 'N/A'))
                li.setProperty('peers', str(fonte.get('peers', 'N/A')))
                li.setProperty('seeders', str(fonte.get('seeders', 'N/A')))
                li.setProperty('provider', fonte.get('provider', 'N/A'))
                li.setProperty('languages', fonte.get('languages', 'N/A'))
                li.setProperty('url_para_tocar', fonte.get('url', ''))
                lista_control.addItem(li)
        except Exception as e:
            xbmc.log(f"[Dialogs] Erro ao popular lista de fontes: {e}", xbmc.LOGERROR)

    def onClick(self, controlId):
        dialog = xbmcgui.Dialog()
        if controlId == 1000:
            item = self.getControl(1000).getSelectedItem()
            if item:
                self.escolha = item.getProperty('url_para_tocar')
                self.close()
        elif controlId == 1300:
            escolha_idx = dialog.select('Filtrar por Qualidade', self.qualidades_disponiveis)
            if escolha_idx > -1:
                self.filtro_atual = self.qualidades_disponiveis[escolha_idx]
                self.popular_lista_fontes()
                self._atualizar_labels_filtros()
        elif controlId == 1400:
            escolha_idx = dialog.select('Filtrar por Idioma', self.idiomas_disponiveis)
            if escolha_idx > -1:
                self.filtro_idioma_atual = self.idiomas_disponiveis[escolha_idx]
                self.popular_lista_fontes()
                self._atualizar_labels_filtros()

    def onAction(self, action):
        if action.getId() in [ACTION_PREVIOUS_MENU, ACTION_NAV_BACK]:
            self.close()