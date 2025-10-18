# -*- coding: utf-8 -*-
# Em: resources/lib/tvshows.py

import os
import re
import json
import sys
import xbmcaddon
import xbmcgui
import xbmcplugin
from urllib.parse import urlencode

# Importações do seu projeto
from .db import db
from .utils import create_video_item, with_view_mode
from .navigation import _fetch_json_from_url

# Configurações e funções comuns
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]
DEFAULT_ITEMS_PER_PAGE = int(ADDON.getSetting("pages"))

ADDON_PATH = ADDON.getAddonInfo('path')
ICON_PATH = os.path.join(ADDON_PATH, 'resources', 'medias', 'icons')


def get_url(**kwargs):
    """Cria uma URL de plugin para uma ação."""
    return f"{BASE_URL}?{urlencode(kwargs)}"


# --- ✅ NOVAS FUNÇÕES AUXILIARES ---

def _prepare_details_data(item_data):
    """Prepara um dicionário com os dados do item para a URL da tela de detalhes."""
    genre_str = ', '.join(item_data.get('genres', []))  # Lista → string
    providers_list = item_data.get('providers', [])
    return {
        'tmdb_id': item_data.get('tmdb_id'),
        'imdb_id': item_data.get('imdb_id'),
        'title': item_data.get('title'),
        'clearlogo': item_data.get('clearlogo'),
        'synopsis': item_data.get('synopsis'),
        'poster': item_data.get('poster'),
        'backdrop': item_data.get('backdrop'),
        'year': item_data.get('year'),
        'rating': item_data.get('rating'),
        'certification': item_data.get('certification'),
        'trailer': item_data.get('trailer'),
        'genre': genre_str,
        'media_type': 'tvshow',
        'providers': json.dumps(providers_list)
    }


def _add_show_item_to_list(show_data):
    """Cria o ListItem para uma série e o adiciona ao diretório do Kodi."""
    li = create_video_item(show_data, 'tvshow')

    if ADDON.getSettingBool('enable_details_dialog'):
        details_data = _prepare_details_data(show_data)
        url = get_url(action='show_details', data=json.dumps(details_data, ensure_ascii=False))
        is_folder = False
    else:
        url = get_url(action='list_seasons', tvshow_tmdb_id=show_data.get('tmdb_id'))
        is_folder = True

    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)


# --- FUNÇÕES DE NAVEGAÇÃO DE SÉRIES ---

@with_view_mode('files', is_menu=True)
def show_tvshows_menu(menu_structure):
    """Cria e exibe o menu da seção 'Séries'."""
    xbmcplugin.setPluginCategory(HANDLE, 'Séries')
    xbmcplugin.setContent(HANDLE, 'files')
    for item in menu_structure:
        li = xbmcgui.ListItem(label=item['title'])
        icon = item.get('icon')
        if icon:
            li.setArt({'thumb': icon})
        url = get_url(action=item['action'])
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


def add_next_page_item(items_on_current_page, current_page, **kwargs):
    """Adiciona o item 'Próxima Página' a uma lista se houver mais itens."""
    if len(items_on_current_page) == DEFAULT_ITEMS_PER_PAGE:
        next_icon = os.path.join(ICON_PATH, 'nextpage.png')
        li_next = xbmcgui.ListItem(label="Próxima Página")
        li_next.setArt({'thumb': next_icon, 'icon': next_icon})
        li_next.setInfo('video', {'plot': f'Ir para a página {current_page + 1}'})

        next_page_args = kwargs.copy()
        next_page_args['page'] = current_page + 1
        next_page_url = get_url(**next_page_args)

        xbmcplugin.addDirectoryItem(HANDLE, next_page_url, li_next, isFolder=True)


# --- TEMPORADAS E EPISÓDIOS ---

def list_seasons(tvshow_tmdb_id):
    """Lista as temporadas de uma série."""
    show = db.get_tvshow_by_id(tvshow_tmdb_id)
    if not show:
        xbmcgui.Dialog().ok("Erro", "Série não encontrada no banco de dados.")
        return

    xbmcplugin.setPluginCategory(HANDLE, show['title'])
    xbmcplugin.setContent(HANDLE, 'seasons')

    for season_data in show.get('seasons_data', []):
        season_number = season_data.get('number', 0)
        li = create_video_item(season_data, 'season', show_data=show)
        url = get_url(action='list_episodes', tvshow_tmdb_id=tvshow_tmdb_id, season_number=season_number)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)


