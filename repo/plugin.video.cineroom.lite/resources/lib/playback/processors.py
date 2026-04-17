# -*- coding: utf-8 -*-
"""
Processamento e formatação de streams
"""
import re
import xbmcaddon

ADDON = xbmcaddon.Addon()


def extrair_idiomas_do_titulo(titulo, extras=None, provider=None):
    provedores_br = ['StarckFilmes', 'SkyFlix', 'Brazuca', 'CDFlix',
                     'ComandoTop', 'Mico-Leão', 'AnimeZey', 'Fonte Local']

    if provider in provedores_br:
        t = (titulo or '').lower()
        if 'dual' in t or 'multi' in t:
            return 'DUAL'
        if 'legendado' in t or ' leg' in t:
            return 'LEG'
        return 'PT-BR'

    if not titulo:
        return 'LEG'

    t = titulo.lower()

    has_pt = any(x in t for x in ['dublado', 'portugues', 'português', 'pt-br', ' pt '])
    has_dual = any(x in t for x in ['dual', 'dual audio', 'dublado e legendado', 'dub e leg'])
    has_multi = 'multi' in t

    if has_dual:
        return 'DUAL'
    if has_multi and has_pt:
        return 'DUAL'
    if has_pt:
        return 'PT-BR'

    return 'LEG'


def get_color_seeders(val, stream_type):
    """
    Retorna label colorido e score para seeders
    """
    if stream_type == 'Direto' or val == 999:
        return "[COLOR cyan]LINK DIRETO[/COLOR]", 999
    
    try:
        v = int(val)
        color = "green" if v >= 10 else ("yellow" if v >= 5 else "red")
        return f"[COLOR {color}]{v}[/COLOR]", v
    except:
        return "[COLOR grey]S:0[/COLOR]", 0


def get_color_quality(q):
    """
    Retorna label colorido e score para qualidade
    """
    q = q.upper()
    if '4K' in q or '2160P' in q:
        return f"[COLOR gold]{q}[/COLOR]", 4
    if '1080P' in q:
        return f"[COLOR blue]{q}[/COLOR]", 3
    if '720P' in q:
        return f"[COLOR orange]{q}[/COLOR]", 2
    return f"[COLOR grey]{q}[/COLOR]", 1


def extrair_codec_hdr(raw_title):
    """
    Extrai codec, HDR e source do título
    """
    t = raw_title.lower()

    # Source
    source = ""
    if any(x in t for x in ['web-dl', 'webdl', 'webrip']):
        source = "web-dl"
    elif any(x in t for x in ['bluray', 'blu-ray', 'bdrip', 'bdremux']):
        source = "bluray"
    elif 'hdrip' in t:
        source = "hdrip"
    elif 'dvdrip' in t:
        source = "dvdrip"
    elif '3d' in t:
        source = "3d"
    elif 'cam' in t:
        source = "cam"
    elif re.search(r'\bts\b', t):
        source = "ts"

    # Codec
    codec = ""
    if any(x in t for x in ('h265', 'x265', 'hevc')):
        codec = "HEVC"
    elif any(x in t for x in ('h264', 'x264', 'avc')):
        codec = "AVC"

    # HDR
    hdr = ""
    if 'hdr' in t:
        hdr = "HDR"
    elif '10bit' in t or '10-bit' in t:
        hdr = "10bit"

    return codec, hdr, source


def extrair_audio(raw_title):
    """
    Extrai informações de áudio do título
    """
    t = raw_title.lower()

    # Canais
    canais = ""
    if re.search(r'7[\.\s]?1', t):
        canais = "7.1"
    elif re.search(r'5[\.\s]?1', t):
        canais = "5.1"
    elif re.search(r'2[\.\s]?0', t):
        canais = "2.0"

    # Codec
    codec = ""
    if 'atmos' in t:
        codec = "Atmos"
    elif 'truehd' in t:
        codec = "TrueHD"
    elif 'dts-hd' in t or 'dtshd' in t:
        codec = "DTS-HD"
    elif 'dts' in t:
        codec = "DTS"
    elif 'eac3' in t or 'dd+' in t:
        codec = "DD+"
    elif 'ac3' in t:
        codec = "AC3"
    elif 'aac' in t:
        codec = "AAC"

    return " ".join(x for x in (codec, canais) if x)


