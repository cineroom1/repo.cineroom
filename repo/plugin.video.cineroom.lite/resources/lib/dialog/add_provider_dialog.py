# -*- coding: utf-8 -*-
"""
add_provider_dialog.py

Configurador guiado de providers Stremio para CineRoom Lite.
Substitui o input de URL manual por menus stepwise — amigável em Android TV.

Providers com template:
  - Torrentio      (fontes, idioma, qualidade, limite, debrid)
  - Nuvio          (multiselect de providers de stream direto)
  - Brazuca        (URL tokenizada + exclusão de fontes)
  - Comet          (instância + debrid obrigatório)
  - MediaFusion    (instância + idioma + tipos de stream)
  - Knightcrawler  (debrid opcional)

Providers sem template: fluxo de URL manual com fetch de manifest.json.

Uso:
    from resources.lib.dialog.add_provider_dialog import open_add_provider_dialog
    open_add_provider_dialog()
"""

import json
import xbmc
import xbmcgui

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except ImportError:
    from urllib2 import urlopen, Request, URLError, HTTPError

from resources.lib.providers_db import add_provider

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

_FETCH_TIMEOUT = 10
_USER_AGENT    = 'CineRoomLite/1.0 (Kodi addon)'


# ─────────────────────────────────────────────────────────────────────────────
# Ponto de entrada
# ─────────────────────────────────────────────────────────────────────────────

def open_add_provider_dialog():
    """Abre o fluxo de adição de provider. Retorna o provider criado ou None."""
    TEMPLATES = [
        ('Torrentio',          _configure_torrentio),
        ('Nuvio',              _configure_nuvio),
        ('Brazuca Torrents',   _configure_brazuca),
        ('Comet',              _configure_comet),
        ('MediaFusion',        _configure_mediafusion),
        ('Knightcrawler',      _configure_knightcrawler),
        ('Outro / URL manual', _configure_manual),
    ]

    labels = [t[0] for t in TEMPLATES]
    sel = xbmcgui.Dialog().select('Escolha o provider', labels)
    if sel < 0:
        return None

    name_hint, configure_fn = TEMPLATES[sel]
    result = configure_fn()
    if result is None:
        return None

    url, provider_type, suggested_name = result

    name = xbmcgui.Dialog().input(
        'Nome do provider',
        defaultt=suggested_name,
        type=xbmcgui.INPUT_ALPHANUM,
    )
    if not name or not name.strip():
        name = suggested_name

    provider = add_provider(name=name.strip(), url=url, provider_type=provider_type)

    if provider is None:
        xbmcgui.Dialog().notification(
            'Duplicado', 'URL já cadastrada', xbmcgui.NOTIFICATION_WARNING, 3000
        )
        return None

    xbmcgui.Dialog().notification(
        'Provider adicionado', provider['name'], xbmcgui.NOTIFICATION_INFO, 2500
    )
    return provider


# ─────────────────────────────────────────────────────────────────────────────
# Torrentio
# ─────────────────────────────────────────────────────────────────────────────

