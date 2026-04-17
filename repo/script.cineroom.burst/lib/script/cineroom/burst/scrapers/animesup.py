# -*- coding: utf-8 -*-
"""
Scraper para AnimeSup — CineRoom Lite (Burst)
Suporte a animes (séries e filmes).
Lookup de mal_id via Jikan a partir de title/romaji_title do item_data.
MP4 extraído diretamente do HTML sem dependência de Resolver externo.
"""

import re
import difflib
import unicodedata
import xbmc
import requests
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

WEBSITE    = 'AnimeSup'
from .scraper_config import get_url
BASE_URL   = get_url('animesup', fallback='https://www.animesup.info')
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/128.0.0.0 Safari/537.36'
)

_session = requests.Session()
_session.headers.update({
    'User-Agent': USER_AGENT,
    'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': BASE_URL + '/',
})

QUOTE_MIN_CHARS = 60
QUOTE_MIN_WORDS = 8


# ---------------------------------------------------------------------------
# Helpers de normalização
# ---------------------------------------------------------------------------

def _normalize(text):
    if not text:
        return ''
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')


def _clean_title(title):
    if not title:
        return ''
    t = _normalize(title.lower())
    t = re.sub(r'\bassistir\s+online\b', '', t)
    t = re.sub(r'\bonline\b', '', t)
    t = re.sub(r'[\"""\'`]', '', t)
    t = re.sub(r'[-_:]', ' ', t)
    t = re.sub(r'[()\[\]]', '', t)
    t = re.sub(r'\b(\d+)(?:st|nd|rd|th|ª|º)\b', r'\1', t)
    return re.sub(r'\s+', ' ', t).strip()


def _strip_dublado(text):
    return re.sub(r'\bdublado\b', '', text).strip()


def _adjust_base_title(title):
    if not title or '"' not in title:
        return title
    words = title.split()
    if len(title) < QUOTE_MIN_CHARS and len(words) < QUOTE_MIN_WORDS:
        return title
    return title.split('"', 1)[0].strip()


def _normalize_movie_hyphen(title):
    if not title:
        return title
    return re.sub(
        r'\s*[\u002D\u2010-\u2015]\s*(the movie\b)',
        r' the movie', title, flags=re.I
    )


def _extract_year(text):
    if not text:
        return None
    m = re.search(r'\b(19|20)\d{2}\b', text)
    return int(m.group()) if m else None


def _extract_season_number(text):
    if not text:
        return None
    for pat in [
        r'\b(\d+)[ªº]?\s*(?:temporada|season|t|temp|s)\b',
        r'\b(temporada|season|t|temp|s)\s*(\d+)\b',
        r'\b(\d+)\b',
    ]:
        m = re.search(pat, text.lower())
        if m:
            try:
                num = int(m.group(1))
                if 1 <= num <= 20:
                    return num
            except Exception:
                pass
    return None


def _similarity_score(base_titles, candidate_title, base_year=None, cand_year=None):
    cand_clean = _clean_title(_normalize_movie_hyphen(candidate_title))
    best = 0.0
    for base_title in base_titles:
        base_clean = _clean_title(_adjust_base_title(base_title))
        if not base_clean:
            continue
        cand_no_dub = _strip_dublado(cand_clean)
        if cand_no_dub != base_clean and len(cand_no_dub.split()) > len(base_clean.split()):
            continue
        score = difflib.SequenceMatcher(None, base_clean, cand_no_dub).ratio()
        if 'dublado' in cand_clean:
            score += 0.25
        if base_year and cand_year:
            score += 0.5 if base_year == cand_year else -0.5
        if score > best:
            best = score
    return best


# ---------------------------------------------------------------------------
# Lookup mal_id via Jikan
# ---------------------------------------------------------------------------

def _find_mal_id(title, romaji_title, year=None):
    for q in [q for q in [title, romaji_title] if q]:
        try:
            r = _session.get(
                f'https://api.jikan.moe/v4/anime?q={quote_plus(q)}&limit=8',
                timeout=10
            )
            if not r.ok:
                continue
            for item in r.json().get('data', []):
                candidates = [
                    item.get('title_english') or '',
                    item.get('title') or '',
                ] + [s.get('title', '') for s in item.get('titles', [])]
                for cand in candidates:
                    if not cand:
                        continue
                    ratio = difflib.SequenceMatcher(
                        None, _clean_title(q), _clean_title(cand)
                    ).ratio()
                    if ratio >= 0.70:
                        if year:
                            item_year = (
                                (item.get('aired') or {})
                                .get('prop', {})
                                .get('from', {})
                                .get('year')
                            )
                            if item_year and abs(int(item_year) - int(year)) > 1:
                                continue
                        mal_id = item.get('mal_id')
                        return mal_id
        except Exception as e:
            xbmc.log(f'[AnimeSup] Erro Jikan para "{q}": {e}', xbmc.LOGWARNING)
    return None


