# -*- coding: utf-8 -*-
"""
Sistema de Avaliação Pós-Playback para Trakt - COM DIÁLOGO VISUAL
✅ Usa o diálogo bonito de estrelas (script-trakt-RatingDialog.xml)
✅ Interface visual elegante
✅ Apenas para usuários autenticados
✅ Configurável (pode desativar)
✅ Não bloqueia navegação
"""

import xbmc
import xbmcgui
import xbmcaddon
import time
import threading
from datetime import datetime

ADDON = xbmcaddon.Addon()


class TraktRatingDialog(xbmcgui.WindowXMLDialog):
    """
    Diálogo de avaliação visual com estrelas (1-10)
    Baseado no design do script.trakt oficial
    """
    
    def __init__(self, *args, **kwargs):
        self.item_info = kwargs.get('item_info', {})
        self.progress = kwargs.get('progress', 0)
        self.rating = None
        
        # IDs dos controles (baseado no XML customizado)
        self.CONTROL_HEADING = 10011
        self.CONTROL_TITLE = 10012
        self.CONTROL_BOTTOM_TEXT = 10013
        self.CONTROL_BUTTON_1 = 11030
        self.CONTROL_BUTTON_10 = 11039
        
        xbmcgui.WindowXMLDialog.__init__(self)
    
    def onInit(self):
        """Inicializa o diálogo"""
        try:
            # Título principal
            self.getControl(self.CONTROL_HEADING).setLabel("Como você avalia?")
            
            # Nome do filme/série
            title_text = self._format_title()
            self.getControl(self.CONTROL_TITLE).setLabel(title_text)
            
            # Texto inferior
            self.getControl(self.CONTROL_BOTTOM_TEXT).setLabel(
                "Selecione de 1 (horrível) a 10 (obra-prima)"
            )
            
            # Foca no botão 10 (padrão otimista)
            self.setFocus(self.getControl(self.CONTROL_BUTTON_10))
            
        except Exception as e:
            xbmc.log(f"[Rating Dialog] Erro no onInit: {e}", xbmc.LOGERROR)
    
    def _format_title(self):
        """Formata título do item"""
        media_type = self.item_info.get('media_type')
        
        if media_type == 'movie':
            title = self.item_info.get('title', 'Filme')
            year = self.item_info.get('year')
            
            if year:
                return f"{title} ({year})"
            return title
            
        elif media_type == 'tvshow':
            show_title = self.item_info.get('title', 'Série')
            season = self.item_info.get('season', 0)
            episode = self.item_info.get('episode', 0)
            episode_title = self.item_info.get('episode_title', '')
            
            parts = [f"{show_title} - S{season:02d}E{episode:02d}"]
            
            if episode_title:
                parts.append(episode_title)
            
            return " - ".join(parts)
        
        return "Item"
    
    def onClick(self, controlId):
        """Quando clica em um botão de avaliação"""
        # Botões de 1 a 10
        if self.CONTROL_BUTTON_1 <= controlId <= self.CONTROL_BUTTON_10:
            # Calcula rating (11030 = 1, 11031 = 2, ... 11039 = 10)
            self.rating = controlId - self.CONTROL_BUTTON_1 + 1
            
            
            # Fecha diálogo
            self.close()
    
    def onAction(self, action):
        """Ações do controle remoto"""
        # ESC, Voltar, etc
        if action.getId() in (9, 10, 92, 216, 247, 257, 275, 61467, 61448):
            self.rating = None
            self.close()