def _configure_torrentio():
    BASE = 'https://torrentio.strem.fun'

    ALL_SOURCES = [
        ('YTS',                  'yts'),
        ('1337x',                '1337x'),
        ('MagnetDL',             'magnetdl'),
        ('NyaaSi',               'nyaasi'),
        ('AniDex',               'anidex'),
        ('Comando (PT)',         'comando'),
        ('BluDV (PT)',           'bludv'),
        ('MiCoLeaoDublado (PT)', 'micoleaodublado'),
        ('Wolfmax4K (PT)',       'wolfmax4k'),
        ('The Pirate Bay',       'thepiratebay'),
        ('KickassTorrent',       'kickasstorrent'),
        ('EZTV',                 'eztv'),
        ('TheRarbg',             'therarbg'),
    ]
    DEFAULT_ON = {
        'yts', '1337x', 'magnetdl', 'nyaasi', 'anidex',
        'comando', 'bludv', 'micoleaodublado', 'wolfmax4k',
    }

    labels    = [s[0] for s in ALL_SOURCES]
    preselect = [i for i, s in enumerate(ALL_SOURCES) if s[1] in DEFAULT_ON]

    sel = xbmcgui.Dialog().multiselect(
        'Fontes de torrent (pré-selecionadas: BR + populares)',
        labels, preselect=preselect,
    )
    if sel is None:
        return None
    sources = [ALL_SOURCES[i][1] for i in sel] if sel else []

    LANGUAGES = [
        ('Português (BR/PT)', 'portuguese'),
        ('Inglês',            'english'),
        ('Espanhol',          'spanish'),
        ('Todos os idiomas',  ''),
    ]
    lang_idx = xbmcgui.Dialog().select('Idioma preferido', [l[0] for l in LANGUAGES])
    if lang_idx < 0:
        return None
    lang = LANGUAGES[lang_idx][1]

    QUALITY_FILTERS = [
        ('Qualidade desconhecida', 'unknown'),
        ('SCR / CAM',             'scr'),
        ('SD',                    'sd'),
        ('480p',                  '480p'),
        ('720p',                  '720p'),
    ]
    qf_sel = xbmcgui.Dialog().multiselect(
        'Excluir qualidades (opcional)',
        [q[0] for q in QUALITY_FILTERS],
        preselect=[0],
    )
    quality_filters = [QUALITY_FILTERS[i][1] for i in qf_sel] if qf_sel else []

    LIMITS = ['5', '10', '15', '25', '50']
    lim_idx = xbmcgui.Dialog().select('Limite de resultados por busca', LIMITS, preselect=2)
    if lim_idx < 0:
        return None
    limit = LIMITS[lim_idx]

    DEBRIDS = [
        ('Sem debrid (magnets diretos)', ''),
        ('Real-Debrid',                  'realdebrid'),
        ('AllDebrid',                    'alldebrid'),
        ('Premiumize',                   'premiumize'),
        ('DebridLink',                   'debridlink'),
        ('TorBox',                       'torbox'),
    ]
    deb_idx = xbmcgui.Dialog().select('Serviço de debrid', [d[0] for d in DEBRIDS])
    if deb_idx < 0:
        return None
    debrid_svc      = DEBRIDS[deb_idx][1]
    debrid_key_part = ''

    if debrid_svc:
        api_key = xbmcgui.Dialog().input(
            f'Chave API do {DEBRIDS[deb_idx][0]}',
            type=xbmcgui.INPUT_ALPHANUM,
        )
        if api_key and api_key.strip():
            debrid_key_part = f'{debrid_svc}={api_key.strip()}'

    parts = []
    if sources:
        parts.append('providers=' + ','.join(sources))
    if lang:
        parts.append('language=' + lang)
    if quality_filters:
        parts.append('qualityfilter=' + ','.join(quality_filters))
    if limit != '5':
        parts.append('limit=' + limit)
    if debrid_key_part:
        parts.append(debrid_key_part)

    config_str = '/'.join(parts) if parts else 'stremio'
    url        = f'{BASE}/{config_str}/manifest.json'
    lang_label     = LANGUAGES[lang_idx][0].split(' ')[0]
    debrid_label   = f' + {DEBRIDS[deb_idx][0].split(" ")[0]}' if debrid_svc else ''
    suggested_name = f'Torrentio {lang_label}{debrid_label}'

    return url, 'torrent', suggested_name


# ─────────────────────────────────────────────────────────────────────────────
# Nuvio
# ─────────────────────────────────────────────────────────────────────────────

def _configure_nuvio():
    """
    URL final: https://nuviostreams.hayd.uk/providers=p1,p2,.../manifest.json
    """
    BASE = 'https://nuviostreams.hayd.uk'

    ALL_PROVIDERS = [
        ('VidZee',      'vidzee'),
        ('VidSrc',      'vidsrc'),
        ('VixSrc',      'vixsrc'),
        ('MP4Hydra',    'mp4hydra'),
        ('UHDMovies',   'uhdmovies'),
        ('Moviesmod',   'moviesmod'),
        ('MoviesDrive', 'moviesdrive'),
        ('4KHDHub',     '4khdhub'),
        ('HDHub4u',     'hdhub4u'),
        ('TopMovies',   'topmovies'),
    ]

    sel = xbmcgui.Dialog().multiselect(
        'Nuvio — selecione os providers ativos',
        [p[0] for p in ALL_PROVIDERS],
        preselect=list(range(len(ALL_PROVIDERS))),  # todos pré-selecionados
    )
    if sel is None:
        return None

    chosen        = [ALL_PROVIDERS[i][1] for i in sel] if sel else [p[1] for p in ALL_PROVIDERS]
    url           = f'{BASE}/providers={",".join(chosen)}/manifest.json'
    return url, 'direct', 'Nuvio'


