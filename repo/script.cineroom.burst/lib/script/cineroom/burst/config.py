# -*- coding: utf-8 -*-
"""
Cineroom Burst - Configurações
================================
Gerencia as configurações do Burst, incluindo providers habilitados.
Prioridade, timeout e max_workers são todos configuráveis via settings.xml.
"""

import xbmcaddon

ADDON = xbmcaddon.Addon('script.cineroom.burst')

# ============================================================
# DEFINIÇÃO DE PROVIDERS
# Apenas dados estáticos (URL, setting_id, prioridade padrão).
# A prioridade efetiva é lida das settings em get_enabled_providers().
# ============================================================
PROVIDERS = {
    # --- Link Direto ---
    "NetCine": {
        "url": "https://netcinett.lat",
        "configurable": False,
        "default_priority": 2,
        "setting_id": "provider.netcine.enabled",
        "priority_setting_id": "provider.netcine.priority",
        "type": "direct"
    },
    "GoFlixy": {
        "url": "https://goflixy.lol",
        "configurable": False,
        "default_priority": 2,
        "setting_id": "provider.goflixy.enabled",
        "priority_setting_id": "provider.goflixy.priority",
        "type": "direct"
    },
    "Fenixflix": {
        "url": "https://fenixflix-ur9u.onrender.com",
        "configurable": False,
        "default_priority": 3,
        "setting_id": "provider.fenixflix.enabled",
        "priority_setting_id": "provider.fenixflix.priority",
        "type": "direct"
    },
    "CloutStream": {
        "url": "https://cloutstream.onrender.com",
        "configurable": False,
        "default_priority": 2,
        "setting_id": "provider.cloutstream.enabled",
        "priority_setting_id": "provider.cloutstream.priority",
        "type": "direct"
    },
    "AnimeSup": {
        "url": "https://www.animesup.info",
        "configurable": False,
        "default_priority": 1,
        "setting_id": "provider.animesup.enabled",
        "priority_setting_id": "provider.animesup.priority",
        "type": "direct"
    },
    "Assistirfilme": {
        "url": "https://assistirfilme.net",
        "configurable": False,
        "default_priority": 1,
        "setting_id": "provider.assistirfilme.enabled",
        "priority_setting_id": "provider.assistirfilme.priority",
        "type": "direct"
    },
    "AnimeZey": {
        "url": "https://1.animezey23112022.workers.dev",
        "configurable": False,
        "default_priority": 1,
        "setting_id": "provider.animezey.enabled",
        "priority_setting_id": "provider.animezey.priority",
        "type": "direct"
    },
    # --- Torrent ---
    "Brazuca": {
        "url": "https://94c8cb9f702d-brazuca-torrents.baby-beamup.club",
        "configurable": False,
        "default_priority": 3,
        "setting_id": "provider.brazuca.enabled",
        "priority_setting_id": "provider.brazuca.priority",
        "type": "torrent"
    },
    "Torrentio": {
        "url": "https://torrentio.strem.fun/providers=comando,bludv,micoleaodublado,yts,nyaasi,1337x%7Clanguage=portuguese,english,japanese",
        "configurable": False,
        "default_priority": 2,
        "setting_id": "provider.torrentio.enabled",
        "priority_setting_id": "provider.torrentio.priority",
        "type": "torrent"
    },
    "Mico-Leão": {
        "url": "https://27a5b2bfe3c0-stremio-brazilian-addon.baby-beamup.club",
        "configurable": False,
        "default_priority": 5,
        "setting_id": "provider.mico-leao.enabled",
        "priority_setting_id": "provider.mico-leao.priority",
        "type": "torrent"
    },
    "StarckFilmes": {
        "url": "https://www.starckfilmes-v11.com",
        "configurable": False,
        "default_priority": 1,
        "setting_id": "provider.starckfilmes.enabled",
        "priority_setting_id": "provider.starckfilmes.priority",
        "type": "torrent"
    },
    "ComandoTop": {
        "url": "https://comandofilmestop.site",
        "configurable": False,
        "default_priority": 3,
        "setting_id": "provider.comandotop.enabled",
        "priority_setting_id": "provider.comandotop.priority",
        "type": "torrent"
    },
    "ApacheTorrent": {
        "url": "https://apachetorrent.com",
        "configurable": False,
        "default_priority": 3,
        "setting_id": "provider.apachetorrent.enabled",
        "priority_setting_id": "provider.apachetorrent.priority",
        "type": "torrent"
    },
    "Filmesmaster": {
        "url": "https://filmesmaster.org/",
        "configurable": False,
        "default_priority": 4,
        "setting_id": "provider.filmesmaster.enabled",
        "priority_setting_id": "provider.filmesmaster.priority",
        "type": "torrent"
    },
    "CMD1": {
        "url": "https://cmd1.xyz",
        "configurable": False,
        "default_priority": 4,
        "setting_id": "provider.cmd1.enabled",
        "priority_setting_id": "provider.cmd1.priority",
        "type": "torrent"
    },
}