# ---------------------------------------------------------------------------
# Scraping do site
# ---------------------------------------------------------------------------

def _search_site(base_titles, base_year):
    anchors = []
    for search_title in base_titles[:2]:
        try:
            r = _session.get(
                f'{BASE_URL}/busca?busca={quote_plus(search_title)}',
                timeout=10
            )
            if not r.ok:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            found = soup.find_all(
                'a', href=re.compile(r'/(animes|anime-dublado)/[^/]+$')
            )
            if found:
                anchors = found
                break
        except Exception as e:
            xbmc.log(f'[AnimeSup] Erro busca "{search_title}": {e}', xbmc.LOGWARNING)

    candidates = []
    for a in anchors:
        raw_title = a.get_text(strip=True)
        page_url  = urljoin(BASE_URL + '/', a['href'])
        cand_year = _extract_year(raw_title)
        score     = _similarity_score(base_titles, raw_title, base_year, cand_year)
        candidates.append({
            'title':       raw_title,
            'url':         page_url,
            'score':       score,
            'year':        cand_year,
            'season':      _extract_season_number(raw_title),
            'clean_title': _clean_title(raw_title),
        })
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates


def _extract_episode_links(page_text):
    soup     = BeautifulSoup(page_text, 'html.parser')
    items    = soup.find_all('div', class_='ultimosEpisodiosHomeItem')
    episodes = {}
    for item in items:
        num_div = item.find('div', class_='ultimosEpisodiosHomeItemInfosNum')
        if not num_div:
            continue
        m = re.search(r'epis[óo]dio\s*(\d+)', num_div.get_text(strip=True), re.I)
        if not m:
            continue
        ep_num = int(m.group(1))
        a = item.find('a', href=True)
        if a and a['href'].startswith('/episodio/'):
            episodes[ep_num] = a['href']
    return episodes


def _get_episode_url(series_url, episode_num):
    page_num = 1
    while True:
        purl = series_url.rstrip('/') + (f'/page/{page_num}' if page_num > 1 else '')
        try:
            r = _session.get(purl, timeout=10)
            if not r.ok:
                break
            episodes = _extract_episode_links(r.text)
            if not episodes:
                break
            if episode_num in episodes:
                return urljoin(BASE_URL + '/', episodes[episode_num])
            page_num += 1
        except Exception as e:
            xbmc.log(f'[AnimeSup] Erro paginação: {e}', xbmc.LOGWARNING)
            break
    return None


def _get_movie_episode_url(page_text):
    soup  = BeautifulSoup(page_text, 'html.parser')
    items = soup.find_all('div', class_='ultimosEpisodiosHomeItem')
    for item in items:
        a = item.find('a', href=True)
        if a and a['href'].startswith('/episodio/'):
            return urljoin(BASE_URL + '/', a['href'])
    return None


def _sign_r2_url(base_url):
    """
    Obtém a assinatura AWS pré-assinada via ads.animeyabu.net.
    Retorna a URL final assinada ou a URL base se falhar.
    """
    import json as _json
    try:
        ads_url = 'https://ads.animeyabu.net/?token=undefined&url=' + base_url
        r = _session.get(ads_url, timeout=10)
        if r.ok:
            data = _json.loads(r.text)
            assinatura = data[0].get('publicidade', '') if data else ''
            if assinatura:
                signed = base_url + assinatura
                return signed
    except Exception as e:
        xbmc.log(f'[AnimeSup] Erro ao assinar URL: {e}', xbmc.LOGWARNING)
    return base_url


def _extract_video_urls(episode_page_text):
    """Extrai URLs MP4 do HTML e assina via ads.animeyabu.net."""
    videos     = {}
    containers = re.split(r'<div class="playerContainer"', episode_page_text)[1:]
    q_order    = ('SD', 'HD', 'FULLHD')
    for i, container in enumerate(containers[:3]):
        m = re.search(r"var\s+vid\s*=\s*'([^']+\.mp4)'", container)
        if not m:
            continue
        base_url = m.group(1).strip()
        if 'r2.cloudflarestorage.com' not in base_url:
            continue
        quality = q_order[i]
        videos[quality] = _sign_r2_url(base_url)
    return videos


def _get_available_qualities(episode_page_text):
    soup     = BeautifulSoup(episode_page_text, 'html.parser')
    abas_box = soup.find('div', class_=re.compile(r'AbasBox', re.I))
    if not abas_box:
        return ['SD']
    available = []
    for aba in abas_box.find_all('div', class_=re.compile(r'Aba', re.I)):
        text = aba.get_text(strip=True).upper()
        if text in ('SD', 'HD'):
            available.append(text)
        elif text in ('FULLHD', 'FULL HD', 'FHD'):
            available.append('FULLHD')
    return available if available else ['SD']