# ─────────────────────────────────────────────────────────────────────────────
# Brazuca Torrents
# ─────────────────────────────────────────────────────────────────────────────

def _configure_brazuca():
    """
    Brazuca usa subdomínio único por usuário.
    URL padrão: https://xxxx-brazuca-torrents.baby-beamup.club
    Opcionalmente o usuário pode excluir algumas fontes.
    """
    url_input = xbmcgui.Dialog().input(
        'URL do Brazuca  (ex: https://xxxx-brazuca-torrents.baby-beamup.club)',
        defaultt='https://',
        type=xbmcgui.INPUT_ALPHANUM,
    )
    if not url_input or not url_input.strip().startswith('http'):
        if url_input is not None:
            xbmcgui.Dialog().notification(
                'URL inválida', 'Use https://', xbmcgui.NOTIFICATION_WARNING, 3000
            )
        return None

    base = _normalize_base_url(url_input.strip())

    ALL_SOURCES = [
        ('ApacheTorrent',        'apachetorrent'),
        ('BaixaFilmesTorrentHD', 'baixafilmestorrenthd'),
        ('EraiRaws',             'erairaws'),
        ('HDRTorrent',           'hdrtorrent'),
        ('NyaaSi',               'nyaasi'),
        ('RedeTorrent',          'redetorrent'),
        ('VacaTorrent',          'vacatorrent'),
    ]

    excl_sel = xbmcgui.Dialog().multiselect(
        'Excluir fontes (deixe vazio para usar todas)',
        [s[0] for s in ALL_SOURCES],
        preselect=[],
    )
    excluded = [ALL_SOURCES[i][1] for i in excl_sel] if excl_sel else []

    if excluded:
        url = f'{base}/exclude={",".join(excluded)}/manifest.json'
    else:
        url = f'{base}/manifest.json'

    return url, 'torrent', 'Brazuca Torrents'


# ─────────────────────────────────────────────────────────────────────────────
# Comet
# ─────────────────────────────────────────────────────────────────────────────

def _configure_comet():
    INSTANCES = [
        ('comet.elfhosted.com (público)',     'https://comet.elfhosted.com'),
        ('comet.api.davidfain.com (público)', 'https://comet.api.davidfain.com'),
        ('URL própria',                       None),
    ]
    inst_idx = xbmcgui.Dialog().select('Instância do Comet', [i[0] for i in INSTANCES])
    if inst_idx < 0:
        return None

    base = INSTANCES[inst_idx][1]
    if base is None:
        base = xbmcgui.Dialog().input('URL da instância', type=xbmcgui.INPUT_ALPHANUM)
        if not base or not base.strip().startswith('http'):
            xbmcgui.Dialog().notification('URL inválida', '', xbmcgui.NOTIFICATION_WARNING, 2500)
            return None
        base = base.strip().rstrip('/')

    DEBRIDS = [
        ('Real-Debrid', 'realdebrid'),
        ('AllDebrid',   'alldebrid'),
        ('Premiumize',  'premiumize'),
        ('DebridLink',  'debridlink'),
        ('TorBox',      'torbox'),
    ]
    deb_idx = xbmcgui.Dialog().select(
        'Serviço de debrid (obrigatório)', [d[0] for d in DEBRIDS]
    )
    if deb_idx < 0:
        return None

    api_key = xbmcgui.Dialog().input(
        f'Chave API do {DEBRIDS[deb_idx][0]}',
        type=xbmcgui.INPUT_ALPHANUM,
    )
    if not api_key or not api_key.strip():
        xbmcgui.Dialog().notification(
            'Chave obrigatória', 'Comet requer debrid', xbmcgui.NOTIFICATION_WARNING, 3000
        )
        return None

    debrid_svc     = DEBRIDS[deb_idx][1]
    url            = f'{base}/{debrid_svc}/{api_key.strip()}/manifest.json'
    suggested_name = f'Comet + {DEBRIDS[deb_idx][0]}'
    return url, 'torrent', suggested_name


