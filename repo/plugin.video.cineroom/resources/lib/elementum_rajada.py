import xbmc
import xbmcgui
import xbmcplugin
from urllib.parse import quote_plus
import sys

HANDLE = int(sys.argv[1])


def is_elementum_installed():
    """Verifica se o Elementum está instalado"""
    return xbmc.getCondVisibility('System.HasAddon(plugin.video.elementum)') == 1


def show_elementum_burst_search_from_title(title, year=None):
    """Abre a busca no Elementum com o título e ano (se fornecido)"""
    if not title:
        title = 'Filme'
    
    search_query = f"{title} {year}" if year else title
    formatted_query = quote_plus(search_query.strip())
    
    search_url = f'plugin://script.elementum.rajada?search={formatted_query}'
    
    xbmc.executebuiltin('Dialog.Close(all,true)')
    xbmc.executebuiltin('Sleep(500)')
    xbmc.executebuiltin(f'ActivateWindow(Videos, "{search_url}")')


def play_elementum(tmdb_id, title):
    """Reproduz diretamente usando o Elementum se o TMDB ID estiver disponível"""
    elementum_url = f"plugin://plugin.video.elementum/library/play/movie/{tmdb_id}"
    list_item = xbmcgui.ListItem(label=title)
    list_item.setPath(elementum_url)
    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=list_item)
    

def process_elementum_choice(tmdb_id, title, year=None):
    """Processa a escolha do usuário apenas quando há um link do Elementum (magnet ou plugin)"""
    if not is_elementum_installed():
        xbmcgui.Dialog().notification('Elementum não instalado', 'O Elementum não foi encontrado.', xbmcgui.NOTIFICATION_ERROR)
        return "cancel"

    # Esse menu só deve aparecer quando o usuário clicou em um link magnet
    options = ["Usar link padrão", "Buscar com Elementum", "Cancelar"]
    escolha = xbmcgui.Dialog().select("Fonte Elementum", options)

    if escolha == 0:
        return "use_link"
    elif escolha == 1:
        if not tmdb_id:
            show_elementum_burst_search_from_title(title, year)
        else:
            play_elementum(tmdb_id, title)
        return "search"
    else:
        xbmcplugin.endOfDirectory(HANDLE)
        return "cancel"
