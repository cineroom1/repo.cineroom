# -*- coding: utf-8 -*-
import xbmcgui
import xbmc
import json
import urllib.parse
import threading
import time
import os
from xbmcaddon import Addon
import xbmcvfs
from collections import OrderedDict

ADDON = Addon('plugin.video.cineroom.lite')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
ADDON_PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

MOVIE_DETAILS_ENABLED = ADDON.getSettingBool("movie.enable_details")
TVSHOW_DETAILS_ENABLED = ADDON.getSettingBool("tvshow.enable_details")

# ===== CONFIGS DE OTIMIZAÇÃO (foco em Android TV / TCL fraca) =====
EXTRAS_LIMIT = 8                 # Menor = mais leve para TVs fracas
EXTRAS_CACHE_TTL = 600            # 10 min
DETAILS_EXTRA_CACHE_TTL = 900     # 15 min
DISK_CACHE_TTL = 1800             # 30 min
CLICK_DEBOUNCE_MS = 350           # Evita double-click acidental
UI_POLL_INTERVAL_MS = 120         # Poll leve e seguro para UI
MAX_DISK_CACHE_ITEMS = 120        # Limita crescimento do cache persistente

# ===== DEBUG CONTROLADO =====
DEBUG_LOGS = False  # Troque para True se quiser logs detalhados


def log(msg, level=xbmc.LOGINFO):
    if DEBUG_LOGS or level >= xbmc.LOGERROR:
        xbmc.log(f"[CINEROOM] {msg}", level)


# ===== GARANTE PASTA PROFILE =====
if not xbmcvfs.exists(ADDON_PROFILE):
    try:
        xbmcvfs.mkdirs(ADDON_PROFILE)
    except Exception as e:
        log(f"Erro criando profile dir: {e}", xbmc.LOGERROR)

CACHE_FILE = os.path.join(ADDON_PROFILE, "details_extras_cache.json")

# ===== CACHE EM MEMÓRIA =====
_EXTRAS_CACHE = {}
_DETAILS_EXTRA_CACHE = {}

# ===== CACHE PERSISTENTE EM DISCO =====
_DISK_CACHE = {}
_DISK_CACHE_LOADED = False
_DISK_CACHE_LOCK = threading.Lock()


def _cache_get(cache, key, ttl):
    entry = cache.get(key)
    if not entry:
        return None

    ts = entry.get('ts', 0)
    if (time.time() - ts) > ttl:
        try:
            del cache[key]
        except Exception:
            pass
        return None

    return entry.get('data')


def _cache_set(cache, key, data):
    cache[key] = {
        'ts': time.time(),
        'data': data
    }


def _load_disk_cache():
    global _DISK_CACHE_LOADED, _DISK_CACHE

    if _DISK_CACHE_LOADED:
        return

    with _DISK_CACHE_LOCK:
        if _DISK_CACHE_LOADED:
            return

        try:
            if xbmcvfs.exists(CACHE_FILE):
                f = xbmcvfs.File(CACHE_FILE)
                raw = f.read()
                f.close()

                if raw:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        _DISK_CACHE = data
        except Exception as e:
            log(f"Erro carregando disk cache: {e}", xbmc.LOGERROR)
            _DISK_CACHE = {}

        _DISK_CACHE_LOADED = True


def _prune_disk_cache():
    """Remove expirados e limita tamanho do cache em disco."""
    now = time.time()

    expired_keys = []
    for k, v in _DISK_CACHE.items():
        ts = v.get('ts', 0)
        if (now - ts) > DISK_CACHE_TTL:
            expired_keys.append(k)

    for k in expired_keys:
        _DISK_CACHE.pop(k, None)

    if len(_DISK_CACHE) > MAX_DISK_CACHE_ITEMS:
        ordered = sorted(_DISK_CACHE.items(), key=lambda kv: kv[1].get('ts', 0))
        to_remove = len(_DISK_CACHE) - MAX_DISK_CACHE_ITEMS
        for i in range(to_remove):
            _DISK_CACHE.pop(ordered[i][0], None)


def _save_disk_cache():
    with _DISK_CACHE_LOCK:
        try:
            _prune_disk_cache()
            payload = json.dumps(_DISK_CACHE, separators=(',', ':'))

            f = xbmcvfs.File(CACHE_FILE, 'w')
            f.write(payload)
            f.close()
        except Exception as e:
            log(f"Erro salvando disk cache: {e}", xbmc.LOGERROR)


def _disk_cache_get(key, ttl=DISK_CACHE_TTL):
    _load_disk_cache()

    with _DISK_CACHE_LOCK:
        entry = _DISK_CACHE.get(key)
        if not entry:
            return None

        ts = entry.get('ts', 0)
        if (time.time() - ts) > ttl:
            _DISK_CACHE.pop(key, None)
            return None

        return entry.get('data')


def _disk_cache_set(key, data):
    _load_disk_cache()

    with _DISK_CACHE_LOCK:
        _DISK_CACHE[key] = {
            'ts': time.time(),
            'data': data
        }

    # Salva async para não travar UI
    threading.Thread(target=_save_disk_cache, daemon=True).start()


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
_LOGO_CACHE_INITIALIZED = False


def _init_logo_cache():
    """Inicializa cache de logos (lazy — roda 1x na primeira chamada)"""
    global _LOGO_CACHE_INITIALIZED
    if _LOGO_CACHE_INITIALIZED:
        return
    base = f"{ADDON_PATH}/resources/logos"
    for k, logo in _PROVIDER_LOGOS.items():
        path = xbmcvfs.translatePath(f"{base}/{logo}")
        if xbmcvfs.exists(path):
            _LOGO_PATHS[k] = path
    _LOGO_CACHE_INITIALIZED = True


