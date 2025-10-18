# -*- coding: utf-8 -*-
# Em: addon.py

import sys
import json
import urllib.parse
from urllib.parse import urlencode, quote_plus, parse_qsl, unquote_plus
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()

# --- Importações dos Módulos ---
# ✅ Importações limpas, apenas o que é necessário.
from resources.lib import favorites
from resources.lib.donation_window import DonationDialog
from resources.lib.constants import MAIN_MENU, MOVIES_MENU, TVSHOWS_MENU
from resources.lib.indexer import run_indexer
from resources.lib.navigation import show_main_menu, play_movie, search, show_my_list, find_and_play_sources
from resources.lib.movies import (
    show_movies_menu, list_genres, list_movies_by_genre,
    list_years, list_movies_by_year, list_movies_by_rating,
    list_4k_movies, list_collections, list_movies_by_collection,
    list_movies_by_popularity, list_recently_added_movies, list_movies_by_revenue
)
from resources.lib.tvshows import (
    show_tvshows_menu, list_tvshows_genres, list_tvshows_by_genre,
    list_seasons, list_episodes, list_providers, list_tvshows_by_provider,
    list_animes, list_kids_tvshows, list_recently_added_tvshows, list_tvshows_by_popularity
)

from resources.lib.extras_dialog import show_details
from resources.lib import navigation
from resources.lib import extras_dialog


import xbmcgui
import os

def show_donation():
    dialog = DonationDialog("DonationDialog.xml", ADDON.getAddonInfo("path"), "Default", "1080i")
    dialog.doModal()
    del dialog


