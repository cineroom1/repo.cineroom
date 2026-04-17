# -*- coding: utf-8 -*-
"""
subtitles.py - Legendas via addon OpenSubtitles PRO (Stremio)
Endpoint: https://opensubtitlesv3-pro.dexter21767.com/{TOKEN}/subtitles/{type}/{imdb_id}.json

Sem API key propria - usa o token de configuracao do addon Stremio.
Retorna arquivos .vtt prontos para uso no Kodi.
"""

import json
import os
import xbmc
import xbmcaddon
import xbmcvfs
import xbmcgui

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except ImportError:
    from urllib2 import urlopen, Request, URLError, HTTPError

ADDON = xbmcaddon.Addon()

BASE_URL = 'https://opensubtitlesv3-pro.dexter21767.com'

# Cache em memoria por sessao
_search_cache = {}

# Ordem de prioridade dos idiomas no topo da lista
_LANG_ORDER = ['pt-br', 'pb', 'pob', 'por-br', 'pt-pt', 'pt', 'por', 'en']

# Segundos para aguardar o video estabilizar antes de aplicar a legenda.
# Streams HLS/torrent ficam bufferizando nos primeiros segundos e o offset
# de tempo pode ficar errado se setSubtitles for chamado muito cedo.
_SUBTITLE_APPLY_DELAY = 3


# -- Helpers -----------------------------------------------------------

def _get_token():
    return ADDON.getSetting('opensubtitles.token').strip()


def _temp_dir():
    path = xbmcvfs.translatePath('special://temp/cineroom_subtitles/')
    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)
    return path


def _fetch(url, timeout=8):
    try:
        req = Request(url)
        req.add_header('User-Agent', 'Kodi/Cineroom')
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        xbmc.log('[Subtitles] Erro ao buscar {}: {}'.format(url, e), xbmc.LOGWARNING)
        return None


def _download_file(url, local_path, timeout=15):
    try:
        req = Request(url)
        req.add_header('User-Agent', 'Kodi/Cineroom')
        with urlopen(req, timeout=timeout) as resp:
            content = resp.read()
        with open(local_path, 'wb') as f:
            f.write(content)
        return True
    except Exception as e:
        xbmc.log('[Subtitles] Erro ao baixar arquivo: {}'.format(e), xbmc.LOGWARNING)
        return False


def _normalize_lang(code):
    """
    Normaliza lang_code para lowercase e mapeia variacoes conhecidas
    para um codigo canonico usado na ordenacao e exibicao.

    IMPORTANTE: a API OpenSubtitles usa 'pt' e 'por' para PT-BR na maioria
    dos casos, nao para PT-PT. Portanto esses codigos ambiguos sao mapeados
    para 'pt-br' por padrao, ja que o publico-alvo do addon e brasileiro.
    Apenas codigos explicitamente de Portugal (pt-pt, por-pt) vao para pt-pt.
    """
    if not code:
        return ''
    c = code.lower().strip()

    # Codigos explicitamente brasileiros
    _br_variants = {'pb', 'pob', 'pt-br', 'por-br', 'ptbr', 'bra', 'pt_br',
                    # 'pt' e 'por' sozinhos sao ambiguos mas a API OpenSubtitles
                    # os usa majoritariamente para conteudo PT-BR
                    'pt', 'por'}

    # Apenas codigos EXPLICITAMENTE de Portugal
    _pt_variants = {'pt-pt', 'por-pt', 'ptpt', 'pt_pt'}

    if c in _br_variants:
        return 'pt-br'
    if c in _pt_variants:
        return 'pt-pt'
    return c


# -- Busca -------------------------------------------------------------

def search_subtitles(item_data):
    """
    Busca legendas para um filme ou serie.
    Retorna lista de dicts com os campos da resposta + 'label' formatado.
    """
    token = _get_token()
    if not token:
        xbmc.log('[Subtitles] Token nao configurado.', xbmc.LOGWARNING)
        return []

    imdb_id    = str(item_data.get('imdb_id') or '').strip()
    media_type = item_data.get('media_type', 'movie')
    season     = item_data.get('season')
    episode    = item_data.get('episode')

    if not imdb_id:
        xbmc.log('[Subtitles] imdb_id ausente - nao e possivel buscar legendas.', xbmc.LOGWARNING)
        return []

    if not imdb_id.startswith('tt'):
        imdb_id = 'tt{}'.format(imdb_id)

    # Monta ID no formato Stremio
    if media_type == 'movie':
        stremio_id = imdb_id
        stype      = 'movie'
    else:
        stremio_id = '{}:{}:{}'.format(imdb_id, season, episode)
        stype      = 'series'

    cache_key = '{}_{}'.format(token, stremio_id)
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    url = '{}/{}/subtitles/{}/{}.json'.format(BASE_URL, token, stype, stremio_id)
    xbmc.log('[Subtitles] Buscando: {}'.format(url), xbmc.LOGINFO)

    resp = _fetch(url)
    if not resp or 'subtitles' not in resp:
        return []

    results = []
    for s in resp['subtitles']:
        sub_url = s.get('url', '')
        if not sub_url:
            continue

        raw_code  = s.get('lang_code', '')
        lang_code = _normalize_lang(raw_code)
        lang_name = _lang_display_name(lang_code)
        title     = s.get('title', '')
        trusted   = s.get('from_trusted', False)

        # Badge simples compativel com todas as skins do Kodi
        trust_badge = ' [COLOR green][verificada][/COLOR]' if trusted else ''
        label = '{}{} | {}'.format(lang_name, trust_badge, _short(title))

        xbmc.log('[Subtitles] raw_code={} -> normalizado={}'.format(raw_code, lang_code), xbmc.LOGDEBUG)

        results.append({
            'id':        s.get('sub_id'),
            'lang_code': lang_code,
            'lang_name': lang_name,
            'title':     title,
            'url':       sub_url,
            'trusted':   trusted,
            'label':     label,
        })

    # Ordena: pt-br primeiro, depois pt-pt, depois o resto
    def _sort_key(s):
        c = s['lang_code']
        try:
            return _LANG_ORDER.index(c)
        except ValueError:
            return 99

    results.sort(key=_sort_key)

    xbmc.log('[Subtitles] {} legenda(s) encontrada(s).'.format(len(results)), xbmc.LOGINFO)
    _search_cache[cache_key] = results
    return results


