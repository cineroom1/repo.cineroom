import os
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import json
import sys
from datetime import datetime
from urllib.parse import urlencode, parse_qsl

# Importa a função get_all_videos.
# Presumi que ela está em 'resources.lib.utils'.
# É crucial que esta função seja eficiente e, idealmente,
# não carregue o catálogo inteiro de uma vez, mas sim,
# permita buscar por ID para otimizar o desempenho.
from resources.lib.utils import get_all_videos



URL = sys.argv[0]
HANDLE = int(sys.argv[1])


ADDON_ID = xbmcaddon.Addon().getAddonInfo('id')
FAVORITES_FILE = xbmcvfs.translatePath(f"special://userdata/addon_data/{ADDON_ID}/favorites.json")


def show_notification(heading, message, icon=xbmcgui.NOTIFICATION_INFO, time=3000):
    """Exibe uma notificação no Kodi."""
    xbmcgui.Dialog().notification(heading, message, icon, time)

def get_url(**kwargs):
    """
    Cria uma URL para chamar o plugin recursivamente a partir dos argumentos fornecidos.
    """
    return '{}?{}'.format(URL, urlencode(kwargs))

def find_item_in_favorites(favorites_list, video_data):
    """
    Encontra um item na lista de favoritos por tmdb_id (preferencialmente) ou título.
    Retorna o índice do item encontrado ou None.
    """
    for i, fav_item in enumerate(favorites_list):
        # Prioriza tmdb_id para identificação única
        if video_data.get('tmdb_id') and fav_item.get('tmdb_id') == video_data['tmdb_id']:
            return i
        # Fallback para título, mas menos confiável para unicidade
        elif fav_item.get('title') == video_data.get('title'):
            # Para filmes, pode ser útil adicionar o ano para maior precisão:
            # and fav_item.get('year') == video_data.get('year')
            return i
    return None

def add_to_favorites(video):
    """
    Adiciona ou atualiza um vídeo/série na lista de favoritos.
    Se for uma série, mescla as informações mantendo dados específicos do usuário.
    """
    favorites = load_favorites()
    existing_index = find_item_in_favorites(favorites, video)

    notification_msg = ""

    if existing_index is not None:
        if video.get('type') == 'tvshow':
            # Preserva metadados específicos do usuário
            preserved_user_data = {
                'user_added_date': favorites[existing_index].get('user_added_date', datetime.now().isoformat()),
                'user_notes': favorites[existing_index].get('user_notes', ''),
                'user_rating': favorites[existing_index].get('user_rating') # Exemplo de dado do usuário
            }
            # Atualiza a série, mesclando os dados novos com os dados preservados do usuário
            favorites[existing_index] = {**video, **preserved_user_data}
            notification_msg = f"{video.get('title', 'Item')} atualizado na sua lista!"
        else:
            # Para filmes ou outros tipos, apenas informa que já está na lista
            show_notification("Minha Lista", f"{video.get('title', 'Item')} já está na sua lista!", xbmcgui.NOTIFICATION_INFO)
            return # Sai da função, não há necessidade de salvar

    else:
        # Adiciona data/hora quando foi adicionado aos favoritos
        video['user_added_date'] = datetime.now().isoformat()
        favorites.append(video)
        notification_msg = f"{video.get('title', 'Item')} adicionado à sua lista!"

    save_favorites(favorites)
    show_notification("Minha Lista", notification_msg)

def load_favorites():
    """Carrega a lista de favoritos com tratamento de erros."""
    if not xbmcvfs.exists(FAVORITES_FILE):
        return []

    try:
        with xbmcvfs.File(FAVORITES_FILE, 'r') as file:
            content = file.read()
            # Retorna lista vazia se o arquivo estiver vazio ou inválido
            return json.loads(content) if content.strip() else []
    except json.JSONDecodeError as e:
        show_notification('Erro', f'Erro ao decodificar favoritos (JSON inválido): {str(e)}', xbmcgui.NOTIFICATION_ERROR)
        return []
    except Exception as e:
        show_notification('Erro', f'Erro ao carregar favoritos: {str(e)}', xbmcgui.NOTIFICATION_ERROR)
        return []

def save_favorites(favorites):
    """Salva a lista de favoritos com tratamento de erros, garantindo o diretório."""
    try:
        fav_dir = os.path.dirname(FAVORITES_FILE)
        # Garante que o diretório existe (xbmcvfs.mkdirs cria recursivamente)
        if not xbmcvfs.exists(fav_dir):
            xbmcvfs.mkdirs(fav_dir)

        with xbmcvfs.File(FAVORITES_FILE, 'w') as file:
            file.write(json.dumps(favorites, indent=4)) # Usar indent para legibilidade do JSON
        return True
    except Exception as e:
        show_notification('Erro', f'Erro ao salvar favoritos: {str(e)}', xbmcgui.NOTIFICATION_ERROR)
        return False