def router():
    """
    Função principal que atua como um "controlador de tráfego",
    lendo a ação da URL e chamando a função correspondente.
    """
    # ✅ Lógica de parse fica DENTRO da função principal.
    params = dict(parse_qsl(sys.argv[2][1:]))
    action = params.get('action')

    if action is None:
        # Mantemos o log aqui para ter certeza de que está funcionando
        xbmc.log(f"[DEBUG] Ação é None, chamando show_main_menu...", xbmc.LOGINFO)
        xbmc.log(f"[DEBUG] Conteúdo do MAIN_MENU: {MAIN_MENU}", xbmc.LOGINFO)
        show_main_menu(MAIN_MENU)

    elif action == 'run_indexer':
        run_indexer()
        
    elif action == 'search':
        search(query=params.get('query'))  

    # -- Filmes --
    elif action == 'movies_menu':
        show_movies_menu(MOVIES_MENU) # ✅ Passando o argumento necessário
    elif action == 'list_genres':
        list_genres()
    elif action == 'list_movies_by_genre':
        list_movies_by_genre(genre=params.get('genre'), page=int(params.get('page', '1')))
    elif action == 'list_years':
        list_years()
    elif action == 'list_movies_by_year':
        list_movies_by_year(year=int(params.get('year')), page=int(params.get('page', '1')))
    elif action == 'list_movies_by_rating':
        page = int(params.get('page', '1'))
        list_movies_by_rating(page) # ✅ Passando a página para a função
    
    elif action == 'list_movies_by_popularity':
        list_movies_by_popularity(page=int(params.get('page', '1')))
    elif action == 'list_4k_movies':
        list_4k_movies(page=int(params.get('page', '1')))
    elif action == 'list_collections':
        list_collections()
    elif action == 'list_movies_by_collection':
        list_movies_by_collection(collection_name=params.get('collection')) 
    elif action == 'list_recently_added_movies':
        list_recently_added_movies(page=int(params.get('page', '1'))) 
    elif action == 'list_movies_by_revenue':
        list_movies_by_revenue(page=int(params.get('page', '1')))  
        

    # -- Séries --
    elif action == 'tvshows_menu':
        show_tvshows_menu(TVSHOWS_MENU) # ✅ Passando o argumento necessário
    elif action == 'list_tvshows_genres':
        list_tvshows_genres()
    elif action == 'list_tvshows_by_genre':
        list_tvshows_by_genre(genre=params.get('genre'), page=int(params.get('page', '1')))
    elif action == 'list_seasons':
        list_seasons(tvshow_tmdb_id=params.get('tvshow_tmdb_id'))
    elif action == 'list_episodes':
        list_episodes(tvshow_tmdb_id=params.get('tvshow_tmdb_id'), season_number=int(params.get('season_number')))
    elif action == 'list_providers':
        list_providers()    
    elif action == 'list_tvshows_by_provider':
        list_tvshows_by_provider(provider=params.get('provider'), page=int(params.get('page', '1')))
    elif action == 'list_animes':
        list_animes(page=int(params.get('page', '1')))    
    elif action == 'list_kids_tvshows':
        list_kids_tvshows(page=int(params.get('page', '1'))) 
    elif action == 'list_recently_added_tvshows':
        list_recently_added_tvshows(page=int(params.get('page', '1'))) 
    elif action =='list_tvshows_by_popularity':
        list_tvshows_by_popularity(page=int(params.get('page', '1')))         
        

    # --- ROTAS DA MINHA LISTA ---
    elif action == 'show_my_list':
        show_my_list()
    elif action == 'add_to_favorites':
        favorites.add_item_to_favorites(params.get('tmdb_id'), params.get('media_type'))
    elif action == 'remove_from_favorites':
        favorites.remove_item_from_favorites(params.get('tmdb_id'), params.get('media_type'))        
                 

    # -- Player --
    elif action == 'find_sources':
       # 1. Crie o dicionário 'item_data' com as informações da URL
        item_data_for_sources = {
            'tmdb_id': params.get('tmdb_id'),
            'imdb_id': params.get("imdb_id") or '', # Proteção contra valores nulos
            'media_type': params.get('media_type'),
            # Você pode adicionar outros dados aqui se precisar, como 'title'
    }
    
        # 2. Chame a função passando o dicionário para o argumento 'item_data'
        find_and_play_sources(
            item_data=item_data_for_sources,
            season=params.get('season'),
            episode=params.get('episode')
    )

    elif action == 'play':
        play_movie(
            streams=params.get('streams'),
            tmdb_id=params.get('tmdb_id'),
            season=params.get('season'),
            episode=params.get('episode'),
            show_title=params.get('show_title'),
            episode_title=params.get('episode_title'),
            episode_plot=params.get('episode_plot'),
            episode_duration=params.get('episode_duration', 0),
            episode_tmdb_id=params.get('episode_tmdb_id')
        )
        
    elif action == 'play_elementum':
        uri = params.get('uri')
        tmdb_id = params.get('tmdb_id')
        season = params.get('season')
        episode = params.get('episode')

        final_elementum_url = (f"plugin://plugin.video.elementum/play?"
                               f"uri={quote_plus(uri)}"
                               f"&tmdb={tmdb_id}"
                               f"&season={season}"
                               f"&episode={episode}")
                               
        list_item = xbmcgui.ListItem(path=final_elementum_url)
        xbmcplugin.setResolvedUrl(handle=HANDLE, succeeded=True, listitem=list_item)  

    if action == 'show_details':
        # ✅ 1. Pega o parâmetro 'data' da URL.
        encoded_data = params.get('data')
        
        if encoded_data:
            # ✅ 2. Decodifica a string da URL para obter o JSON original.
            item_data_json = urllib.parse.unquote_plus(encoded_data)
            
            # ✅ 3. Converte a string JSON de volta para um dicionário Python.
            full_item_data = json.loads(item_data_json)
            
            # ✅ 4. Chama a função show_details, passando o dicionário completo.
            extras_dialog.show_details(full_item_data) 

    elif action == 'play_item_direct':
        encoded_data = params.get('data')
        if encoded_data:
            item_data_json = urllib.parse.unquote_plus(encoded_data)
            full_item_data = json.loads(item_data_json)

            # Chama a busca de fontes diretamente com autoplay
            navigation.find_and_play_sources(
                item_data=full_item_data, 
                autoplay=False
            )            
        
    if action == 'show_donation':
        show_donation()
   

if __name__ == '__main__':
    router()