def list_episodes(tvshow_tmdb_id, season_number):
    """Lista os episódios de uma temporada."""
    show = db.get_tvshow_by_id(tvshow_tmdb_id)
    if not show:
        return

    target_season = next((s for s in show.get('seasons_data', []) if int(s.get('number', -99)) == season_number), None)
    if not target_season:
        return

    xbmcplugin.setPluginCategory(HANDLE, f"{show['title']} - {target_season.get('title', '')}")
    xbmcplugin.setContent(HANDLE, 'episodes')

    episodes_list = _load_episodes_list(target_season, season_number)
    if not episodes_list:
        xbmcgui.Dialog().ok("Aviso", "Nenhum episódio encontrado para esta temporada.")
        xbmcplugin.endOfDirectory(HANDLE)
        return

    for ep_data in episodes_list:
        _add_episode_directory_item(ep_data, show, tvshow_tmdb_id, season_number, episodes_list)

    xbmcplugin.endOfDirectory(HANDLE)


def _load_episodes_list(season_data, season_number):
    """Carrega a lista de episódios da temporada."""
    episodes_list = []

    if season_data.get('episodios_link'):
        episodes_data = _fetch_json_from_url(season_data['episodios_link'])
        if episodes_data and 'episodios' in episodes_data:
            for ep in episodes_data['episodios']:
                ep['season_number'] = season_number
            episodes_list = episodes_data['episodios']
    else:
        episodes_list = season_data.get('episodios', [])

    return episodes_list


def _extract_episode_number(episode_title):
    """Extrai o número do episódio do título."""
    match = re.match(r'(\d+)', episode_title)
    return int(match.group(1)) if match else 0


def _extract_correct_episode_number(ep_data, current_ep_number):
    """Extrai o número do episódio de forma mais robusta."""
    if current_ep_number > 0:
        return current_ep_number

    if ep_data.get('episode_number'):
        return int(ep_data['episode_number'])

    title = ep_data.get('title', '')
    patterns = [
        r'E(\d+)',
        r'Episódio\s+(\d+)',
        r'Episode\s+(\d+)',
        r'#(\d+)',
        r'(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return int(match.group(1))

    episodes_list = ep_data.get('_episodes_list', [])
    if episodes_list and ep_data in episodes_list:
        return episodes_list.index(ep_data) + 1

    return current_ep_number


def _add_episode_directory_item(ep_data, show_data, tvshow_tmdb_id, season_number, all_episodes=None):
    """Adiciona um item de episódio ao diretório do Kodi."""
    li = create_video_item(ep_data, 'episode', show_data=show_data)

    ep_number = _extract_episode_number(ep_data.get('title', ''))
    if ep_number == 0:
        if all_episodes:
            ep_data['_episodes_list'] = all_episodes
        ep_number = _extract_correct_episode_number(ep_data, ep_number)

    url_list = ep_data.get('url', [])
    if not url_list:
        li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle=HANDLE, url='', listitem=li, isFolder=False)
        return

    playable_url = url_list[0]
    final_url = ''

    if 'plugin.video.elementum' in playable_url or playable_url.startswith("magnet:"):
        match = re.search(r'btih:([a-fA-F0-9]{40})', playable_url, re.IGNORECASE)
        if match:
            magnet_hash = match.group(1)
            clean_magnet_uri = f"magnet:?xt=urn:btih:{magnet_hash}"
            final_url = get_url(
                action='play_elementum',
                uri=clean_magnet_uri,
                tmdb_id=tvshow_tmdb_id,
                season=season_number,
                episode=ep_number
            )
        else:
            playable_url = None

    if not final_url:
        streams_for_player = [{'url': u, 'quality': 'HD'} for u in url_list]
        streams_json = json.dumps(streams_for_player)
        final_url = get_url(
            action='play',
            streams=streams_json,
            tmdb_id=tvshow_tmdb_id,
            season=season_number,
            episode=ep_number,
            show_title=show_data.get('title', ''),
            episode_title=ep_data.get('title', ''),
            episode_plot=ep_data.get('plot', ep_data.get('synopsis', '')),
            episode_tmdb_id=ep_data.get('tmdb_id', '')
        )

    info_tag = li.getVideoInfoTag()
    info_tag.setTitle(ep_data.get('title', ''))
    info_tag.setTvShowTitle(show_data.get('title', ''))
    info_tag.setSeason(season_number)
    info_tag.setEpisode(ep_number)
    info_tag.setMediaType('episode')
    info_tag.setPlot(ep_data.get('synopsis', ''))
    runtime_seconds = int(ep_data.get('runtime', 0)) * 60
    if runtime_seconds > 0:
        info_tag.setDuration(runtime_seconds)
    info_tag.setUniqueIDs({'tmdb': str(tvshow_tmdb_id)}, 'tmdb')

    li.setProperty("IsPlayable", "true")
    li.setPath(final_url)
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=final_url, listitem=li, isFolder=False)


