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
from resources.lib.utils import get_all_videos


# As variáveis globais URL e HANDLE foram removidas daqui para evitar o erro.
# Elas serão definidas apenas no momento da execução do plugin.

ADDON_ID = xbmcaddon.Addon().getAddonInfo('id')
FAVORITES_FILE = xbmcvfs.translatePath(f"special://userdata/addon_data/{ADDON_ID}/favorites.json")


def show_notification(heading, message, icon=xbmcgui.NOTIFICATION_INFO, time=3000):
    """Exibe uma notificação no Kodi."""
    xbmcgui.Dialog().notification(heading, message, icon, time)

def get_url(**kwargs):
    """
    Cria uma URL para chamar o plugin recursivamente a partir dos argumentos fornecidos.
    Usa sys.argv[0] para a URL base.
    """
    return '{}?{}'.format(sys.argv[0], urlencode(kwargs))

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
                'user_rating': favorites[existing_index].get('user_rating')
            }
            # Atualiza a série, mesclando os dados novos com os dados preservados do usuário
            favorites[existing_index] = {**video, **preserved_user_data}
            notification_msg = f"{video.get('title', 'Item')} atualizado na sua lista!"
        else:
            # Para filmes ou outros tipos, apenas informa que já está na lista
            show_notification("Minha Lista", f"{video.get('title', 'Item')} já está na sua lista!", xbmcgui.NOTIFICATION_INFO)
            return

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
            file.write(json.dumps(favorites, indent=4))
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
        if video.get('tmdb_id') and fav.get('tmdb_id') == video['tmdb_id']:
            removed = True
            continue
        elif not video.get('tmdb_id') and fav.get('title') == video.get('title'):
            removed = True
            continue

        updated_favorites.append(fav)

    if removed:
        save_favorites(updated_favorites)
        show_notification("Minha Lista", f"{video.get('title', 'Item')} removido da sua lista!")
    else:
        show_notification("Sua Lista", f"{video.get('title', 'Item')} não está na sua lista!", xbmcgui.NOTIFICATION_INFO)

def list_favorites(handle):
    from resources.action.video_listing import create_video_item
    from resources.action.movies import fetch_collection_art
    favorites = load_favorites()

    if not favorites:
        xbmcgui.Dialog().ok('Favoritos', 'Nenhum item encontrado na lista!')
        xbmcplugin.endOfDirectory(handle, succeeded=True)
        return

    xbmcplugin.setPluginCategory(handle, 'Minha Lista')
    xbmcplugin.setContent(handle, 'movies')

    def get_collection_art_by_name(collection_name):
        all_videos = get_all_videos()
        movies = [m for m in all_videos if m.get('collection') == collection_name]
        tmdb_id = None
        for m in movies:
            if m.get('tmdb_id'):
                tmdb_id = m['tmdb_id']
                break
        if tmdb_id:
            return fetch_collection_art(tmdb_id)
        return None

    for video in favorites:
        if video.get('type') == 'set':
            collection_name = video.get('title')
            art = get_collection_art_by_name(collection_name)
            item = xbmcgui.ListItem(label=collection_name)
            item.setInfo('video', {
                'title': collection_name,
                'plot': 'Coleção de filmes',
                'mediatype': 'set'
            })
            if art:
                item.setArt({
                    'poster': art.get('poster', 'DefaultSet.png'),
                    'thumb': art.get('poster', 'DefaultSet.png'),
                    'fanart': art.get('backdrop', 'DefaultVideo.png'),
                })
            else:
                item.setArt({
                    'icon': 'DefaultSet.png',
                    'thumb': 'DefaultSet.png',
                    'poster': 'DefaultSet.png',
                    'fanart': 'DefaultVideo.png'
                })
            item.addContextMenuItems([
                ('Remover da sua Lista',
                 f'RunPlugin({get_url(action="remove_from_favorites", video=json.dumps(video))})')
            ])
            url = get_url(action='list_movies_by_collection', collection=collection_name)
            xbmcplugin.addDirectoryItem(handle, url, item, True)
        else:
            list_item, url, is_folder = create_video_item(handle, video)

            context_menu = [
                ('Remover da sua Lista', f'RunPlugin({get_url(action="remove_from_favorites", video=json.dumps(video))})')
            ]
            if video.get('type') == 'tvshow' and video.get('tmdb_id'):
                context_menu.append((
                    'Atualizar Série',
                    f'RunPlugin({get_url(action="force_update_series", video_id=str(video["tmdb_id"]))})'
                ))

            list_item.addContextMenuItems(context_menu)
            xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=is_folder)

    xbmcplugin.endOfDirectory(handle)

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
    all_catalog_items = get_all_videos()

    catalog_series = find_item_in_catalog(all_catalog_items, int(video_id) if video_id.isdigit() else None, None)

    if not catalog_series:
        show_notification("Erro", "Série não encontrada no catálogo para atualização.", xbmcgui.NOTIFICATION_ERROR)
        return

    updated = False
    for i, fav in enumerate(favorites):
        if str(fav.get('tmdb_id')) == str(video_id):
            user_data = {
                'user_added_date': fav.get('user_added_date', datetime.now().isoformat()),
                'user_notes': fav.get('user_notes', ''),
                'user_rating': fav.get('user_rating')
            }

            favorites[i] = {**catalog_series, **user_data}
            updated = True
            break

    if updated:
        save_favorites(favorites)
        show_notification("Sucesso", f"{catalog_series.get('title', 'Série')} atualizada com sucesso!")
        xbmc.executebuiltin('Container.Refresh')
    else:
        show_notification("Erro", "Série não encontrada nos favoritos para atualização.", xbmcgui.NOTIFICATION_ERROR)


def handle_plugin_call():
    """
    Processa os argumentos de linha de comando para determinar
    qual ação deve ser executada quando o plugin é chamado.
    """
    try:
        # Define URL e HANDLE dentro do escopo da execução do plugin
        URL = sys.argv[0]
        HANDLE = int(sys.argv[1])
        
        params = dict(parse_qsl(sys.argv[2][1:]))
        action = params.get('action')

        if action == 'add_to_favorites':
            video_data_str = params.get('video')
            if video_data_str:
                video_data = json.loads(video_data_str)
                add_to_favorites(video_data)
        elif action == 'remove_from_favorites':
            video_data_str = params.get('video')
            if video_data_str:
                video_data = json.loads(video_data_str)
                remove_from_favorites(video_data)
        elif action == 'list_favorites':
            list_favorites(HANDLE)
        elif action == 'force_update_series':
            video_id = params.get('video_id')
            force_update_series(video_id)
        else:
            list_favorites(HANDLE)
            
    except IndexError:
        # Este bloco é executado quando o script é importado
        # por outro módulo. Nenhuma ação é necessária.
        pass


# Este bloco só é executado quando o script favorites.py é o
# programa principal (ex: o usuário clica no plugin).
if __name__ == '__main__':
    handle_plugin_call()