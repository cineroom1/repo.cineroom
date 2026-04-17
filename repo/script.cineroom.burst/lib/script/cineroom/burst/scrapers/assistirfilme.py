# -*- coding: utf-8 -*-
"""
Scraper para AssistirFilme — CineRoom Lite (Burst)

Fluxo filmes:
  1. assistirfilme.net/busca?q={titulo}  → encontra slug
  2. assistirfilme.net/iframe/{slug}?player=1
     → <source src="/direct/mf/{id}/{token}/hd?expires=...">
  3. assistirfilme.net/direct/mf/...  → 302 → MediaFire MP4

Fluxo séries:
  1. assistirfilme.net/busca?q={titulo}  → encontra slug
  2. assistirfilme.net/serie/{slug}/temporada-{N}
     → <tr onclick="reloadVideoSerie('BASE64_ID', 'TOKEN')">
  3. assistirfilme.net/direct/mf/{id_decoded}/{token}/hd  → 302 → MP4
"""

import re
import base64
import difflib
import unicodedata
import xbmc
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, quote

WEBSITE  = 'AssistirFilme'
from .scraper_config import get_url
BASE_URL = get_url('assistirfilme', fallback='https://assistirfilmes.biz')
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)

_session = requests.Session()
_session.headers.update({
    'User-Agent':      USER_AGENT,
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    'Referer':         BASE_URL + '/',
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(url, referer=None, allow_redirects=True, timeout=15):
    headers = {}
    if referer:
        headers['Referer'] = referer
    try:
        r = _session.get(url, headers=headers,
                         allow_redirects=allow_redirects, timeout=timeout)
        return r
    except Exception as e:
        xbmc.log(f'[AssistirFilme] GET falhou {url}: {e}', xbmc.LOGWARNING)
        return None


def _soup(r):
    if not r:
        return None
    return BeautifulSoup(r.text, 'html.parser')


def _remove_accents(text):
    """Remove todos os acentos e caracteres especiais, retorna só ASCII."""
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', str(text))
    return nfkd.encode('ascii', 'ignore').decode('ascii')


def _normalize(text):
    """
    Normalização completa para comparação e busca:
    - Remove acentos
    - Minúsculas
    - Remove ano entre parênteses/colchetes
    - Remove tudo após : ; - – — (subtítulos)
    - Remove pontuação exceto espaços
    - Colapsa espaços múltiplos
    """
    if not text:
        return ''
    text = str(text)
    text = re.sub(r'\s*[\(\[]\d{4}[\)\]].*', '', text)
    text = re.sub(r'[\:\;\-–—].*', '', text)
    text = _remove_accents(text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _search_queries(title):
    """
    Gera lista de queries progressivamente mais simples a partir do título.
    Todas sem acentos e sem pontuação.
    Ex: "Invencível: A Série (2021)" →
        ["invencivel a serie", "invencivel a", "invencivel"]
    """
    base  = _normalize(title)
    words = base.split()
    queries = [base]
    if len(words) >= 3:
        queries.append(' '.join(words[:3]))
    if len(words) >= 2:
        queries.append(' '.join(words[:2]))
    if len(words) >= 1:
        queries.append(words[0])
    seen, result = set(), []
    for q in queries:
        if q and q not in seen:
            seen.add(q)
            result.append(q)
    return result


def _similarity(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def _build_stream_string(stream_url):
    h = {
        'User-Agent': USER_AGENT,
        'Referer':    BASE_URL + '/',
    }
    header_str = '&'.join(f'{k}={quote(v)}' for k, v in h.items())
    return f'{stream_url}|{header_str}'


def _is_invalid_url(url):
    if not url:
        return True
    return any(p in url for p in ('link_invalido', 'video_indisponivel', '/assets/video/'))


# ---------------------------------------------------------------------------
# Etapa 1 — Busca e slug
# ---------------------------------------------------------------------------

def _search(title, want_serie=False):
    path_type  = '/serie/' if want_serie else '/filme/'
    title_norm = _normalize(title)
    queries    = _search_queries(title)

    for q in queries:
        url = f'{BASE_URL}/busca?q={quote_plus(q)}'
        r   = _get(url)
        doc = _soup(r)
        if not doc:
            continue

        for a in doc.select('a[href]'):
            href = a.get('href', '')
            if path_type not in href:
                continue

            card     = a.find_parent('div', class_='card')
            title_el = card.select_one('h3.card__title') if card else None
            page_raw = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            page_norm = _normalize(page_raw)
            if not page_norm:
                continue

            sim   = _similarity(title_norm, page_norm)
            match = sim >= 0.4 or title_norm in page_norm or page_norm in title_norm

            if match:
                slug = href.rstrip('/').split('/')[-1]
                xbmc.log(
                    f'[AssistirFilme] Encontrado: {href} '
                    f'(q="{q}" page="{page_norm}" sim={sim:.2f})',
                    xbmc.LOGDEBUG
                )
                return slug

    xbmc.log(
        f'[AssistirFilme] Não encontrado: "{title}" queries={queries}',
        xbmc.LOGDEBUG
    )
    return None


# ---------------------------------------------------------------------------
# Etapa 2a — Resolver filme
# ---------------------------------------------------------------------------

def _resolve_movie(slug):
    iframe_url = f'{BASE_URL}/iframe/{slug}?player=1'
    r   = _get(iframe_url, referer=f'{BASE_URL}/filme/{slug}')
    doc = _soup(r)
    if not doc:
        return None

    source = doc.select_one('video source[src]')
    if not source:
        xbmc.log(f'[AssistirFilme] <source> não encontrado em {iframe_url}', xbmc.LOGWARNING)
        return None

    src = source.get('src', '').strip()
    if not src:
        return None
    if src.startswith('//'):
        src = 'https:' + src
    elif src.startswith('/'):
        src = BASE_URL + src

    xbmc.log(f'[AssistirFilme] direct URL: {src[:80]}', xbmc.LOGDEBUG)

    r2 = _get(src, referer=iframe_url, allow_redirects=False)
    if not r2:
        return None

    if r2.status_code in (301, 302, 303, 307, 308):
        final_url = r2.headers.get('Location', '').strip()
        if not _is_invalid_url(final_url):
            xbmc.log(f'[AssistirFilme] MP4 filme: {final_url[:80]}', xbmc.LOGINFO)
            return final_url
        xbmc.log(f'[AssistirFilme] Link inválido para slug={slug}', xbmc.LOGWARNING)
        return None

    if r2.status_code == 200 and not _is_invalid_url(src):
        return src

    xbmc.log(f'[AssistirFilme] Redirect filme falhou status={r2.status_code}', xbmc.LOGWARNING)
    return None


# ---------------------------------------------------------------------------
# Etapa 2b — Resolver série
# ---------------------------------------------------------------------------

def _decode_episode_id(b64_id):
    """
    O site usa DUAS camadas de base64 (equivalente a atob(atob(x)) no JS).
    O resultado binário é tratado como latin-1 e vai URL-encoded na requisição.
    """
    try:
        # Primeira camada
        raw1 = base64.b64decode(b64_id + '==')
        mid  = raw1.decode('latin-1')

        # Segunda camada — o mid pode ter padding irregular
        raw2 = base64.b64decode(mid + '==')
        # Retorna como latin-1 para preservar todos os bytes
        return raw2.decode('latin-1')

    except Exception as e:
        xbmc.log(f'[AssistirFilme] Erro ao decodificar b64 "{b64_id}": {e}', xbmc.LOGWARNING)
        return b64_id


def _resolve_serie(slug, season, episode):
    season_url = f'{BASE_URL}/serie/{slug}/temporada-{season}'
    r   = _get(season_url, referer=f'{BASE_URL}/serie/{slug}')
    doc = _soup(r)
    if not doc:
        return None

    episode_int = int(episode)
    rows        = doc.select('table.accordion__list tbody tr[onclick]')

    if not rows:
        xbmc.log(f'[AssistirFilme] Nenhum episódio em {season_url}', xbmc.LOGWARNING)
        return None

    # Localiza pelo número na primeira coluna
    target_row = None
    for row in rows:
        th = row.select_one('th:first-child')
        if th:
            try:
                if int(th.get_text(strip=True)) == episode_int:
                    target_row = row
                    break
            except ValueError:
                pass

    # Fallback por índice (1-based)
    if not target_row:
        if episode_int <= len(rows):
            target_row = rows[episode_int - 1]
        else:
            xbmc.log(
                f'[AssistirFilme] Ep {episode_int} fora do range ({len(rows)}) em {season_url}',
                xbmc.LOGDEBUG
            )
            return None

    onclick = target_row.get('onclick', '')
    m = re.search(
        r"reloadVideoSerie\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
        onclick
    )
    if not m:
        xbmc.log(f'[AssistirFilme] reloadVideoSerie não parseado: {onclick[:80]}', xbmc.LOGWARNING)
        return None

    b64_id = m.group(1).strip()
    token  = m.group(2).strip()

    xbmc.log(f'[AssistirFilme] b64={b64_id} token={token}', xbmc.LOGDEBUG)

    direct_url = f'{BASE_URL}/playserie/{b64_id}/{token}'

    r2 = _get(direct_url, referer=season_url, allow_redirects=True)
    if not r2:
        return None

    final_url = r2.url
    xbmc.log(f'[AssistirFilme] URL final série: {final_url[:120]}', xbmc.LOGDEBUG)

    if _is_invalid_url(final_url):
        xbmc.log(f'[AssistirFilme] Link inválido b64={b64_id}', xbmc.LOGWARNING)
        return None

    return final_url


# ---------------------------------------------------------------------------
# Montagem de sources no padrão Burst
# ---------------------------------------------------------------------------

def _detect_quality(url):
    u = url.lower()
    if any(x in u for x in ('2160', '4k', 'uhd')):
        return '4K'
    if any(x in u for x in ('1080', 'fhd')):
        return '1080p'
    if '720' in u:
        return '720p'
    if 'hd' in u:
        return 'HD'
    return 'SD'


def _detect_lang(text):
    if 'LEGENDA' in text.upper():
        return 'LEGENDADO'
    return 'DUBLADO'


def _build_source(stream_url, lang, ep_code='', quality=None):
    quality    = quality or _detect_quality(stream_url)
    stream_str = _build_stream_string(stream_url)
    url, _, headers_str = stream_str.partition('|')
    return {
        'url':              url,
        'quality':          quality,
        'type':             'Direto',
        'provider':         WEBSITE,
        'languages':        lang,
        'release_title':    ep_code,
        'label':            f'{WEBSITE} • {lang} [{quality}]',
        'size':             'N/A',
        'seeders':          0,
        'extras':           [],
        'headers':          headers_str,
        'manifest_type':    'mp4',
        'inputstreamaddon': '',
    }


# ---------------------------------------------------------------------------
# Entry point (padrão Burst)
# ---------------------------------------------------------------------------

def scrape(provider_url, item_data, season=None, episode=None):
    _session.cookies.clear()

    media_type = item_data.get('media_type', 'movie')
    title      = item_data.get('title', '')

    if not title:
        xbmc.log('[AssistirFilme] Título não informado.', xbmc.LOGDEBUG)
        return []

    want_serie = (media_type == 'tvshow')
    ep_label   = (
        f'S{int(season):02d}E{int(episode):02d}'
        if want_serie and season is not None and episode is not None
        else ''
    )

    xbmc.log(f'[AssistirFilme] Buscando: "{title}" {ep_label}'.strip(), xbmc.LOGDEBUG)

    slug = _search(title, want_serie=want_serie)
    if not slug:
        return []

    xbmc.log(f'[AssistirFilme] slug={slug}', xbmc.LOGDEBUG)

    # ── FILME ─────────────────────────────────────────────────────────────
    if media_type == 'movie':
        stream_url = _resolve_movie(slug)
        if not stream_url:
            return []
        r    = _get(f'{BASE_URL}/filme/{slug}')
        lang = _detect_lang(r.text[:3000] if r else '')
        xbmc.log(f'[AssistirFilme] Filme: 1 fonte resolvida.', xbmc.LOGINFO)
        return [_build_source(stream_url, lang, quality='720p')]

    # ── SÉRIE ──────────────────────────────────────────────────────────────
    if media_type == 'tvshow':
        if season is None or episode is None:
            xbmc.log('[AssistirFilme] season/episode obrigatórios.', xbmc.LOGDEBUG)
            return []
        season_int  = int(season)
        episode_int = int(episode)
        ep_code     = f'S{season_int:02d}E{episode_int:02d}'
        stream_url  = _resolve_serie(slug, season_int, episode_int)
        if not stream_url:
            return []
        xbmc.log(f'[AssistirFilme] {ep_code}: 1 fonte resolvida.', xbmc.LOGINFO)
        return [_build_source(stream_url, 'DUBLADO', ep_code, quality='720p')]

    return []