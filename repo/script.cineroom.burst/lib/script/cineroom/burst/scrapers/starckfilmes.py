# -*- coding: utf-8 -*-
"""
Scraper para Starck Filmes
Suporta 3 tipos de página:
  1. Filme            → <div class="post-buttons"> com <span class="btn-down">
  2. Série completa   → <div class="post-buttons"> com <span class="btn-down">  (ex: ONE PIECE T2)
  3. Série episódios  → <div class="epsodios"> com <p><strong>EPISÓDIO XX:</strong><a data-u="...">
"""
import re
import xbmc
import requests
from bs4 import BeautifulSoup

from .scraper_config import get_url
BASE_URL   = get_url('starckfilmes', fallback='https://www.starckfilmes-v12.com')
SEARCH_URL = BASE_URL + "/?s={query}"
HEADERS    = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    )
}


# ---------------------------------------------------------------------------
# Decodificador do magnet embaralhado
# ---------------------------------------------------------------------------

def unshuffle_string(shuffled):
    try:
        length   = len(shuffled)
        original = [''] * length
        used     = [False] * length
        step     = 3
        index    = 0
        for i in range(length):
            while used[index]:
                index = (index + 1) % length
            used[index]  = True
            original[i]  = shuffled[index]
            index        = (index + step) % length
        return ''.join(original)
    except Exception as e:
        xbmc.log(f"[Starck] unshuffle erro: {e}", xbmc.LOGERROR)
        return None



# ---------------------------------------------------------------------------
# Helpers de validação
# ---------------------------------------------------------------------------

_SERIE_PATTERNS = re.compile(
    r'\b(\d+[aªº°]\s*temporada|temporada\s*\d+|t\d+\b|season\s*\d+|'
    r'episod|completo\s+\d+|parte\s+\d+)\b',
    re.IGNORECASE
)

def _titulo_parece_serie(texto):
    """Retorna True se o título contiver marcadores de série/temporada."""
    return bool(_SERIE_PATTERNS.search(texto or ''))


