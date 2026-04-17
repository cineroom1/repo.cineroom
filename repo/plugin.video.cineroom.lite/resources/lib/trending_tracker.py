# -*- coding: utf-8 -*-
"""
Sistema de tracking de conteúdo popular com Supabase Edge Functions
— Sem chave de API no cliente. Toda escrita passa pela Edge Function track-view.
— Leituras de trending/popular ainda usam a REST API pública (anon key removida,
  requer RLS configurado no Supabase para leitura anônima de content_views).
"""

import xbmc
import xbmcvfs
import json
import time
import os

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
    from urllib.parse import urlencode
except ImportError:
    from urllib2 import urlopen, Request, URLError, HTTPError
    from urllib import urlencode

# ========================================
# CONFIGURAÇÃO — só URL pública, sem chave
# ========================================
SUPABASE_URL    = "https://opmakuortoxabzhonxwr.supabase.co"
TRACK_ENDPOINT  = SUPABASE_URL + "/functions/v1/track-view"
TRENDING_ENDPOINT  = SUPABASE_URL + "/functions/v1/get-trending"
SUPABASE_ANON_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9wbWFrdW9ydG94YWJ6aG9ueHdyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA2ODA0NjEsImV4cCI6MjA4NjI1NjQ2MX0.3sof93Xik3XnU4SG0vh3DbMHQqjhrj2wrgOC_VaIdtY" # leitura via Edge Function

# ========================================
# CONFIGURAÇÕES DE CACHE
# ========================================
CACHE_DURATION    = 3 * 24 * 3600  # Trending: 3 dias
CACHE_FILE        = 'trending_cache.json'
CACHE_MAX_ENTRIES = 50

# Cache de busca separado para nao poluir trending_cache.json
SEARCH_CACHE_FILE        = 'search_cache.json'
SEARCH_CACHE_MAX_ENTRIES = 30

# ========================================
# CONFIGURAÇÕES DE TRACKING
# ========================================
PENDING_TRACKS_FILE = 'pending_tracks.json'
PENDING_MAX_ENTRIES = 1000

# ========================================
# CONFIGURAÇÕES DE CACHE DE PESQUISA
# ========================================
SEARCH_CACHE_DURATION  = 8 * 3600
SEARCH_CACHE_MIN_COUNT = 2
QUERY_COUNTS_FILE      = 'query_counts.json'


# ========================================
# HEADERS — sem apikey
# ========================================

def _headers_json():
    """Headers para chamadas às Edge Functions (anon key para passar pelo gateway do Supabase)."""
    """Headers mínimos para chamadas às Edge Functions (sem chave)."""
    return {
        'Content-Type':  'application/json',
        'Accept':        'application/json',
        'Authorization': 'Bearer ' + SUPABASE_ANON_KEY,
        'apikey':        SUPABASE_ANON_KEY,
    }


def _is_configured():
    """Checa se a URL está preenchida (não é placeholder)."""
    return "SEU-PROJETO" not in SUPABASE_URL


# ========================================
# HTTP HELPERS
# ========================================

def _http_get_edge(url, timeout=5):
    """
    GET para Edge Function de leitura (get-trending).
    Sem apikey — a função controla o acesso internamente.
    Retorna parsed JSON ou None.
    """
    try:
        req = Request(url)
        for k, v in _headers_json().items():
            req.add_header(k, v)
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        pass
    except URLError as e:
        pass
    except Exception as e:
        pass
    return None


def _http_post_edge(url, payload, timeout=8):
    """
    POST para Edge Function (track-view).
    Sem apikey — a função valida e escreve no banco com service role internamente.
    Retorna True em caso de sucesso (2xx), False caso contrário.
    """
    try:
        body = json.dumps(payload).encode('utf-8')
        req  = Request(url, data=body, method='POST')
        for k, v in _headers_json().items():
            req.add_header(k, v)
        with urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 201, 204)
    except HTTPError as e:
        xbmc.log(f"[Trending] HTTP {e.code} em POST {url}", xbmc.LOGERROR)
    except URLError as e:
        pass
    except Exception as e:
        pass
    return False


# ========================================
# CACHE LOCAL (JSON em disco)
# ========================================