def show_rating_dialog(item_info, progress):
    """
    Exibe diálogo de avaliação após playback
    
    Args:
        item_info: Informações do item reproduzido
        progress: Progresso final (0-100)
    
    Returns:
        bool: True se avaliou, False se cancelou/pulou
    """
    # ✅ CACHE DE CONFIGURAÇÕES (busca UMA VEZ só)
    try:
        ask_rating_enabled = ADDON.getSettingBool('trakt_ask_rating_after_playback')
        min_progress = int(ADDON.getSetting('trakt_rating_min_progress') or 70)

        # Preferir o novo; se não existir ainda, cai no antigo
        if ADDON.getSetting('trakt_show_rating_notifications') != '':
            show_notifications = ADDON.getSettingBool('trakt_show_rating_notifications')
        else:
            show_notifications = ADDON.getSettingBool('trakt_show_notifications')

    except Exception:
        ask_rating_enabled = True
        min_progress = 70
        show_notifications = True

    
    # Verifica se feature está habilitada
    if not ask_rating_enabled:
        return False
    
    # Verifica autenticação
    from resources.lib.trakt.trakt_sync import get_trakt_settings, refresh_trakt_token
    
    settings = get_trakt_settings()
    if not settings.get('access_token'):
        return False

    
    # Só exibe se assistiu significativamente
    if progress < min_progress:
        return False
    
    try:
        # ✅ OTIMIZAÇÃO: Pega o path do addon UMA VEZ
        addon_path = ADDON.getAddonInfo('path')
        
        # Cria e exibe diálogo customizado
        dialog = TraktRatingDialog(
            'script-trakt-RatingDialog.xml',
            addon_path,
            'default',
            '1080i',
            item_info=item_info,
            progress=progress
        )
        
        dialog.doModal()
        
        rating = dialog.rating
        del dialog
        
        if rating is None:
            return False

        if not refresh_trakt_token():
            xbmcgui.Dialog().notification(
                "Trakt",
                "Falha na autenticação (token expirado)",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            return False

        # Envia avaliação
        success = _send_rating_to_trakt(item_info, rating)
        
        if success:
            # Notificação elegante
            if show_notifications:  # ✅ Usa variável cacheada
                stars = "⭐" * rating
                xbmcgui.Dialog().notification(
                    "Trakt",
                    f"{stars} Nota {rating}/10!",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
            return True
        else:
            xbmcgui.Dialog().notification(
                "Trakt",
                "Erro ao enviar avaliação",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
            return False
    
    except Exception as e:
        xbmc.log(f"[Rating] Erro ao exibir diálogo: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        
        # Fallback: usa diálogo simples
        return _show_simple_rating_dialog(item_info, progress)


def _show_simple_rating_dialog(item_info, progress):
    """
    Fallback: diálogo simples caso o XML não esteja disponível
    """
    media_type = item_info.get('media_type')
    
    if media_type == 'movie':
        title = item_info.get('title', 'Filme')
        dialog_title = f"Avaliar: {title}"
    elif media_type == 'tvshow':
        show_title = item_info.get('title', 'Série')
        season = item_info.get('season', 0)
        episode = item_info.get('episode', 0)
        dialog_title = f"Avaliar: {show_title} S{season:02d}E{episode:02d}"
    else:
        return False
    
    # Opções de avaliação
    options = [
        "⭐ 10 - Obra-prima!",
        "⭐ 9 - Excelente",
        "⭐ 8 - Muito bom",
        "⭐ 7 - Bom",
        "⭐ 6 - Razoável",
        "⭐ 5 - Mediano",
        "⭐ 4 - Fraco",
        "⭐ 3 - Ruim",
        "⭐ 2 - Muito ruim",
        "⭐ 1 - Horrível",
        "🚫 Não avaliar agora"
    ]
    
    choice = xbmcgui.Dialog().select(dialog_title, options)
    
    if choice < 0 or choice == 10:
        return False
    
    rating = 10 - choice
    
    success = _send_rating_to_trakt(item_info, rating)
    
    if success:
        xbmcgui.Dialog().notification(
            "Trakt",
            f"Avaliado com nota {rating}!",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return True
    
    return False


def _send_rating_to_trakt(item_info, rating):
    """
    Envia avaliação para o Trakt
    
    Args:
        item_info: Dados do item
        rating: Nota de 1 a 10
    
    Returns:
        bool: Sucesso/falha
    """
    try:
        from resources.lib.trakt.trakt_sync import trakt_request
        
        media_type = item_info.get('media_type')
        tmdb_id = item_info.get('tmdb_id')
        
        if not tmdb_id:
            xbmc.log("[Rating] TMDB ID não encontrado", xbmc.LOGERROR)
            return False
        
        rated_at = datetime.now().isoformat()
        
        # Monta payload baseado no tipo
        if media_type == 'movie':
            payload = {
                'movies': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'rating': int(rating),
                    'rated_at': rated_at
                }]
            }
            
        elif media_type == 'tvshow':
            season = item_info.get('season')
            episode = item_info.get('episode')
            
            if not season or not episode:
                xbmc.log("[Rating] Season/Episode não encontrados", xbmc.LOGERROR)
                return False
            
            # Para séries, avaliamos o episódio específico
            # API Trakt aceita show + season + episode
            payload = {
                'shows': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'seasons': [{
                        'number': int(season),
                        'episodes': [{
                            'number': int(episode),
                            'rating': int(rating),
                            'rated_at': rated_at
                        }]
                    }]
                }]
            }
        else:
            return False
        
        # Envia para Trakt
        
        response = trakt_request('POST', '/sync/ratings', payload)
        
        if response:
            return True
        else:
            xbmc.log("[Rating] ✗ Falha ao enviar avaliação", xbmc.LOGERROR)
            return False
        
    except Exception as e:
        xbmc.log(f"[Rating] Erro ao enviar avaliação: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        return False


def ask_rating_after_playback(item_info, progress, delay=1):
    """
    Agenda pergunta de avaliação com delay
    (não-bloqueante, executa em thread separada)
    
    Args:
        item_info: Informações do item
        progress: Progresso final
        delay: Segundos para esperar antes de perguntar
    """
    def _delayed_ask():
        time.sleep(delay)
        
        # Verifica se usuário não iniciou outro playback
        player = xbmc.Player()
        if player.isPlaying():
            return
        
        # Exibe diálogo
        show_rating_dialog(item_info, progress)
    
    # Executa em thread separada para não bloquear
    thread = threading.Thread(target=_delayed_ask, daemon=True)
    thread.start()


# ============================================
# AVALIAÇÃO VIA MENU DE CONTEXTO
# ============================================

def rate_item_from_context_menu(tmdb_id, media_type, season=None, episode=None, title=None):
    """
    Permite avaliar item via menu de contexto
    (pode ser chamado de qualquer lugar)
    
    Args:
        tmdb_id: ID do TMDB
        media_type: 'movie' ou 'tvshow'
        season: Temporada (para séries)
        episode: Episódio (para séries)
        title: Título do item (opcional)
    
    Returns:
        bool: Sucesso/falha
    """
    from resources.lib.trakt.trakt_sync import get_trakt_settings, refresh_trakt_token
    
    # Verifica autenticação
    settings = get_trakt_settings()
    if not settings.get('access_token'):
        xbmcgui.Dialog().ok("Trakt", "Você precisa estar autenticado no Trakt.")
        return False

    
    # Monta item_info mínimo
    item_info = {
        'tmdb_id': tmdb_id,
        'media_type': media_type,
        'season': season,
        'episode': episode,
        'title': title or f"Item {tmdb_id}"
    }
    
    # Se for série, busca informações do episódio
    if media_type == 'tvshow' and season and episode:
        try:
            from resources.lib import tmdb_api
            episode_details = tmdb_api.get_episode_details(tmdb_id, season, episode)
            
            if episode_details:
                item_info['episode_title'] = episode_details.get('name', '')
        except Exception as e:
            pass
    
    return show_rating_dialog(item_info, progress=75)