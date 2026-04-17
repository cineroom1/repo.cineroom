# -*- coding: utf-8 -*-
import sys

import xbmc
import xbmcaddon
import xbmcplugin

# Variáveis globais (mantidas como antes)
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")

# ============ PROFILE MANAGER - LAZY LOADING ============
_PROFILE_MANAGER = None

def get_profile_manager():
    """Lazy loading do gerenciador de perfis (singleton por execução)."""
    global _PROFILE_MANAGER

    if _PROFILE_MANAGER is None:
        try:
            from resources.lib.profile_manager import ProfileManager
            _PROFILE_MANAGER = ProfileManager()
        except Exception as e:
            xbmc.log(f"[Cineroom] Erro ao inicializar ProfileManager: {e}", xbmc.LOGERROR)
            _PROFILE_MANAGER = False

    return _PROFILE_MANAGER if _PROFILE_MANAGER is not False else None


# ============ SCROBBLER - LAZY LOADING REAL ============
_SCROBBLER = None

def init_scrobbler():
    """Inicializa o monitor de scrobble automático do Trakt (chamado no router)."""
    global _SCROBBLER

    try:
        # Verifica se o scrobbler está ativado nas configurações
        if not ADDON.getSettingBool('trakt_auto_scrobble'):
            if _SCROBBLER:
                del _SCROBBLER
                _SCROBBLER = None
            return None

        # Se já existe, retorna
        if _SCROBBLER is not None:
            return _SCROBBLER

        # Lazy import + criação
        from resources.lib.trakt.trakt_sync import init_trakt_scrobbler
        _SCROBBLER = init_trakt_scrobbler()
        return _SCROBBLER

    except Exception as e:
        xbmc.log(f"[Cineroom] Erro ao inicializar Scrobbler: {e}", xbmc.LOGERROR)
        _SCROBBLER = None
        return None

def get_scrobbler():
    return _SCROBBLER


# ============ SISTEMA DE CACHE OTIMIZADO ============
_MODULE_CACHE = {}
_JSON_CACHE = {}

def get_module(name):
    """Lazy loading ultrarrápido com cache de módulos."""
    if name in _MODULE_CACHE:
        return _MODULE_CACHE[name]

    try:
        # Módulos principais
        if name == 'movies':
            from resources.lib import movies as mod
        elif name == 'tvshows':
            from resources.lib import tvshows as mod
        elif name == 'navigation':
            from resources.lib import navigation as mod
        elif name == 'indexer':
            from resources.lib import indexer as mod
        elif name == 'favorites':
            from resources.lib import favorites as mod
        elif name == 'db':
            from resources.lib.db import db as mod
        elif name == 'constants':
            from resources.lib import constants as mod
        elif name == 'library':
            from resources.lib import library as mod

        # Diálogos
        elif name == 'extras_dialog':
            from resources.lib.dialog import extras_dialog as mod
        elif name == 'donation_window':
            from resources.lib.dialog.donation_window import DonationDialog as mod
        elif name == 'changelog_dialog':
            from resources.lib.dialog.changelog_dialog import ChangelogDialog as mod

        # Funcionalidades
        elif name == 'search':
            from resources.lib.search import search as mod
        elif name == 'playback':
            from resources.lib import playback as mod
        elif name == 'trakt_sync':
            from resources.lib.trakt import trakt_sync as mod

        # Sistema
        elif name == 'xbmcplugin':
            import xbmcplugin as mod
        else:
            return None

        _MODULE_CACHE[name] = mod
        return mod
    except ImportError as e:
        xbmc.log(f"[Cineroom] Falha ao importar {name}: {e}", xbmc.LOGERROR)
        return None


def parse_json(data):
    """Cache inteligente de JSON com LRU simples."""
    if not data:
        return {}

    cached = _JSON_CACHE.get(data)
    if cached is not None:
        return cached

    try:
        from urllib.parse import unquote_plus
        import json
        parsed = json.loads(unquote_plus(data))

        if len(_JSON_CACHE) >= 50:
            _JSON_CACHE.pop(next(iter(_JSON_CACHE)))
        _JSON_CACHE[data] = parsed
        return parsed
    except Exception as e:
        return {}


def end_dir(success=True):
    """Helper para endOfDirectory"""
    xbmcplugin.endOfDirectory(HANDLE, succeeded=success)


def clear_runtime_caches():
    """Limpa caches runtime (útil após troca de perfil)."""
    _MODULE_CACHE.clear()
    _JSON_CACHE.clear()