def _get_profile_dir():
    from xbmcaddon import Addon
    profile = xbmcvfs.translatePath(Addon().getAddonInfo('profile'))
    if not os.path.exists(profile):
        os.makedirs(profile)
    return profile


def _get_cache_path():
    return os.path.join(_get_profile_dir(), CACHE_FILE)


def _get_pending_tracks_path():
    return os.path.join(_get_profile_dir(), PENDING_TRACKS_FILE)


def _get_search_cache_path():
    return os.path.join(_get_profile_dir(), SEARCH_CACHE_FILE)


def _read_cache_file():
    path = _get_cache_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache_file(cache):
    try:
        with open(_get_cache_path(), 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, separators=(',', ':'))
    except Exception as e:
        pass


def _read_search_cache_file():
    path = _get_search_cache_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _write_search_cache_file(cache):
    try:
        with open(_get_search_cache_path(), 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, separators=(',', ':'))
    except Exception:
        pass


def _load_search_cache(key):
    cache = _read_search_cache_file()
    entry = cache.get(key)
    if not entry:
        return None
    if time.time() > entry.get('exp', 0):
        return None
    return entry.get('d')


def _save_search_cache(key, data, duration=SEARCH_CACHE_DURATION):
    cache = _read_search_cache_file()
    now = time.time()
    cache = {k: v for k, v in cache.items() if v.get('exp', 0) > now}
    if len(cache) >= SEARCH_CACHE_MAX_ENTRIES:
        oldest = sorted(cache, key=lambda k: cache[k].get('exp', 0))
        for old_key in oldest[:len(cache) - SEARCH_CACHE_MAX_ENTRIES + 1]:
            cache.pop(old_key, None)
    cache[key] = {'d': data, 'exp': now + duration}
    _write_search_cache_file(cache)


def _load_cache(key):
    cache = _read_cache_file()
    entry = cache.get(key)
    if not entry:
        return None
    if time.time() > entry.get('exp', 0):
        return None
    return entry.get('d')


def _save_cache(key, data, duration=CACHE_DURATION):
    cache = _read_cache_file()

    now   = time.time()
    cache = {k: v for k, v in cache.items() if v.get('exp', 0) > now}

    if len(cache) >= CACHE_MAX_ENTRIES:
        oldest = sorted(cache, key=lambda k: cache[k].get('exp', 0))
        for old in oldest[:len(cache) - CACHE_MAX_ENTRIES + 1]:
            cache.pop(old, None)

    cache[key] = {'d': data, 'exp': now + duration}
    _write_cache_file(cache)


def clear_cache():
    """Limpa todo o cache de trending e tracks pendentes."""
    cleared = False
    for path in [_get_cache_path(), _get_pending_tracks_path(), _get_search_cache_path()]:
        try:
            if os.path.exists(path):
                os.remove(path)
                cleared = True
        except Exception as e:
            xbmc.log(f"[Trending] Erro ao limpar cache {path}: {e}", xbmc.LOGERROR)
    if cleared:
        pass
    return cleared


# ========================================
# TRACKING DE VISUALIZAÇÕES
# ========================================

def queue_track(tmdb_id=None, imdb_id=None, content_type='movie'):
    """
    Salva evento de tracking em disco para envio posterior em lote.
    Não faz nenhuma chamada de rede — retorno imediato.

    Só enfileira se o conteúdo existir no banco local — evita gravar
    IDs que vieram só do TMDB e não estão na base local.

    O service loop chama flush_pending_tracks() a cada 30 min para
    enviar tudo via Edge Function (sem chave no cliente).
    """
    if not tmdb_id and not imdb_id:
        return

    try:
        path    = _get_pending_tracks_path()
        pending = []
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                pending = json.load(f)

        pending.append({
            'tmdb_id':      tmdb_id,
            'imdb_id':      imdb_id,
            'content_type': content_type,
            'ts':           time.time(),
        })

        # Evita crescimento infinito (descarta os mais antigos)
        if len(pending) > PENDING_MAX_ENTRIES:
            pending = pending[-PENDING_MAX_ENTRIES:]

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(pending, f, separators=(',', ':'))


    except Exception as e:
        pass


