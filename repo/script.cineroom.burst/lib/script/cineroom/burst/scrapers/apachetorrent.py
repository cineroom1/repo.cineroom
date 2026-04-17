# -*- coding: utf-8 -*-
import re
import urllib.parse
import unicodedata
import xbmc
import requests
from bs4 import BeautifulSoup

from .utils import extract_magnets
from .scraper_config import get_url

_APACHE_BASE = get_url('apachetorrent', fallback='https://apachetorrent.com')

def normalize_text_partial(text):
    if not text:
        return ""
    return text.lower().strip()

def normalize_for_compare(text):
    if not text:
        return ""
    
    text = text.lower()
    
    try:
        text = unicodedata.normalize('NFKD', text)
        text = text.encode('ASCII', 'ignore').decode('utf-8')
    except:
        pass
    
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def clean_query(query):
    if not query:
        return ""
    
    try:
        query = unicodedata.normalize('NFKD', query)
        query = query.encode('ASCII', 'ignore').decode('utf-8')
    except:
        pass
    
    query = query.replace(":", " ")
    query = re.sub(r"[^\w\s]", "", query)
    query = re.sub(r"\s+", "+", query)
    return query.strip()

def search_apache_torrent(query):
    """
    Busca otimizada para o ApacheTorrent.
    """
    query_clean = clean_query(query)
    search_url = f"https://apachetorrent.com/index.php?s={query_clean}"
    
    xbmc.log(f"[apachetorrent] Buscando: '{query}'", xbmc.LOGINFO)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        'Referer': _APACHE_BASE + '/'
    }

    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        xbmc.log(f"[apachetorrent] Status: {response.status_code}", xbmc.LOGINFO)
        
        if response.status_code == 200:
            # Força encoding UTF-8
            response.encoding = 'utf-8'
            return response.content
        else:
            xbmc.log(f"[apachetorrent] Status não OK: {response.status_code}", xbmc.LOGWARNING)
            
    except Exception as e:
        xbmc.log(f"[apachetorrent] Erro na busca: {str(e)}", xbmc.LOGERROR)
    
    return None

def parse_search_results(html):
    """
    Parseia os resultados da busca.
    """
    if not html:
        return []
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        results = soup.find_all("div", class_="capaname")
        
        if results:
            xbmc.log(f"[apachetorrent] Encontrados {len(results)} resultados", xbmc.LOGINFO)
            return results
        else:
            xbmc.log("[apachetorrent] Nenhum resultado encontrado", xbmc.LOGWARNING)
            
    except Exception as e:
        xbmc.log(f"[apachetorrent] Erro ao parsear HTML: {str(e)}", xbmc.LOGERROR)
    
    return []

def find_apache_post_url(html, title, season=None, media_type="movie"):
    """
    Encontra o link do post correspondente.
    """
    if not html:
        return None
    
    results = parse_search_results(html)
    
    if not results:
        return None
    
    title_norm = normalize_for_compare(title)
    xbmc.log(f"[apachetorrent] Buscando: '{title}' -> '{title_norm}'", xbmc.LOGINFO)
    
    for idx, result in enumerate(results):
        # Encontra o link
        link_tag = result.find("a", href=True)
        if not link_tag:
            continue
            
        href = link_tag.get("href", "")
        
        # Extrai título do h2
        h2_tag = result.find("h2")
        if not h2_tag:
            continue
            
        post_title = h2_tag.get_text(strip=True)
        
        # Limpa o título
        post_title = re.sub(r'\s*\(.*?\)', '', post_title)  # Remove (Filme de 2025)
        post_title = re.sub(r'\s*Torrent.*', '', post_title)
        post_title = post_title.strip()
        
        post_norm = normalize_for_compare(post_title)
        
        xbmc.log(f"[apachetorrent] Resultado {idx}: '{post_title}' -> '{post_norm}'", xbmc.LOGDEBUG)
        
        # Verifica correspondência
        if title_norm in post_norm or post_norm in title_norm:
            xbmc.log(f"[apachetorrent] CORRESPONDÊNCIA ENCONTRADA: {post_title}", xbmc.LOGINFO)
            return href
    
    xbmc.log("[apachetorrent] Nenhuma correspondência encontrada", xbmc.LOGWARNING)
    return None

def scrape_apache(provider_url, item_data, season=None, episode=None):
    """
    Scraper principal do ApacheTorrent - VERSÃO FUNCIONAL.
    """
    title = item_data.get("title", "")
    media_type = item_data.get("media_type", "movie")
    year = item_data.get("year", "")
    
    xbmc.log(f"[apachetorrent] === SCRAPER INICIADO ===", xbmc.LOGINFO)
    xbmc.log(f"[apachetorrent] Título: {title}", xbmc.LOGINFO)
    xbmc.log(f"[apachetorrent] Tipo: {media_type}", xbmc.LOGINFO)
    xbmc.log(f"[apachetorrent] Ano: {year}", xbmc.LOGINFO)
    
    # Monta a query de busca
    query = title
    if year and media_type == "movie":
        query = f"{title} {year}"
    
    xbmc.log(f"[apachetorrent] Query: '{query}'", xbmc.LOGINFO)
    
    # Busca
    html = search_apache_torrent(query)
    if not html:
        # Tenta sem o ano se não encontrar
        if year and query != title:
            xbmc.log(f"[apachetorrent] Tentando sem ano...", xbmc.LOGINFO)
            html = search_apache_torrent(title)
        
        if not html:
            xbmc.log(f"[apachetorrent] Nenhum resultado na busca", xbmc.LOGWARNING)
            return []
    
    # Encontra o link do post
    post_url = find_apache_post_url(html, title, season, media_type)
    
    if not post_url:
        xbmc.log(f"[apachetorrent] Nenhum post encontrado", xbmc.LOGWARNING)
        return []
    
    # Completa a URL se necessário
    if not post_url.startswith('http'):
        if post_url.startswith('/'):
            post_url = _APACHE_BASE + post_url
        else:
            post_url = f'{_APACHE_BASE}/{post_url}'
    
    xbmc.log(f"[apachetorrent] Acessando post: {post_url}", xbmc.LOGINFO)
    
    # Acessa o post
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': _APACHE_BASE + '/'
    }
    
    try:
        response = requests.get(post_url, headers=headers, timeout=15)
        xbmc.log(f"[apachetorrent] Status do post: {response.status_code}", xbmc.LOGINFO)
        
        if response.status_code != 200:
            xbmc.log(f"[apachetorrent] Erro ao acessar post: {response.status_code}", xbmc.LOGWARNING)
            return []
        
        # Extrai os magnets
        magnets = extract_magnets(
            response.content,
            title,
            target_episode=episode,
            season=season,
            media_type=media_type
        )
        
        if magnets:
            xbmc.log(f"[apachetorrent] Sucesso! {len(magnets)} magnets encontrados", xbmc.LOGINFO)
            return magnets
        else:
            xbmc.log(f"[apachetorrent] Nenhum magnet encontrado no post", xbmc.LOGWARNING)
            return []
            
    except Exception as e:
        xbmc.log(f"[apachetorrent] Erro ao acessar post: {str(e)}", xbmc.LOGERROR)
        return []