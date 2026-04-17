# -*- coding: utf-8 -*-
"""
Scraper Stremio para providers configurados pelo usuário.
Sem providers hardcoded — tudo vem de providers_db.py.

Lógica de scraping idêntica ao antigo stremio_basic.py,
mas _get_active_providers() lê do JSON persistido.
"""
import re
import urllib.parse

import requests
import xbmc

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

_MANIFEST_CACHE = {}


def _strip_manifest(url):
    """
    Garante que provider_url é a URL BASE sem /manifest.json.
    O banco salva URLs com /manifest.json (ex: https://host/config/manifest.json),
    mas _get_id_prefixes e _search_catalog_id concatenam /manifest.json diretamente,
    causando /manifest.json/manifest.json na requisição.
    URLs sem /manifest.json passam intactas.
    """
    url = url.rstrip('/')
    if url.endswith('/manifest.json'):
        url = url[:-len('/manifest.json')]
    return url


# ─────────────────────────────────────────────────────────────────────────────
# Interface pública
# ─────────────────────────────────────────────────────────────────────────────

def has_providers_configured():
    """True se o usuário configurou ao menos um provider ativo."""
    from resources.lib.providers_db import has_active_providers
    return has_active_providers()


def scrape_all_stremio(item_data, progress_callback=None):
    """
    Scrape sequencial de todos os providers ativos configurados pelo usuário.

    Args:
        item_data (dict): {imdb_id, media_type, season, episode, title, ...}
        progress_callback (callable): fn(current, total, provider_name)

    Returns:
        list[dict]: Lista de fontes normalizadas
    """
    imdb_id = item_data.get('imdb_id')
    if not imdb_id:
        return []

    from resources.lib.providers_db import get_active_providers
    providers = get_active_providers()

    if not providers:
        xbmc.log('[Stremio] Nenhum provider configurado.', xbmc.LOGWARNING)
        return []

    media_type  = item_data.get('media_type', 'movie')
    season      = item_data.get('season')
    episode     = item_data.get('episode')
    all_sources = []
    seen_ids    = set()
    total       = len(providers)

    for i, config in enumerate(providers, 1):
        if progress_callback:
            try:
                progress_callback(i, total, config['name'])
            except Exception:
                pass

        # Normaliza URL: remove /manifest.json se presente no banco.
        # _get_id_prefixes e _search_catalog_id concatenam /manifest.json
        # diretamente, então provider_url deve ser sempre a URL base.
        provider_url = _strip_manifest(config['url'])

        sources = _scrape_provider(
            provider_url=provider_url,
            provider_type=config['type'],
            imdb_id=imdb_id,
            media_type=media_type,
            season=season,
            episode=episode,
            item_data=item_data,
        )

        for source in sources:
            source_id = source.get('url') or source.get('infoHash')
            if source_id and source_id in seen_ids:
                continue
            source['provider'] = config['name']
            source['priority'] = config.get('priority', i)
            all_sources.append(source)
            if source_id:
                seen_ids.add(source_id)

    return all_sources


# ─────────────────────────────────────────────────────────────────────────────
# Internals — lógica de scraping
# ─────────────────────────────────────────────────────────────────────────────

def _scrape_provider(provider_url, provider_type, imdb_id, media_type,
                     season, episode, item_data):
    """Scrape individual de um provider Stremio."""
    stream_id = _resolve_stream_id(provider_url, imdb_id, media_type, item_data)
    if not stream_id:
        xbmc.log(f'[Stremio] {provider_url}: não foi possível resolver ID', xbmc.LOGWARNING)
        return []

    endpoints = _build_endpoints(media_type, stream_id, season, episode)
    if not endpoints:
        return []

    streams = []
    for endpoint in endpoints:
        url = f'{provider_url}{endpoint}'
        for stream in _fetch_streams(url):
            stream = _normalize_stream(stream, provider_type, item_data, media_type, season, episode)
            streams.append(stream)
    return streams


def _resolve_stream_id(provider_url, imdb_id, media_type, item_data):
    prefixes = _get_id_prefixes(provider_url)
    xbmc.log(f'[Stremio] {provider_url} idPrefixes={prefixes}', xbmc.LOGINFO)

    if not prefixes or any(p in ('tt', 'tmdb:') for p in prefixes):
        return imdb_id

    title = item_data.get('title') or item_data.get('name') or ''
    if not title:
        xbmc.log(f'[Stremio] {provider_url}: título ausente', xbmc.LOGWARNING)
        return None

    return _search_catalog_id(provider_url, media_type, item_data, imdb_id)