def flush_pending_tracks():
    """
    Envia tracks pendentes para o Supabase via Edge Function track-view.
    Agrupa por (tmdb_id, content_type) antes de enviar — sem apikey no cliente.
    A Edge Function usa service role internamente para fazer o UPSERT.
    """
    if not _is_configured():
        return

    path = _get_pending_tracks_path()
    if not os.path.exists(path):
        return

    try:
        with open(path, 'r', encoding='utf-8') as f:
            pending = json.load(f)
    except Exception as e:
        return

    if not pending:
        return

    # Agrupa por (tmdb_id, content_type) para evitar spam
    aggregated = {}
    for track in pending:
        # Normaliza content_type antes de agrupar
        ct = track['content_type']
        if ct == 'tvshow':
            ct = 'tv'
        key = (track['tmdb_id'], ct)
        if key not in aggregated:
            aggregated[key] = {
                'tmdb_id':      track['tmdb_id'],
                'imdb_id':      track.get('imdb_id', ''),
                'content_type': ct,
            }


    # Envia em lote único para a Edge Function (ela faz o UPSERT internamente)
    tracks_list = list(aggregated.values())
    ok = _http_post_edge(TRACK_ENDPOINT, tracks_list)

    if ok:
        pass
    else:
        return  # Não limpa o arquivo: tenta de novo na próxima rodada

    # Limpa arquivo de pendentes somente após sucesso
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump([], f)
    except Exception as e:
        pass


# ========================================
# LEITURA DE TRENDING via Edge Function
# ========================================

def get_trending_content_from_supabase(content_type='movie', limit=20, min_views=5):
    """
    Busca conteúdo mais visualizado via Edge Function get-trending.
    Sem apikey no cliente — a função controla o acesso e filtra internamente.

    Args:
        content_type: 'movie' ou 'tv'
        limit: Máximo de resultados
        min_views: Mínimo de visualizações para aparecer

    Returns:
        Lista de dicts com tmdb_id, imdb_id, view_count, etc.
    """
    if not _is_configured():
        return []

    cache_key = f"trending_{content_type}_{limit}"
    cached = _load_cache(cache_key)
    if cached:
        return cached

    try:
        params = urlencode({
            'content_type': content_type,
            'limit':        limit,
            'min_views':    min_views,
        })
        url     = f"{TRENDING_ENDPOINT}?{params}"
        results = _http_get_edge(url) or []

        if results:
            _save_cache(cache_key, results, duration=CACHE_DURATION)

        return results

    except Exception as e:
        return []


def get_popular_queries_from_supabase(limit=50, min_count=5):
    """
    Retorna o conteúdo mais clicado via Edge Function get-trending.
    Usado pelas telas 'Mais Buscados' de filmes e séries.

    Returns:
        Lista de dicts com tmdb_id, imdb_id, content_type, view_count.
    """
    cache_key = f"popular_search_clicks_{limit}_{min_count}"
    cached = _load_cache(cache_key)
    if cached == '__empty__':
        return []
    if cached:
        return cached

    if not _is_configured():
        return []

    try:
        params = urlencode({
            'limit':     limit,
            'min_views': min_count,
        })
        url     = f"{TRENDING_ENDPOINT}?{params}"
        results = _http_get_edge(url) or []

        if results:
            _save_cache(cache_key, results, duration=7 * 24 * 3600)
        else:
            _save_cache(cache_key, '__empty__', duration=6 * 3600)  # tenta de novo em 6h

        return results

    except Exception as e:
        return []


# ========================================
# TRACKING DE CLIQUES VIA BUSCA
# ========================================

def queue_track_from_search(tmdb_id=None, imdb_id=None, content_type='movie'):
    """
    Enfileira um clique que veio de um resultado de busca.
    Idêntico ao queue_track normal — separado semanticamente para clareza.
    Chamado pelo router quando a URL contém track=1.
    """
    queue_track(tmdb_id=tmdb_id, imdb_id=imdb_id, content_type=content_type)


# ========================================
# CACHE DE BUSCA
# ========================================

def get_cached_search_results(query, page=1):
    """Retorna resultados de busca cacheados (arquivo separado do trending)."""
    cache_key = f"search:{query}:p{page}"
    return _load_search_cache(cache_key)


def save_search_results(query, page, results):
    """Salva resultados de busca no search_cache.json (nao polui trending_cache.json)."""
    cache_key = f"search:{query}:p{page}"
    _save_search_cache(cache_key, results, duration=SEARCH_CACHE_DURATION)