# ─────────────────────────────────────────────────────────────────────────────
# MediaFusion
# ─────────────────────────────────────────────────────────────────────────────

def _configure_mediafusion():
    INSTANCES = [
        ('mediafusion.elfhosted.com (público)', 'https://mediafusion.elfhosted.com'),
        ('URL própria',                          None),
    ]
    inst_idx = xbmcgui.Dialog().select('Instância do MediaFusion', [i[0] for i in INSTANCES])
    if inst_idx < 0:
        return None

    base = INSTANCES[inst_idx][1]
    if base is None:
        base = xbmcgui.Dialog().input('URL da instância', type=xbmcgui.INPUT_ALPHANUM)
        if not base or not base.strip().startswith('http'):
            return None
        base = base.strip().rstrip('/')

    LANGUAGES = [
        ('Português', 'pt'),
        ('Inglês',    'en'),
        ('Espanhol',  'es'),
        ('Todos',     ''),
    ]
    lang_idx = xbmcgui.Dialog().select('Idioma preferido', [l[0] for l in LANGUAGES])
    if lang_idx < 0:
        return None
    lang = LANGUAGES[lang_idx][1]

    STREAM_TYPES = ['torrent', 'debrid', 'live', 'p2p']
    st_sel = xbmcgui.Dialog().multiselect(
        'Tipos de stream habilitados', STREAM_TYPES, preselect=[0, 1]
    )
    streams = [STREAM_TYPES[i] for i in st_sel] if st_sel else STREAM_TYPES[:2]

    params = []
    if lang:
        params.append(f'language={lang}')
    for s in streams:
        params.append(f'streams={s}')

    qs             = '&'.join(params)
    url            = base + (f'?{qs}' if qs else '') + '/manifest.json'
    suggested_name = f'MediaFusion {LANGUAGES[lang_idx][0]}'
    provider_type  = 'torrent' if 'torrent' in streams or 'debrid' in streams else 'direct'
    return url, provider_type, suggested_name


# ─────────────────────────────────────────────────────────────────────────────
# Knightcrawler
# ─────────────────────────────────────────────────────────────────────────────

def _configure_knightcrawler():
    BASE = 'https://knightcrawler.elfhosted.com'

    DEBRIDS = [
        ('Sem debrid',  ''),
        ('Real-Debrid', 'realdebrid'),
        ('AllDebrid',   'alldebrid'),
        ('Premiumize',  'premiumize'),
    ]
    deb_idx = xbmcgui.Dialog().select('Serviço de debrid', [d[0] for d in DEBRIDS])
    if deb_idx < 0:
        return None
    debrid_svc = DEBRIDS[deb_idx][1]
    debrid_key = ''

    if debrid_svc:
        debrid_key = xbmcgui.Dialog().input(
            f'Chave API do {DEBRIDS[deb_idx][0]}',
            type=xbmcgui.INPUT_ALPHANUM,
        )
        if not debrid_key or not debrid_key.strip():
            debrid_key = ''

    if debrid_svc and debrid_key:
        url            = f'{BASE}/{debrid_svc}={debrid_key.strip()}/manifest.json'
        suggested_name = f'Knightcrawler + {DEBRIDS[deb_idx][0]}'
    else:
        url            = f'{BASE}/manifest.json'
        suggested_name = 'Knightcrawler'

    return url, 'torrent', suggested_name


# ─────────────────────────────────────────────────────────────────────────────
# Manual — fallback com fetch de manifest
# ─────────────────────────────────────────────────────────────────────────────

