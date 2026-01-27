# -*- coding: utf-8 -*-
import xbmcgui
import xbmc
import json
import urllib.parse
from xbmcaddon import Addon
import xbmcvfs
from collections import OrderedDict

ADDON = Addon('plugin.video.cineroom.lite')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))

MOVIE_DETAILS_ENABLED = ADDON.getSettingBool("movie.enable_details")
TVSHOW_DETAILS_ENABLED = ADDON.getSettingBool("tvshow.enable_details")
AUTOPLAY = ADDON.getSettingBool("playback.autoplay")

# === CACHE DE LOGOS (OTIMIZADO) ===
_PROVIDER_LOGOS = {
    "hulu": "hulu.png",
    "netflix": "netflix.png",
    "amazon video": "prime_video.png",
    "amazon prime": "prime_video.png",
    "amazon prime video": "prime_video.png",
    "prime video": "prime_video.png",
    "primevideo": "prime_video.png",
    "disney plus": "disney_plus.png",
    "hbo max": "hbo_max.png",
    "max": "hbo_max.png",
    "apple tv+": "apple_tv.png",
    "apple tv plus": "apple_tv.png",
    "paramount plus": "paramount_plus.png",
    "paramount plus amazon channel": "paramount_plus.png",
    "crunchyroll": "crunchyroll.png",
    "movistar plus": "movistar_plus.png",
    "globoplay": "globoplay.png",
    "claro tv+": "claro_tv.png",
    "claro tv": "claro_tv.png",
    "claro tv plus": "claro_tv.png",
    "claro video": "claro_tv.png",
    "telecine": "telecine.png",
    "looke": "looke.png",
    "google play movies": "google_play.png",
    "adult swim": "adult_swim.png",
}

_LOGO_PATHS = {}

def _init_logo_cache():
    """Inicializa cache de logos (roda 1x no import)"""
    for k, logo in _PROVIDER_LOGOS.items():
        path = xbmcvfs.translatePath(f"{ADDON_PATH}/resources/logos/{logo}")
        if xbmcvfs.exists(path):
            _LOGO_PATHS[k] = path

_init_logo_cache()

def get_logo_path(provider):
    """Retorna caminho do logo (com cache)"""
    if not provider:
        return ""
    return _LOGO_PATHS.get(provider.lower(), "")

