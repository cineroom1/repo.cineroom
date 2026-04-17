# -*- coding: utf-8 -*-
"""
Scraper Stremio básico para FREE users
Providers pré-configurados + opção de URL customizada
"""
import re
import requests
import xbmc
import xbmcaddon

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# ============================================================
# PROVIDERS PADRÃO (hardcoded, sempre disponíveis)
# Usuário pode desativar nas settings, mas não precisa digitar nada
# ============================================================
STREMIO_PROVIDERS = {
    'Brazuca': {
        'url':      'https://94c8cb9f702d-brazuca-torrents.baby-beamup.club',
        'priority': 2,
        'setting_id': 'provider_brazuca',
        'type':     'torrent',
    },
    'Torrentio': {
        'url':      'https://torrentio.strem.fun/providers=comando,bludv,micoleaodublado,yts,nyaasi,1337x%7Clanguage=portuguese,english,japanese',
        'priority': 4,
        'setting_id': 'provider_torrentio',
        'type':     'torrent',
    },
    'Mico-Leão': {
        'url':      'https://27a5b2bfe3c0-stremio-brazilian-addon.baby-beamup.club',
        'priority': 3,
        'setting_id': 'provider_micoleao',
        'type':     'direct',
    },
    'FENIXFLIX': {
        'url':      'https://fenixflix-ur9u.onrender.com',
        'priority': 1,
        'setting_id': 'provider_fenixflix',
        'type':     'direct',
    },
}

MAX_CUSTOM = 3
_MANIFEST_CACHE = {}


def _get_active_providers():
    """
    Retorna lista de providers ativos, combinando:
    1. Providers padrão que o usuário não desativou
    2. URLs customizadas configuradas pelo usuário
    """
    addon = xbmcaddon.Addon()
    active = []

    # ── Providers padrão ────────────────────────────────────────────────────
    for name, config in STREMIO_PROVIDERS.items():
        setting_id = config.get('setting_id')
        try:
            enabled = addon.getSettingBool(setting_id) if setting_id else True
        except Exception:
            enabled = True

        if enabled:
            active.append({
                'name':     name,
                'url':      config['url'],
                'priority': config['priority'],
                'type':     config.get('type', 'direct'),
            })

    # ── URLs customizadas ────────────────────────────────────────────────────
    for i in range(1, MAX_CUSTOM + 1):
        try:
            url = addon.getSetting(f'custom_url_{i}').strip()
        except Exception:
            url = ''

        if not url or not url.startswith('http'):
            continue

        url  = url.rstrip('/')
        name = f'Custom {i}'
        try:
            custom_name = addon.getSetting(f'custom_name_{i}').strip()
            if custom_name:
                name = custom_name
        except Exception:
            pass

        # Tipo definido pelo usuário nas settings: "Direto" ou "Torrent"
        provider_type = 'direct'
        try:
            type_setting = addon.getSetting(f'custom_type_{i}').strip().lower()
            if type_setting == 'torrent':
                provider_type = 'torrent'
        except Exception:
            pass

        active.append({
            'name':     name,
            'url':      url,
            'priority': 10 + i,
            'type':     provider_type,
        })

    return active


def has_providers_configured():
    """Sempre True pois existem providers padrão (a menos que todos sejam desativados)."""
    return len(_get_active_providers()) > 0


def scrape_all_stremio(item_data, progress_callback=None):
    """
    Scrape sequencial de todos os providers ativos.

    Args:
        item_data (dict): {imdb_id, media_type, season, episode, title, ...}
        progress_callback (callable): fn(current, total, provider_name)

    Returns:
        list[dict]: Lista de fontes encontradas
    """
    imdb_id = item_data.get('imdb_id')
    if not imdb_id:
        return []

    providers = _get_active_providers()
    if not providers:
        xbmc.log('[Cineroom] Nenhum provider ativo.', xbmc.LOGWARNING)
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

        sources = _scrape_provider(
            provider_url=config['url'],
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
            source['priority'] = config['priority']
            all_sources.append(source)
            if source_id:
                seen_ids.add(source_id)

    return all_sources


# Em _scrape_provider, substitui a função inteira:

def _scrape_provider(provider_url, provider_type, imdb_id, media_type,
                     season, episode, item_data):
    """Scrape individual de um provider Stremio."""
    
    # Descobre qual ID usar (imdb ou interno)
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

    return _search_catalog_id(provider_url, media_type, item_data, imdb_id)  # passa item_data inteiro


def _get_id_prefixes(provider_url):
    """
    Lê o manifest do provider e retorna a lista idPrefixes.
    Resultado cacheado em memória para não chamar 2x no mesmo scrape.
    """
    if provider_url in _MANIFEST_CACHE:
        return _MANIFEST_CACHE[provider_url]

    try:
        resp = requests.get(
            f'{provider_url}/manifest.json',
            headers={'User-Agent': USER_AGENT},
            timeout=10,
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
            timeout=10,
        )
        resp.raise_for_status()
        manifest = resp.json()
    except Exception:
        return None

    stremio_type = 'series' if media_type in ('tv', 'tvshow', 'series') else 'movie'
    catalogs = [
        c for c in manifest.get('catalogs', [])
        if c.get('type') == stremio_type
    ]

    if not catalogs:
        return None

    # Títulos para tentar, em ordem de confiabilidade
    title          = item_data.get('title') or item_data.get('name') or ''
    original_title = item_data.get('original_title') or item_data.get('original_name') or ''

    search_titles = []
    for t in (title, original_title):
        t = t.strip()
        if t and t not in search_titles:
            search_titles.append(t)

    import urllib.parse

    for search_term in search_titles:
        xbmc.log(f'[Stremio] Tentando busca com título: "{search_term}"', xbmc.LOGINFO)
        title_encoded = urllib.parse.quote(search_term)

        for catalog in catalogs:
            catalog_id = catalog.get('id', '')
            url = f'{provider_url}/catalog/{stremio_type}/{catalog_id}/search={title_encoded}.json'
            xbmc.log(f'[Stremio] Buscando ID interno: {url}', xbmc.LOGINFO)

            try:
                resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=15)
                resp.raise_for_status()
                metas = resp.json().get('metas', [])
            except Exception as e:
                xbmc.log(f'[Stremio] Erro na busca: {e}', xbmc.LOGWARNING)
                continue

            xbmc.log(f'[Stremio] {len(metas)} resultado(s) em "{catalog_id}" para "{search_term}"', xbmc.LOGINFO)

            for meta in metas:
                meta_id    = meta.get('id', '')
                meta_imdb  = meta.get('imdb_id') or meta.get('imdbId') or ''
                meta_title = (meta.get('name') or meta.get('title') or '').lower()

                # 1. Match por IMDb — mais confiável
                if meta_imdb and meta_imdb == imdb_id:
                    xbmc.log(f'[Stremio] Match IMDb: {meta_id}', xbmc.LOGINFO)
                    return meta_id

                # 2. Match por título exato (case-insensitive)
                if meta_title == search_term.lower():
                    xbmc.log(f'[Stremio] Match título exato: {meta_id}', xbmc.LOGINFO)
                    return meta_id

    xbmc.log(f'[Stremio] ID interno não encontrado para "{title}" / "{original_title}"', xbmc.LOGWARNING)
    return None