def _resolve_episode(ep_url):
    """Acessa página do episódio e retorna lista de (quality, url)."""
    results = []
    try:
        r = _session.get(ep_url, timeout=10)
        if not r.ok:
            return results
        available = _get_available_qualities(r.text)
        videos    = _extract_video_urls(r.text)
        for q in ('SD', 'HD', 'FULLHD'):
            if q in available and q in videos:
                results.append((q, videos[q]))
    except Exception as e:
        xbmc.log(f'[AnimeSup] Erro ao resolver episódio {ep_url}: {e}', xbmc.LOGWARNING)
    return results


# ---------------------------------------------------------------------------
# Formatação de sources no padrão Burst
# ---------------------------------------------------------------------------

def _build_sources(streams, lang, media_type, season=None, episode=None):
    q_map   = {'FULLHD': '1080p', 'HD': '720p', 'SD': '480p'}
    ep_code = ''
    if media_type == 'tvshow' and season is not None and episode is not None:
        ep_code = f'S{int(season):02d}E{int(episode):02d}'
    sources = []
    for quality, stream_url in streams:
        q_label = q_map.get(quality, 'HD')
        sources.append({
            'url':           stream_url,
            'quality':       q_label,
            'type':          'Direto',
            'provider':      WEBSITE,
            'languages':     lang,
            'release_title': ep_code,
            'label':         f'{WEBSITE} • {lang} [{q_label}]',
            'size':          'N/A',
            'seeders':       0,
            'extras':        [],
            'headers': (
                f'User-Agent={USER_AGENT}'
                f'&Referer=https%3A%2F%2Fwww.animesup.info%2F'
                f'&Origin=https%3A%2F%2Fwww.animesup.info'
                f'&seekable=0'
            ),
            'manifest_type': '',
        })
    return sources


# ---------------------------------------------------------------------------
# Entry point (padrão Burst)
# ---------------------------------------------------------------------------

def scrape(provider_url, item_data, season=None, episode=None):
    _session.cookies.clear()
    title        = item_data.get('title', '')
    romaji_title = item_data.get('romaji_title', '') or item_data.get('original_title', '')
    media_type   = item_data.get('media_type', 'movie')
    year         = item_data.get('year')
    is_movie     = (media_type == 'movie')

    if not title and not romaji_title:
        return []

    xbmc.log(
        f'[AnimeSup] Buscando: title="{title}" romaji="{romaji_title}" '
        f'media_type={media_type} season={season} episode={episode}',
        xbmc.LOGINFO
    )

    # 1. Obtém mal_id via Jikan
    mal_id = _find_mal_id(title, romaji_title, year)
    if not mal_id:
        xbmc.log(f'[AnimeSup] MAL ID não encontrado para "{title}"', xbmc.LOGWARNING)
        return []

    # 2. Obtém títulos completos do MAL
    base_titles = [title]
    base_year   = year
    try:
        r = _session.get(
            f'https://api.jikan.moe/v4/anime/{mal_id}/full', timeout=10
        )
        if r.ok:
            data        = r.json().get('data', {})
            t_en        = data.get('title_english')
            t_def       = data.get('title')
            syns        = [s.get('title', '') for s in data.get('titles', [])]
            base_titles = [t for t in [t_en, t_def] + syns if t]
            base_year   = data.get('year') or year
    except Exception as e:
        xbmc.log(f'[AnimeSup] Erro ao obter dados MAL {mal_id}: {e}', xbmc.LOGWARNING)

    # 3. Busca no site
    candidates = _search_site(base_titles, base_year)
    if not candidates:
        xbmc.log(f'[AnimeSup] Nenhum resultado no site para {base_titles[:2]}', xbmc.LOGDEBUG)
        return []

    # 4. Itera candidatos e tenta resolver
    seen = set()
    for c in candidates:
        if c['score'] < 0.5:
            break
        if c['url'] in seen:
            continue
        seen.add(c['url'])

        lang = 'DUBLADO' if 'dublado' in c['title'].lower() else 'LEGENDADO'

        try:
            r_page = _session.get(c['url'], timeout=10)
            if not r_page.ok:
                continue

            if is_movie:
                ep_url = _get_movie_episode_url(r_page.text)
            else:
                if season is None or episode is None:
                    continue
                ep_url = _get_episode_url(c['url'], int(episode))

            if not ep_url:
                xbmc.log(f'[AnimeSup] Episódio não encontrado em {c["url"]}', xbmc.LOGDEBUG)
                continue

            streams = _resolve_episode(ep_url)
            if not streams:
                xbmc.log(f'[AnimeSup] Sem stream em {ep_url}', xbmc.LOGDEBUG)
                continue

            xbmc.log(
                f'[AnimeSup] Resolvido: {len(streams)} qualidade(s) {lang}',
                xbmc.LOGINFO
            )
            return _build_sources(streams, lang, media_type, season, episode)

        except Exception as e:
            xbmc.log(f'[AnimeSup] Erro ao processar {c["url"]}: {e}', xbmc.LOGWARNING)

    xbmc.log(f'[AnimeSup] Nenhuma fonte resolvida para "{title}"', xbmc.LOGDEBUG)
    return []