def _get_id_prefixes(provider_url):
    """Lê o manifest e retorna idPrefixes. Resultado cacheado em memória."""
    if provider_url in _MANIFEST_CACHE:
        return _MANIFEST_CACHE[provider_url]

    try:
        resp = requests.get(
            f'{provider_url}/manifest.json',
            headers={'User-Agent': USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        prefixes = resp.json().get('idPrefixes', [])
    except Exception as e:
        xbmc.log(f'[Stremio] Erro ao ler manifest {provider_url}: {e}', xbmc.LOGWARNING)
        prefixes = []

    _MANIFEST_CACHE[provider_url] = prefixes
    return prefixes


def _search_catalog_id(provider_url, media_type, item_data, imdb_id):
    try:
        resp = requests.get(
            f'{provider_url}/manifest.json',
            headers={'User-Agent': USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        manifest = resp.json()
    except Exception:
        return None

    stremio_type = 'series' if media_type in ('tv', 'tvshow', 'series') else 'movie'
    catalogs = [c for c in manifest.get('catalogs', []) if c.get('type') == stremio_type]
    if not catalogs:
        return None

    title          = item_data.get('title') or item_data.get('name') or ''
    original_title = item_data.get('original_title') or item_data.get('original_name') or ''

    search_titles = []
    for t in (title, original_title):
        t = t.strip()
        if t and t not in search_titles:
            search_titles.append(t)

    for search_term in search_titles:
        xbmc.log(f'[Stremio] Buscando: "{search_term}"', xbmc.LOGINFO)
        title_encoded = urllib.parse.quote(search_term)

        for catalog in catalogs:
            catalog_id = catalog.get('id', '')
            url = f'{provider_url}/catalog/{stremio_type}/{catalog_id}/search={title_encoded}.json'

            try:
                resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=15)
                resp.raise_for_status()
                metas = resp.json().get('metas', [])
            except Exception as e:
                xbmc.log(f'[Stremio] Erro na busca: {e}', xbmc.LOGWARNING)
                continue

            for meta in metas:
                meta_id    = meta.get('id', '')
                meta_imdb  = meta.get('imdb_id') or meta.get('imdbId') or ''
                meta_title = (meta.get('name') or meta.get('title') or '').lower()

                if meta_imdb and meta_imdb == imdb_id:
                    xbmc.log(f'[Stremio] Match IMDb: {meta_id}', xbmc.LOGINFO)
                    return meta_id

                if meta_title == search_term.lower():
                    xbmc.log(f'[Stremio] Match título: {meta_id}', xbmc.LOGINFO)
                    return meta_id

    xbmc.log(f'[Stremio] ID não encontrado para "{title}"', xbmc.LOGWARNING)
    return None


def _normalize_stream(stream, provider_type, item_data, media_type, season, episode):
    """
    Normaliza campos de um stream Stremio para exibição consistente.

    Providers diretos: description = "Qualidade - Idioma\nGrupo"
    Providers torrent: name = "Torrentio\n1080p BluRay", description = "👤 42 💾 2.1 GB ⚙️ grupo"
    """
    description = (stream.get('description') or '').strip()
    name        = (stream.get('name') or '').strip()

    is_torrent = (
        provider_type == 'torrent'
        or bool(stream.get('infoHash'))
        or '\n' in name
        or any(k in description for k in ('👤', '💾', '⚙️', 'Seeds', 'Peers'))
    )

    if is_torrent:
        name_lines  = name.split('\n')
        quality_str = name_lines[1].strip() if len(name_lines) > 1 else ''
        quality     = _extract_quality(quality_str) or _extract_quality(description)
        audio_label = _parse_audio_label(description + ' ' + name)
        group       = _extract_torrent_group(description)
    else:
        desc_lines  = description.split('\n')
        first_line  = desc_lines[0].strip()
        group       = desc_lines[1].strip() if len(desc_lines) > 1 else ''
        quality     = _extract_quality(first_line)
        audio_label = _parse_audio_label(first_line)

    parts = [quality or 'Embed']
    if audio_label:
        parts.append(audio_label)
    if group:
        parts.append(group)

    stream['release_title'] = ' • '.join(parts)
    stream['audio_label']   = audio_label
    stream['quality']       = quality or ''
    stream['group']         = group
    return stream


def _parse_audio_label(text):
    t = text.lower()
    if any(k in t for k in ('dual', 'dublado e legendado', 'dub e leg', 'dual audio')):
        return 'DUAL'
    if any(k in t for k in ('dublado', 'dubbed', 'português', 'portuguese', '🇧🇷', '🇵🇹')):
        return 'DUB'
    if any(k in t for k in ('legendado', 'legenda', 'subtitled', 'sub ')):
        return 'LEG'
    return ''


def _extract_quality(text):
    for pat in (r'4K', r'2160p', r'1080p', r'720p', r'480p', r'360p',
                r'BluRay', r'BDRip', r'WEBRip', r'WEB-DL', r'HDTV', r'Embed'):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0)
    return ''


def _extract_torrent_group(description):
    m = re.search(r'⚙️\s*(\S+)', description)
    return m.group(1) if m else ''


def _build_endpoints(media_type, imdb_id, season, episode):
    if media_type == 'movie':
        return [f'/stream/movie/{imdb_id}.json']
    if media_type in ('tv', 'tvshow', 'series'):
        if season is not None and episode is not None:
            return [f'/stream/series/{imdb_id}:{season}:{episode}.json']
    return []


def _fetch_streams(url):
    try:
        resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=20)
        resp.raise_for_status()
        return resp.json().get('streams', [])
    except Exception:
        return []