def process_single_stream(stream, is_local=False, p_name='Fonte Local', p_priority=999, item_data=None):
    """
    Processa um único stream e retorna dict formatado
    """
    url = stream.get('url') or stream.get('infoHash')
    if not url:
        return None

    raw_title = stream.get('title') or stream.get('name') or ""
    if raw_title and isinstance(raw_title, str):
        try:
            raw_title = raw_title.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass  # já está correto, ignora

    # Limpa título para display
    display_title = raw_title
    display_title = re.sub(r'👤\s*\d+', '', display_title)
    display_title = re.sub(r'S:\s*\d+', '', display_title)
    display_title = re.sub(r'\[\s*\d+\.?\d*\s*(?:GB|MB)\s*\]', '', display_title, flags=re.IGNORECASE)
    display_title = re.sub(r'⚙️\s*[^\n]+$', '', display_title)
    display_title = ' '.join(display_title.split()).strip()
    
    if len(display_title) > 80:
        display_title = display_title[:77] + '...'
    
    # Fallback se vazio
    if not display_title and item_data:
        nome_base = item_data.get('title') or 'Vídeo'
        ano = item_data.get('year') or ''
        if item_data.get('season') and item_data.get('episode'):
            s = str(item_data['season']).zfill(2)
            e = str(item_data['episode']).zfill(2)
            display_title = f"{nome_base} S{s}E{e}"
        else:
            display_title = f"{nome_base} ({ano})" if ano else nome_base

    # Detecta tipo
    if is_local:
        is_torrent = "elementum" in url or stream.get('server_name', '').upper() == 'TORRENT'
        stype = 'Torrent' if is_torrent else 'Direto'
    else:
        force_direct_providers = ('Fenixflix', 'Nuvio')

        if p_name in force_direct_providers:
            stype = 'Direto'
        else:
            stype = stream.get('type', 'Direto')
            if re.match(r'^[a-fA-F0-9]{40}$', url) or url.startswith('magnet:'):
                stype = 'Torrent'

    # Seeders
    seed_match = re.search(r'(?:👤|S:)\s*(\d+)', raw_title)
    s_val = seed_match.group(1) if seed_match else stream.get('seeders', 0)
    if stype == 'Direto':
        s_val = 999

    # Size
    size_match = re.search(r'(\d+(?:\.\d+)?\s*(?:GB|MB))', raw_title, re.IGNORECASE)
    size_str = size_match.group(1) if size_match else stream.get('size', 'N/A')

    # Quality
    q_match = re.search(r'(4K|2160p|1080p|720p)', raw_title, re.IGNORECASE)
    q_str = q_match.group(1).upper() if q_match else str(stream.get('quality', 'HD')).upper()

    # Codec/HDR/Source
    codec, hdr, source = extrair_codec_hdr(raw_title)
    audio = extrair_audio(raw_title)
    video_info = " ".join(x for x in (codec, hdr, audio) if x)

    # Labels coloridos
    seed_label, seed_score = get_color_seeders(s_val, stype)
    qual_label, qual_score = get_color_quality(q_str)

    _LANG_MAP = {'DUB': 'PT-BR', 'LEG': 'LEG', 'DUAL': 'DUAL'}
    raw_lang = (
        stream.get('languages')
        or stream.get('audio_label')
        or extrair_idiomas_do_titulo(raw_title, stream.get('extras', []), p_name)
    )
    languages = _LANG_MAP.get((raw_lang or '').upper(), raw_lang) if raw_lang else 'LEG'

    return {
        'url': url,
        'display_title': display_title,
        'raw_title': raw_title,
        'quality_label': qual_label,
        'seeders_label': seed_label,
        'size': size_str,
        'provider': p_name,
        'languages': languages,
        'codec': codec.lower() if codec else '',
        'hdr': hdr.lower() if hdr else '',
        'audio': audio.lower() if audio else '',
        'source': source,
        'video_info': video_info,
        'p_priority': p_priority,
        'q_score': qual_score,
        's_score': int(s_val),
        'manifest_type': stream.get('manifest_type', ''),
        'headers': stream.get('headers', ''),
        'type': stype,
    }