# -- Download ----------------------------------------------------------

def download_subtitle(subtitle):
    """
    Baixa o arquivo .vtt da legenda e retorna o caminho local.
    """
    url        = subtitle.get('url', '')
    sub_id     = subtitle.get('id', 'unknown')
    filename   = 'subtitle_{}.vtt'.format(sub_id)
    local_path = os.path.join(_temp_dir(), filename)

    if os.path.exists(local_path):
        return local_path

    xbmc.log('[Subtitles] Baixando: {}'.format(url), xbmc.LOGINFO)
    if _download_file(url, local_path):
        return local_path

    return None


# -- Dialog de selecao -------------------------------------------------

def show_subtitle_dialog(item_data):
    """
    Mostra dialog de selecao e retorna caminho local do .vtt escolhido.
    DEVE ser chamado de thread daemon — verifica se player ainda está ativo
    antes de qualquer operação de GUI para evitar deadlock no Windows.
    """
    if not _get_token():
        return None

    monitor = xbmc.Monitor()
    player  = xbmc.Player()

    # Aguarda o player iniciar (máx 10s)
    for _ in range(20):
        if monitor.abortRequested():
            return None
        if player.isPlaying():
            break
        xbmc.sleep(500)
    else:
        return None  # player não iniciou

    subtitles = search_subtitles(item_data)

    # Checa novamente antes do dialog — player pode ter parado durante o _fetch
    if not player.isPlaying() or monitor.abortRequested():
        return None

    if not subtitles:
        xbmcgui.Dialog().notification(
            'Cineroom',
            'Nenhuma legenda encontrada.',
            xbmcgui.NOTIFICATION_INFO,
            3000
        )
        return None

    labels = ['[COLOR gray]Sem legenda[/COLOR]'] + [s['label'] for s in subtitles]
    title  = item_data.get('title') or item_data.get('name') or 'Legendas'

    sel = xbmcgui.Dialog().select('Legendas - {}'.format(title), labels)

    if sel <= 0:
        return None

    chosen     = subtitles[sel - 1]
    local_path = download_subtitle(chosen)

    if not local_path:
        xbmcgui.Dialog().notification(
            'Cineroom',
            'Erro ao baixar legenda.',
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )
        return None

    return local_path


# -- Aplicar ao player -------------------------------------------------

def apply_subtitle_to_player(subtitle_path):
    """
    Aplica o arquivo de legenda ao player.

    Aguarda o player estar reproduzindo e, depois, adiciona um delay
    extra (_SUBTITLE_APPLY_DELAY) para que o stream HLS/torrent estabilize
    antes de chamar setSubtitles — evita offset de sincronizacao no inicio.
    """
    if not subtitle_path or not os.path.exists(subtitle_path):
        return
    try:
        monitor = xbmc.Monitor()
        player  = xbmc.Player()

        # Espera o player iniciar
        for _ in range(10):
            if monitor.abortRequested():
                return
            if player.isPlaying():
                break
            xbmc.sleep(500)

        if not player.isPlaying() or monitor.abortRequested():
            return

        # Delay extra para o stream estabilizar e evitar dessincronizacao
        # Usa sleep em fatias de 500ms para nao bloquear o monitor
        ticks = _SUBTITLE_APPLY_DELAY * 2  # cada tick = 500ms
        for _ in range(ticks):
            if monitor.abortRequested() or not player.isPlaying():
                return
            xbmc.sleep(500)

        if player.isPlaying() and not monitor.abortRequested():
            player.setSubtitles(subtitle_path)
            player.showSubtitles(True)
            xbmc.log('[Subtitles] Legenda aplicada: {}'.format(subtitle_path), xbmc.LOGINFO)
    except Exception as e:
        xbmc.log('[Subtitles] Erro ao aplicar legenda: {}'.format(e), xbmc.LOGERROR)


# -- Limpar temp -------------------------------------------------------

def clear_temp_subtitles():
    try:
        temp = _temp_dir()
        for f in os.listdir(temp):
            if f.endswith('.vtt') or f.endswith('.srt'):
                try:
                    os.remove(os.path.join(temp, f))
                except Exception:
                    pass
    except Exception:
        pass


# -- Display helpers ---------------------------------------------------

def _lang_display_name(code):
    _map = {
        'pt-br': 'Portugues (Brasil)',
        'pt-pt': 'Portugues (Portugal)',
        'en':    'Ingles',
        'es':    'Espanhol',
        'fr':    'Frances',
        'de':    'Alemao',
        'it':    'Italiano',
        'ja':    'Japones',
        'ko':    'Coreano',
        'zh':    'Chines',
        'ar':    'Arabe',
        'ru':    'Russo',
    }
    return _map.get((code or '').lower(), code)


def _short(text, max_len=45):
    if not text:
        return ''
    return text[:max_len] + '...' if len(text) > max_len else text