# === DIALOG DE DETALHES ESTILO NETFLIX ===
class CineroomDetailsWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meta = kwargs.get('meta', {})
        self.is_tvshow = self.meta.get('media_type') == 'tvshow'
        self.has_collection = bool(self.meta.get('collection'))
        self._is_favorite = None
        
        # Setup inicial
        self._setup_properties()
    
    def _check_favorite_status(self):
        """Verifica status de favorito (com cache)"""
        if self._is_favorite is None:
            from resources.lib.db import db
            tmdb_id = self.meta.get("tmdb_id")
            media_type = "tvshow" if self.is_tvshow else "movie"
            
            try:
                self._is_favorite = db.is_favorite(tmdb_id, media_type)
            except AttributeError:
                conn = db._get_conn()
                cur = conn.cursor()
                cur.execute(
                    "SELECT 1 FROM favorites WHERE tmdb_id=? AND media_type=? LIMIT 1",
                    (tmdb_id, media_type)
                )
                self._is_favorite = cur.fetchone() is not None
                db._release_conn(conn)
        
        return self._is_favorite
    
    def _setup_properties(self):
        """Define propriedades do dialog"""
        m = self.meta
        
        # Propriedades básicas
        self.setProperty("media_type", "tvshow" if self.is_tvshow else "movie")
        self.setProperty("title", m.get("title", ""))
        self.setProperty("poster", m.get("poster", ""))
        self.setProperty("backdrop", m.get("backdrop", ""))
        self.setProperty("year", m.get("year_str", ""))
        self.setProperty("duration", m.get("duration_str", ""))
        self.setProperty("plot", m.get("synopsis", ""))
        self.setProperty("clearlogo", m.get("clearlogo", ""))
        self.setProperty("HasCollection", "true" if self.has_collection else "false")
        self.setProperty("Collection.Label", str(m.get("collection", "")))
        self.setProperty("tmdb_id", str(m.get("tmdb_id", "")))
        
        # Label de favorito
        is_favorite = self._check_favorite_status()
        label = "Minha Lista" if not is_favorite else "Remover"
        self.setProperty("FavoriteLabel", label)
        
        # Gêneros (max 3)
        for i, g in enumerate(m.get('genre_list', []), 1):
            self.setProperty(f"Genre.{i}.Label", g)
        
        # Provedores (max 4)
        provider_data = m.get('provider_data', [])
        xbmc.log(f"[CINEROOM] Provider data: {provider_data}", xbmc.LOGINFO)
        
        for i, prov in enumerate(provider_data, 1):
            label = prov.get('name', '')
            icon = prov.get('icon', '')
            xbmc.log(f"[CINEROOM] Setting Provider.{i}: label={label}, icon={icon}", xbmc.LOGINFO)
            self.setProperty(f"Provider.{i}.Label", label)
            self.setProperty(f"Provider.{i}.Icon", icon)
        
        # Limpa provedores não utilizados
        for i in range(len(provider_data) + 1, 5):
            self.setProperty(f"Provider.{i}.Label", "")
            self.setProperty(f"Provider.{i}.Icon", "")
    
    def onInit(self):
        """Inicialização - define foco"""
        self.set_focus_immediate()
    
    def set_focus_immediate(self):
        """Define foco no botão principal"""
        # Prioriza botão de play/temporadas
        if self.is_tvshow:
            focus_ids = [321, 322, 10]
        elif self.has_collection:
            focus_ids = [301, 302, 304, 305, 10]
        else:
            focus_ids = [301, 302, 305, 10]
        
        for control_id in focus_ids:
            try:
                self.setFocusId(control_id)
                break
            except:
                continue
    
    def onClick(self, controlID):
        """Handler de cliques"""
        try:
            tmdb_id = self.meta.get("tmdb_id")
            media_type = "tvshow" if self.is_tvshow else "movie"
            
            # === REPRODUZIR (FILMES) ===
            if controlID == 301:
                self.close()
                self._play(True)
            
            # === ESCOLHER FONTE (FILMES) ===
            elif controlID == 302:
                self.close()
                self._play(False)
            
            # === VER TEMPORADAS (SÉRIES) ===
            elif controlID == 321:
                self.close()
                self._open_container(
                    f"plugin://plugin.video.cineroom.lite?"
                    f"action=list_seasons&tvshow_tmdb_id={tmdb_id}"
                )
            
            # === VER COLEÇÃO ===
            elif controlID == 304:
                self.close()
                collection = urllib.parse.quote_plus(str(self.meta.get("collection", "")))
                self._open_container(
                    f"plugin://plugin.video.cineroom.lite?"
                    f"action=list_movies_by_collection&collection={collection}"
                )
            
            # === TOGGLE FAVORITO ===
            elif controlID in (305, 322):
                self._toggle_favorite(tmdb_id, media_type)
            
            # === CLIQUE EM GÊNERO (401-403) ===
            elif 400 < controlID < 404:
                idx = controlID - 401
                genres = self.meta.get('genre_list', [])
                if idx < len(genres):
                    self.close()
                    genre = urllib.parse.quote_plus(genres[idx])
                    action = "list_tvshows_by_genre" if self.is_tvshow else "list_movies_by_genre"
                    self._open_container(
                        f"plugin://plugin.video.cineroom.lite?"
                        f"action={action}&genre={genre}"
                    )
            
            # === CLIQUE EM PROVEDOR (501-504) ===
            elif 500 < controlID < 505:
                idx = controlID - 501
                providers = self.meta.get('provider_data', [])
                if idx < len(providers):
                    self.close()
                    provider = urllib.parse.quote_plus(providers[idx]['name'])
                    action = "list_tvshows_by_provider" if self.is_tvshow else "list_movies_by_provider"
                    self._open_container(
                        f"plugin://plugin.video.cineroom.lite?"
                        f"action={action}&provider={provider}"
                    )
            
            # === FECHAR ===
            elif controlID == 999:
                self.close()
        
        except Exception as e:
            xbmc.log(f"[CINEROOM] onClick error: {e}", xbmc.LOGERROR)
            self._show_error("Operação falhou. Tente novamente.")
    
    def _open_container(self, url):
        """Abre container"""
        xbmc.executebuiltin(f"Container.Update({url})")
    
    def _play(self, autoplay):
        """Inicia reprodução"""
        from resources.lib import navigation
        navigation.find_and_play_sources(self.meta, autoplay=autoplay)
    
    def _toggle_favorite(self, tmdb_id, media_type):
        """Adiciona/remove favorito"""
        from resources.lib.favorites import add_item_to_favorites, remove_item_from_favorites
        
        was_favorite = self._check_favorite_status()
        
        try:
            if was_favorite:
                remove_item_from_favorites(tmdb_id, media_type)
                new_label = "Minha Lista"
                self._is_favorite = False
            else:
                add_item_to_favorites(tmdb_id, media_type)
                new_label = "Remover"
                self._is_favorite = True
            
            # Atualiza UI
            self.setProperty("FavoriteLabel", new_label)
            
        except Exception as e:
            xbmc.log(f"[CINEROOM] Erro ao alternar favorito: {e}", xbmc.LOGERROR)
            self._show_error("Erro ao atualizar lista")
    
    def _show_error(self, message):
        """Mostra notificação de erro"""
        xbmcgui.Dialog().notification(
            "Cineroom",
            message,
            xbmcgui.NOTIFICATION_ERROR,
            2000
        )
    
    def onAction(self, action):
        """Handler de ações (back, esc)"""
        if action.getId() in (10, 92, xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.close()
    
    def __del__(self):
        """Cleanup"""
        self.meta = None
        self._is_favorite = None

# === PREPARAÇÃO DE METADADOS ===
def _prepare_common_meta(item_data):
    """Prepara metadados comuns"""
    meta = item_data.copy()
    
    # Gêneros (limite 3)
    raw_genres = meta.get("genre", "")
    meta['genre_list'] = (
        [g.strip() for g in raw_genres.split(",") if g.strip()][:3]
        if isinstance(raw_genres, str) else []
    )
    
    # Poster em alta resolução
    poster = meta.get("poster", "")
    if poster and 'image.tmdb.org' in poster:
        from resources.lib.utils import scale_tmdb
        meta["poster"] = scale_tmdb(poster, "original")
    
    # Ano
    meta["year_str"] = str(meta.get("year", ""))
    
    # Provedores (max 4, sem duplicatas)
    providers = meta.get("providers", [])
    xbmc.log(f"[CINEROOM] Raw providers: {providers}", xbmc.LOGINFO)
    
    if isinstance(providers, str):
        try:
            providers = json.loads(providers)
            xbmc.log(f"[CINEROOM] Providers after JSON parse: {providers}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[CINEROOM] Failed to parse providers JSON: {e}", xbmc.LOGERROR)
            providers = []
    
    unique_providers = OrderedDict()
    
    for p in providers:
        logo = get_logo_path(p)
        xbmc.log(f"[CINEROOM] Provider '{p}' -> logo: {logo}", xbmc.LOGINFO)
        if logo and logo not in unique_providers:
            unique_providers[logo] = {'name': p, 'icon': logo}
            if len(unique_providers) >= 4:
                break
    
    meta['provider_data'] = list(unique_providers.values())
    xbmc.log(f"[CINEROOM] Final provider_data: {meta['provider_data']}", xbmc.LOGINFO)
    
    return meta

# === FUNÇÕES PÚBLICAS ===
def show_details_movie(item_data):
    """Mostra detalhes de filme"""
    if not item_data:
        return
    
    meta = _prepare_common_meta(item_data)
    meta['media_type'] = 'movie'
    meta["duration_str"] = f"{int(meta.get('runtime', 0))} min" if meta.get('runtime') else ""
    meta['streams'] = item_data.get('streams', [])
    
    win = CineroomDetailsWindow(
        "CineroomDetails.xml",
        ADDON_PATH,
        "Default",
        "1080i",
        meta=meta
    )
    win.doModal()
    del win

def show_details_tvshow(item_data):
    """Mostra detalhes de série"""
    if not item_data:
        return
    
    meta = _prepare_common_meta(item_data)
    meta['media_type'] = 'tvshow'
    meta["duration_str"] = ""
    meta['total_seasons'] = item_data.get('total_seasons')
    meta['status'] = item_data.get('status')
    
    win = CineroomDetailsWindow(
        "CineroomDetails.xml",
        ADDON_PATH,
        "Default",
        "1080i",
        meta=meta
    )
    win.doModal()
    del win

def show_details(item_data):
    """Dispatcher principal"""
    if not item_data:
        return
    
    media_type = item_data.get("media_type")
    
    # FILMES
    if media_type == "movie":
        if not MOVIE_DETAILS_ENABLED:
            from resources.lib import navigation
            navigation.find_and_play_sources(item_data, autoplay=AUTOPLAY)
        else:
            show_details_movie(item_data)
        return
    
    # SÉRIES
    if media_type == "tvshow":
        if not TVSHOW_DETAILS_ENABLED:
            tmdb_id = item_data.get("tmdb_id")
            xbmc.executebuiltin(
                f"Container.Update("
                f"plugin://plugin.video.cineroom.lite?"
                f"action=list_seasons&tvshow_tmdb_id={tmdb_id})"
            )
        else:
            show_details_tvshow(item_data)
        return