def _configure_manual():
    url_input = xbmcgui.Dialog().input(
        'URL do addon (base, /configure ou /manifest.json)',
        defaultt='https://',
        type=xbmcgui.INPUT_ALPHANUM,
    )
    if not url_input or not url_input.strip().startswith('http'):
        if url_input is not None:
            xbmcgui.Dialog().notification(
                'URL inválida', 'Use http:// ou https://', xbmcgui.NOTIFICATION_WARNING, 3000
            )
        return None

    base         = _normalize_base_url(url_input.strip())
    manifest_url = base + '/manifest.json'
    manifest     = _fetch_manifest(manifest_url)

    if manifest:
        addon_name    = manifest.get('name') or _extract_name_from_url(base)
        provider_type = _detect_provider_type(manifest, base)
        config_defs   = manifest.get('config') or []
        config_values = {}

        if config_defs:
            result = _collect_config_fields(config_defs, addon_name)
            if result is None:
                return None
            config_values = result

        if config_values:
            parts = [f'{k}={v}' for k, v in config_values.items()]
            base  = base + '/' + '|'.join(parts)

        url = base + '/manifest.json'
        return url, provider_type, addon_name

    # Manifest não disponível — salva direto
    tipo_idx = xbmcgui.Dialog().select(
        'Tipo de stream', ['Direto (HTTP / HLS)', 'Torrent / Magnet']
    )
    if tipo_idx < 0:
        return None

    provider_type  = 'torrent' if tipo_idx == 1 else 'direct'
    suggested_name = _extract_name_from_url(base)
    return base + '/manifest.json', provider_type, suggested_name


# ─────────────────────────────────────────────────────────────────────────────
# Coleta dinâmica de campos (fallback manual com manifest.config)
# ─────────────────────────────────────────────────────────────────────────────

def _collect_config_fields(config_defs, addon_name):
    values = {}
    for field in config_defs:
        key      = field.get('key', '')
        title    = field.get('title') or field.get('name') or key
        ftype    = (field.get('type') or 'text').lower()
        required = field.get('required', False)
        default  = field.get('default') or ''
        options  = field.get('options') or []

        dialog_title = f'{addon_name} › {title}'

        if ftype == 'select' and options:
            labels = [str(o) for o in options]
            presel = labels.index(str(default)) if str(default) in labels else 0
            idx    = xbmcgui.Dialog().select(dialog_title, labels, preselect=presel)
            if idx < 0:
                if required:
                    return None
                continue
            values[key] = options[idx]

        elif ftype == 'multiselect' and options:
            labels   = [str(o) for o in options]
            defaults = [str(d) for d in (default if isinstance(default, list) else [default])]
            presel   = [i for i, o in enumerate(options) if str(o) in defaults]
            sel      = xbmcgui.Dialog().multiselect(dialog_title, labels, preselect=presel)
            if sel is None:
                if required:
                    return None
                continue
            values[key] = ','.join(str(options[i]) for i in sel)

        elif ftype in ('checkbox', 'bool'):
            values[key] = 'true' if xbmcgui.Dialog().yesno(dialog_title, title) else 'false'

        else:
            val = xbmcgui.Dialog().input(
                dialog_title + (' (obrigatório)' if required else ' (opcional)'),
                defaultt=str(default),
                type=xbmcgui.INPUT_ALPHANUM,
            )
            if val is None:
                if required:
                    return None
                continue
            if required and not val.strip():
                xbmcgui.Dialog().notification(
                    'Campo obrigatório', title, xbmcgui.NOTIFICATION_WARNING, 2500
                )
                return None
            if val.strip():
                values[key] = val.strip()

    return values


# ─────────────────────────────────────────────────────────────────────────────
# Utilitários
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_base_url(url):
    for suffix in ('/configure', '/manifest.json', '/'):
        if url.endswith(suffix):
            url = url[:-len(suffix)]
    return url


def _fetch_manifest(manifest_url):
    try:
        req = Request(manifest_url, headers={'User-Agent': _USER_AGENT})
        with urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        xbmc.log(f'[CineRoom] Manifest fetch error ({manifest_url}): {e}', xbmc.LOGWARNING)
        return None


def _detect_provider_type(manifest, url):
    torrent_keywords = (
        'torrent', 'magnet', 'torrentio', 'knightcrawler',
        'brazuca', 'comet', 'debrid', '1337x', 'nyaa',
    )
    combined = url.lower() + manifest.get('name', '').lower()
    if any(kw in combined for kw in torrent_keywords):
        return 'torrent'
    if manifest.get('behaviorHints', {}).get('p2p'):
        return 'torrent'
    return 'direct'


def _extract_name_from_url(url):
    try:
        host  = url.split('//')[1].split('/')[0]
        parts = host.split('.')
        if parts[0] == 'www':
            parts = parts[1:]
        return parts[0].capitalize() if parts else host
    except Exception:
        return 'Provider externo'