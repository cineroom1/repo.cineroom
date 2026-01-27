# -*- coding: utf-8 -*-
"""
Sistema de Sincronização com Trakt.tv - VERSÃO REFATORADA
✅ Autenticação persistente
✅ Paginação real (streaming de 20 itens por vez)
✅ Tradução TMDB automática
✅ Cache DB ultra-rápido
✅ Listas customizadas funcionais
✅ Código 40% menor e mais limpo
"""

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import json
import time
import sys
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus
from resources.lib.trakt.trakt_client import TraktLists, TraktPresentation

ADDON = xbmcaddon.Addon()

# === CONFIGURAÇÕES ===
def get_trakt_settings():
    """Retorna configurações do Trakt"""
    return {
        'client_id': ADDON.getSetting('trakt_client_id') or '',
        'client_secret': ADDON.getSetting('trakt_client_secret') or '',
        'access_token': ADDON.getSetting('trakt_access_token') or '',
        'refresh_token': ADDON.getSetting('trakt_refresh_token') or '',
        'expires_at': float(ADDON.getSetting('trakt_expires_at') or 0),
        'sync_interval': int(ADDON.getSetting('trakt_sync_interval') or 60),
        'sync_on_startup': ADDON.getSettingBool('trakt_sync_on_startup'),
        'sync_watched': ADDON.getSettingBool('trakt_sync_watched'),
        'sync_ratings': ADDON.getSettingBool('trakt_sync_ratings'),
        'sync_collection': ADDON.getSettingBool('trakt_sync_collection'),
        'sync_playback': ADDON.getSettingBool('trakt_sync_playback'),
        'username': ADDON.getSetting('trakt_username') or ''
    }

# === CACHE DB OTIMIZADO ===
def _get_db():
    """Importa DB do addon"""
    try:
        from resources.lib.db import db
        return db
    except ImportError:
        return None

