# -*- coding: utf-8 -*-
import xbmc
import xbmcgui

from ..context import get_module

def handle_library(action, params):
    # Menu não precisa de import pesado
    if action == 'library_menu':
        win = xbmcgui.Window(10000)
        warned = win.getProperty("cineroom.library.warning")

        if not warned:
            ok = xbmcgui.Dialog().yesno(
                "Biblioteca",
                "Recomendado apenas para usuários avançados!\n\nDeseja continuar?"
            )
            if not ok:
                return False
            win.setProperty("cineroom.library.warning", "true")

        lib = get_module('library')
        if lib and hasattr(lib, 'show_library_menu'):
            lib.show_library_menu()
            return True
        return False

    lib = get_module('library')
    if not lib:
        return False

    db = get_module('db')

    if action == 'library_add':
        tmdb_id = params.get('tmdb_id')
        media_type = params.get('media_type')

        if tmdb_id and media_type and db:
            if media_type == 'movie':
                item_data = db.get_movie_by_id(tmdb_id)
                if item_data and hasattr(lib, 'add_movie_to_library'):
                    lib.add_movie_to_library(item_data)

            elif media_type == 'tvshow':
                item_data = db.get_tvshow_by_id(tmdb_id)
                if item_data and xbmcgui.Dialog().yesno("Adicionar", f"Adicionar {item_data.get('title')}?"):
                    if hasattr(lib, 'add_tvshow_to_library'):
                        lib.add_tvshow_to_library(item_data)
                    if xbmcgui.Dialog().yesno("Kodi", "Atualizar biblioteca agora?"):
                        if hasattr(lib, 'update_kodi_library'):
                            lib.update_kodi_library(media_type)
        return True

    if action == 'library_remove':
        tmdb_id = params.get('tmdb_id')
        media_type = params.get('media_type')
        if tmdb_id and media_type and xbmcgui.Dialog().yesno("Remover", "Deseja remover da biblioteca?"):
            if hasattr(lib, 'remove_from_library'):
                lib.remove_from_library(tmdb_id, media_type)
        return True

    if action == 'library_update':
        if hasattr(lib, 'update_kodi_library'):
            lib.update_kodi_library(params.get('media_type', 'video'))
        return True

    if action == 'library_add_all_movies':
        if hasattr(lib, 'add_all_movies_to_library'):
            lib.add_all_movies_to_library()
        return True

    if action == 'library_add_all_tvshows':
        if hasattr(lib, 'add_all_tvshows_to_library'):
            lib.add_all_tvshows_to_library()
        return True

    if action == 'library_stats':
        if hasattr(lib, 'get_library_stats'):
            stats = lib.get_library_stats()
            xbmcgui.Dialog().ok("Estatísticas", f"Filmes: {stats['movies']}\nSéries: {stats['tvshows']}\nEpisódios: {stats['episodes']}")
        return True

    return False
