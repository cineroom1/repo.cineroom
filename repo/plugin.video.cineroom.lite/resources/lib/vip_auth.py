# -*- coding: utf-8 -*-
"""
vip_auth.py — com rate limiting no cliente + sessão assinada por HMAC.
"""

import xbmc
import xbmcvfs
import xbmcaddon
import json
import time
import os
import hmac
import hashlib
import uuid
from datetime import datetime, timezone, timedelta

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except ImportError:
    from urllib2 import urlopen, Request, URLError, HTTPError

# ============================================================
# CONFIGURAÇÃO
# ============================================================
SUPABASE_URL      = "https://opmakuortoxabzhonxwr.supabase.co"
EDGE_AUTH         = SUPABASE_URL + "/functions/v1/vip-auth"
EDGE_VERIFY       = SUPABASE_URL + "/functions/v1/vip-verify"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9wbWFrdW9ydG94YWJ6aG9ueHdyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA2ODA0NjEsImV4cCI6MjA4NjI1NjQ2MX0.3sof93Xik3XnU4SG0vh3DbMHQqjhrj2wrgOC_VaIdtY"

# ============================================================
# CONFIGURAÇÕES LOCAIS
# ============================================================
VIP_SESSION_FILE   = 'vip_session.json'
DEVICE_SECRET_FILE = 'device_secret.key'
DEVICE_ID_FILE     = 'device_id.txt'
LAST_USERNAME_FILE = 'last_username.txt'
LAST_PASSWORD_FILE = 'last_password.txt'
VIP_SESSION_TTL    = 24 * 3600
VIP_OFFLINE_TTL    = 72 * 3600  # fallback se servidor não retornar offline_ttl

# Rate limiting no cliente
RL_MAX_ATTEMPTS   = 3
RL_WINDOW         = 60
RL_BLOCK_DURATION = 10 * 60


# ============================================================
# AÇÕES VIP
# ============================================================
VIP_ACTIONS = {
    'vip_menu',
    'list_most_searched_movies',
    'list_most_searched_shows',
    'list_4k_movies',
    'list_movie_themes',
    'list_tvshow_themes',
    'trakt_main_menu',
    'trakt_auth',
    'trakt_movies_submenu',
    'trakt_tv_submenu',
    'trakt_watchlist_menu',
    'trakt_collection_menu',
    'trakt_watched_menu',
    'trakt_lists_menu',
    'trakt_sync_menu',
    'movies_vip_menu',
    'tvshows_vip_menu',
    'profile_select',
    'profile_manage',
    'profile_create',
    'profile_menu',
    'library_menu',
    'library_add',
    'library_remove',
}


# ============================================================
# HELPERS DE PATH
# ============================================================

def _profile_dir():
    profile = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
    if not os.path.exists(profile):
        os.makedirs(profile)
    return profile

def _session_path():
    return os.path.join(_profile_dir(), VIP_SESSION_FILE)

def _device_secret_path():
    return os.path.join(_profile_dir(), DEVICE_SECRET_FILE)

def _device_id_path():
    return os.path.join(_profile_dir(), DEVICE_ID_FILE)

def _rl_path():
    return os.path.join(_profile_dir(), 'vip_rl.json')

def _last_user_path():
    return os.path.join(_profile_dir(), LAST_USERNAME_FILE)

def _last_password_path():
    return os.path.join(_profile_dir(), LAST_PASSWORD_FILE)

def _save_last_username(username):
    try:
        with open(_last_user_path(), 'w', encoding='utf-8') as f:
            f.write(username)
    except Exception:
        pass

def _save_last_password(password):
    try:
        with open(_last_password_path(), 'w', encoding='utf-8') as f:
            f.write(password)
    except Exception:
        pass