def _normalize_stream(stream, provider_type, item_data, media_type, season, episode):
    """
    Normaliza campos de um stream Stremio para exibição consistente.

    Providers diretos (FenixFlix, CDFlix, SkyFlix, etc.):
        name        → nome do provider  ex: "FenixFlix"   (ignorar)
        description → info real         ex: "Embed - Dublado\nAzullog"
          linha 0: qualidade + idioma   ex: "Embed - Dublado", "1080p - Legendado"
          linha 1: grupo/uploader       ex: "Azullog"  (opcional)

    Providers de torrent (Torrentio, Brazuca):
        name        → "Torrentio\n1080p BluRay"
        description → "👤 42 💾 2.1 GB ⚙️ comando"

    Campos escritos no stream:
        release_title  label para o dialog  ex: "Embed • DUB • Azullog"
        audio_label    'DUB' | 'LEG' | 'DUAL' | ''
        quality        '1080p' | '720p' | 'Embed' | ''
        group          uploader/grupo
    """
    description = (stream.get('description') or '').strip()
    name        = (stream.get('name') or '').strip()

    # provider_type vem explícito do config; como fallback detecta por heurística
    # (útil para quando infoHash está presente mesmo em provider marcado como direto)
    is_torrent = (
        provider_type == 'torrent'
        or bool(stream.get('infoHash'))
        or '\n' in name
        or any(k in description for k in ('👤', '💾', '⚙️', 'Seeds', 'Peers'))
    )

    if is_torrent:
        # Qualidade vem na 2ª linha do name: "Torrentio\n1080p BluRay"
        name_lines  = name.split('\n')
        quality_str = name_lines[1].strip() if len(name_lines) > 1 else ''
        quality     = _extract_quality(quality_str) or _extract_quality(description)
        audio_label = _parse_audio_label(description + ' ' + name)
        group       = _extract_torrent_group(description)
    else:
        # Provider direto: tudo no description
        # ex: "Embed - Dublado\nAzullog"  |  "1080p - Legendado\nGrupo"
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
    """Retorna 'DUB', 'LEG', 'DUAL' ou '' com base no texto do stream."""
    t = text.lower()
    # DUAL antes de DUB para evitar falso positivo
    if any(k in t for k in ('dual', 'dublado e legendado', 'dub e leg', 'dual audio')):
        return 'DUAL'
    if any(k in t for k in ('dublado', 'dubbed', 'português', 'portuguese', '🇧🇷', '🇵🇹')):
        return 'DUB'
    if any(k in t for k in ('legendado', 'legenda', 'subtitled', 'sub ')):
        return 'LEG'
    return ''


def _extract_quality(text):
    """Extrai token de qualidade de uma string."""
    for pat in (r'4K', r'2160p', r'1080p', r'720p', r'480p', r'360p',
                r'BluRay', r'BDRip', r'WEBRip', r'WEB-DL', r'HDTV', r'Embed'):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0)
    return ''


def _extract_torrent_group(description):
    """Extrai grupo/uploader da description do Torrentio (após ⚙️)."""
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


def _generate_release_title(item_data, media_type, season, episode):
    title = item_data.get('title', 'Unknown')
    if media_type == 'movie':
        year = item_data.get('year', '')
        return f'{title} ({year})' if year else title
    if season and episode:
        return f'{title} S{season:02d}E{episode:02d}'
    return title