# --- LISTAGENS DE SÉRIES (MENUS) ---

@with_view_mode('genres', is_menu=True)
def list_tvshows_genres():
    """Cria e exibe a lista de Gêneros de Séries."""
    xbmcplugin.setPluginCategory(HANDLE, 'Gêneros de Séries')
    xbmcplugin.setContent(HANDLE, 'genres')
    genres_from_db = db.get_all_unique_tvshow_genres()
    for genre_name in genres_from_db:
        li = xbmcgui.ListItem(label=genre_name)
        url = get_url(action='list_tvshows_by_genre', genre=genre_name)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('files', is_menu=True)
def list_providers():
    xbmcplugin.setPluginCategory(HANDLE, "Provedores")
    xbmcplugin.setContent(HANDLE, 'files')
    providers = db.get_all_unique_providers()
    for provider_name in providers:
        li = xbmcgui.ListItem(label=provider_name)
        url = get_url(action='list_tvshows_by_provider', provider=provider_name)
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)


# --- LISTAGENS DE CONTEÚDO (SÉRIES) ---

@with_view_mode('tvshows')
def list_tvshows_by_genre(genre, page=1):
    xbmcplugin.setPluginCategory(HANDLE, genre)
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_tvshows_by_genre(genre, page, DEFAULT_ITEMS_PER_PAGE)
    for show in shows:
        _add_show_item_to_list(show)
    add_next_page_item(shows, page, action='list_tvshows_by_genre', genre=genre)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_provider(provider, page=1):
    xbmcplugin.setPluginCategory(HANDLE, provider)
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_tvshows_by_provider(provider, page, DEFAULT_ITEMS_PER_PAGE)
    for show in shows:
        _add_show_item_to_list(show)
    add_next_page_item(shows, page, action='list_tvshows_by_provider', provider=provider)
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_tvshows_by_popularity(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Mais Populares")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_tvshows_by_popularity(page, DEFAULT_ITEMS_PER_PAGE)
    for show in shows:
        _add_show_item_to_list(show)
    add_next_page_item(shows, page, action='list_tvshows_by_popularity')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_animes(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Animes")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_tvshows_by_genre('anime', page, DEFAULT_ITEMS_PER_PAGE)
    for show in shows:
        _add_show_item_to_list(show)
    add_next_page_item(shows, page, action='list_animes')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_kids_tvshows(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Infantil")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_kids_tvshows(page, DEFAULT_ITEMS_PER_PAGE)
    for show in shows:
        _add_show_item_to_list(show)
    add_next_page_item(shows, page, action='list_kids_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)


@with_view_mode('tvshows')
def list_recently_added_tvshows(page=1):
    xbmcplugin.setPluginCategory(HANDLE, "Adicionados Recentemente")
    xbmcplugin.setContent(HANDLE, 'tvshows')
    shows = db.get_recently_added_tvshows(page, DEFAULT_ITEMS_PER_PAGE)
    for show in shows:
        _add_show_item_to_list(show)
    add_next_page_item(shows, page, action='list_recently_added_tvshows')
    xbmcplugin.endOfDirectory(HANDLE)