def remove_from_favorites(video):
    """
    Remove um vídeo ou série da lista de favoritos.
    Prioriza tmdb_id para remoção precisa.
    """
    favorites = load_favorites()
    initial_len = len(favorites)
    
    updated_favorites = []
    removed = False

    for fav in favorites:
        # Tenta remover por tmdb_id se ambos tiverem
        if video.get('tmdb_id') and fav.get('tmdb_id') == video['tmdb_id']:
            removed = True
            continue # Pula este item (remove)
        # Fallback para remover por título se tmdb_id não estiver disponível ou não coincidir
        elif not video.get('tmdb_id') and fav.get('title') == video.get('title'):
            removed = True
            continue # Pula este item (remove)
        
        updated_favorites.append(fav) # Mantém este item

    if removed:
        save_favorites(updated_favorites)
        show_notification("Minha Lista", f"{video.get('title', 'Item')} removido da sua lista!")
    else:
        show_notification("Sua Lista", f"{video.get('title', 'Item')} não está na sua lista!", xbmcgui.NOTIFICATION_INFO)

def list_favorites():
    """Lista os favoritos usando apenas os dados salvos em favorites.json (sem consultar catálogo)."""
    from resources.action.video_listing import create_video_item
    favorites = load_favorites()
    
    if not favorites:
        xbmcgui.Dialog().ok('Favoritos', 'Nenhum item encontrado na lista!')
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)
        return

    xbmcplugin.setPluginCategory(HANDLE, 'Minha Lista')
    xbmcplugin.setContent(HANDLE, 'videos')  # ou 'movies', se preferir

    for video in favorites:
        # Usa apenas os dados já salvos em favorites.json
        list_item, url, is_folder = create_video_item(video)

        context_menu = [
            ('Remover da sua Lista', f'RunPlugin({get_url(action="remove_from_favorites", video=json.dumps(video))})')
        ]

        if video.get('type') == 'tvshow' and video.get('tmdb_id'):
            context_menu.append(('Atualizar Série', f'RunPlugin({get_url(action="force_update_series", video_id=str(video["tmdb_id"]))})'))

        list_item.addContextMenuItems(context_menu)
        xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=is_folder)

    xbmcplugin.endOfDirectory(HANDLE)


def find_item_in_catalog(catalog_data, tmdb_id, title):
    """
    Busca um item no catálogo principal por tmdb_id ou título.
    Assume que catalog_data é uma lista de todos os itens do catálogo.
    """
    if tmdb_id:
        for item in catalog_data:
            if item.get('tmdb_id') == tmdb_id:
                return item
    
    # Fallback para busca por título
    for item in catalog_data:
        if item.get('title') == title:
            # Considerar adicionar ano para filmes: item.get('year') == year
            return item
            
    return None

def force_update_series(video_id):
    """
    Atualiza manualmente os dados de uma série nos favoritos
    buscando informações atualizadas do catálogo principal.
    """
    if not video_id:
        show_notification("Erro", "ID da série não fornecido para atualização", xbmcgui.NOTIFICATION_ERROR)
        return

    favorites = load_favorites()
    all_catalog_items = get_all_videos() # CUIDADO: Pode ser lento

    catalog_series = find_item_in_catalog(all_catalog_items, int(video_id) if video_id.isdigit() else None, None) # Assume video_id é tmdb_id

    if not catalog_series:
        show_notification("Erro", "Série não encontrada no catálogo para atualização.", xbmcgui.NOTIFICATION_ERROR)
        return
        
    updated = False
    for i, fav in enumerate(favorites):
        if str(fav.get('tmdb_id')) == str(video_id): # Garante comparação entre strings
            # Mantém metadados específicos do usuário ao atualizar
            user_data = {
                'user_added_date': fav.get('user_added_date', datetime.now().isoformat()),
                'user_notes': fav.get('user_notes', ''),
                'user_rating': fav.get('user_rating')
            }
            
            # Combina dados atualizados do catálogo com dados do usuário
            favorites[i] = {**catalog_series, **user_data}
            updated = True
            break
            
    if updated:
        save_favorites(favorites)
        show_notification("Sucesso", f"{catalog_series.get('title', 'Série')} atualizada com sucesso!")
        xbmc.executebuiltin('Container.Refresh') # Atualiza a lista para mostrar as mudanças
    else:
        show_notification("Erro", "Série não encontrada nos favoritos para atualização.", xbmcgui.NOTIFICATION_ERROR)