def _titulo_compativel(titulo_pagina, titulo_busca, is_serie=False):
    """
    Valida se o título da página é compatível com o que foi buscado.
    - is_serie=False (filme): rejeita se o título contiver padrões de série
    - is_serie=True  (série): rejeita se o título não contiver padrão de temporada
      correspondente à temporada buscada (verificação mais fina feita depois)
    """
    if not is_serie and _titulo_parece_serie(titulo_pagina):
        xbmc.log(
            f"[Starck] Rejeitado (série detectada em busca de filme): {titulo_pagina}",
            xbmc.LOGDEBUG
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Helpers de idioma
# ---------------------------------------------------------------------------

def _idioma_do_texto(texto):
    """
    Detecta idioma a partir de qualquer texto livre.
    Retorna 'DUAL', 'DUBLADO', 'LEGENDADO' ou 'PT-BR'.
    """
    t = (texto or '').lower()
    if 'dual' in t:
        return 'DUAL'
    if 'dublado' in t:
        return 'DUBLADO'
    if 'legendado' in t:
        return 'LEGENDADO'
    return 'PT-BR'


def _idioma_btn_down(btn):
    """
    Lê idioma do <span class="text"> dentro de um <span class="btn-down">.
    Estrutura: filhos[0] = "Dual Áudio<strong>MKV</strong>"
    """
    text_span = btn.find('span', class_='text')
    if not text_span:
        return 'PT-BR'
    filhos = text_span.find_all('span', recursive=False)
    if not filhos:
        return 'PT-BR'
    return _idioma_do_texto(filhos[0].get_text(separator=' '))


# ---------------------------------------------------------------------------
# Parsers da página de conteúdo
# ---------------------------------------------------------------------------

def _get_titulo_limpo(soup):
    """<h2 class="post-title"> → título sem sufixos"""
    h2 = soup.find('h2', class_='post-title')
    if h2:
        return h2.get_text(strip=True)
    h1 = soup.find('h1')
    if h1:
        t = h1.get_text(strip=True)
        return re.sub(r'\s*[Tt]orrent.*$', '', t).strip()
    return ''


def _get_ano(soup):
    desc = soup.find('div', class_='post-description')
    if not desc:
        return ''
    for p in desc.find_all('p'):
        spans = p.find_all('span')
        if len(spans) >= 2 and 'lançamento' in spans[0].get_text().lower():
            return spans[1].get_text(strip=True)
    return ''


def _get_qualidade(soup):
    span = soup.find('span', class_='sl-quality')
    if not span:
        return 'HD'
    return {'FHD': '1080p', 'UHD': '4K', 'HD': '720p', 'SD': '480p'}.get(
        span.get_text(strip=True).upper(), span.get_text(strip=True)
    )


def _get_tamanho(soup):
    desc = soup.find('div', class_='post-description')
    if not desc:
        return 'N/A'
    for p in desc.find_all('p'):
        spans = p.find_all('span')
        if len(spans) >= 2 and 'tamanho' in spans[0].get_text().lower():
            return spans[1].get_text(strip=True)
    return 'N/A'


def _parse_btn_down(btn, qualidade_fallback='HD', tamanho_fallback='N/A'):
    """
    Extrai { url, idioma, qualidade, tamanho } de um <span class="btn-down">.
    """
    link = btn.find('a')
    if not link:
        return None
    data_u = link.get('data-u', '')
    if not data_u:
        return None
    magnet = unshuffle_string(data_u)
    if not magnet or 'magnet:' not in magnet:
        return None

    idioma    = _idioma_btn_down(btn)
    qualidade = qualidade_fallback
    tamanho   = tamanho_fallback

    text_span = btn.find('span', class_='text')
    if text_span:
        filhos = text_span.find_all('span', recursive=False)
        if len(filhos) >= 3:
            texto_res = filhos[2].get_text(strip=True)  # "1080p (2.13 GB)"
            m_q = re.search(r'(4K|2160p|1080p|720p|480p)', texto_res, re.IGNORECASE)
            if m_q:
                qualidade = m_q.group(1)
            m_s = re.search(r'\(([^)]+(?:GB|MB))\)', texto_res, re.IGNORECASE)
            if m_s:
                tamanho = m_s.group(1)

    return {'url': magnet, 'idioma': idioma, 'qualidade': qualidade, 'tamanho': tamanho}


# ---------------------------------------------------------------------------
# Busca no site
# ---------------------------------------------------------------------------

def _buscar_paginas(query, max_results=5):
    search_url = SEARCH_URL.format(query=requests.utils.quote(query))
    try:
        r = requests.get(search_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception as e:
        xbmc.log(f"[Starck] Erro na busca: {e}", xbmc.LOGERROR)
        return []

    soup  = BeautifulSoup(r.text, 'html.parser')
    itens = []
    for card in soup.select('.sub-item'):
        a = card.select_one('a.title') or card.find('a', href=re.compile(r'/catalog/'))
        if not a:
            continue
        url    = a.get('href', '')
        titulo = a.get_text(strip=True)
        if url:
            itens.append((titulo, url))
        if len(itens) >= max_results:
            break

    return itens


def _fetch_pagina(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        xbmc.log(f"[Starck] Erro ao carregar {url}: {e}", xbmc.LOGERROR)
        return None


def _ano_ok(soup, ano_esperado):
    if not ano_esperado:
        return True
    try:
        return abs(int(_get_ano(soup)) - int(ano_esperado)) <= 1
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Busca de FILME
# ---------------------------------------------------------------------------

def buscar_filme(item_data):
    titulo          = item_data.get('title', '')
    titulo_original = item_data.get('original_title', '')
    ano             = item_data.get('year', '')

    if not titulo:
        return []

    queries = [titulo]
    if titulo_original and titulo_original.lower() != titulo.lower():
        queries.append(titulo_original)

    sources = []

    for query in queries:
        for _titulo_card, url in _buscar_paginas(query):
            soup = _fetch_pagina(url)
            if not soup or not _ano_ok(soup, ano):
                continue

            titulo_limpo = _get_titulo_limpo(soup) or titulo
            
            if not _titulo_compativel(titulo_limpo, titulo, is_serie=False):
                continue
            
            qualidade    = _get_qualidade(soup)
            tamanho      = _get_tamanho(soup)

            for btn in soup.find_all('span', class_='btn-down'):
                parsed = _parse_btn_down(btn, qualidade, tamanho)
                if not parsed:
                    continue
                stream = {
                    'url':       parsed['url'],
                    'title':     titulo_limpo,
                    'quality':   parsed['qualidade'],
                    'size':      parsed['tamanho'],
                    'type':      'Torrent',
                    'seeders':   0,
                    'extras':    [],
                    'languages': parsed['idioma'],
                }
                sources.append(stream)

            if sources:
                break
        if sources:
            break

    return sources


# ---------------------------------------------------------------------------
# Busca de SÉRIE
# ---------------------------------------------------------------------------

def buscar_serie(item_data, season, episode):
    titulo          = item_data.get('title', '')
    titulo_original = item_data.get('original_title', '')

    if not titulo or season is None or episode is None:
        return []

    s_num = int(season)
    e_num = int(episode)
    s_pad = str(s_num).zfill(2)
    e_pad = str(e_num).zfill(2)

    queries = [titulo]
    if titulo_original and titulo_original.lower() != titulo.lower():
        queries.append(titulo_original)

    sources = []

    for query in queries:
        for _titulo_card, url in _buscar_paginas(query, max_results=8):
            soup = _fetch_pagina(url)
            if not soup:
                continue

            titulo_pagina = _get_titulo_limpo(soup).lower()

            # ----------------------------------------------------------------
            # CASO A: página com <div class="epsodios"> — episódios separados
            # ----------------------------------------------------------------
            epsodios_div = soup.find('div', class_='epsodios')
            if epsodios_div:
                # Verifica se é a temporada certa
                padrao_temporada = re.search(
                    rf'({s_num}[aªº°]?\s*temporada|temporada\s*{s_num})',
                    titulo_pagina, re.IGNORECASE
                )
                if not padrao_temporada:
                    continue

                # Idioma vem do <h3> dentro de epsodios
                # ex: <h3><strong>VERSÃO DUAL ÁUDIO</strong></h3>
                h3 = epsodios_div.find('h3')
                idioma_ep = _idioma_do_texto(h3.get_text() if h3 else '')

                qualidade = _get_qualidade(soup)
                tamanho   = _get_tamanho(soup)
                titulo_limpo = _get_titulo_limpo(soup) or titulo

                for p in epsodios_div.find_all('p'):
                    strong = p.find('strong')
                    if not strong:
                        continue

                    ep_text = strong.get_text().lower()
                    episodio_encontrado = False

                    # "EPISÓDIO 03:" ou "EPISODIO 3:"
                    if re.search(rf'episódios?\s+0?{e_num}\b', ep_text):
                        episodio_encontrado = True

                    # "EPISÓDIOS 01 E 02:" ou "EPISÓDIO 08 ao 09:"
                    if not episodio_encontrado:
                        m = re.search(r'episódios?\s+0?(\d+)\s+(?:e|ao)\s+0?(\d+)', ep_text)
                        if m and int(m.group(1)) <= e_num <= int(m.group(2)):
                            episodio_encontrado = True

                    if not episodio_encontrado:
                        continue


                    link = p.find('a')
                    if not link:
                        continue
                    data_u = link.get('data-u', '')
                    if not data_u:
                        continue
                    magnet = unshuffle_string(data_u)
                    if not magnet or 'magnet:' not in magnet:
                        continue

                    # Qualidade do texto do link: "1080p"
                    q_link = link.get_text(strip=True)
                    m_q = re.search(r'(4K|2160p|1080p|720p|480p)', q_link, re.IGNORECASE)
                    if m_q:
                        qualidade = m_q.group(1)

                    stream = {
                        'url':       magnet,
                        'title':     f"{titulo_limpo} S{s_pad}E{e_pad}",
                        'quality':   qualidade,
                        'size':      tamanho,
                        'type':      'Torrent',
                        'seeders':   0,
                        'extras':    [],
                        'languages': idioma_ep,
                    }
                    sources.append(stream)
                    break  # achou o episódio, sai do loop de parágrafos

                if sources:
                    break
                continue  # não achou o ep nessa página, tenta a próxima

            # ----------------------------------------------------------------
            # CASO B: página com <span class="btn-down"> — temporada inteira
            # ----------------------------------------------------------------
            padrao_temporada = re.search(
                rf'({s_num}[aªº°]?\s*temporada|temporada\s*{s_num})',
                titulo_pagina, re.IGNORECASE
            )
            if not padrao_temporada:
                continue

            titulo_limpo = _get_titulo_limpo(soup) or titulo
            qualidade    = _get_qualidade(soup)
            tamanho      = _get_tamanho(soup)

            for btn in soup.find_all('span', class_='btn-down'):
                parsed = _parse_btn_down(btn, qualidade, tamanho)
                if not parsed:
                    continue
                stream = {
                    'url':       parsed['url'],
                    'title':     titulo_limpo,
                    'quality':   parsed['qualidade'],
                    'size':      parsed['tamanho'],
                    'type':      'Torrent',
                    'seeders':   0,
                    'extras':    [],
                    'languages': parsed['idioma'],
                }
                sources.append(stream)

            if sources:
                break

        if sources:
            break

    return sources


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def scrape(provider_url, item_data, season=None, episode=None):
    xbmc.log("[Starck] Iniciando scraper...", xbmc.LOGINFO)
    media_type = item_data.get('media_type', 'movie')

    if media_type == 'movie':
        return buscar_filme(item_data)
    elif media_type == 'tvshow':
        return buscar_serie(item_data, season, episode)

    return []