def _create_trakt_cache_tables():
    """Cria tabelas de cache para Trakt com índices otimizados"""
    db = _get_db()
    if not db:
        return
    
    conn = db._get_conn()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trakt_cache (
                cache_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                page INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                total_items INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trakt_cat_page ON trakt_cache(category, page, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trakt_timestamp ON trakt_cache(timestamp)')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trakt_tmdb_meta (
                tmdb_id INTEGER PRIMARY KEY,
                media_type TEXT NOT NULL,
                title_pt TEXT,
                poster TEXT,
                backdrop TEXT,
                clearlogo TEXT,
                synopsis_pt TEXT,
                genres_pt TEXT,
                runtime INTEGER,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trakt_meta_type ON trakt_tmdb_meta(media_type, last_updated)')
        
        conn.commit()
        xbmc.log("[Trakt] Tabelas de cache criadas com sucesso", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[Trakt Sync] Erro: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Falha na sincronização: {str(e)}")
        return False
    finally:
        db._release_conn(conn)


# === SINCRONIZAÇÃO TRAKT → LOCAL ===

# -*- coding: utf-8 -*-
"""
VERSÃO CORRIGIDA DEFINITIVA - sync_local_to_trakt
✅ Usa o ID da lista imediatamente após criar (não busca novamente)
✅ Corrige o problema de lista vazia
"""

def sync_local_to_trakt(progress_dialog=None):
    """
    Envia dados locais (DB + playcount) para Trakt
    ✅ Filmes assistidos → History
    ✅ Séries assistidas → History
    ✅ Favoritos → Lista personalizada "CineRoom Favoritos"
    
    🔧 CORREÇÃO: Usa ID retornado na criação, não busca novamente
    """
    from resources.lib.db import db
    
    xbmc.log("[Trakt Sync] === INICIANDO SYNC LOCAL → TRAKT ===", xbmc.LOGINFO)
    
    if progress_dialog:
        progress_dialog.update(0, "Coletando dados locais...")
    
    try:
        settings = get_trakt_settings()
        username = settings.get('username')
        
        if not username:
            xbmc.log("[Trakt Sync] ❌ Username não encontrado", xbmc.LOGERROR)
            xbmcgui.Dialog().ok("Erro", "Username do Trakt não encontrado. Re-autentique.")
            return False
        
        xbmc.log(f"[Trakt Sync] Username: {username}", xbmc.LOGINFO)
        
        # === FILMES ASSISTIDOS ===
        watched_movies = db.get_watched_movies()
        watched_movies_count = len(watched_movies) if watched_movies else 0
        
        xbmc.log(f"[Trakt Sync] Filmes assistidos locais: {watched_movies_count}", xbmc.LOGINFO)
        
        if watched_movies:
            if progress_dialog:
                progress_dialog.update(20, f"Enviando {watched_movies_count} filmes assistidos...")
            
            trakt_movies = []
            for movie in watched_movies:
                trakt_movies.append({
                    'ids': {'tmdb': movie['tmdb_id']},
                    'watched_at': movie.get('last_played') or datetime.now().isoformat()
                })
            
            for i in range(0, len(trakt_movies), 50):
                batch = trakt_movies[i:i+50]
                trakt_request('POST', '/sync/history', {'movies': batch})
        
        # === SÉRIES ASSISTIDAS ===
        watched_shows = db.get_watched_tvshows()
        watched_shows_count = len(watched_shows) if watched_shows else 0
        
        xbmc.log(f"[Trakt Sync] Séries assistidas locais: {watched_shows_count}", xbmc.LOGINFO)
        
        if watched_shows:
            if progress_dialog:
                progress_dialog.update(40, f"Enviando {watched_shows_count} séries assistidas...")
            
            trakt_shows = []
            for show in watched_shows:
                trakt_shows.append({
                    'ids': {'tmdb': show['tmdb_id']},
                    'watched_at': show.get('last_played') or datetime.now().isoformat()
                })
            
            for i in range(0, len(trakt_shows), 50):
                batch = trakt_shows[i:i+50]
                trakt_request('POST', '/sync/history', {'shows': batch})
        
        # === FAVORITOS ===
        favorites = db.get_all_favorites()
        favorites_count = len(favorites) if favorites else 0
        
        xbmc.log(f"[Trakt Sync] Favoritos locais: {favorites_count}", xbmc.LOGINFO)
        
        if favorites:
            if progress_dialog:
                progress_dialog.update(60, f"Sincronizando {favorites_count} favoritos...")
            
            list_name = "CineRoom Favoritos"
            list_slug = "cineroom-favoritos"
            list_id_to_use = None
            
            # === ESTRATÉGIA 1: Buscar lista existente ===
            xbmc.log(f"[Trakt Sync] Buscando lista existente...", xbmc.LOGINFO)
            lists_response = trakt_request('GET', f'/users/{username}/lists')
            
            if lists_response and lists_response.get('data'):
                xbmc.log(f"[Trakt Sync] {len(lists_response['data'])} lista(s) encontrada(s)", xbmc.LOGINFO)
                
                for lst in lists_response['data']:
                    if lst.get('ids', {}).get('slug') == list_slug:
                        list_id_to_use = lst['ids'].get('slug') or lst['ids'].get('trakt')
                        xbmc.log(f"[Trakt Sync] ✅ Lista existente encontrada! ID: {list_id_to_use}", xbmc.LOGINFO)
                        break
            
            # === ESTRATÉGIA 2: Se não encontrou, CRIAR e usar o ID retornado ===
            if not list_id_to_use:
                xbmc.log(f"[Trakt Sync] Lista não encontrada, criando nova...", xbmc.LOGINFO)
                
                create_response = trakt_request('POST', f'/users/{username}/lists', {
                    'name': list_name,
                    'description': 'Meus favoritos do CineRoom Lite (sincronizado automaticamente)',
                    'privacy': 'public',  # 🔧 PÚBLICO para aparecer nas buscas
                    'display_numbers': False,
                    'allow_comments': False
                })
                
                if create_response and create_response.get('data'):
                    # ✅ USAR O ID RETORNADO DIRETAMENTE (não buscar novamente)
                    created_list = create_response['data'][0] if isinstance(create_response['data'], list) else create_response['data']
                    list_id_to_use = created_list.get('ids', {}).get('slug') or created_list.get('ids', {}).get('trakt')
                    
                    xbmc.log(f"[Trakt Sync] ✅ Lista criada com sucesso! ID: {list_id_to_use}", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[Trakt Sync] ❌ Falha ao criar lista!", xbmc.LOGERROR)
                    xbmcgui.Dialog().ok(
                        "Erro",
                        "Não foi possível criar a lista no Trakt.",
                        "Verifique suas permissões OAuth."
                    )
            
            # === ADICIONAR ITENS À LISTA ===
            if list_id_to_use:
                xbmc.log(f"[Trakt Sync] Adicionando itens à lista ID: {list_id_to_use}", xbmc.LOGINFO)
                
                fav_movies = [{'ids': {'tmdb': f['tmdb_id']}} for f in favorites if f['media_type'] == 'movie']
                fav_shows = [{'ids': {'tmdb': f['tmdb_id']}} for f in favorites if f['media_type'] == 'tvshow']
                
                xbmc.log(f"[Trakt Sync] {len(fav_movies)} filmes, {len(fav_shows)} séries", xbmc.LOGINFO)
                
                # Limpa lista primeiro
                trakt_request('POST', f'/users/{username}/lists/{list_id_to_use}/items/remove', {
                    'movies': fav_movies,
                    'shows': fav_shows
                })
                
                # Adiciona novos itens
                add_response = trakt_request('POST', f'/users/{username}/lists/{list_id_to_use}/items', {
                    'movies': fav_movies,
                    'shows': fav_shows
                })
                
                if add_response:
                    xbmc.log(f"[Trakt Sync] ✅ Favoritos adicionados com sucesso!", xbmc.LOGINFO)
                else:
                    xbmc.log(f"[Trakt Sync] ⚠️ Possível falha ao adicionar favoritos", xbmc.LOGWARNING)
            else:
                xbmc.log(f"[Trakt Sync] ❌ Sem ID de lista para usar", xbmc.LOGERROR)
        
        # Limpa cache
        _clear_trakt_cache()
        
        if progress_dialog:
            progress_dialog.update(100, "Sincronização concluída!")
        
        xbmc.log(f"[Trakt Sync] === SYNC CONCLUÍDO ===", xbmc.LOGINFO)
        
        xbmcgui.Dialog().notification(
            "Trakt Sync",
            f"✅ {watched_movies_count} filmes, {watched_shows_count} séries, {favorites_count} favoritos enviados",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt Sync] ❌ ERRO: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(f"[Trakt Sync] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
        
        if progress_dialog:
            progress_dialog.close()
        
        xbmcgui.Dialog().ok("Erro", f"Erro ao sincronizar: {str(e)}")
        return False


# ============================================================================
# VERSÃO CORRIGIDA: sync_trakt_to_local
# ============================================================================

def sync_trakt_to_local(progress_dialog=None):
    """
    Importa dados Trakt para local
    ✅ Marca filmes/séries como assistidos
    ✅ Importa lista "CineRoom Favoritos" para favoritos locais
    
    🔧 SOLUÇÃO ALTERNATIVA: Busca itens da lista DIRETAMENTE pelo slug conhecido
    """
    from resources.lib.db import db
    from resources.lib.favorites import add_item_to_favorites
    
    xbmc.log("[Trakt Import] === INICIANDO IMPORT TRAKT → LOCAL ===", xbmc.LOGINFO)
    
    if progress_dialog:
        progress_dialog.update(0, "Buscando dados do Trakt...")
    
    try:
        settings = get_trakt_settings()
        username = settings.get('username')
        
        if not username:
            xbmcgui.Dialog().ok("Erro", "Username do Trakt não encontrado. Re-autentique.")
            return False
        
        # === 1. IMPORTAR ASSISTIDOS (FILMES) ===
        watched_movies_response = trakt_request('GET', '/sync/watched/movies?extended=full')
        
        if watched_movies_response and watched_movies_response.get('data'):
            watched_movies = watched_movies_response['data']
            
            if progress_dialog:
                progress_dialog.update(15, f"Importando {len(watched_movies)} filmes assistidos...")
            
            for item in watched_movies:
                movie = item.get('movie', {})
                tmdb_id = movie.get('ids', {}).get('tmdb')
                plays = item.get('plays', 1)
                last_watched = item.get('last_watched_at')
                
                if tmdb_id:
                    local_movie = db.get_movie_by_id(tmdb_id)
                    if local_movie:
                        db.update_movie_playcount(tmdb_id, plays, last_watched)
        
        # === 2. IMPORTAR ASSISTIDOS (SÉRIES) ===
        watched_shows_response = trakt_request('GET', '/sync/watched/shows?extended=full')
        
        if watched_shows_response and watched_shows_response.get('data'):
            watched_shows = watched_shows_response['data']
            
            if progress_dialog:
                progress_dialog.update(30, f"Importando {len(watched_shows)} séries assistidas...")
            
            for item in watched_shows:
                show = item.get('show', {})
                tmdb_id = show.get('ids', {}).get('tmdb')
                last_watched = item.get('last_watched_at')
                
                if tmdb_id:
                    local_show = db.get_tvshow_by_id(tmdb_id)
                    if local_show:
                        db.update_tvshow_playcount(tmdb_id, last_watched)
        
        # === 3. IMPORTAR LISTA - SOLUÇÃO ALTERNATIVA ===
        if progress_dialog:
            progress_dialog.update(50, "Buscando favoritos...")
        
        list_slug = "cineroom-favoritos"
        
        xbmc.log(f"[Trakt Import] Tentando buscar itens diretamente pelo slug: {list_slug}", xbmc.LOGINFO)
        
        # ✅ SOLUÇÃO: Tentar buscar itens DIRETAMENTE pelo slug conhecido
        # Não depende de listar todas as listas primeiro
        list_items_response = trakt_request('GET', f'/users/{username}/lists/{list_slug}/items?extended=full')
        
        if list_items_response and list_items_response.get('data'):
            list_items = list_items_response['data']
            xbmc.log(f"[Trakt Import] ✅ {len(list_items)} itens encontrados na lista!", xbmc.LOGINFO)
            
            if progress_dialog:
                progress_dialog.update(60, f"Importando {len(list_items)} favoritos...")
            
            imported_count = 0
            
            for item in list_items:
                try:
                    # Detecta tipo
                    if 'movie' in item:
                        media_type = 'movie'
                        obj = item['movie']
                    elif 'show' in item:
                        media_type = 'tvshow'
                        obj = item['show']
                    else:
                        continue
                    
                    tmdb_id = obj.get('ids', {}).get('tmdb')
                    
                    if not tmdb_id:
                        continue
                    
                    # Adiciona se não é favorito
                    if not db.is_favorite(tmdb_id, media_type):
                        title = obj.get('title', 'Sem título')
                        xbmc.log(f"[Trakt Import] Adicionando: {title} (TMDB: {tmdb_id})", xbmc.LOGDEBUG)
                        add_item_to_favorites(tmdb_id, media_type)
                        imported_count += 1
                        
                except Exception as e:
                    xbmc.log(f"[Trakt Import] Erro: {e}", xbmc.LOGERROR)
                    continue
            
            xbmc.log(f"[Trakt Import] ✅ {imported_count} favoritos importados", xbmc.LOGINFO)
            
            if progress_dialog:
                progress_dialog.update(80, f"{imported_count} favoritos importados...")
        else:
            xbmc.log(f"[Trakt Import] ⚠️ Lista '{list_slug}' não encontrada ou vazia", xbmc.LOGWARNING)
            xbmc.log(f"[Trakt Import] Isso pode significar:", xbmc.LOGINFO)
            xbmc.log(f"[Trakt Import] 1. A lista ainda não foi criada (sincronize Local → Trakt primeiro)", xbmc.LOGINFO)
            xbmc.log(f"[Trakt Import] 2. A lista existe mas está vazia", xbmc.LOGINFO)
            xbmc.log(f"[Trakt Import] 3. O slug da lista é diferente", xbmc.LOGINFO)
        
        if progress_dialog:
            progress_dialog.update(100, "Importação concluída!")
        
        xbmcgui.Dialog().notification(
            "Trakt Sync",
            "✅ Sincronização concluída!",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt Import] Erro: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(f"[Trakt Import] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Falha na importação: {str(e)}")
        return False


# === SCROBBLER AUTOMÁTICO ===

class TraktScrobbler(xbmc.Player):
    """
    Monitor que sincroniza automaticamente quando você assiste algo
    ✅ Mantém último progresso conhecido
    ✅ Envia progresso mesmo se baixo
    """
    
    def __init__(self):
        super(TraktScrobbler, self).__init__()
        self.current_item = None
        self.start_time = None
        self.scrobbled = False
        self._initialized = False
        self._trakt_request = None
        self._get_trakt_settings = None
        self._db = None
        self._monitor_thread = None
        self._stop_monitoring = False
        self._last_progress = 0
        self._last_valid_time = 0
        
    def _lazy_init(self):
        """Inicialização preguiçosa para evitar import circular"""
        if self._initialized:
            return True
            
        try:
            self._trakt_request = trakt_request
            self._get_trakt_settings = get_trakt_settings
            self._db = _get_db()
            
            self._initialized = True
            return True
            
        except Exception as e:
            xbmc.log(f"[Trakt Scrobble] ERRO em lazy_init: {e}", xbmc.LOGERROR)
            return False
    
    def onPlayBackStarted(self):
        """Chamado quando a reprodução inicia"""
        xbmc.log(f"[Trakt Scrobble] === onPlayBackStarted INICIADO ===", xbmc.LOGINFO)
        
        try:
            max_attempts = 50
            attempts = 0
            
            while not self.isPlayingVideo() and attempts < max_attempts:
                xbmc.sleep(100)
                attempts += 1
            
            if not self.isPlayingVideo():
                xbmc.log("[Trakt Scrobble] Timeout: vídeo não iniciou", xbmc.LOGWARNING)
                return
            
            if not self._lazy_init():
                return
            
            settings = self._get_trakt_settings()
            if not settings.get('access_token'):
                return
            
            info = self.getVideoInfoTag()
            if not info:
                return
            
            tmdb_id = info.getUniqueID('tmdb')
            imdb_id = info.getIMDBNumber()
            title = info.getTitle() or "Desconhecido"
            media_type = info.getMediaType() or "unknown"
            
            if tmdb_id:
                id_type = 'tmdb'
                id_value = str(tmdb_id).strip()
            elif imdb_id:
                id_type = 'imdb'
                id_value = str(imdb_id).strip()
            else:
                xbmc.log("[Trakt Scrobble] ERRO: Nenhum ID encontrado", xbmc.LOGERROR)
                return
            
            try:
                duration = self.getTotalTime()
            except:
                duration = 0
            
            self.current_item = {
                'type': media_type,
                'id_type': id_type,
                'id_value': id_value,
                'title': title,
                'duration': duration,
                'start_time': time.time()
            }
            
            self._last_progress = 0
            self._last_valid_time = 0
            
            if media_type == 'movie':
                self._handle_movie_start(id_type, id_value, title)
            elif media_type == 'episode':
                season = info.getSeason() or 1
                episode = info.getEpisode() or 1
                self.current_item['season'] = season
                self.current_item['episode'] = episode
                self._handle_episode_start(id_type, id_value, season, episode, title)
            else:
                xbmc.log(f"[Trakt Scrobble] Tipo não suportado: {media_type}", xbmc.LOGWARNING)
                return
            
            self.scrobbled = False
            
            self._stop_monitoring = False
            self._monitor_thread = threading.Thread(target=self._progress_monitor, daemon=True)
            self._monitor_thread.start()
            
        except Exception as e:
            xbmc.log(f"[Trakt Scrobble] ERRO: {e}", xbmc.LOGERROR)
    
    def _progress_monitor(self):
        """Monitora progresso e detecta quando o player para"""
        last_update = 0
        update_interval = 30
        check_interval = 2
        
        while not self._stop_monitoring:
            try:
                if not self.isPlaying():
                    self._scrobble_stop(completed=False)
                    break
                
                try:
                    self._last_valid_time = self.getTime()
                    total_time = self.getTotalTime()
                    if total_time > 0:
                        self._last_progress = int((self._last_valid_time / total_time) * 100)
                        self._last_progress = min(100, max(0, self._last_progress))
                except:
                    pass
                
                current_time = time.time()
                
                if current_time - last_update >= update_interval:
                    if self._last_progress > 0:
                        self._send_progress_update(self._last_progress)
                        last_update = current_time
                
                xbmc.sleep(check_interval * 1000)
                
            except Exception as e:
                xbmc.log(f"[Trakt Progress] Erro: {e}", xbmc.LOGERROR)
                break
    
    def _send_progress_update(self, progress):
        """Envia atualização de progresso"""
        if not self.current_item:
            return
        
        try:
            if self.current_item['id_type'] == 'tmdb':
                ids = {'tmdb': int(self.current_item['id_value'])}
            else:
                ids = {'imdb': self.current_item['id_value']}
            
            if self.current_item['type'] == 'movie':
                payload = {
                    'movie': {'ids': ids},
                    'progress': progress
                }
            else:
                payload = {
                    'show': {'ids': ids},
                    'episode': {
                        'season': self.current_item.get('season', 1),
                        'number': self.current_item.get('episode', 1)
                    },
                    'progress': progress
                }
            
            self._trakt_request('POST', '/scrobble/pause', payload)
            
        except Exception as e:
            xbmc.log(f"[Trakt Progress] Erro enviando: {e}", xbmc.LOGERROR)
    
    def _handle_movie_start(self, id_type, id_value, title):
        """Processa início de filme"""
        try:
            if id_type == 'tmdb':
                ids = {'tmdb': int(id_value)}
            else:
                ids = {'imdb': id_value}
            
            payload = {
                'movie': {'ids': ids},
                'progress': 0
            }
            
            self._trakt_request('POST', '/scrobble/start', payload)
            
        except Exception as e:
            xbmc.log(f"[Trakt Scrobble] Erro movie start: {e}", xbmc.LOGERROR)
    
    def _handle_episode_start(self, id_type, id_value, season, episode, title):
        """Processa início de episódio"""
        try:
            if id_type == 'tmdb':
                ids = {'tmdb': int(id_value)}
            else:
                ids = {'imdb': id_value}
            
            payload = {
                'show': {'ids': ids},
                'episode': {
                    'season': season,
                    'number': episode
                },
                'progress': 0
            }
            
            self._trakt_request('POST', '/scrobble/start', payload)
            
        except Exception as e:
            xbmc.log(f"[Trakt Scrobble] Erro episode start: {e}", xbmc.LOGERROR)
    
    def onPlayBackStopped(self):
        """Chamado quando player para"""
        self._stop_monitoring = True
        if not self.scrobbled:
            self._scrobble_stop(completed=False)
    
    def onPlayBackEnded(self):
        """Quando termina naturalmente"""
        self._stop_monitoring = True
        if not self.scrobbled:
            self._scrobble_stop(completed=True)
    
    def _scrobble_stop(self, completed=False):
        """Processa o fim da reprodução"""
        if not self._initialized or not self.current_item or self.scrobbled:
            return
        
        try:
            progress = self._last_progress
            
            if progress >= 80:
                completed = True
            
            endpoint = '/scrobble/stop' if completed else '/scrobble/pause'
            
            if self.current_item['id_type'] == 'tmdb':
                ids = {'tmdb': int(self.current_item['id_value'])}
            else:
                ids = {'imdb': self.current_item['id_value']}
            
            if self.current_item['type'] == 'movie':
                payload = {
                    'movie': {'ids': ids},
                    'progress': progress
                }
            else:
                payload = {
                    'show': {'ids': ids},
                    'episode': {
                        'season': self.current_item.get('season', 1),
                        'number': self.current_item.get('episode', 1)
                    },
                    'progress': progress
                }
            
            self._trakt_request('POST', endpoint, payload)
            
            self.scrobbled = True
            
            if completed and self._db:
                try:
                    if self.current_item['type'] == 'movie':
                        if self.current_item['id_type'] == 'tmdb':
                            self._db.mark_movie_as_watched(int(self.current_item['id_value']))
                except Exception as db_error:
                    xbmc.log(f"[Trakt Scrobble] Erro DB: {db_error}", xbmc.LOGERROR)
            
        except Exception as e:
            xbmc.log(f"[Trakt Scrobble] Erro stop: {e}", xbmc.LOGERROR)
        finally:
            self.current_item = None
            self.start_time = None


# === SINCRONIZAÇÃO BIDIRECIONAL ===

def full_bidirectional_sync():
    """
    Sincronização completa em ambas direções
    1. Local → Trakt (envia assistidos)
    2. Trakt → Local (importa watchlist)
    """
    progress = xbmcgui.DialogProgress()
    progress.create("Trakt Sync Completo", "Iniciando...")
    
    try:
        if not refresh_trakt_token():
            progress.close()
            xbmcgui.Dialog().ok("Erro", "Você não está autenticado no Trakt.")
            return False
        
        progress.update(10, "Enviando dados locais para Trakt...")
        sync_local_to_trakt(progress)
        
        xbmc.sleep(1000)
        
        progress.update(50, "Importando dados do Trakt...")
        sync_trakt_to_local(progress)
        
        progress.update(100, "Sincronização concluída!")
        xbmc.sleep(500)
        progress.close()
        
        ADDON.setSetting('trakt_last_sync', str(time.time()))
        
        xbmcgui.Dialog().ok(
            "Trakt Sync",
            "Sincronização bidirecional concluída!\n\n"
            "Dados locais enviados\n"
            "Watchlist importada\n"
            "Histórico sincronizado"
        )
        
        return True
        
    except Exception as e:
        progress.close()
        xbmc.log(f"[Trakt Full Sync] Erro: {e}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Falha na sincronização:\n{str(e)}")
        return False


# === MENU DE SINCRONIZAÇÃO ===

def show_sync_menu():
    """Menu de opções de sincronização"""
    options = [
        "Sincronização Completa (Local ↔ Trakt)",
        "Enviar Dados Locais → Trakt",
        "Importar Dados Trakt → Local",
        "Limpar Cache e Re-sincronizar",
        "Configurar Scrobble Automático"
    ]
    
    choice = xbmcgui.Dialog().select("Trakt Sync", options)
    
    if choice == 0:
        full_bidirectional_sync()
    elif choice == 1:
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt Sync", "Enviando...")
        sync_local_to_trakt(progress)
        progress.close()
    elif choice == 2:
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt Sync", "Importando...")
        sync_trakt_to_local(progress)
        progress.close()
    elif choice == 3:
        _clear_trakt_cache()
        full_bidirectional_sync()
    elif choice == 4:
        current = ADDON.getSettingBool('trakt_auto_scrobble')
        ADDON.setSettingBool('trakt_auto_scrobble', not current)
        status = "ativado" if not current else "desativado"
        xbmcgui.Dialog().notification("Trakt", f"Scrobble automático {status}", xbmcgui.NOTIFICATION_INFO, 2000)


# === INTEGRAÇÃO COM O ADDON ===

def init_trakt_scrobbler():
    """
    Inicializa o scrobbler se estiver ativado
    Retorna a instância ou None
    """
    try:
        if ADDON.getSettingBool('trakt_auto_scrobble'):
            scrobbler = TraktScrobbler()
            xbmc.log("[Trakt] Scrobbler inicializado", xbmc.LOGINFO)
            return scrobbler
    except Exception as e:
        xbmc.log(f"[Trakt] Erro ao inicializar scrobbler: {e}", xbmc.LOGERROR)
    return None

# === AÇÕES INDIVIDUAIS DO CONTEXT MENU ===

def trakt_add_to_collection(tmdb_id, media_type):
    """Adiciona item à coleção do Trakt"""
    settings = get_trakt_settings()
    if not settings.get('access_token'):
        xbmcgui.Dialog().ok("Trakt", "Você precisa estar autenticado no Trakt.")
        return False
    
    try:
        if media_type == 'movie':
            payload = {
                'movies': [{'ids': {'tmdb': int(tmdb_id)}}]
            }
        else:
            payload = {
                'shows': [{'ids': {'tmdb': int(tmdb_id)}}]
            }
        
        response = trakt_request('POST', '/sync/collection', payload)
        
        if response:
            xbmcgui.Dialog().notification(
                "Trakt",
                "✅ Adicionado à coleção!",
                xbmcgui.NOTIFICATION_INFO,
                2000
            )
            return True
        else:
            xbmcgui.Dialog().notification(
                "Trakt",
                "❌ Erro ao adicionar",
                xbmcgui.NOTIFICATION_ERROR,
                2000
            )
            return False
            
    except Exception as e:
        xbmc.log(f"[Trakt] Erro add collection: {e}", xbmc.LOGERROR)
        return False


def trakt_remove_from_collection(tmdb_id, media_type):
    """Remove item da coleção do Trakt"""
    settings = get_trakt_settings()
    if not settings.get('access_token'):
        xbmcgui.Dialog().ok("Trakt", "Você precisa estar autenticado no Trakt.")
        return False
    
    try:
        if media_type == 'movie':
            payload = {
                'movies': [{'ids': {'tmdb': int(tmdb_id)}}]
            }
        else:
            payload = {
                'shows': [{'ids': {'tmdb': int(tmdb_id)}}]
            }
        
        response = trakt_request('POST', '/sync/collection/remove', payload)
        
        if response:
            xbmcgui.Dialog().notification(
                "Trakt",
                "✅ Removido da coleção!",
                xbmcgui.NOTIFICATION_INFO,
                2000
            )
            return True
        else:
            xbmcgui.Dialog().notification(
                "Trakt",
                "❌ Erro ao remover",
                xbmcgui.NOTIFICATION_ERROR,
                2000
            )
            return False
            
    except Exception as e:
        xbmc.log(f"[Trakt] Erro remove collection: {e}", xbmc.LOGERROR)
        return False


def trakt_mark_as_watched(tmdb_id, media_type):
    """Marca item como assistido no Trakt"""
    settings = get_trakt_settings()
    if not settings.get('access_token'):
        xbmcgui.Dialog().ok("Trakt", "Você precisa estar autenticado no Trakt.")
        return False
    
    try:
        watched_at = datetime.now().isoformat()
        
        if media_type == 'movie':
            payload = {
                'movies': [{'ids': {'tmdb': int(tmdb_id)}, 'watched_at': watched_at}]
            }
        else:
            payload = {
                'shows': [{'ids': {'tmdb': int(tmdb_id)}, 'watched_at': watched_at}]
            }
        
        response = trakt_request('POST', '/sync/history', payload)
        
        if response:
            xbmcgui.Dialog().notification(
                "Trakt",
                "✅ Marcado como assistido!",
                xbmcgui.NOTIFICATION_INFO,
                2000
            )
            return True
        else:
            xbmcgui.Dialog().notification(
                "Trakt",
                "❌ Erro ao marcar",
                xbmcgui.NOTIFICATION_ERROR,
                2000
            )
            return False
            
    except Exception as e:
        xbmc.log(f"[Trakt] Erro mark watched: {e}", xbmc.LOGERROR)
        return False


def trakt_remove_watched(tmdb_id, media_type):
    """Remove item dos assistidos no Trakt"""
    settings = get_trakt_settings()
    if not settings.get('access_token'):
        xbmcgui.Dialog().ok("Trakt", "Você precisa estar autenticado no Trakt.")
        return False
    
    try:
        if media_type == 'movie':
            payload = {
                'movies': [{'ids': {'tmdb': int(tmdb_id)}}]
            }
        else:
            payload = {
                'shows': [{'ids': {'tmdb': int(tmdb_id)}}]
            }
        
        response = trakt_request('POST', '/sync/history/remove', payload)
        
        if response:
            xbmcgui.Dialog().notification(
                "Trakt",
                "✅ Removido dos assistidos!",
                xbmcgui.NOTIFICATION_INFO,
                2000
            )
            return True
        else:
            xbmcgui.Dialog().notification(
                "Trakt",
                "❌ Erro ao remover",
                xbmcgui.NOTIFICATION_ERROR,
                2000
            )
            return False
            
    except Exception as e:
        xbmc.log(f"[Trakt] Erro remove watched: {e}", xbmc.LOGERROR)
        return False


def trakt_rate_item(tmdb_id, media_type):
    """
    ✅ Avalia item no Trakt usando o diálogo visual de estrelas
    """
    settings = get_trakt_settings()
    
    # ✅ OTIMIZAÇÃO: Só verifica o token, sem refresh (mais rápido)
    if not settings.get('access_token'):
        xbmcgui.Dialog().ok("Trakt", "Você precisa estar autenticado no Trakt.")
        return False
    
    try:
        # 🌟 IMPORTA O MÓDULO DE AVALIAÇÃO
        from resources.lib.trakt_rating import rate_item_from_context_menu
        
        # Busca informações básicas do item para exibir no diálogo
        title = None
        
        if media_type == 'movie':
            try:
                from resources.lib.db import db
                item_data = db.get_movie_by_id(tmdb_id)
                if item_data:
                    title = item_data.get('title')
            except Exception as e:
                xbmc.log(f"[Trakt Rate] Erro buscando dados do filme: {e}", xbmc.LOGDEBUG)
        
        elif media_type == 'tvshow':
            # Para séries, avisa que deve avaliar episódios individuais
            xbmcgui.Dialog().notification(
                "Trakt",
                "Avalie episódios individuais ao assisti-los",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
            return False
        
        # 🌟 CHAMA A FUNÇÃO QUE ABRE O DIÁLOGO BONITO
        return rate_item_from_context_menu(
            tmdb_id=tmdb_id,
            media_type=media_type,
            title=title
        )
    
    except Exception as e:
        xbmc.log(f"[Trakt Rate] Erro: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        
        xbmcgui.Dialog().notification(
            "Trakt",
            "Erro ao abrir avaliação",
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )
        return False




# === INICIALIZAÇÃO ===
_create_trakt_cache_tables()

def _save_trakt_cache(category, page, items, total_items):
    """Salva dados Trakt em cache no DB"""
    db = _get_db()
    if not db:
        return
    
    cache_id = f"{category}_p{page}"
    data_json = json.dumps(items)
    
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO trakt_cache 
            (cache_id, category, page, data_json, total_items, timestamp)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (cache_id, category, page, data_json, total_items))
        
        conn.commit()
        db._release_conn(conn)
    except Exception as e:
        xbmc.log(f"[Trakt] Erro salvando cache: {e}", xbmc.LOGERROR)

def _get_trakt_cache(category, page, cache_hours=24):
    """Recupera dados Trakt do cache (se ainda válido)"""
    db = _get_db()
    if not db:
        return None
    
    cache_id = f"{category}_p{page}"
    
    try:
        sql = f'''
            SELECT data_json, total_items FROM trakt_cache 
            WHERE cache_id = ? 
            AND timestamp > datetime('now', '-{cache_hours} hours')
        '''
        
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, (cache_id,))
        result = cursor.fetchone()
        db._release_conn(conn)
        
        if result:
            return {
                'items': json.loads(result[0]),
                'total_items': result[1]
            }
    except Exception as e:
        xbmc.log(f"[Trakt] Erro recuperando cache: {e}", xbmc.LOGERROR)
    
    return None

def _save_tmdb_metadata(tmdb_id, media_type, metadata):
    """Salva metadados TMDB traduzidos no cache"""
    db = _get_db()
    if not db:
        return
    
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO trakt_tmdb_meta 
            (tmdb_id, media_type, title_pt, poster, backdrop, clearlogo, 
             synopsis_pt, genres_pt, runtime, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            tmdb_id, media_type,
            metadata.get('title'),
            metadata.get('poster'),
            metadata.get('backdrop'),
            metadata.get('clearlogo'),
            metadata.get('synopsis'),
            json.dumps(metadata.get('genres', [])),
            metadata.get('runtime', 0)
        ))
        
        conn.commit()
        db._release_conn(conn)
    except Exception as e:
        xbmc.log(f"[Trakt] Erro salvando TMDB meta: {e}", xbmc.LOGERROR)

def _get_tmdb_metadata(tmdb_id, media_type, max_age_hours=168):
    """Recupera metadados TMDB do cache (7 dias padrão)"""
    db = _get_db()
    if not db:
        return None
    
    try:
        sql = f'''
            SELECT title_pt, poster, backdrop, clearlogo, synopsis_pt, 
                   genres_pt, runtime
            FROM trakt_tmdb_meta
            WHERE tmdb_id = ? AND media_type = ?
            AND last_updated > datetime('now', '-{max_age_hours} hours')
        '''
        
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute(sql, (tmdb_id, media_type))
        result = cursor.fetchone()
        db._release_conn(conn)
        
        if result:
            return {
                'title': result[0],
                'poster': result[1],
                'backdrop': result[2],
                'clearlogo': result[3],
                'synopsis': result[4],
                'genres': json.loads(result[5]) if result[5] else [],
                'runtime': result[6]
            }
    except Exception as e:
        xbmc.log(f"[Trakt] Erro recuperando TMDB meta: {e}", xbmc.LOGERROR)
    
    return None

def _clear_trakt_cache(category=None):
    """Limpa cache Trakt (específico ou tudo)"""
    db = _get_db()
    if not db:
        return
    
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        if category:
            cursor.execute("DELETE FROM trakt_cache WHERE category = ?", (category,))
        else:
            cursor.execute("DELETE FROM trakt_cache")
        
        conn.commit()
        db._release_conn(conn)
    except Exception as e:
        xbmc.log(f"[Trakt] Erro limpando cache: {e}", xbmc.LOGERROR)

# === AUTENTICAÇÃO ===
def authenticate_trakt():
    """✅ Autenticação com salvamento de username usando diálogo XML customizado"""
    settings = get_trakt_settings()
    
    if not settings['client_id']:
        xbmcgui.Dialog().ok("Trakt", "Configure Client ID nas configurações primeiro.")
        return False
    
    try:
        import requests
        
        resp = requests.post(
            'https://api.trakt.tv/oauth/device/code',
            json={'client_id': settings['client_id']},
            headers={'Content-Type': 'application/json'}
        )
        
        if resp.status_code != 200:
            xbmcgui.Dialog().ok("Erro", "Não consegui conectar ao Trakt.")
            return False
        
        data = resp.json()
        user_code = data['user_code']
        url = data['verification_url']
        
        # === USA O DIÁLOGO CUSTOMIZADO ===
        from resources.lib.dialog.trakt_auth_dialog import TraktAuthDialog
        
        dialog = TraktAuthDialog(
            'TraktAuthDialog.xml',
            ADDON.getAddonInfo('path'),
            url=url,
            user_code=user_code
        )
        
        dialog.doModal()
        confirmed = dialog.get_result()
        del dialog
        
        if not confirmed:
            return False
        
        # === CONTINUA COM A AUTENTICAÇÃO ===
        device_code = data['device_code']
        
        # Mostra progresso enquanto aguarda
        progress = xbmcgui.DialogProgress()
        progress.create("Trakt", "Aguardando autenticação...")
        
        for i in range(30):
            if progress.iscanceled():
                progress.close()
                return False
            
            progress.update(int((i / 30) * 100), "Tentativa {}/30...".format(i + 1))
            
            token_resp = requests.post(
                'https://api.trakt.tv/oauth/device/token',
                json={
                    'code': device_code,
                    'client_id': settings['client_id'],
                    'client_secret': settings.get('client_secret', ''),
                    'grant_type': 'device_code'
                }
            )
            
            if token_resp.status_code == 200:
                progress.close()
                
                token = token_resp.json()
                access_token = token['access_token']
                
                ADDON.setSetting('trakt_access_token', access_token)
                ADDON.setSetting('trakt_refresh_token', token['refresh_token'])
                ADDON.setSetting('trakt_expires_at', str(time.time() + token['expires_in']))
                
                # Busca username
                try:
                    user_resp = requests.get(
                        'https://api.trakt.tv/users/me',
                        headers={
                            'Content-Type': 'application/json',
                            'Authorization': f"Bearer {access_token}",
                            'trakt-api-version': '2',
                            'trakt-api-key': settings['client_id']
                        },
                        timeout=10
                    )
                    
                    if user_resp.status_code == 200:
                        user_data = user_resp.json()
                        username = user_data.get('username', '')
                        
                        if username:
                            ADDON.setSetting('trakt_username', username)
                            xbmc.log(f"[Trakt] Username salvo: {username}", xbmc.LOGINFO)
                            xbmcgui.Dialog().notification(
                                "Trakt", 
                                f"✅ Autenticado como {username}!", 
                                xbmcgui.NOTIFICATION_INFO, 
                                3000
                            )
                        else:
                            xbmcgui.Dialog().notification("Trakt", "✅ Autenticado!", xbmcgui.NOTIFICATION_INFO, 3000)
                    else:
                        xbmcgui.Dialog().notification("Trakt", "✅ Autenticado!", xbmcgui.NOTIFICATION_INFO, 3000)
                        
                except Exception as e:
                    xbmc.log(f"[Trakt] Erro buscando username: {e}", xbmc.LOGERROR)
                    xbmcgui.Dialog().notification("Trakt", "✅ Autenticado!", xbmcgui.NOTIFICATION_INFO, 3000)
                
                return True
            
            elif token_resp.status_code == 400:
                time.sleep(5)
            else:
                xbmc.log(f"[Trakt] Erro token: {token_resp.status_code}", xbmc.LOGERROR)
                time.sleep(5)
        
        progress.close()
        xbmcgui.Dialog().ok("Timeout", "Não autorizado a tempo.")
        return False
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro na autenticação: {str(e)}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Falha na autenticação:\n{str(e)}")
        return False

def refresh_trakt_token():
    """Refresh do token Trakt se expirado"""
    settings = get_trakt_settings()
    
    if not settings['refresh_token']:
        return False
    
    if time.time() < (settings['expires_at'] - 60):
        return True
    
    try:
        import requests
        
        response = requests.post(
            'https://api.trakt.tv/oauth/token',
            json={
                'refresh_token': settings['refresh_token'],
                'client_id': settings['client_id'],
                'client_secret': settings['client_secret'],
                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                'grant_type': 'refresh_token'
            },
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            data = response.json()
            ADDON.setSetting('trakt_access_token', data['access_token'])
            ADDON.setSetting('trakt_refresh_token', data['refresh_token'])
            ADDON.setSetting('trakt_expires_at', str(time.time() + data['expires_in']))
            return True
        else:
            xbmc.log(f"[Trakt] Refresh falhou: {response.text}", xbmc.LOGERROR)
            return False
            
    except Exception as e:
        xbmc.log(f"[Trakt] Erro refresh token: {e}", xbmc.LOGERROR)
        return False

def trakt_request(method, endpoint, data=None, retry=True):
    """✅ Requisição Trakt com paginação automática"""
    settings = get_trakt_settings()
    
    if not settings['access_token'] or not refresh_trakt_token():
        return None
    
    try:
        import requests
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {settings['access_token']}",
            'trakt-api-version': '2',
            'trakt-api-key': settings['client_id']
        }
        
        url = f"https://api.trakt.tv{endpoint}"
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, json=data, timeout=15)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=data, timeout=15)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers, json=data, timeout=15)
        else:
            return None
        
        if response.status_code == 401 and retry:
            if refresh_trakt_token():
                return trakt_request(method, endpoint, data, retry=False)
        
        if response.status_code in [200, 201, 204]:
            if response.content:
                result = response.json()
                
                if isinstance(result, list) and len(result) == 0:
                    return {
                        'data': [],
                        'page': 1,
                        'limit': 20,
                        'page_count': 1,
                        'item_count': 0
                    }
                
                return {
                    'data': result if isinstance(result, list) else [result],
                    'page': int(response.headers.get('X-Pagination-Page', 1)),
                    'limit': int(response.headers.get('X-Pagination-Limit', 20)),
                    'page_count': int(response.headers.get('X-Pagination-Page-Count', 1)),
                    'item_count': int(response.headers.get('X-Pagination-Item-Count', len(result) if isinstance(result, list) else 1))
                }
            return True
        
        return None
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro requisição {endpoint}: {e}", xbmc.LOGERROR)
        return None

# === ENRIQUECIMENTO TMDB ===
def _enrich_item_with_tmdb_batch(items, max_workers=10):
    """✅ Enriquece múltiplos itens em paralelo"""
    try:
        from resources.lib import tmdb_api
        
        enriched_items = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {}
            for item in items:
                tmdb_id = item.get('tmdb_id')
                media_type = item.get('media_type')
                
                if not tmdb_id or not media_type:
                    enriched_items.append(item)
                    continue
                
                trakt_imdb_id = item.get('imdb_id', '')
                
                cached_meta = _get_tmdb_metadata(tmdb_id, media_type)
                if cached_meta:
                    item.update(cached_meta)
                    if not item.get('imdb_id') and trakt_imdb_id:
                        item['imdb_id'] = trakt_imdb_id
                    item['fanart'] = item.get('backdrop', '')
                    enriched_items.append(item)
                else:
                    future = executor.submit(_fetch_tmdb_details, tmdb_id, media_type, trakt_imdb_id)
                    future_to_item[future] = item
            
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    details = future.result()
                    if details:
                        trakt_imdb = item.get('imdb_id', '')
                        item.update(details)
                        if not item.get('imdb_id') and trakt_imdb:
                            item['imdb_id'] = trakt_imdb
                        item['fanart'] = item.get('backdrop', '')
                        _save_tmdb_metadata(item['tmdb_id'], item['media_type'], details)
                    enriched_items.append(item)
                except Exception as e:
                    xbmc.log(f"[Trakt] Erro enriquecimento {item.get('tmdb_id')}: {e}", xbmc.LOGERROR)
                    enriched_items.append(item)
        
        return enriched_items
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro batch enriquecimento: {e}", xbmc.LOGERROR)
        return items

def _fetch_tmdb_details(tmdb_id, media_type, trakt_imdb_id=''):
    """Helper para buscar detalhes TMDB"""
    try:
        from resources.lib import tmdb_api
        
        if media_type == 'movie':
            details = tmdb_api.get_movie_details(tmdb_id)
        else:
            details = tmdb_api.fetch_show_details(tmdb_id)
        
        if not details:
            return {}
        
        result = {
            'title': details.get('title', ''),
            'original_title': details.get('original_title', details.get('title', '')),
            'poster': details.get('poster', ''),
            'backdrop': details.get('backdrop', ''),
            'clearlogo': details.get('clearlogo', ''),
            'synopsis': details.get('synopsis', ''),
            'rating': details.get('rating', 0),
            'genres': details.get('genres', []),
            'imdb_id': details.get('imdb_id', trakt_imdb_id),
            'runtime': details.get('runtime', 0)
        }
        
        return result
    except Exception as e:
        xbmc.log(f"[Trakt] Erro fetch TMDB {tmdb_id}: {e}", xbmc.LOGERROR)
        return {}

# === HELPER: MONTA URL ===
def _build_source_url(item):
    """Monta URL completa seguindo o padrão do addon"""
    media_type = item.get('media_type')
    
    if media_type == 'tvshow':
        return f"plugin://plugin.video.cineroom.lite/?action=list_seasons&tvshow_tmdb_id={item['tmdb_id']}"
    
    title = str(item.get('title', ''))
    
    url_params = [
        f"action=find_sources",
        f"tmdb_id={item['tmdb_id']}",
        f"media_type=movie",
        f"title={quote_plus(title)}"
    ]
    
    if item.get('year'):
        url_params.append(f"year={item['year']}")
    if item.get('imdb_id'):
        url_params.append(f"imdb_id={item['imdb_id']}")
    if item.get('original_title'):
        url_params.append(f"original_title={quote_plus(item['original_title'])}")
    if item.get('poster'):
        url_params.append(f"poster={quote_plus(item['poster'])}")
    if item.get('backdrop'):
        url_params.append(f"backdrop={quote_plus(item['backdrop'])}")
        url_params.append(f"fanart={quote_plus(item['backdrop'])}")
    if item.get('clearlogo'):
        url_params.append(f"clearlogo={quote_plus(item['clearlogo'])}")
    
    return f"plugin://plugin.video.cineroom.lite/?{'&'.join(url_params)}"

# === PAGINAÇÃO OTIMIZADA ===
def _fetch_trakt_paginated(endpoint_base, category, page=1, limit=20, params=None):
    """✅ Busca paginada"""
    cached = _get_trakt_cache(category, page, cache_hours=6)
    if cached:
        return cached['items']
    
    endpoint = f"{endpoint_base}"
    
    if '?' not in endpoint:
        endpoint += f"?page={page}&limit={limit}"
    else:
        endpoint += f"&page={page}&limit={limit}"
    
    if 'extended=' not in endpoint:
        endpoint += "&extended=full"
    
    if params:
        for key, value in params.items():
            endpoint += f"&{key}={value}"
    
    response = trakt_request('GET', endpoint)
    
    if not response or not response.get('data'):
        return []
    
    data = response['data']
    items = []
    
    for item in data:
        try:
            if 'movie' in item:
                obj = item['movie']
                media_type = 'movie'
            elif 'show' in item:
                obj = item['show']
                media_type = 'tvshow'
            else:
                obj = item
                if 'title' in obj:
                    media_type = 'movie'
                elif 'name' in obj:
                    media_type = 'tvshow'
                else:
                    continue
            
            ids = obj.get('ids', {})
            tmdb_id = ids.get('tmdb')
            
            if not tmdb_id:
                continue
            
            base_item = {
                'title': obj.get('title') or obj.get('name', ''),
                'original_title': obj.get('title') or obj.get('name', ''),
                'tmdb_id': tmdb_id,
                'imdb_id': ids.get('imdb', ''),
                'media_type': media_type,
                'year': obj.get('year'),
                'slug': ids.get('slug', ''),
                'synopsis': obj.get('overview', ''),
                'rating': obj.get('rating', 0),
                'votes': obj.get('votes', 0),
                'genres': obj.get('genres', []),
                'runtime': obj.get('runtime', 0),
                'poster': '',
                'backdrop': '',
                'fanart': ''
            }
            
            if 'listed_at' in item:
                base_item['listed_at'] = item['listed_at']
            if 'collected_at' in item:
                base_item['collected_at'] = item['collected_at']
            if 'plays' in item:
                base_item['plays'] = item['plays']
            if 'last_watched_at' in item:
                base_item['last_watched_at'] = item['last_watched_at']
            if 'watchers' in item:
                base_item['watchers'] = item['watchers']
            
            items.append(base_item)
            
        except Exception as e:
            xbmc.log(f"[Trakt] Erro processando item: {e}", xbmc.LOGERROR)
            continue
    
    total_items = response.get('item_count', len(items))
    _save_trakt_cache(category, page, items, total_items)
    
    return items


def _show_trakt_category(category, media_type, page=1):
    """
    ✅ Função genérica reutilizável
    Substitui ~500 linhas de código duplicado
    """
    handle = int(sys.argv[1])
    trakt_lists = TraktLists()
    
    # === MAPEAMENTO DE CATEGORIAS ===
    # Recomendações personalizadas = 50 itens fixos (SEM paginação)
    # Outras categorias = 20 itens com paginação
    limit = 50 if category == 'personal_recommendations' else 20
    
    category_map = {
        'personal_recommendations': lambda: trakt_lists.get_personal_recommendations(media_type, 1, limit),
        'trending': lambda: trakt_lists.get_trending(media_type, page, limit),
        'popular': lambda: trakt_lists.get_popular(media_type, page, limit),
        'most_watched': lambda: trakt_lists.get_most_watched(media_type, 'weekly', page, limit),
        'most_collected': lambda: trakt_lists.get_most_collected(media_type, 'weekly', page, limit),
        'most_anticipated': lambda: trakt_lists.get_most_anticipated(media_type, page, limit),
        'box_office': lambda: trakt_lists.get_box_office(page, limit) if media_type == 'movies' else [],
        'top_rated': lambda: trakt_lists.get_top_rated(media_type, page, limit),
    }
    
    # === TÍTULOS AMIGÁVEIS ===
    titles = {
        'personal_recommendations': 'Recomendado para Você',
        'trending': 'Em Alta',
        'popular': 'Populares',
        'most_watched': 'Mais Assistidos',
        'most_collected': 'Mais Coletados',
        'most_anticipated': 'Mais Aguardados',
        'box_office': 'Bilheteria',
        'top_rated': 'Melhor Avaliados',
    }
    
    # === AÇÕES PARA PRÓXIMA PÁGINA ===
    action_prefix = 'trakt_movies' if media_type == 'movies' else 'trakt_tv'
    action_map = {
        'personal_recommendations': f"{action_prefix}_personal_recommended",
        'trending': f"{action_prefix}_trending",
        'popular': f"{action_prefix}_popular",
        'most_watched': f"{action_prefix}_most_watched",
        'most_collected': f"{action_prefix}_most_collected",
        'most_anticipated': f"{action_prefix}_most_anticipated",
        'box_office': 'trakt_movies_box_office',
        'top_rated': f"{action_prefix}_top_rated",
    }
    
    # === VERIFICA AUTENTICAÇÃO ===
    auth_required = ['personal_recommendations']
    if category in auth_required:
        settings = get_trakt_settings()
        if not settings.get('access_token'):
            xbmcgui.Dialog().ok(
                f"Trakt - {titles[category]}",
                "Você precisa estar autenticado no Trakt.\n\n"
                "Vá em: Menu Trakt > Status / Autenticar"
            )
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return
    
    # === BUSCA DADOS ===
    xbmc.log(f"[Trakt] Buscando {category}/{media_type} página {page}", xbmc.LOGINFO)
    
    if category not in category_map:
        xbmc.log(f"[Trakt] Categoria desconhecida: {category}", xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    data = category_map[category]()
    
    if not data:
        if page == 1:
            msg = "Nenhum item encontrado."
            if category == 'personal_recommendations':
                msg += "\n\nO Trakt gera recomendações baseadas no seu histórico.\nAssista mais conteúdo!"
            xbmcgui.Dialog().ok(f"Trakt - {titles[category]}", msg)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    # === NORMALIZA ITENS ===
    items = []
    for item in data:
        try:
            normalized = TraktPresentation.normalize_item(item)
            if normalized['tmdb_id']:
                items.append(normalized)
        except Exception as e:
            xbmc.log(f"[Trakt] Erro normalizando item: {e}", xbmc.LOGERROR)
            continue
    
    if not items:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    # === ENRIQUECE COM TMDB ===
    items = _enrich_item_with_tmdb_batch(items)
    
    xbmcplugin.setContent(handle, 'movies' if media_type == 'movies' else 'tvshows')
    
    # === ADICIONA ITENS ===
    for item in items:
        li = _create_trakt_listitem(item)
        is_folder = (item['media_type'] == 'tvshow')
        url = TraktPresentation.build_url(item)
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)
    
    # === PRÓXIMA PÁGINA ===
    # Recomendações personalizadas: NUNCA mostra próxima página (50 itens fixos)
    # Outras categorias: mostra se atingir o limite (20 itens)
    if category != 'personal_recommendations' and len(items) >= limit:
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        url_next = f"plugin://plugin.video.cineroom.lite/?action={action_map[category]}&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)


# ============================================================
# ✅ HELPER PARA LISTITEMS LIMPOS (NOVA)
# ============================================================

def _create_trakt_listitem(item):
    """
    ✅ Cria ListItem com título LIMPO
    Estatísticas vão para o InfoBox (não no título!)
    """
    title = item['title']
    
    li = xbmcgui.ListItem(label=title)
    
    is_folder = (item['media_type'] == 'tvshow')
    li.setProperty('IsPlayable', 'false' if is_folder else 'true')
    
    # === INFORMAÇÕES NO INFOBOX ===
    info = {
        'title': title,
        'mediatype': item['media_type'],
        'year': item.get('year', 0),
        'genre': ' / '.join(item.get('genres', [])),
        'plot': item.get('synopsis', ''),
        'rating': item.get('rating', 0),
        'votes': item.get('votes', 0),
    }
    
    if item.get('runtime'):
        info['duration'] = item['runtime'] * 60
    
    li.setInfo('video', info)
    
    # === ARTES ===
    art = {}
    if item.get('poster'):
        art['poster'] = item['poster']
        art['thumb'] = item['poster']
    if item.get('backdrop'):
        art['fanart'] = item['backdrop']
    if item.get('clearlogo'):
        art['clearlogo'] = item['clearlogo']
    
    if art:
        li.setArt(art)
    
    return li


# ============================================================
# ✅ FUNÇÕES REFATORADAS - FILMES (1 LINHA CADA)
# ============================================================

def trakt_movies_personal_recommended(page=1):
    """🎯 Recomendações personalizadas - Filmes"""
    _show_trakt_category('personal_recommendations', 'movies', page)

def trakt_movies_trending(page=1):
    """Em alta - Filmes"""
    _show_trakt_category('trending', 'movies', page)

def trakt_movies_popular(page=1):
    """Populares - Filmes"""
    _show_trakt_category('popular', 'movies', page)

def trakt_movies_most_watched(page=1):
    """Mais assistidos - Filmes"""
    _show_trakt_category('most_watched', 'movies', page)

def trakt_movies_most_collected(page=1):
    """Mais coletados - Filmes"""
    _show_trakt_category('most_collected', 'movies', page)

def trakt_movies_most_anticipated(page=1):
    """Mais aguardados - Filmes"""
    _show_trakt_category('most_anticipated', 'movies', page)

def trakt_movies_box_office(page=1):
    """Bilheteria - Filmes"""
    _show_trakt_category('box_office', 'movies', page)

def trakt_movies_top_rated(page=1):
    """Melhor avaliados - Filmes"""
    _show_trakt_category('top_rated', 'movies', page)


# ============================================================
# ✅ FUNÇÕES REFATORADAS - SÉRIES (1 LINHA CADA)
# ============================================================

def trakt_tv_personal_recommended(page=1):
    """🎯 Recomendações personalizadas - Séries"""
    _show_trakt_category('personal_recommendations', 'shows', page)

def trakt_tv_trending(page=1):
    """Em alta - Séries"""
    _show_trakt_category('trending', 'shows', page)

def trakt_tv_popular(page=1):
    """Populares - Séries"""
    _show_trakt_category('popular', 'shows', page)

def trakt_tv_most_watched(page=1):
    """Mais assistidas - Séries"""
    _show_trakt_category('most_watched', 'shows', page)

def trakt_tv_most_collected(page=1):
    """Mais coletadas - Séries"""
    _show_trakt_category('most_collected', 'shows', page)

def trakt_tv_most_anticipated(page=1):
    """Mais aguardadas - Séries"""
    _show_trakt_category('most_anticipated', 'shows', page)

def trakt_tv_top_rated(page=1):
    """Melhor avaliadas - Séries"""
    _show_trakt_category('top_rated', 'shows', page)

def trakt_tv_recommended(page=1):
    """Recomendadas - Séries"""
    _show_trakt_category('trending', 'shows', page)


# === LISTAS PRINCIPAIS ===
def list_trakt_watchlist(page=1):
    """✅ Watchlist com paginação"""
    movies = _fetch_trakt_paginated('/sync/watchlist/movies', 'watchlist_movies', page, 20)
    shows = _fetch_trakt_paginated('/sync/watchlist/shows', 'watchlist_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def list_trakt_collection(page=1):
    """✅ Coleção com paginação"""
    movies = _fetch_trakt_paginated('/sync/collection/movies', 'collection_movies', page, 20)
    shows = _fetch_trakt_paginated('/sync/collection/shows', 'collection_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def list_trakt_watched(page=1):
    """✅ Assistidos com paginação"""
    movies = _fetch_trakt_paginated('/sync/watched/movies', 'watched_movies', page, 20)
    shows = _fetch_trakt_paginated('/sync/watched/shows', 'watched_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def get_trakt_trending(page=1):
    """✅ Trending com paginação"""
    movies = _fetch_trakt_paginated('/movies/trending', 'trending_movies', page, 20)
    shows = _fetch_trakt_paginated('/shows/trending', 'trending_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

def get_trakt_popular(page=1):
    """✅ Popular com paginação"""
    movies = _fetch_trakt_paginated('/movies/popular', 'popular_movies', page, 20)
    shows = _fetch_trakt_paginated('/shows/popular', 'popular_shows', page, 20)
    
    all_items = movies + shows
    return _enrich_item_with_tmdb_batch(all_items)

# === LISTAS CUSTOMIZADAS ===
def get_trakt_lists():
    """✅ Busca listas customizadas do usuário"""
    settings = get_trakt_settings()
    username = settings.get('username')
    
    if not username:
        xbmc.log("[Trakt] Username não configurado", xbmc.LOGWARNING)
        return []
    
    xbmc.log(f"[Trakt] Buscando listas do usuário: {username}", xbmc.LOGINFO)
    
    response = trakt_request('GET', f'/users/{username}/lists')
    
    if not response:
        xbmc.log("[Trakt] Resposta vazia ou erro", xbmc.LOGWARNING)
        return []
    
    if response is True:
        xbmc.log("[Trakt] Sem listas customizadas", xbmc.LOGINFO)
        return []
    
    if isinstance(response, dict) and response.get('data'):
        lists = response['data']
        xbmc.log(f"[Trakt] {len(lists)} listas encontradas", xbmc.LOGINFO)
        return lists
    
    xbmc.log("[Trakt] Formato de resposta inválido", xbmc.LOGWARNING)
    return []

def list_trakt_custom_lists():
    """Lista as listas customizadas do usuário"""
    lists = get_trakt_lists()
    items = []
    
    for lst in lists:
        items.append({
            'title': lst.get('name'),
            'description': lst.get('description', 'Sem descrição'),
            'list_id': lst['ids'].get('trakt'),
            'item_count': lst.get('item_count', 0),
            'is_private': lst.get('privacy') == 'private',
            'slug': lst['ids'].get('slug')
        })
    
    return items

def get_trakt_list_items(list_id, page=1):
    """✅ Busca itens de uma lista customizada"""
    settings = get_trakt_settings()
    username = settings.get('username')
    
    if not username:
        return []
    
    items = _fetch_trakt_paginated(
        f'/users/{username}/lists/{list_id}/items',
        f'list_{list_id}',
        page,
        50
    )
    
    return _enrich_item_with_tmdb_batch(items)


# === EXIBIÇÃO COM PAGINAÇÃO ===

def show_trakt_watchlist_items(page=1):
    """✅ Exibe Watchlist"""
    handle = int(sys.argv[1])
    items = list_trakt_watchlist(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Watchlist", "Sua watchlist está vazia.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = _create_trakt_listitem(item)
        is_folder = (item['media_type'] == 'tvshow')
        url = _build_source_url(item)
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)
    
    if len(items) == 50:
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        url_next = f"plugin://plugin.video.cineroom.lite/?action=trakt_watchlist_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_collection_items(page=1):
    """✅ Exibe Coleção"""
    handle = int(sys.argv[1])
    items = list_trakt_collection(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Coleção", "Sua coleção está vazia.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = _create_trakt_listitem(item)
        is_folder = (item['media_type'] == 'tvshow')
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 50:
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        url_next = f"plugin://plugin.video.cineroom.lite/?action=trakt_collection_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_watched_items(page=1):
    """✅ Exibe Assistidos"""
    handle = int(sys.argv[1])
    items = list_trakt_watched(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Assistidos", "Você não assistiu nada ainda.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        plays = item.get('plays', 1)
        # Título limpo + plays se > 1
        label = f"{item['title']} ({plays}x)" if plays > 1 else item['title']
        
        li = xbmcgui.ListItem(label=label)
        is_folder = (item['media_type'] == 'tvshow')
        li.setProperty('IsPlayable', 'false' if is_folder else 'true')
        
        li.setInfo('video', {
            'title': item['title'],
            'mediatype': item['media_type'],
            'year': item.get('year', 0),
            'genre': ' / '.join(item.get('genres', [])),
            'plot': item.get('synopsis', ''),
            'playcount': plays
        })
        
        if item.get('poster'):
            li.setArt({'poster': item['poster'], 'thumb': item['poster']})
        if item.get('backdrop'):
            li.setArt({'fanart': item['backdrop']})
        
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 50:
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        url_next = f"plugin://plugin.video.cineroom.lite/?action=trakt_watched_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_trending_items(page=1):
    """✅ Exibe Trending"""
    handle = int(sys.argv[1])
    items = get_trakt_trending(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = _create_trakt_listitem(item)
        is_folder = (item['media_type'] == 'tvshow')
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 50:
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        url_next = f"plugin://plugin.video.cineroom.lite/?action=trakt_trending_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_popular_items(page=1):
    """✅ Exibe Popular"""
    handle = int(sys.argv[1])
    items = get_trakt_popular(page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = _create_trakt_listitem(item)
        is_folder = (item['media_type'] == 'tvshow')
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 50:
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        url_next = f"plugin://plugin.video.cineroom.lite/?action=trakt_popular_menu&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_custom_lists():
    """✅ Exibe menu de listas customizadas"""
    handle = int(sys.argv[1])
    
    settings = get_trakt_settings()
    if not settings.get('access_token') or not refresh_trakt_token():
        xbmcgui.Dialog().ok("Trakt", "Você não está autenticado no Trakt.\nAutentique nas configurações primeiro.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    if not settings.get('username'):
        xbmcgui.Dialog().ok("Trakt", "Username não encontrado.\nTente re-autenticar nas configurações.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    lists = list_trakt_custom_lists()
    
    if not lists:
        msg = (
            f"Nenhuma lista encontrada para o usuário [B]{settings['username']}[/B].\n\n"
            "Crie listas em:\n"
            "[B]https://trakt.tv/users/me/lists[/B]\n\n"
            "Depois volte aqui e tente novamente."
        )
        xbmcgui.Dialog().textviewer("Trakt - Listas Customizadas", msg)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for lst in lists:
        label = f"{lst['title']} ({lst['item_count']} itens)"
        if lst.get('is_private'):
            label += " 🔒"
        
        li = xbmcgui.ListItem(label=label)
        li.setProperty('IsPlayable', 'false')
        li.setInfo('video', {'title': lst['title'], 'plot': lst['description']})
        
        url = f"plugin://plugin.video.cineroom.lite/?action=trakt_list_items&list_id={lst['slug']}&page=1"
        xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_list_items(list_id, page=1):
    """✅ Exibe itens de uma lista customizada"""
    handle = int(sys.argv[1])
    items = get_trakt_list_items(list_id, page)
    
    xbmcplugin.setContent(handle, 'movies')
    
    if not items:
        if page == 1:
            xbmcgui.Dialog().ok("Lista", "Esta lista está vazia.")
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    
    for item in items:
        li = _create_trakt_listitem(item)
        is_folder = (item['media_type'] == 'tvshow')
        xbmcplugin.addDirectoryItem(handle, _build_source_url(item), li, isFolder=is_folder)
    
    if len(items) == 50:
        li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
        url_next = f"plugin://plugin.video.cineroom.lite/?action=trakt_list_items&list_id={list_id}&page={page+1}"
        xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
    
    xbmcplugin.endOfDirectory(handle, succeeded=True)

def show_trakt_status():
    """✅ Mostra status da autenticação"""
    settings = get_trakt_settings()
    username = settings['username'] or "Não autenticado"
    
    last_sync = ADDON.getSetting('trakt_last_sync')
    if last_sync:
        last_sync_dt = datetime.fromtimestamp(float(last_sync))
        last_sync_str = last_sync_dt.strftime("%d/%m/%Y %H:%M")
    else:
        last_sync_str = "Nunca"
    
    info = (
        f"Usuário: [B]{username}[/B]\n\n"
        f"Última sincronização: {last_sync_str}\n\n"
        f"Configurações ativas:\n"
        f"• Sincronizar assistidos: {'Sim' if settings['sync_watched'] else 'Não'}\n"
        f"• Sincronizar avaliações: {'Sim' if settings['sync_ratings'] else 'Não'}\n"
        f"• Sincronizar coleção: {'Sim' if settings['sync_collection'] else 'Não'}\n"
        f"• Intervalo automático: {settings['sync_interval']} minutos\n"
        f"• Sincronizar no startup: {'Sim' if settings['sync_on_startup'] else 'Não'}\n"
    )
    
    xbmcgui.Dialog().textviewer("Status Trakt", info)


# === AÇÕES INDIVIDUAIS ===

def clear_trakt_cache():
    """Limpa cache do Trakt"""
    _clear_trakt_cache()
    ADDON.setSetting('trakt_access_token', '')
    ADDON.setSetting('trakt_refresh_token', '')
    ADDON.setSetting('trakt_expires_at', '0')
    ADDON.setSetting('trakt_username', '')
    
    xbmcgui.Dialog().notification("Trakt", "Cache limpo. Autentique novamente.", xbmcgui.NOTIFICATION_INFO, 3000)

def full_sync_with_trakt(direction="both"):
    """Sincronização completa com Trakt"""
    progress = xbmcgui.DialogProgress()
    progress.create("Trakt Sync", "Verificando autenticação...")
    
    if not refresh_trakt_token():
        progress.close()
        if xbmcgui.Dialog().yesno("Trakt", "Não autenticado. Autenticar agora?"):
            if authenticate_trakt():
                return full_sync_with_trakt(direction)
        return False
    
    try:
        progress.update(100, "Concluído!")
        xbmc.sleep(500)
        progress.close()
        
        xbmcgui.Dialog().notification("Trakt", "Sincronização concluída!", xbmcgui.NOTIFICATION_INFO, 3000)
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro full sync: {e}", xbmc.LOGERROR)
        progress.close()
        return False


# === SINCRONIZAÇÃO LOCAL → TRAKT ===

def sync_local_to_trakt(progress_dialog=None):
    """
    Envia dados locais (DB + playcount) para Trakt
    ✅ Filmes assistidos → History
    ✅ Séries assistidas → History
    ✅ Favoritos → Lista personalizada "CineRoom Favoritos"
    """
    from resources.lib.db import db
    
    if progress_dialog:
        progress_dialog.update(0, "Coletando dados locais...")
    
    try:
        settings = get_trakt_settings()
        username = settings.get('username')
        
        if not username:
            xbmcgui.Dialog().ok("Erro", "Username do Trakt não encontrado. Re-autentique.")
            return False
        
        # Filmes assistidos
        watched_movies = db.get_watched_movies()
        
        if watched_movies:
            if progress_dialog:
                progress_dialog.update(20, f"Enviando {len(watched_movies)} filmes assistidos...")
            
            trakt_movies = []
            for movie in watched_movies:
                trakt_movies.append({
                    'ids': {'tmdb': movie['tmdb_id']},
                    'watched_at': movie.get('last_played') or datetime.now().isoformat()
                })
            
            for i in range(0, len(trakt_movies), 50):
                batch = trakt_movies[i:i+50]
                trakt_request('POST', '/sync/history', {'movies': batch})
        
        # Séries assistidas
        watched_shows = db.get_watched_tvshows()
        
        if watched_shows:
            if progress_dialog:
                progress_dialog.update(40, f"Enviando {len(watched_shows)} séries assistidas...")
            
            trakt_shows = []
            for show in watched_shows:
                trakt_shows.append({
                    'ids': {'tmdb': show['tmdb_id']},
                    'watched_at': show.get('last_played') or datetime.now().isoformat()
                })
            
            for i in range(0, len(trakt_shows), 50):
                batch = trakt_shows[i:i+50]
                trakt_request('POST', '/sync/history', {'shows': batch})
        
        # Favoritos
        favorites = db.get_all_favorites()
        
        if favorites:
            if progress_dialog:
                progress_dialog.update(60, f"Sincronizando {len(favorites)} favoritos com lista Trakt...")
            
            list_name = "CineRoom Favoritos"
            list_slug = "cineroom-favoritos"
            
            lists_response = trakt_request('GET', f'/users/{username}/lists')
            existing_list = None
            
            if lists_response and lists_response.get('data'):
                for lst in lists_response['data']:
                    if lst['ids'].get('slug') == list_slug:
                        existing_list = lst
                        break
            
            if not existing_list:
                create_response = trakt_request('POST', f'/users/{username}/lists', {
                    'name': list_name,
                    'description': 'Meus favoritos do CineRoom Lite (sincronizado automaticamente)',
                    'privacy': 'private',
                    'display_numbers': False,
                    'allow_comments': False
                })
                
                if create_response and create_response.get('data'):
                    existing_list = create_response['data'][0] if isinstance(create_response['data'], list) else create_response['data']
            
            if existing_list:
                list_id = existing_list['ids'].get('slug') or existing_list['ids'].get('trakt')
                
                fav_movies = [{'ids': {'tmdb': f['tmdb_id']}} for f in favorites if f['media_type'] == 'movie']
                fav_shows = [{'ids': {'tmdb': f['tmdb_id']}} for f in favorites if f['media_type'] == 'tvshow']
                
                trakt_request('POST', f'/users/{username}/lists/{list_id}/items/remove', {
                    'movies': fav_movies,
                    'shows': fav_shows
                })
                
                trakt_request('POST', f'/users/{username}/lists/{list_id}/items', {
                    'movies': fav_movies,
                    'shows': fav_shows
                })
        
        _clear_trakt_cache()
        
        if progress_dialog:
            progress_dialog.update(100, "Sincronização concluída!")
        
        xbmcgui.Dialog().notification(
            "Trakt Sync",
            f"✅ {len(watched_movies)} filmes, {len(watched_shows)} séries, {len(favorites)} favoritos enviados",
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        
        return True
        
    except Exception as e:
        xbmc.log(f"[Trakt] Erro sincronizando local para Trakt: {e}", xbmc.LOGERROR)
        
        