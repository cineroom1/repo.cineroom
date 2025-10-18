import xbmcgui
import xbmc
import json
import urllib.parse
from xbmcaddon import Addon
import xbmcvfs

from resources.lib.favorites import add_item_to_favorites, remove_item_from_favorites
from resources.lib.db import db
from resources.lib import navigation

# Caminho do Addon
ADDON = Addon('plugin.video.cineroom.lite')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))


class CineroomDetailsWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.item_data = {}

    def is_item_in_favorites(self, tmdb_id, media_type):
        if not tmdb_id or not media_type:
            return False
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM favorites WHERE tmdb_id=? AND media_type=?",
            (tmdb_id, media_type)
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def onInit(self):
        data_json = self.getProperty('DATA_JSON')
        if not data_json:
            self.close()
            return

        self.item_data = json.loads(data_json)

        # --- Define propriedades gerais ---
        self.setProperty('title', self.item_data.get('title', ''))
        self.setProperty('clearlogo', self.item_data.get('clearlogo', ''))
        self.setProperty('plot', self.item_data.get('synopsis', 'Sem sinopse disponível.'))
        self.setProperty('poster', self.item_data.get('poster', ''))
        self.setProperty('backdrop', self.item_data.get('backdrop', ''))
        self.setProperty('year', str(self.item_data.get('year', 'N/A')))
        
        media_type = self.item_data.get('media_type', 'movie')

        # --- Controle de botões conforme o tipo ---
        if media_type == 'tvshow':
            self.getControl(303).setVisible(True)
            self.getControl(301).setVisible(False)
            self.getControl(302).setVisible(False)
            self.setFocusId(303)
        else:
            self.getControl(301).setVisible(True)
            self.getControl(302).setVisible(True)
            self.getControl(303).setVisible(False)
            self.setFocusId(301)

        # --- Duração ---
        runtime = self.item_data.get('runtime', 0)
        self.setProperty('duration', f"{runtime} min" if runtime else '')

        # --- Gêneros ---
        for i in range(1, 5):
            self.setProperty(f"Genre.{i}.Label", "")
        genre_string = self.item_data.get('genre', '')
        if genre_string:
            genres = [g.strip() for g in genre_string.split(',') if g.strip()]
            for i, genre in enumerate(genres[:4]):
                self.setProperty(f"Genre.{i+1}.Label", genre)
        
        # --- AJUSTE: Lógica dos Provedores (Streamings) ---
        providers_group = self.getControl(6000)
        if media_type == 'tvshow':
            providers_data = self.item_data.get('providers')
            providers_list = []

            # Lógica robusta para tratar string JSON ou lista
            if isinstance(providers_data, str) and providers_data.startswith('['):
                try: providers_list = json.loads(providers_data) 
                except: pass
            elif isinstance(providers_data, list):
                providers_list = providers_data
            
            if providers_list:
                providers_group.setVisible(True)
                for i in range(1, 5): self.setProperty(f"Provider.{i}.Label", "") # Limpa
                
                for i, provider_name in enumerate(providers_list[:4]):
                    self.setProperty(f"Provider.{i+1}.Label", provider_name)
            else:
                providers_group.setVisible(False)
        else:
            providers_group.setVisible(False)

        # --- Label do botão de favoritos ---
        tmdb_id = self.item_data.get("tmdb_id")
        if self.is_item_in_favorites(tmdb_id, media_type):
            self.setProperty("FavoriteLabel", "Remover da Lista")
        else:
            self.setProperty("FavoriteLabel", "Adicionar à Lista")

    def onClick(self, controlID):
        tmdb_id = self.item_data.get("tmdb_id")
        media_type = self.item_data.get("media_type")

        if controlID == 999:
            self.close()

        elif controlID == 301:  # Assistir
            self.close()
            navigation.find_and_play_sources(item_data=self.item_data, autoplay=True)

        elif controlID == 302:  # Selecionar Fonte
            self.close()
            navigation.find_and_play_sources(item_data=self.item_data, autoplay=False)

        elif controlID == 303:  # Temporadas
            self.close()
            plugin_url = f"plugin://plugin.video.cineroom.lite?action=list_seasons&tvshow_tmdb_id={tmdb_id}"
            xbmc.executebuiltin(f"Container.Update({plugin_url})")

        elif controlID == 304:  # Minha Lista
            if self.is_item_in_favorites(tmdb_id, media_type):
                remove_item_from_favorites(tmdb_id, media_type)
                xbmcgui.Dialog().notification("Minha Lista", "Removido da sua lista.", xbmcgui.NOTIFICATION_INFO)
                self.setProperty("FavoriteLabel", "Adicionar à Lista")
            else:
                add_item_to_favorites(tmdb_id, media_type)
                xbmcgui.Dialog().notification("Minha Lista", "Adicionado à sua lista!", xbmcgui.NOTIFICATION_INFO)
                self.setProperty("FavoriteLabel", "Remover da Lista")

        elif 400 < controlID < 410:  # Gêneros
            genre_prop = f"Genre.{controlID - 400}.Label"
            genre_clicked = self.getProperty(genre_prop)
            if genre_clicked:
                self.close()
                encoded_genre = urllib.parse.quote_plus(genre_clicked)
                action = 'list_tvshows_by_genre' if media_type == 'tvshow' else 'list_movies_by_genre'
                plugin_url = f"plugin://plugin.video.cineroom.lite?action={action}&genre={encoded_genre}"
                xbmc.executebuiltin(f"Container.Update({plugin_url})")
        
        elif 500 < controlID < 510: # Provedores
            provider_prop = f"Provider.{controlID - 500}.Label"
            provider_clicked = self.getProperty(provider_prop)
            if provider_clicked:
                self.close()
                encoded_provider = urllib.parse.quote_plus(provider_clicked)
                plugin_url = f"plugin://plugin.video.cineroom.lite?action=list_tvshows_by_provider&provider={encoded_provider}"
                xbmc.executebuiltin(f"Container.Update({plugin_url})")

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PARENT_DIR):
            self.close()


def show_details(item_data):
    
    runtime_value = item_data.get('runtime')
    safe_runtime = int(runtime_value) if runtime_value else 0
    
    providers = item_data.get('providers', [])
    if isinstance(providers, list):
        providers = json.dumps(providers)

    full_data = {
        'title': item_data.get('title', 'Título Desconhecido'),
        'clearlogo': item_data.get('clearlogo', ''),
        'synopsis': item_data.get('synopsis', ''),
        'poster': item_data.get('poster', ''),
        'backdrop': item_data.get('backdrop', ''),
        'year': item_data.get('year', ''),
        'runtime': safe_runtime,
        'rating': float(item_data.get('rating', 0)),
        'genre': item_data.get('genre', ''),
        'tmdb_id': item_data.get('tmdb_id'),
        'media_type': item_data.get('media_type'),
        'imdb_id': item_data.get('imdb_id'),
        'streams': item_data.get('streams', []),
        'providers': item_data.get('providers', '[]'),
    }

    window = CineroomDetailsWindow('CineroomDetails.xml', ADDON_PATH, 'Default', '1080i')
    window.setProperty('DATA_JSON', json.dumps(full_data))
    window.doModal()
    del window