def _read_priority(provider_data):
    """
    Lê a prioridade efetiva de um provider.
    Tenta ler das settings; se não configurado, usa default_priority.

    Menor número = maior prioridade (1 é o mais prioritário).
    """
    priority_setting_id = provider_data.get('priority_setting_id')
    if priority_setting_id:
        try:
            value = int(float(ADDON.getSetting(priority_setting_id) or 0))
            if value > 0:
                return value
        except (ValueError, TypeError):
            pass
    return provider_data.get('default_priority', 999)


def get_enabled_providers():
    """
    Retorna lista de providers habilitados, com prioridade efetiva injetada.

    Returns:
        list[tuple[str, dict]]: Lista de (nome, dados_do_provider).
        Os dados já incluem a chave 'priority' resolvida das settings.

    Example:
        >>> for name, data in get_enabled_providers():
        ...     print(f"{name}: prioridade={data['priority']}")
    """
    enabled = []
    for name, data in PROVIDERS.items():
        setting_id = data.get('setting_id')
        if setting_id and ADDON.getSettingBool(setting_id):
            # Injeta a prioridade resolvida (setting ou default)
            resolved = dict(data)
            resolved['priority'] = _read_priority(data)
            enabled.append((name, resolved))
    return enabled


def get_all_providers():
    """
    Retorna todos os providers disponíveis com prioridade efetiva.

    Returns:
        dict[str, dict]
    """
    result = {}
    for name, data in PROVIDERS.items():
        resolved = dict(data)
        resolved['priority'] = _read_priority(data)
        result[name] = resolved
    return result


def get_provider_priority(provider_name):
    """
    Retorna a prioridade efetiva de um provider específico.

    Args:
        provider_name (str): Nome do provider.

    Returns:
        int: Prioridade (menor = mais prioritário). 999 se não encontrado.
    """
    data = PROVIDERS.get(provider_name)
    if not data:
        return 999
    return _read_priority(data)


def is_provider_enabled(provider_name):
    """
    Verifica se um provider específico está habilitado.

    Args:
        provider_name (str): Nome do provider.

    Returns:
        bool
    """
    data = PROVIDERS.get(provider_name)
    if not data:
        return False
    setting_id = data.get('setting_id')
    if not setting_id:
        return False
    return ADDON.getSettingBool(setting_id)


def get_scraper_timeout():
    """
    Retorna o timeout configurado para cada provider (em segundos).

    Returns:
        int: Padrão 15s.
    """
    try:
        return max(1, int(float(ADDON.getSetting('scraper.timeout') or 15)))
    except (ValueError, TypeError):
        return 15


def get_max_workers():
    """
    Retorna o número máximo de providers rodando em paralelo.

    Returns:
        int: Padrão 5.
    """
    try:
        return max(1, int(float(ADDON.getSetting('scraper.max_workers') or 5)))
    except (ValueError, TypeError):
        return 5


def is_cache_enabled():
    """
    Verifica se o cache está habilitado.

    Returns:
        bool
    """
    return ADDON.getSettingBool('scraper.cache.enabled')


def get_cache_duration():
    """
    Retorna a duração do cache em segundos.

    Returns:
        int: Padrão 3600 (1 hora).
    """
    try:
        return max(60, int(float(ADDON.getSetting('scraper.cache.duration') or 3600)))
    except (ValueError, TypeError):
        return 3600