def get_saved_username():
    try:
        path = _session_path()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            username = data.get('username', '')
            if username:
                return username
    except Exception:
        pass
    try:
        with open(_last_user_path(), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return ''

def get_saved_password():
    # tenta sessão ativa primeiro
    session = _load_session()
    pw = session.get('password', '')
    if pw:
        return pw
    # fallback: arquivo separado (persiste após logout)
    try:
        with open(_last_password_path(), 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return ''

# ============================================================
# RATE LIMITING NO CLIENTE
# ============================================================

def _rl_load():
    try:
        with open(_rl_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _rl_save(data):
    try:
        with open(_rl_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception:
        pass

def _rl_is_blocked():
    data = _rl_load()
    now  = time.time()

    blocked_until = data.get('blocked_until', 0)
    if blocked_until and now < blocked_until:
        return True, int(blocked_until - now)

    window_start = data.get('window_start', 0)
    if now - window_start > RL_WINDOW:
        _rl_save({'attempts': 0, 'window_start': now, 'blocked_until': 0})
        return False, 0

    return False, 0

def _rl_record_attempt(success=False):
    if success:
        _rl_save({'attempts': 0, 'window_start': time.time(), 'blocked_until': 0})
        return

    data = _rl_load()
    now  = time.time()

    window_start = data.get('window_start', now)
    if now - window_start > RL_WINDOW:
        window_start = now

    attempts = data.get('attempts', 0) + 1
    blocked_until = 0

    if attempts >= RL_MAX_ATTEMPTS:
        blocked_until = now + RL_BLOCK_DURATION

    _rl_save({
        'attempts':      attempts,
        'window_start':  window_start,
        'blocked_until': blocked_until,
    })


# ============================================================
# DEVICE SECRET + HMAC
# ============================================================

def _get_device_secret():
    path = _device_secret_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                secret = f.read().strip()
            if len(secret) == 64:
                return secret
        except Exception:
            pass
    secret = uuid.uuid4().hex + uuid.uuid4().hex
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(secret)
    except Exception as e:
        xbmc.log('[VIP] Erro ao salvar device secret: ' + str(e), xbmc.LOGERROR)
    return secret

def _get_device_id():
    path = _device_id_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                v = f.read().strip()
            if v and len(v) >= 8:
                return v
        except Exception:
            pass

    v = str(uuid.uuid4())
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(v)
    except Exception:
        pass
    return v

def _sha256_hex(s):
    try:
        return hashlib.sha256(s.encode('utf-8')).hexdigest()
    except Exception:
        return ''

def _sign_session(payload: dict) -> str:
    secret  = _get_device_secret().encode('utf-8')
    message = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hmac.new(secret, message, hashlib.sha256).hexdigest()

def _verify_session_signature(data: dict) -> bool:
    stored_sig = data.pop('sig', None)
    if not stored_sig:
        return False
    expected_sig = _sign_session(data)
    valid = hmac.compare_digest(stored_sig, expected_sig)
    data['sig'] = stored_sig
    return valid


# ============================================================
# HTTP
# ============================================================

def _http_post_verify(url, access_token, timeout=8):
    try:
        body = json.dumps({}).encode('utf-8')
        req  = Request(url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', 'Bearer ' + access_token)
        req.add_header('apikey', SUPABASE_ANON_KEY)
        req.add_header('Accept', 'application/json')
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        try:
            return json.loads(e.read().decode('utf-8'))
        except Exception:
            return {'error': 'http_error', 'status': e.code}
    except URLError:
        return None
    except Exception:
        return None


def _http_post_edge(url, payload, timeout=8):
    try:
        body = json.dumps(payload).encode('utf-8')
        req  = Request(url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', 'Bearer ' + SUPABASE_ANON_KEY)
        req.add_header('apikey', SUPABASE_ANON_KEY)
        req.add_header('Accept', 'application/json')
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        try:
            body = json.loads(e.read().decode('utf-8'))
            if e.code == 429:
                _rl_record_attempt(success=False)
            return body
        except Exception:
            return None
    except URLError:
        return None
    except Exception:
        return None


# ============================================================
# PARSE DE DATA
# ============================================================

def _parse_expires_at(expires_at_str):
    if not expires_at_str:
        return None
    try:
        dt_str = expires_at_str.replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(dt_str)
        except AttributeError:
            dt_str = dt_str[:19]
            return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ============================================================
# SESSÃO LOCAL
# ============================================================

def _load_session():
    path = _session_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return {}
    if not _verify_session_signature(data):
        _clear_session()
        return {}
    return data

def _save_session(username, password=None, access_token=None, expires_in=None, vip_expires_at=None,
                  offline_ttl=None, offline_expires_at=None, streams_url=None, streams_token=None):
    now = time.time()
    token_exp = 0
    try:
        if expires_in:
            token_exp = now + int(expires_in)
    except Exception:
        token_exp = 0

    _save_last_username(username)

    payload = {
        'username':           username,
        'password':           password,
        'auth_ts':            now,
        'token':              access_token,
        'token_exp':          token_exp,
        'vip_expires_at':     vip_expires_at,
        'offline_ttl':        int(offline_ttl) if offline_ttl else None,
        'offline_expires_at': offline_expires_at,
        'streams_url':        streams_url,
        'streams_token':      streams_token,
    }

    payload['sig'] = _sign_session(payload)
    try:
        with open(_session_path(), 'w', encoding='utf-8') as f:
            json.dump(payload, f)
    except Exception as e:
        xbmc.log('[VIP] Erro ao salvar sessão: ' + str(e), xbmc.LOGERROR)

def is_session_valid():
    session = _load_session()
    if not session:
        return False

    token     = session.get('token')
    token_exp = session.get('token_exp', 0)

    if token and time.time() < token_exp:
        vip_expires_at = session.get('vip_expires_at')
        if vip_expires_at:
            exp_dt = _parse_expires_at(vip_expires_at)
            if exp_dt and datetime.now(timezone.utc) >= exp_dt:
                _clear_session()
                return False
        return True

    if token:
        try:
            ok, status = verify_session(force=True)
            if ok:
                xbmc.log('[VIP] Token renovado automaticamente.', xbmc.LOGINFO)
                return True
        except Exception:
            pass

    # Fallback offline
    username = session.get('username')
    if username:
        ok, _ = _try_offline_session(username)
        if ok:
            xbmc.log('[VIP] Usando modo offline.', xbmc.LOGINFO)
            return True

    return False

def get_current_vip_user():
    session = _load_session()
    if not session:
        return ''

    username = session.get('username', '')
    if not username:
        return ''

    if session.get('token') and time.time() < session.get('token_exp', 0):
        return username

    try:
        ok, _ = verify_session(force=False)
        if ok:
            return _load_session().get('username', '') or username
    except Exception:
        pass

    ok, _ = _try_offline_session(username)
    if ok:
        return username

    return ''

def get_vip_expiry_str():
    session = _load_session()
    vip_expires_at = session.get('vip_expires_at')
    if not vip_expires_at:
        return 'Vitalício'
    exp_dt = _parse_expires_at(vip_expires_at)
    if not exp_dt:
        return 'Vitalício'
    return exp_dt.strftime('%d/%m/%Y')


# ============================================================
# SESSÃO OFFLINE
# ============================================================

def _try_offline_session(username):
    session = _load_session()
    if not session:
        return False, 'offline'

    if session.get('username') != username:
        return False, 'offline'

    if not session.get('token'):
        return False, 'offline'

    now = time.time()

    offline_expires_at = session.get('offline_expires_at')
    if offline_expires_at:
        exp_dt = _parse_expires_at(offline_expires_at)
        if exp_dt:
            if datetime.now(timezone.utc) >= exp_dt:
                return False, 'offline'
        else:
            offline_expires_at = None

    if not offline_expires_at:
        offline_ttl = session.get('offline_ttl')
        auth_ts = session.get('auth_ts', 0)

        if offline_ttl and auth_ts:
            try:
                if now >= float(auth_ts) + int(offline_ttl):
                    return False, 'offline'
            except Exception:
                pass
        else:
            if now >= session.get('auth_ts', 0) + VIP_OFFLINE_TTL:
                return False, 'offline'

    vip_expires_at = session.get('vip_expires_at')
    if vip_expires_at:
        exp_dt = _parse_expires_at(vip_expires_at)
        if exp_dt and datetime.now(timezone.utc) >= exp_dt:
            return False, 'vip_expired'

    remaining = int(session.get('token_exp', 0)) - int(time.time())

    _save_session(
        username,
        password=session.get('password'),
        access_token=session.get('token'),
        expires_in=remaining if remaining > 0 else 7 * 24 * 3600,
        vip_expires_at=vip_expires_at,
        offline_ttl=session.get('offline_ttl'),
        offline_expires_at=session.get('offline_expires_at'),
        streams_url=session.get('streams_url'),
        streams_token=session.get('streams_token'),
    )
    return True, 'offline_cached'


# ============================================================
# AUTENTICAÇÃO
# ============================================================

def authenticate(username, password):
    username = username.strip().lower()
    if not username or not password:
        return False, 'empty_fields'

    blocked, seconds_left = _rl_is_blocked()
    if blocked:
        return False, 'rate_limited'

    device_id = _get_device_id()
    payload = {
        'username':      username,
        'password':      password,
        'password_hash': _sha256_hex(password),
        'device_id':     device_id,
        'device_name':   xbmc.getInfoLabel('System.FriendlyName') or 'Kodi',
    }
    resp = _http_post_edge(EDGE_AUTH, payload)

    if resp is None:
        return _try_offline_session(username)

    error = resp.get('error')
    if error:
        if error == 'rate_limited':
            _rl_record_attempt(success=False)
            return False, 'rate_limited'
        if error == 'device_limit_reached':
            return False, 'device_limit_reached'
        if error == 'missing_device_id':
            return False, 'missing_device_id'
        if error == 'vip_expired':
            return False, 'vip_expired'
        if error in ('wrong_password', 'not_found', 'empty_fields'):
            _rl_record_attempt(success=False)
            return False, error
        _rl_record_attempt(success=False)
        return False, 'wrong_password'

    if resp.get('ok'):
        access_token       = resp.get('access_token')
        expires_in         = resp.get('expires_in')
        if expires_in is None:
            expires_in = 24 * 3600
        vip_exp            = resp.get('vip_expires_at')
        offline_ttl        = resp.get('offline_ttl') or resp.get('off_exp')
        offline_expires_at = resp.get('offline_expires_at')

        if not access_token:
            _rl_record_attempt(success=False)
            return False, 'wrong_password'

        _save_session(username,
                      password=password,
                      access_token=access_token,
                      expires_in=expires_in,
                      vip_expires_at=vip_exp,
                      offline_ttl=offline_ttl,
                      offline_expires_at=offline_expires_at,
                      streams_url=resp.get('streams_url'),
                      streams_token=resp.get('streams_token'))
        # persiste credenciais separado — sobrevive ao logout
        _save_last_password(password)
        _rl_record_attempt(success=True)
        return True, 'ok'

    return False, 'wrong_password'


def _clear_session():
    path = _session_path()
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


def logout():
    _clear_session()
    # last_username.txt e last_password.txt são preservados intencionalmente


def verify_session(force=False):
    session = _load_session()
    if not session or not session.get('token'):
        return False, 'no_session'

    # Cache local de 6h — reduz chamadas, mas mantém UX boa
    if (not force) and (time.time() - session.get('auth_ts', 0) < 6 * 3600):
        return True, 'cached'

    resp = _http_post_verify(EDGE_VERIFY, session.get('token'))

    if resp is None:
        # Servidor inacessível — usa offline_ttl/offline_expires_at
        now = time.time()

        offline_expires_at = session.get('offline_expires_at')
        if offline_expires_at:
            exp_dt = _parse_expires_at(offline_expires_at)
            if exp_dt and datetime.now(timezone.utc) < exp_dt:
                return True, 'offline_cached'
            return False, 'offline'

        offline_ttl = session.get('offline_ttl')
        auth_ts     = session.get('auth_ts', 0)
        if offline_ttl and auth_ts:
            try:
                if now < float(auth_ts) + int(offline_ttl):
                    return True, 'offline_cached'
            except Exception:
                pass

        if now < session.get('auth_ts', 0) + VIP_OFFLINE_TTL:
            return True, 'offline_cached'

        return False, 'offline'

    if resp.get('ok'):
        new_token = resp.get('access_token') or session.get('token')
        expires_in = resp.get('expires_in') or 7 * 24 * 3600

        offline_ttl = resp.get('offline_ttl')
        if offline_ttl is None:
            offline_ttl = resp.get('off_exp') or session.get('offline_ttl')

        offline_expires_at = resp.get('offline_expires_at') or session.get('offline_expires_at')

        vip_exp = (
            resp.get('vip_expires_at')
            or (resp.get('user') or {}).get('expires_at')
            or session.get('vip_expires_at')
        )

        _save_session(
            session.get('username', ''),
            password=session.get('password'),
            access_token=new_token,
            expires_in=expires_in,
            vip_expires_at=vip_exp,
            offline_ttl=offline_ttl,
            offline_expires_at=offline_expires_at,
            streams_url=resp.get('streams_url') or session.get('streams_url'),
            streams_token=resp.get('streams_token') or session.get('streams_token'),
        )
        return True, 'ok'

    err = resp.get('error') or 'invalid_token'

    fatal_errors = {
        'invalid_token',
        'invalid_token_claims',
        'device_not_found',
        'device_revoked',
        'token_stale_password_changed',
        'user_not_found',
        'user_inactive',
        'vip_expired',
    }

    if err in fatal_errors:
        _clear_session()

    return False, err


# ============================================================
# VERIFICAÇÃO DE ACESSO
# ============================================================

def requires_vip(action):
    return action in VIP_ACTIONS

def check_vip_access(action):
    if not requires_vip(action):
        return True

    return is_session_valid()


# ============================================================
# TELA DE BOAS-VINDAS
# ============================================================

def show_welcome_screen():
    try:
        from resources.lib.router.handlers.vip import WelcomeDialog
        addon_path = xbmcaddon.Addon().getAddonInfo('path')
        dlg = WelcomeDialog('WelcomeDialog.xml', addon_path, 'Default', '1080i')
        dlg.doModal()
        choice = dlg.choice
        del dlg
        return choice
    except Exception:
        return 'anon'


# ============================================================
# AÇÕES DO USUÁRIO (vip-user Edge Function)
# ============================================================

EDGE_USER = SUPABASE_URL + "/functions/v1/vip-user"


def _get_session_token() -> str:
    session = _load_session()
    if not session:
        return ''

    token = session.get('token', '') or ''
    if not token:
        return ''

    if time.time() < session.get('token_exp', 0):
        return token

    try:
        ok, _ = verify_session(force=True)
        if ok:
            session = _load_session()
            return session.get('token', '') or ''
    except Exception:
        pass

    return ''


def _http_post_user(action: str, extra: dict = None, timeout: int = 10):
    token = _get_session_token()
    if not token:
        return {'error': 'no_session'}

    payload = {'action': action}
    if extra:
        payload.update(extra)

    try:
        body = json.dumps(payload).encode('utf-8')
        req  = Request(EDGE_USER, data=body, method='POST')
        req.add_header('Content-Type',  'application/json')
        req.add_header('Authorization', 'Bearer ' + token)
        req.add_header('apikey',        SUPABASE_ANON_KEY)
        req.add_header('Accept',        'application/json')
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        try:
            return json.loads(e.read().decode('utf-8'))
        except Exception:
            return {'error': 'http_error', 'status': e.code}
    except URLError:
        return None
    except Exception as e:
        xbmc.log(f'[VIP] _http_post_user error: {e}', xbmc.LOGERROR)
        return None


def list_my_devices() -> tuple:
    resp = _http_post_user('list_devices')
    if resp is None:
        return False, 'offline'
    if resp.get('error'):
        return False, resp['error']
    return True, resp.get('devices', [])


def revoke_device(device_id: str) -> tuple:
    if not device_id:
        return False, 'missing_device_id'
    resp = _http_post_user('revoke_device', {'device_id': device_id})
    if resp is None:
        return False, 'offline'
    if resp.get('error'):
        return False, resp['error']
    return True, None


def revoke_all_devices(keep_current: bool = True) -> tuple:
    extra = {'include_current': not keep_current}
    resp = _http_post_user('revoke_all', extra)
    if resp is None:
        return False, 'offline'
    if resp.get('error'):
        return False, resp['error']
    return True, None


def change_password(current_password: str, new_password: str) -> tuple:
    if not current_password or not new_password:
        return False, 'missing_fields'
    resp = _http_post_user('change_password', {
        'current_password': current_password,
        'new_password':     new_password,
    })
    if resp is None:
        return False, 'offline'
    if resp.get('error'):
        return False, resp['error']
    return True, None


def fetch_vip_streams_cached(tmdb_id: int, media_type: str = 'movie', cache_hours: int = 6):
    """
    Busca streams VIP do repositório privado, com cache local de cache_hours horas.
    """
    try:
        from resources.lib.db import db

        cache_key = f"vip_streams_{tmdb_id}_{media_type}"
        cached = db.get_tmdb_cache(cache_key, hours=cache_hours)
        if cached is not None:
            return cached

        session       = _load_session()
        streams_url   = session.get('streams_url')
        streams_token = session.get('streams_token')

        if not streams_url or not streams_token:
            return []

        from urllib.request import Request, urlopen
        req = Request(streams_url)
        req.add_header('Authorization', f'token {streams_token}')
        req.add_header('User-Agent', 'Kodi/Cineroom')
        with urlopen(req, timeout=10) as resp:
            all_streams = json.loads(resp.read().decode('utf-8'))

        streams = [
            s for s in all_streams
            if str(s.get('tmdb_id')) == str(tmdb_id)
            and s.get('media_type', 'movie') == media_type
        ]

        db.save_tmdb_cache(cache_key, streams)
        return streams

    except Exception as e:
        xbmc.log(f'[VIP] Erro ao buscar streams remotos: {e}', xbmc.LOGWARNING)
        return []