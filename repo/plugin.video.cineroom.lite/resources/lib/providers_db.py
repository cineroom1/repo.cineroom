# -*- coding: utf-8 -*-

import json
import os
import uuid

import xbmcaddon
import xbmc
import xbmcvfs

_ADDON    = xbmcaddon.Addon()
_FILENAME = 'stremio_providers.json'


_DEFAULT_PROVIDERS = [
    
    {
        'name':     'Torrentio',
        'url':      'https://torrentio.strem.fun/providers=yts,1337x,magnetdl,nyaasi,anidex,comando,bludv,micoleaodublado,wolfmax4k|language=portuguese|qualityfilter=unknown|limit=30',
        'type':     'torrent',
        'enabled':  True,
        'priority': 1,
    },
    {
        'name':     'Brazuca',
        'url':      'https://94c8cb9f702d-brazuca-torrents.baby-beamup.club',
        'type':     'torrent',
        'enabled':  True,
        'priority': 2,
    },
]


def _providers_path():
    profile = _ADDON.getAddonInfo('profile')
    profile = xbmcvfs.translatePath(profile)
    return os.path.join(profile, _FILENAME)


def _seed_defaults(path):
    """
    Cria o arquivo com os providers padrão.
    Chamado apenas quando o arquivo ainda não existe.
    """
    providers = [
        {
            'id':       str(uuid.uuid4()),
            'name':     p['name'],
            'url':      p['url'].rstrip('/'),
            'type':     p['type'],
            'enabled':  p['enabled'],
            'priority': p['priority'],
        }
        for p in _DEFAULT_PROVIDERS
    ]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(providers, f, ensure_ascii=False, indent=2)
        xbmc.log('[ProvidersDB] Providers padrão criados.', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[ProvidersDB] Erro ao criar defaults: {e}', xbmc.LOGWARNING)
    return providers


def load_providers():
    """Retorna lista de providers. Nunca lança exceção."""
    path = _providers_path()

    # Primeira execução: semeia os defaults e retorna direto
    if not os.path.exists(path):
        return _seed_defaults(path)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        # Garante campos obrigatórios com defaults
        result = []
        for i, p in enumerate(data):
            if not isinstance(p, dict):
                continue
            if not p.get('url', '').startswith('http'):
                continue
            result.append({
                'id':       p.get('id') or str(uuid.uuid4()),
                'name':     p.get('name') or f'Provider {i + 1}',
                'url':      p['url'].rstrip('/'),
                'type':     p.get('type', 'direct'),
                'enabled':  bool(p.get('enabled', True)),
                'priority': int(p.get('priority', i + 1)),
            })
        return result
    except Exception as e:
        xbmc.log(f'[ProvidersDB] Erro ao carregar: {e}', xbmc.LOGWARNING)
        return []


def save_providers(providers):
    """Salva a lista completa de providers."""
    path = _providers_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(providers, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        xbmc.log(f'[ProvidersDB] Erro ao salvar: {e}', xbmc.LOGERROR)
        return False


def add_provider(name, url, provider_type='direct'):
    """Adiciona um novo provider. Retorna o provider criado ou None se URL duplicada."""
    url = url.strip().rstrip('/')
    if not url.startswith('http'):
        return None

    providers = load_providers()

    # Checa duplicata de URL
    for p in providers:
        if p['url'].lower() == url.lower():
            return None

    new_provider = {
        'id':       str(uuid.uuid4()),
        'name':     name.strip() or url,
        'url':      url,
        'type':     provider_type if provider_type in ('direct', 'torrent') else 'direct',
        'enabled':  True,
        'priority': len(providers) + 1,
    }
    providers.append(new_provider)
    save_providers(providers)
    return new_provider


def remove_provider(provider_id):
    """Remove provider pelo id. Retorna True se removeu."""
    providers = load_providers()
    original_len = len(providers)
    providers = [p for p in providers if p['id'] != provider_id]
    if len(providers) == original_len:
        return False
    # Reordena prioridade após remoção
    for i, p in enumerate(providers):
        p['priority'] = i + 1
    return save_providers(providers)


def toggle_provider(provider_id):
    """Alterna enabled/disabled. Retorna o novo estado ou None se não encontrado."""
    providers = load_providers()
    for p in providers:
        if p['id'] == provider_id:
            p['enabled'] = not p['enabled']
            save_providers(providers)
            return p['enabled']
    return None


def reorder_providers(ordered_ids):
    """
    Reordena providers conforme lista de IDs fornecida.
    IDs ausentes na lista ficam no final mantendo ordem relativa.
    """
    providers = load_providers()
    id_map = {p['id']: p for p in providers}

    reordered = []
    for i, pid in enumerate(ordered_ids):
        if pid in id_map:
            id_map[pid]['priority'] = i + 1
            reordered.append(id_map[pid])

    # Adiciona os que não vieram na lista (edge case)
    for p in providers:
        if p['id'] not in {r['id'] for r in reordered}:
            p['priority'] = len(reordered) + 1
            reordered.append(p)

    return save_providers(reordered)


def get_active_providers():
    """Retorna apenas os providers habilitados, ordenados por prioridade."""
    providers = load_providers()
    return sorted(
        [p for p in providers if p.get('enabled', True)],
        key=lambda x: x.get('priority', 999)
    )


def has_active_providers():
    return len(get_active_providers()) > 0