def get_logo_path(provider):
    """Retorna caminho do logo (com cache lazy)"""
    if not provider:
        return ""
    _init_logo_cache()
    return _LOGO_PATHS.get(str(provider).lower(), "")


# ===== VIP AUTH =====

def _is_vip():
    """Retorna True se o usuário tem sessão VIP válida."""
    try:
        from resources.lib.vip_auth import is_session_valid
        return is_session_valid()
    except Exception:
        return False


def _require_vip(feature_name="este recurso"):
    """
    Exibe apenas uma mensagem se o usuário não for VIP.
    Retorna True se pode prosseguir, False caso contrário.
    """
    if _is_vip():
        return True

    xbmcgui.Dialog().ok(
        "Cineroom PLUS",
        f"[B]{feature_name}[/B] é exclusivo para assinantes PLUS.\n\nAssine o PLUS e desbloqueie todos os recursos"
    )
    return False


# === DIALOG DE DETALHES ESTILO NETFLIX ===
class CineroomDetailsWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.meta = kwargs.get('meta', {})
        self.is_tvshow = self.meta.get('media_type') == 'tvshow'
        self.has_collection = bool(self.meta.get('collection'))
        self._is_favorite = None
        self.rec_items = []
        self.sim_items = []
        self.col_items = []
        self.cast_items = []       # lista de atores para o painel
        self.actor_items = []      # filmes+séries do ator clicado
        self._cast_ready = False
        self._cast_thread_started = False
        self._ui_cast_poll_thread = None
        self._col_ready = False
        self._col_thread_started = False
        self._ui_col_poll_thread = None
        self._rec_ready = False
        self._sim_ready = False
        self._controls = {}
        self._closed = False
        self._extras_error = False
        self._extras_thread_started = False
        self._ui_poll_thread = None
        self._last_click_ts = 0

    # ===== HELPERS DE CONTROLE =====
    def _get_control_safe(self, control_id):
        ctrl = self._controls.get(control_id)
        if ctrl is not None:
            return ctrl

        try:
            ctrl = self.getControl(control_id)
            self._controls[control_id] = ctrl
            return ctrl
        except Exception as e:
            log(f"Control {control_id} não encontrado: {e}", xbmc.LOGERROR)
            return None

    def _reset_and_add_items(self, control_id, items):
        """
        Só chamar isso da thread de UI polling (seguro no fluxo adotado).
        """
        if self._closed:
            return

        ctrl = self._get_control_safe(control_id)
        if not ctrl:
            return

        try:
            ctrl.reset()
            if items:
                ctrl.addItems(items)
        except Exception as e:
            log(f"Erro ao popular control {control_id}: {e}", xbmc.LOGERROR)

    def _build_listitems(self, items):
        listitems = []
        append = listitems.append

        for item in items:
            li = xbmcgui.ListItem(label=item.get('title', ''))
            li.setArt({'thumb': item.get('poster', '')})
            li.setProperty('media_type', item.get('media_type', 'movie'))

            # Gêneros para exibição nos cards de similares/recomendados
            genres = item.get('genres', [])
            if isinstance(genres, list):
                li.setProperty('genres', ' • '.join(g for g in genres[:3] if g))
            elif isinstance(genres, str):
                li.setProperty('genres', genres)

            append(li)

        return listitems

    def _click_allowed(self):
        now = int(time.time() * 1000)
        if (now - self._last_click_ts) < CLICK_DEBOUNCE_MS:
            return False
        self._last_click_ts = now
        return True

    # ===== EXTRAS LOADING (worker thread + ui polling) =====
    def _fetch_extras_async(self):
        """
        Busca recomendados e similares com:
        - cache memória
        - cache disco
        - paralelismo com lazy load (rec aparece antes de sim)
        - SEM tocar na UI aqui (mais seguro para Kodi/Android)
        - Só executa para usuários VIP
        """
        try:
            from resources.lib.tmdb_api import fetch_recommendations

            tmdb_id = self.meta.get('tmdb_id')
            media_type = 'tv' if self.is_tvshow else 'movie'

            if not tmdb_id or self._closed:
                self._extras_error = True
                return

            cache_key = f"extras:{media_type}:{tmdb_id}"

            # Kids filter lido 1x aqui — evita instanciar ProfileManager múltiplas vezes
            age_range = self._get_kids_age_range()

            # 1) memória
            cached = _cache_get(_EXTRAS_CACHE, cache_key, EXTRAS_CACHE_TTL)

            # 2) disco
            if not cached:
                cached = _disk_cache_get(cache_key, DISK_CACHE_TTL)
                if cached:
                    _cache_set(_EXTRAS_CACHE, cache_key, cached)

            if cached:
                self.rec_items = cached.get('rec', []) or []
                self.sim_items = []

                # Kids filter (cache pode ter sido gerado por perfil adulto)
                if age_range is not None:
                    self.rec_items = self._filter_kids(self.rec_items, age_range)
                    self.sim_items = []

                # Sinaliza ambos prontos de uma vez (veio do cache)
                self._rec_ready = True
                self._sim_ready = False

            else:
                rec_items = []
                sim_items = []

                def load_rec():
                    nonlocal rec_items
                    try:
                        rec_items = fetch_recommendations(tmdb_id, media_type, limit=EXTRAS_LIMIT) or []
                    except Exception as e:
                        log(f"Erro fetch recommendations: {e}", xbmc.LOGERROR)
                        rec_items = []
                    finally:
                        # Sinaliza rec pronto imediatamente (lazy load)
                        self.rec_items = rec_items
                        self._rec_ready = True

                t1 = threading.Thread(target=load_rec, daemon=True)
                t1.start()
                t1.join()

                if self._closed:
                    self._extras_error = True
                    return

                # Kids filter reutiliza age_range já lido no início
                if age_range is not None:
                    self.rec_items = self._filter_kids(self.rec_items, age_range)
                    self.sim_items = self._filter_kids(self.sim_items, age_range)

                # Salva no cache
                payload = {
                    'rec': self.rec_items
                }
                _cache_set(_EXTRAS_CACHE, cache_key, payload)
                _disk_cache_set(cache_key, payload)

        except Exception as e:
            log(f"Erro extras: {e}", xbmc.LOGERROR)
            self._extras_error = True

    def _ui_extras_poll_loop(self):
        """
        Polling leve e seguro com lazy load:
        - popula recomendados assim que ficam prontos
        - popula similares assim que ficam prontos
        - não espera os dois ao mesmo tempo
        """
        try:
            monitor = xbmc.Monitor()
            rec_populated = False
            sim_populated = False

            while not monitor.abortRequested() and not self._closed:
                if self._rec_ready and not rec_populated:
                    rec_lis = self._build_listitems(self.rec_items)
                    self._reset_and_add_items(600, rec_lis)
                    rec_populated = True

                if rec_populated:
                    return

                if self._extras_error:
                    return

                xbmc.sleep(UI_POLL_INTERVAL_MS)

        except Exception as e:
            log(f"Erro ui extras poll: {e}", xbmc.LOGERROR)

    def _start_extras_thread(self):
        """Só inicia busca de recomendados para usuários VIP."""
        if self._extras_thread_started:
            return

        self._extras_thread_started = True

        # Worker: busca dados
        threading.Thread(target=self._fetch_extras_async, daemon=True).start()

        # Poller: aguarda e popula UI
        self._ui_poll_thread = threading.Thread(target=self._ui_extras_poll_loop, daemon=True)
        self._ui_poll_thread.start()
        
        
    def _fetch_collection_async(self):
        try:
            collection_name = self.meta.get('collection', '')
            if not collection_name or self._closed:
                return
            from resources.lib.db import db
            age_range = self._get_kids_age_range()
            movies = db.get_movies_by_collection(collection_name) or []
            own_tmdb = self.meta.get('tmdb_id')
            if own_tmdb:
                movies = [m for m in movies if str(m.get('tmdb_id','')) != str(own_tmdb)]
            col_items = []
            for m in movies:
                genres = m.get('genres', [])
                if isinstance(genres, str):
                    try: genres = json.loads(genres)
                    except: genres = [g.strip() for g in genres.split(',') if g.strip()]
                col_items.append({
                    'title': m.get('title',''), 'poster': m.get('poster',''),
                    'media_type': 'movie', 'tmdb_id': m.get('tmdb_id'),
                    'imdb_id': m.get('imdb_id', ''),
                    'genres': genres, 'synopsis': m.get('synopsis','') or m.get('plot',''),
                    'year': m.get('year',''), 'rating': m.get('rating',''),
                    'certification': m.get('certification','') or m.get('classification',''),
                    'backdrop': m.get('backdrop',''), 'clearlogo': m.get('clearlogo',''),
                    'providers': m.get('providers',[]), 'runtime': m.get('runtime',0),
                    'streams': m.get('streams',[]), 'collection': m.get('collection',''),
                })
            if age_range is not None:
                col_items = self._filter_kids(col_items, age_range)
            self.col_items = col_items
        except Exception as e:
            log(f"Erro fetch collection: {e}", xbmc.LOGERROR)
        finally:
            self._col_ready = True  
            
    def _ui_col_poll_loop(self):
        try:
            monitor = xbmc.Monitor()
            populated = False
            while not monitor.abortRequested() and not self._closed:
                if self._col_ready and not populated:
                    self._reset_and_add_items(700, self._build_listitems(self.col_items))
                    populated = True
                    return
                xbmc.sleep(UI_POLL_INTERVAL_MS)
        except Exception as e:
            log(f"Erro ui col poll: {e}", xbmc.LOGERROR)   
            
            
    def _start_collection_thread(self):
        if self._col_thread_started or not self.has_collection:
            return
        self._col_thread_started = True
        threading.Thread(target=self._fetch_collection_async, daemon=True).start()
        self._ui_col_poll_thread = threading.Thread(target=self._ui_col_poll_loop, daemon=True)
        self._ui_col_poll_thread.start()    
        
        
        
    def _fetch_cast_async(self):
        try:
            cast = self.meta.get('cast', [])
        
            # Se não veio no meta, busca direto no DB
            if not cast:
                tmdb_id = self.meta.get('tmdb_id')
                media_type = self.meta.get('media_type', 'movie')
                if tmdb_id:
                    try:
                        from resources.lib.db import db
                        if media_type == 'tvshow':
                            record = db.get_tvshow_by_id(tmdb_id)
                        else:
                            record = db.get_movie_by_id(tmdb_id)
                        if record:
                            cast = record.get('cast', [])
                    except Exception as e:
                        log(f"Erro buscando cast no DB: {e}", xbmc.LOGERROR)

            if isinstance(cast, str):
                try:
                    cast = json.loads(cast)
                except Exception:
                    cast = []

            log(f"CAST RAW: {type(cast)} - {len(cast) if cast else 0} items", xbmc.LOGINFO)
            if cast:
                log(f"First cast item: {cast[0]}", xbmc.LOGINFO)

                items = []
                for actor in cast[:8]:  # mesmo limite do EXTRAS_LIMIT
                    if not actor.get('tmdb_person_id'):
                        continue
                    items.append({
                        'name': actor.get('name', ''),
                        'character': actor.get('character', ''),
                        'profile': actor.get('profile', ''),
                        'tmdb_person_id': actor.get('tmdb_person_id'),
                    })

                age_range = self._get_kids_age_range()
            # Cast não tem classificação etária, então só filtra se perfil kids estiver
            # configurado para bloquear tudo — por segurança, permitimos elenco sempre.
            self.cast_items = items
        except Exception as e:
            log(f"Erro fetch cast: {e}", xbmc.LOGERROR)
        finally:
            self._cast_ready = True


    def _build_cast_listitems(self, cast_items):
        listitems = []
        for actor in cast_items:
            li = xbmcgui.ListItem(label=actor.get('name', ''))
            li.setArt({'thumb': actor.get('profile', '')})
            li.setProperty('character', actor.get('character', ''))
            li.setProperty('tmdb_person_id', str(actor.get('tmdb_person_id', '')))
            listitems.append(li)
        return listitems


    def _ui_cast_poll_loop(self):
        try:
            monitor = xbmc.Monitor()
            populated = False
            while not monitor.abortRequested() and not self._closed:
                if self._cast_ready and not populated:
                    self._reset_and_add_items(800, self._build_cast_listitems(self.cast_items))
                    populated = True
                    return
                xbmc.sleep(UI_POLL_INTERVAL_MS)
        except Exception as e:
            log(f"Erro ui cast poll: {e}", xbmc.LOGERROR)


    def _start_cast_thread(self):
        if self._cast_thread_started:
            return
        self._cast_thread_started = True
        threading.Thread(target=self._fetch_cast_async, daemon=True).start()
        self._ui_cast_poll_thread = threading.Thread(
            target=self._ui_cast_poll_loop, daemon=True
        )
        self._ui_cast_poll_thread.start()


    def _open_actor_detail(self, actor):
        """Busca filmes+séries do ator no DB local e abre lista igual à coleção."""
        if not actor:
            return

        tmdb_person_id = actor.get('tmdb_person_id')
        actor_name = actor.get('name', 'Ator')

        if not tmdb_person_id:
            return

        if not _require_vip("Filmografia do Ator"):
            return

        # Busca local — sem rede
        try:
            from resources.lib.db import db
            movies = db.get_movies_by_cast_id(tmdb_person_id) or []
            shows  = db.get_tvshows_by_cast_id(tmdb_person_id) or []
        except Exception as e:
            log(f"Erro buscando filmografia: {e}", xbmc.LOGERROR)
            movies, shows = [], []

        all_items = []
        for m in movies:
            genres = m.get('genres', [])
            if isinstance(genres, str):
                try: genres = json.loads(genres)
                except: genres = [g.strip() for g in genres.split(',') if g.strip()]
            all_items.append({
                'title': m.get('title', ''), 'poster': m.get('poster', ''),
                'media_type': 'movie', 'tmdb_id': m.get('tmdb_id'),
                'imdb_id': m.get('imdb_id', ''), 'genres': genres,
                'synopsis': m.get('synopsis', '') or m.get('plot', ''),
                'year': m.get('year', ''), 'rating': m.get('rating', ''),
                'certification': m.get('certification', '') or m.get('classification', ''),
                'backdrop': m.get('backdrop', ''), 'clearlogo': m.get('clearlogo', ''),
                'providers': m.get('providers', []), 'runtime': m.get('runtime', 0),
                'streams': m.get('streams', []), 'collection': m.get('collection', ''),
            })
        for s in shows:
            genres = s.get('genres', [])
            if isinstance(genres, str):
                try: genres = json.loads(genres)
                except: genres = [g.strip() for g in genres.split(',') if g.strip()]
            all_items.append({
                'title': s.get('title', ''), 'poster': s.get('poster', ''),
                'media_type': 'tvshow', 'tmdb_id': s.get('tmdb_id'),
                'imdb_id': s.get('imdb_id', ''), 'genres': genres,
                'synopsis': s.get('synopsis', '') or s.get('plot', ''),
                'year': s.get('year', ''), 'rating': s.get('rating', ''),
                'certification': s.get('certification', ''),
                'backdrop': s.get('backdrop', ''), 'clearlogo': s.get('clearlogo', ''),
                'providers': s.get('providers', []),
            })

        if not all_items:
            xbmcgui.Dialog().ok(actor_name, "Nenhum título disponível no catálogo.")
            return

        self._open_actor_results_dialog(actor_name, all_items)


    # ===== KIDS FILTER =====
    def _get_kids_age_range(self):
        """Retorna age_range do perfil ativo se for kids, senão None."""
        try:
            from resources.lib.profile_manager import ProfileManager
            profile = ProfileManager().get_current_profile()
            if profile and profile.get('is_kids'):
                return profile.get('preferences', {}).get('age_range', 'livre')
        except Exception:
            pass
        return None

    _KIDS_ALLOWED = {
        '2_6_anos':   {'L', 'G', 'TV-Y', 'TV-G'},
        '7_10_anos':  {'L', 'G', 'TV-Y', 'TV-Y7', 'TV-G', 'TV-PG', '10'},
        '11_14_anos': {'L', 'G', 'TV-Y', 'TV-Y7', 'TV-G', 'TV-PG', '10', '12', 'PG', '14'},
    }

    def _filter_kids(self, items, age_range):
        """Remove itens acima da faixa etária do perfil kids."""
        allowed = self._KIDS_ALLOWED.get(age_range, set())
        result = []
        for item in items:
            cert = str(item.get('certification') or item.get('classification') or '').strip().upper()
            # Sem classificação → permite (TMDB frequentemente não retorna para conteúdo kids)
            if not cert or cert in allowed:
                result.append(item)
        return result

    # ===== NAVEGAÇÃO / ABERTURA DE ITEM =====
    def _open_similar_detail(self, item):
        """
        Abre item similar/recomendado com:
        - cache memória
        - cache disco
        - evita refetch desnecessário
        """
        self._closed = True
        self.close()

        if not item:
            return

        media_type = item.get('media_type', 'movie')
        tmdb_id = item.get('tmdb_id')

        try:
            needs_extra = (
                not item.get('clearlogo') or
                not item.get('providers') or
                not item.get('runtime') or
                not item.get('certification')
            )

            if tmdb_id and needs_extra:
                cache_key = f"detail_extra:{media_type}:{tmdb_id}"

                # 1) memória
                cached_extra = _cache_get(_DETAILS_EXTRA_CACHE, cache_key, DETAILS_EXTRA_CACHE_TTL)

                # 2) disco
                if not cached_extra:
                    cached_extra = _disk_cache_get(cache_key, DISK_CACHE_TTL)
                    if cached_extra:
                        _cache_set(_DETAILS_EXTRA_CACHE, cache_key, cached_extra)

                if cached_extra:
                    item.update(cached_extra)
                else:
                    from resources.lib.tmdb_api import _fetch_tmdb_extra, fetch_certification

                    extra = _fetch_tmdb_extra({'id': tmdb_id}, media_type) or {}

                    cert = extra.get('certification')
                    if not cert:
                        cert = fetch_certification(tmdb_id, media_type)

                    extra_payload = {
                        'clearlogo': extra.get('clearlogo', ''),
                        'providers': extra.get('providers', []),
                        'runtime': extra.get('runtime', 0),
                        'imdb_id': extra.get('imdb_id', ''),
                        'certification': cert or '',
                    }

                    item.update(extra_payload)

                    _cache_set(_DETAILS_EXTRA_CACHE, cache_key, extra_payload)
                    _disk_cache_set(cache_key, extra_payload)

        except Exception as e:
            log(f"Erro extras similar: {e}", xbmc.LOGERROR)

        # Kids filter antes de abrir o dialog
        age_range = self._get_kids_age_range()
        if age_range is not None:
            filtered = self._filter_kids([item], age_range)
            if not filtered:
                import xbmcgui
                xbmcgui.Dialog().ok(
                    'Conteúdo Bloqueado',
                    'Este conteúdo não está disponível para este perfil.'
                )
            return
        
        if media_type == 'movie' and not item.get('collection') and tmdb_id:
            try:
                from resources.lib.db import db
                row = db.get_movie_by_id(tmdb_id)
                if row:
                    item['collection'] = row.get('collection', '')
            except Exception:
                pass

        if media_type == 'tvshow':
            show_details_tvshow(item)
        else:
            show_details_movie(item)

    def _check_favorite_status(self):
        if self._is_favorite is None:
            from resources.lib.db.favorites_db import favorites_db
            from resources.lib.favorites import _resolve_profile_id

            tmdb_id = self.meta.get("tmdb_id")
            media_type = "tvshow" if self.is_tvshow else "movie"
            profile_id = _resolve_profile_id()

            favorites_db._cache_delete_prefix(f"is_fav:{tmdb_id}:{media_type}")
            self._is_favorite = favorites_db.is_favorite(tmdb_id, media_type, profile_id=profile_id)

        return self._is_favorite

    # ===== PROPERTIES =====
    def _setup_properties(self):
        """Define propriedades do dialog"""
        m = self.meta

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
        self.setProperty("rating", m.get("rating_str", ""))
        self.setProperty("rating_percent", m.get("rating_percent", "0"))
        self.setProperty("certification", m.get("certification", ""))

        # Gêneros (max 3)
        genre_list = m.get('genre_list', [])
        for i, g in enumerate(genre_list, 1):
            self.setProperty(f"Genre.{i}.Label", g)

        # Limpa sobras caso item anterior tenha mais gêneros
        for i in range(len(genre_list) + 1, 4):
            self.setProperty(f"Genre.{i}.Label", "")

        # Provedores
        provider_data = m.get('provider_data', [])
        self.setProperty("HasProviders", "true" if provider_data else "false")

    # ===== CICLO DE VIDA =====
    def onInit(self):
        self._closed = False
        self._is_favorite = None
        self._setup_properties()

        # VIP flag para o skin (use em CineroomDetails.xml para mostrar/ocultar elementos)
        self.setProperty("IsVIP", "true" if _is_vip() else "false")

        # Mostra label padrão imediatamente — DB query roda em background para não travar UI
        self.setProperty("FavoriteLabel", "Minha Lista")
        threading.Thread(target=self._load_favorite_async, daemon=True).start()

        self._populate_providers()
        self.set_focus_immediate()
        self._start_extras_thread()
        self._start_collection_thread()
        self._start_cast_thread()


    def _load_favorite_async(self):
        """Lê status de favorito em background e atualiza a property."""
        try:
            is_fav = self._check_favorite_status()
            if not self._closed:
                self.setProperty("FavoriteLabel", "Remover" if is_fav else "Minha Lista")
        except Exception as e:
            log(f"Erro ao carregar favorito async: {e}", xbmc.LOGERROR)

    def _populate_providers(self):
        """Popula panel de providers dinamicamente"""
        provider_data = self.meta.get('provider_data', [])
        panel = self._get_control_safe(510)
        if not panel:
            return

        try:
            panel.reset()
            if not provider_data:
                return

            items = []
            append = items.append

            for prov in provider_data:
                li = xbmcgui.ListItem(label=prov.get('name', ''))
                li.setArt({'thumb': prov.get('icon', '')})
                append(li)

            panel.addItems(items)

        except Exception as e:
            log(f"providers panel: {e}", xbmc.LOGERROR)

    def set_focus_immediate(self):
        """Define foco no botão principal (tenta 301 → 302 → 303)"""
        for control_id in (301, 302, 303):
            try:
                self.setFocusId(control_id)
                return  # sai no primeiro que funcionar
            except Exception:
                continue

    # ===== HELPERS DE NAVEGAÇÃO =====
    def _open_collection_detail(self, item):
        self._closed = True
        self.close()
        if not item:
            return
        age_range = self._get_kids_age_range()
        if age_range is not None:
            if not self._filter_kids([item], age_range):
                xbmcgui.Dialog().ok('Conteúdo Bloqueado', 'Este conteúdo não está disponível para este perfil.')
                return
        show_details_movie(item)
        
    
    def _open_actor_results_dialog(self, actor_name, items):
        actor = {'name': actor_name, 'profile': '', 'tmdb_person_id': None}
        for c in (self.cast_items or []):
            if c.get('name') == actor_name:
                actor = c
                break

        try:
            win = ActorInfoWindow(
                "CineroomActorInfo.xml",
                ADDON_PATH,
                "Default",
                "1080i",
                actor=actor,
                local_items=items,
            )
            win.doModal()
            navigated = win.navigated_away
            del win

            # Se o usuário navegou para fora a partir da bio (play, list_seasons, etc.),
            # fecha o CineroomDetailsWindow pai também para não ficar sobreposto.
            if navigated and not self._closed:
                self._closed = True
                self.close()

        except Exception as e:
            log(f"Erro abrindo ActorInfoWindow: {e}", xbmc.LOGERROR)

    def _open_seasons(self, tmdb_id):
        self._closed = True
        self.close()
        self._open_container(
            f"plugin://plugin.video.cineroom.lite?"
            f"action=list_seasons&tvshow_tmdb_id={tmdb_id}"
        )

    def _open_provider(self, provider_name):
        provider = urllib.parse.quote_plus(provider_name)
        action = "list_tvshows_by_provider" if self.is_tvshow else "list_movies_by_provider"
        self._closed = True
        self.close()
        self._open_container(
            f"plugin://plugin.video.cineroom.lite?"
            f"action={action}&provider={provider}"
        )

    def _open_genre(self, genre_name):
        genre = urllib.parse.quote_plus(genre_name)
        action = "list_tvshows_by_genre" if self.is_tvshow else "list_movies_by_genre"
        self._closed = True
        self.close()
        self._open_container(
            f"plugin://plugin.video.cineroom.lite?"
            f"action={action}&genre={genre}"
        )

    # ===== EVENTOS =====
    def onClick(self, controlID):
        """Handler de cliques com gate VIP."""
        try:
            if not self._click_allowed():
                return

            tmdb_id = self.meta.get("tmdb_id")
            media_type = "tvshow" if self.is_tvshow else "movie"

            # === BOTÃO PRINCIPAL (301) — FREE: assistir / abrir temporadas ===
            if controlID == 301:
                if self.is_tvshow:
                    self._open_seasons(tmdb_id)
                else:
                    self._closed = True
                    self.close()
                    self._play()

            # === SELECIONAR FONTE (300) — FREE ===
            elif controlID == 300:
                self._closed = True
                self.close()
                self._play(force_select=True)

            # === MINHA LISTA / FAVORITO (302, 305, 322) — FREE ===
            elif controlID in (302, 305, 322):
                self._toggle_favorite(tmdb_id, media_type)

            # === VER COLEÇÃO (303, 304) — FREE ===
            elif controlID == 700:
                ctrl = self._get_control_safe(700)
                if ctrl:
                    pos = ctrl.getSelectedPosition()
                    if 0 <= pos < len(self.col_items):
                        self._open_collection_detail(self.col_items[pos])
                        
            # === CAST PANEL (800) — VIP ===
            elif controlID == 800:
                if not _require_vip("Filmografia do Ator"):
                    return
                ctrl = self._get_control_safe(800)
                if ctrl:
                    pos = ctrl.getSelectedPosition()
                    if 0 <= pos < len(self.cast_items):
                        self._open_actor_detail(self.cast_items[pos])            

            # === TEMPORADAS LEGADO (321) — FREE (navegação normal) ===
            elif controlID == 321:
                self._open_seasons(tmdb_id)

            # === GÊNEROS (401-403) — VIP ===
            elif 400 < controlID < 404:
                if not _require_vip("Atalhos de Gênero"):
                    return
                idx = controlID - 401
                genres = self.meta.get('genre_list', [])
                if idx < len(genres):
                    self._open_genre(genres[idx])

            # === PROVIDER PANEL (510) — VIP ===
            elif controlID == 510:
                if not _require_vip("Atalhos de Plataforma"):
                    return
                panel = self._get_control_safe(510)
                if panel:
                    idx = panel.getSelectedPosition()
                    providers = self.meta.get('provider_data', [])
                    if 0 <= idx < len(providers):
                        self._open_provider(providers[idx].get('name', ''))

            # === PROVIDERS LEGADOS (501-504) — VIP ===
            elif 500 < controlID < 505:
                if not _require_vip("Atalhos de Plataforma"):
                    return
                idx = controlID - 501
                providers = self.meta.get('provider_data', [])
                if idx < len(providers):
                    self._open_provider(providers[idx].get('name', ''))

            # === RECOMENDADOS (600) — FREE vê, VIP navega ===
            elif controlID == 600:
                ctrl = self._get_control_safe(600)
                if ctrl:
                    pos = ctrl.getSelectedPosition()
                    items = self.rec_items or []
                    if 0 <= pos < len(items):
                        if not _require_vip("Atalhos de Recomendados"):
                           return
                        self._open_similar_detail(items[pos])

            # === FECHAR (999) ===
            elif controlID == 999:
                self._closed = True
                self.close()

        except Exception as e:
            log(f"onClick error: {e}", xbmc.LOGERROR)
            self._show_error("Operação falhou. Tente novamente.")

    def _open_container(self, url):
        xbmc.executebuiltin(f"Container.Update({url})")

    def _play(self, force_select=False):
        from resources.lib import navigation
        navigation.find_and_play_sources(self.meta, force_select=force_select)

    def _toggle_favorite(self, tmdb_id, media_type):
        from resources.lib.favorites import add_item_to_favorites, remove_item_from_favorites

        was_favorite = self._check_favorite_status()

        try:
            if was_favorite:
                remove_item_from_favorites(tmdb_id, media_type)
                self.setProperty("FavoriteLabel", "Minha Lista")
                self._is_favorite = False
            else:
                add_item_to_favorites(tmdb_id, media_type)
                self.setProperty("FavoriteLabel", "Remover")
                self._is_favorite = True

        except Exception as e:
            log(f"Erro ao alternar favorito: {e}", xbmc.LOGERROR)
            self._show_error("Erro ao atualizar lista")

    def _show_error(self, message):
        xbmcgui.Dialog().notification(
            "Cineroom",
            message,
            xbmcgui.NOTIFICATION_ERROR,
            2000
        )

    def onAction(self, action):
        if action.getId() in (10, 92, xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self._closed = True
            self.close()

    def __del__(self):
        self._closed = True
        self.meta = None
        self._is_favorite = None
        self.rec_items = None
        self.sim_items = None
        self._controls = None
        self._ui_poll_thread = None
        self.col_items = None
        self._ui_col_poll_thread = None 
        self.cast_items = None
        self.actor_items = None
        self._ui_cast_poll_thread = None



# === DIALOG DE INFO DO ATOR ===
class ActorInfoWindow(xbmcgui.WindowXMLDialog):
    """
    Dialog de filmografia do ator.
    XML: CineroomActorInfo.xml
    Mostra bio, foto e filmografia do catálogo local (DB).
    Mantém a janela viva ao abrir um details, para o BACK voltar para a biografia.
    """

    def __init__(self, *args, **kwargs):
        self.actor = kwargs.pop('actor', {})
        self.local_items = kwargs.pop('local_items', [])
        self._person_data = None
        self._closed = False
        self._last_click_ts = 0
        # Flag: True quando o usuário navegou para fora (play, list_seasons, etc.)
        # O CineroomDetailsWindow pai checa isso após o doModal() retornar
        # para saber se deve fechar também.
        self.navigated_away = False
        super().__init__(*args, **kwargs)

    def onInit(self):
        self._closed = False

        # Propriedades imediatas — sem esperar rede
        self.setProperty("actor.name",       self.actor.get('name', ''))
        self.setProperty("actor.profile",    self.actor.get('profile', ''))
        self.setProperty("actor.known_for",  '')
        self.setProperty("actor.birthday",   '')
        self.setProperty("actor.birthplace", '')
        self.setProperty("actor.biography",  'Carregando...')
        self.setProperty("actor.credits_count", '')

        # Popula panel imediatamente com itens locais
        if self.local_items:
            self._populate_panel(self.local_items)

        # Bio em background (mantido)
        threading.Thread(target=self._fetch_person_async, daemon=True).start()

        # Foco na lista (como você quer)
        try:
            self.setFocusId(9002)
        except Exception:
            pass

    def _fetch_person_async(self):
        try:
            from resources.lib.tmdb_api import fetch_person_details
            tmdb_person_id = self.actor.get('tmdb_person_id')
            if not tmdb_person_id or self._closed:
                return

            data = fetch_person_details(tmdb_person_id)
            if not data or self._closed:
                return

            self._person_data = data

            if not self._closed:
                self.setProperty("actor.known_for",     data.get('known_for', ''))
                self.setProperty("actor.birthday",      data.get('birthday', ''))
                self.setProperty("actor.birthplace",    data.get('birthplace', ''))
                self.setProperty("actor.biography",     data.get('biography', ''))
                self.setProperty("actor.credits_count", str(data.get('credits_count', '')))

            # Mantém somente itens locais (DB), como você pediu
            merged = self.local_items

            if not self._closed:
                self._populate_panel(merged)

        except Exception as e:
            xbmc.log(f"[CINEROOM] ActorInfoWindow fetch error: {e}", xbmc.LOGERROR)

    def _populate_panel(self, items):
        try:
            ctrl = self.getControl(9002)
            ctrl.reset()

            lis = []
            for item in items:
                li = xbmcgui.ListItem(label=item.get('title', ''))
                li.setArt({'thumb': item.get('poster', '')})
                li.setProperty('character',  item.get('character', ''))
                li.setProperty('year',       str(item.get('year', '')))
                li.setProperty('media_type', item.get('media_type', 'movie'))
                # in_catalog: streams não é None → veio do DB local
                li.setProperty('in_catalog', '1' if item.get('streams') is not None else '0')
                lis.append(li)

            if lis:
                ctrl.addItems(lis)

        except Exception as e:
            xbmc.log(f"[CINEROOM] ActorInfoWindow populate error: {e}", xbmc.LOGERROR)

    def _open_selected_item(self, item):
        """
        Abre o details do item selecionado na biografia.
        Ao retornar, seta navigated_away para que o CineroomDetailsWindow
        pai saiba que deve fechar também.
        """
        if not item:
            return

        try:
            if item.get('media_type') == 'tvshow':
                # Séries: fecha a bio antes — Container.Update não funciona com modais empilhados.
                self.navigated_away = True
                self._closed = True
                self.close()
                xbmc.sleep(200)
                show_details_tvshow(item)
            else:
                # Filmes: abre o details e aguarda o doModal() retornar.
                show_details_movie(item)
                # doModal() retornou — details do filho fechou.
                # Fecha a bio e sinaliza ao pai que deve fechar também.
                if not self._closed:
                    self.navigated_away = True
                    self._closed = True
                    self.close()
        except Exception as e:
            xbmc.log(f"[CINEROOM] ActorInfoWindow open item error: {e}", xbmc.LOGERROR)

    def onClick(self, controlID):
        try:
            now = int(time.time() * 1000)
            if (now - self._last_click_ts) < CLICK_DEBOUNCE_MS:
                return
            self._last_click_ts = now

            if controlID == 9002:
                ctrl = self.getControl(9002)
                pos = ctrl.getSelectedPosition()

                merged = self.local_items

                if 0 <= pos < len(merged):
                    item = merged[pos]

                    if not item.get('tmdb_id'):
                        xbmcgui.Dialog().notification(
                            item.get('title', ''),
                            "Título não disponível no catálogo.",
                            xbmcgui.NOTIFICATION_INFO,
                            2500
                        )
                        return

                    # IMPORTANTE:
                    # NÃO fecha ActorInfoWindow aqui.
                    # Abre o details por cima, mantendo a biografia viva na stack.
                    self._open_selected_item(item)

            elif controlID == 9999:
                self._closed = True
                self.close()

        except Exception as e:
            xbmc.log(f"[CINEROOM] ActorInfoWindow onClick error: {e}", xbmc.LOGERROR)

    def onAction(self, action):
        if action.getId() in (10, 92, xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self._closed = True
            self.close()

    def __del__(self):
        self._closed = True
        self.local_items = None
        self._person_data = None


# === PREPARAÇÃO DE METADADOS ===
def _prepare_common_meta(item_data):
    meta = item_data.copy()

    raw_rating = meta.get("rating")
    if raw_rating:
        try:
            rating_float = float(raw_rating)
            meta["rating_str"] = f"{rating_float:.1f}"
            meta["rating_percent"] = str(int(round(rating_float * 10)))
        except Exception:
            meta["rating_str"] = ""
            meta["rating_percent"] = "0"
    else:
        meta["rating_str"] = ""
        meta["rating_percent"] = "0"

    # Gêneros (limite 3) — aceita tanto lista (TMDB) quanto string separada por vírgula (Kodi legacy)
    raw_genres = meta.get("genre", "") or meta.get("genres", [])
    if isinstance(raw_genres, list):
        meta['genre_list'] = [g for g in raw_genres if g][:3]
    elif isinstance(raw_genres, str) and raw_genres:
        meta['genre_list'] = [g.strip() for g in raw_genres.split(",") if g.strip()][:3]
    else:
        meta['genre_list'] = []

    # Poster em alta resolução
    poster = meta.get("poster", "")
    if poster and 'image.tmdb.org' in poster:
        try:
            from resources.lib.utils import scale_tmdb
            meta["poster"] = scale_tmdb(poster, "original")
        except Exception as e:
            log(f"Erro scale_tmdb: {e}", xbmc.LOGERROR)

    # Ano
    meta["year_str"] = str(meta.get("year", ""))

    # Provedores (max 4, sem duplicatas)
    providers = meta.get("providers", [])

    if isinstance(providers, str):
        try:
            providers = json.loads(providers)
        except Exception as e:
            log(f"Failed to parse providers JSON: {e}", xbmc.LOGERROR)
            providers = []

    unique_providers = OrderedDict()

    if isinstance(providers, (list, tuple)):
        for p in providers:
            logo = get_logo_path(p)
            if logo and logo not in unique_providers:
                unique_providers[logo] = {'name': p, 'icon': logo}
                if len(unique_providers) >= 4:
                    break

    meta['provider_data'] = list(unique_providers.values())

    # Certification
    cert = meta.get("certification") or meta.get("classification") or ""
    meta["certification"] = str(cert).strip()

    log(
        f"DEBUG cert raw: certification={meta.get('certification')} | "
        f"classification={meta.get('classification')} | final={meta['certification']}",
        xbmc.LOGINFO
    )

    return meta


# === FUNÇÕES PÚBLICAS ===
def show_details_movie(item_data):
    log(f"DEBUG item_data keys: {list(item_data.keys()) if item_data else []}", xbmc.LOGINFO)

    if item_data:
        try:
            cert_debug = item_data.get('certification')
        except Exception:
            cert_debug = ''
        log(f"DEBUG certification no item_data: {cert_debug!r}", xbmc.LOGINFO)

    if not item_data:
        return

    meta = _prepare_common_meta(item_data)
    meta['media_type'] = 'movie'
    meta["duration_str"] = f"{int(meta.get('runtime', 0))} MIN" if meta.get('runtime') else ""
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
    if not item_data:
        return

    media_type = item_data.get("media_type")

    if media_type == "movie":
        if not MOVIE_DETAILS_ENABLED:
            from resources.lib import navigation
            navigation.find_and_play_sources(item_data)
        else:
            show_details_movie(item_data)
        return

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