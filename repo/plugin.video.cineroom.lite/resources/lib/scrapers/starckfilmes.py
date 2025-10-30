# Em: resources/lib/scrapers/starckfilmes.py
import re
import requests
import xbmc
import urllib.parse
from urllib.parse import urljoin
import traceback

# --- Imports do Pacote ---
# (Assumindo que você tem session.py e utils.py na mesma pasta)
try:
    from .session import SCRAPER_INSTANCE, HTML_HEADERS
    from .utils import normalize_for_compare, guess_quality_from_name, get_anime_search_codes
except ImportError:
    # Fallback se a estrutura de importação mudar
    from session import SCRAPER_INSTANCE, HTML_HEADERS
    from utils import normalize_for_compare, guess_quality_from_name, get_anime_search_codes

try:
    from bs4 import BeautifulSoup
except ImportError:
    xbmc.log("Modulo BeautifulSoup4 não encontrado! Instale script.module.beautifulsoup4.", xbmc.LOGERROR)
    BeautifulSoup = None

# ####################################################################
# --- SCRAPER STARCKFILMES (VERSÃO BEAUTIFULSOUP FINAL) ---
# ####################################################################
def scrape(provider_url, item_data, season, episode):
    """
    Scraper HTML para o StarckFilmes (VERSÃO TORRENT).
    Usa BeautifulSoup para parsing estruturado, com fallback para Regex.
    Inclui lógica refinada para qualidade e filtro de episódios/season packs.
    """
    log_prefix = "[starckfilmes.scrape-CS]" if 'cloudscraper' in str(type(SCRAPER_INSTANCE)) else "[starckfilmes.scrape-REQ]"

    if not BeautifulSoup:
        xbmc.log(f"{log_prefix} BeautifulSoup não está disponível. Scraper StarckFilmes desativado.", xbmc.LOGERROR)
        return []

    xbmc.log(f"{log_prefix} Iniciando scraper TORRENT (BS4) para {provider_url}", xbmc.LOGINFO)

    try:
        title = item_data.get('title', '').strip()
        original_title = item_data.get('original_title', '').strip()
        year = item_data.get('year')
        media_type = item_data.get('media_type') # 'movie' ou 'tvshow'

        title_no_year = re.sub(r'\s*\(\d{4}\)$', '', title).strip()
        original_title_no_year = re.sub(r'\s*\(\d{4}\)$', '', original_title).strip()
        search_queries = []
        if title_no_year: search_queries.append(title_no_year)
        if original_title_no_year and original_title_no_year.lower() != title_no_year.lower():
            search_queries.append(original_title_no_year)
        if not search_queries:
            xbmc.log(f"{log_prefix} Nenhum título válido para buscar.", xbmc.LOGERROR)
            return []

        content_url = None
        best_partial_match_url = None # Armazena o melhor match parcial de TODAS as buscas

        # --- BUSCA PELO LINK DO CATÁLOGO ---
        for query in search_queries:
            if content_url: break # Se já achou um match exato, para
            
            search_query_encoded = urllib.parse.quote_plus(query)
            search_url = f"{provider_url}/?s={search_query_encoded}"
            xbmc.log(f"{log_prefix} Buscando por '{query}' em: {search_url}", xbmc.LOGDEBUG)

            try:
                response_search = SCRAPER_INSTANCE.get(search_url, headers=HTML_HEADERS, timeout=15)
                response_search.raise_for_status()
                html_search = response_search.content.decode('utf-8', 'ignore')
            except requests.exceptions.RequestException as e:
                xbmc.log(f"{log_prefix} Falha ao BUSCAR '{query}': {e}", xbmc.LOGERROR)
                continue

            matches = re.findall(r'<a\s+href="([^"]+)"\s+title="([^"]+)">', html_search, re.IGNORECASE)
            if not matches: continue

            title_norm = normalize_for_compare(query)
            
            # --- ✅ LÓGICA DE MATCH EXATO/PARCIAL ATUALIZADA ✅ ---
            
            # Prepara os padrões de temporada para procurar
            season_str_long = ""
            season_str_norm = ""
            if media_type == 'tvshow' and season:
                season_str_long = f"{season}ª temporada" # "2ª temporada"
                season_str_norm = normalize_for_compare(season_str_long) # "2temporada"

            for url, title_found in matches:
                if '/catalog/' not in url: continue
                
                title_found_norm = normalize_for_compare(title_found)
                url_norm = normalize_for_compare(url)

                # Condição 1: O título base bate (ex: "strangerthings" in "strangerthings1temporada")
                title_match = title_norm in title_found_norm
                if not title_match: 
                    continue # Se nem o nome bate, pula

                # Condição 2: Verifica o tipo (Filme vs Série)
                if media_type == 'movie':
                    year_match = (not year or str(year) in title_found_norm or str(year) in url_norm)
                    if year_match: 
                        # Para filmes, o primeiro match parcial com ano é bom o suficiente
                        content_url = urljoin(provider_url, url)
                        xbmc.log(f"{log_prefix} ✅ Match de FILME encontrado: {content_url}", xbmc.LOGINFO)
                        break 
                
                elif media_type == 'tvshow':
                    # Procura por "2temporada" no título encontrado
                    season_match = season_str_norm in title_found_norm
                    
                    if season_match: # É uma série E a temporada bate
                        content_url = urljoin(provider_url, url)
                        xbmc.log(f"{log_prefix} ✅ Match de SÉRIE (com temporada {season}) encontrado: {content_url}", xbmc.LOGINFO)
                        break # Achou a temporada certa, para
                    
                    # Se não é a temporada certa, mas é o primeiro match parcial, salva como fallback
                    elif not best_partial_match_url: 
                        best_partial_match_url = urljoin(provider_url, url)
                        xbmc.log(f"{log_prefix} Match PARCIAL de série encontrado (temporada não bateu, S{season} esperado). Salvando como fallback: {best_partial_match_url}", xbmc.LOGDEBUG)

            if content_url:
                break # Sai do loop 'for query' (achou um match com temporada)
            # --- FIM DA LÓGICA DE MATCH ---
        
        # Se NENHUM match com temporada foi encontrado, usa o primeiro match parcial (ex: S1)
        if not content_url and best_partial_match_url:
            content_url = best_partial_match_url
            xbmc.log(f"{log_prefix} ⚠️ Match de temporada não encontrado. Usando primeiro match PARCIAL: {content_url}", xbmc.LOGWARNING)

        if not content_url:
            xbmc.log(f"{log_prefix} Títulos {search_queries} não encontrados nos resultados da busca.", xbmc.LOGINFO)
            return []

        # --- ACESSA A PÁGINA DE CONTEÚDO ---
        xbmc.log(f"{log_prefix} Acessando página de conteúdo: {content_url}", xbmc.LOGDEBUG)
        try:
            response_content = SCRAPER_INSTANCE.get(content_url, headers=HTML_HEADERS, timeout=15)
            response_content.raise_for_status()
            html_content = response_content.content.decode('utf-8', 'ignore')
        except requests.exceptions.RequestException as e:
            xbmc.log(f"{log_prefix} Falha ao ACESSAR CONTEÚDO: {e}", xbmc.LOGERROR)
            return []

        # --- PARSEANDO COM BEAUTIFULSOUP ---
        soup = BeautifulSoup(html_content, 'html.parser')
        all_magnets = []

        ep_patterns_to_check = []
        if media_type == 'tvshow' and season is not None and episode is not None:
            ep_patterns_to_check = get_anime_search_codes(season, episode)
            ep_patterns_to_check = [normalize_for_compare(pat) for pat in ep_patterns_to_check]
            xbmc.log(f"{log_prefix} Filtrando por padrões de episódio: {ep_patterns_to_check}", xbmc.LOGDEBUG)

        # Tenta encontrar a estrutura de TV ('epsodios')
        download_sections = soup.find_all('div', class_='epsodios')
        
        # Se não achou 'epsodios', tenta a estrutura de Filmes/Packs ('post-buttons')
        if not download_sections:
            xbmc.log(f"{log_prefix} Nenhuma seção 'div.epsodios' encontrada. Procurando estrutura 'post-buttons'.", xbmc.LOGDEBUG)
            movie_section = soup.find('div', class_='post-buttons')
            
            # --- ✅ CORREÇÃO PARA O HTML DE STRANGER THINGS S2 ✅ ---
            # O HTML que você mandou tem 'post-buttons', mas os links estão em 'buttons-content'
            if movie_section:
                 download_sections = movie_section.find_all('div', class_='buttons-content')
                 if not download_sections:
                     download_sections = [movie_section] # Usa o 'post-buttons' como seção
            # --- FIM DA CORREÇÃO ---
            else:
                xbmc.log(f"{log_prefix} Nenhuma seção 'div.post-buttons' encontrada.", xbmc.LOGWARNING)
                # Fallback FINAL para Regex
                magnet_matches_fallback = re.findall(r'<a[^>]+href="(magnet:[^"]+)"[^>]*>(.*?)</a>', html_content, re.IGNORECASE)
                if not magnet_matches_fallback:
                    xbmc.log(f"{log_prefix} Fallback Regex também não encontrou links.", xbmc.LOGERROR)
                    return []
                xbmc.log(f"{log_prefix} Usando Regex fallback como último recurso...", xbmc.LOGDEBUG)
                download_sections = [{'html': html_content, 'fallback': True}]

        # Itera sobre as seções encontradas
        for section in download_sections:
            section_languages = 'PT-BR'
            section_subs = None
            is_fallback = section.get('fallback', False) if isinstance(section, dict) else False

            magnet_links = [] # Lista para guardar os links encontrados

            if not is_fallback:
                # --- Lógica BeautifulSoup ---
                heading = section.find(['h3', 'strong'])
                # O HTML de S2 não tem <h3>, então pegamos o texto de 'span.text'
                if not heading:
                    span_text = section.find_all('span', class_='text')
                    if span_text:
                        # Concatena os textos para adivinhar a língua (ex: "Dual Áudio Download 720p")
                        heading_text = " ".join([s.get_text(strip=True) for s in span_text]).upper()
                else:
                    heading_text = heading.get_text(strip=True).upper()

                if heading_text:
                    if 'LEGENDADO' in heading_text:
                        section_languages = 'EN'
                        section_subs = 'PT-BR'
                    elif 'DUAL ÁUDIO' in heading_text or 'DUAL' in heading_text:
                        section_languages = 'PT-BR, EN'
                    elif 'NACIONAL' in heading_text:
                        section_languages = 'PT-BR'

                magnet_links_bs = section.find_all('a', href=lambda href: href and href.startswith('magnet:'))
                if not magnet_links_bs: continue

                for link_tag in magnet_links_bs:
                    parent_p = link_tag.find_parent('p')
                    ep_text_node = parent_p.find('strong') if parent_p else None
                    ep_text = ep_text_node.get_text(strip=True) if ep_text_node else ""
                    
                    # Pega o texto de qualidade da nova estrutura
                    quality_text_node = link_tag.find_parent().find('span', class_='text')
                    quality_text = quality_text_node.get_text(" ", strip=True) if quality_text_node else link_tag.get_text(strip=True)
                    
                    magnet_links.append( (link_tag, ep_text, quality_text) ) # (tag, ep_text, quality_text)
            else:
                # --- Lógica Fallback (Regex) ---
                magnet_links_regex = re.findall(r'<a[^>]+href="(magnet:[^"]+)"[^>]*>(.*?)</a>', section['html'], re.IGNORECASE)
                # (tag=None, ep_text=Regex Group 2, quality_text=Regex Group 2)
                magnet_links = [ (None, match[1].strip() if len(match)>1 else "", match[1].strip() if len(match)>1 else "", match[0]) for match in magnet_links_regex ]

            
            # --- Processa cada link encontrado ---
            for magnet_data in magnet_links:
                magnet_url = ""
                quality_text = ""
                episode_text_from_html = ""
                
                try:
                    if not is_fallback: # Modo BeautifulSoup
                        link_tag = magnet_data[0]
                        episode_text_from_html = magnet_data[1]
                        quality_text = magnet_data[2] # Texto de qualidade (ex: "Dual Áudio Download 720p")
                        magnet_url = link_tag['href']
                    else: # Modo Fallback (Regex)
                        magnet_url = magnet_data[3]
                        episode_text_from_html = magnet_data[1] # regex group 2
                        quality_text = magnet_data[1] # regex group 2
                except (AttributeError, KeyError, IndexError, TypeError) as e:
                    xbmc.log(f"{log_prefix} Erro ao extrair dados do link: {e} | Data: {magnet_data}", xbmc.LOGWARNING)
                    continue

                if not magnet_url.startswith('magnet:'): continue

                current_ep_numbers = []
                if episode_text_from_html: # Se for estrutura de TV (epsodios)
                    numbers = re.findall(r'\d+', episode_text_from_html)
                    try:
                        if len(numbers) == 1: current_ep_numbers.append(int(numbers[0]))
                        elif len(numbers) >= 2:
                            current_ep_numbers = list(range(int(numbers[0]), int(numbers[-1]) + 1))
                    except ValueError: pass

                # --- 3. Monta o release_title ---
                episode_part = ""
                if media_type == 'tvshow' and season is not None and episode is not None and current_ep_numbers:
                    if len(current_ep_numbers) > 1:
                        episode_part = f" S{season:02d}E{current_ep_numbers[0]:02d}-E{current_ep_numbers[-1]:02d}"
                    elif len(current_ep_numbers) == 1:
                        episode_part = f" S{season:02d}E{current_ep_numbers[0]:02d}"

                dn_match = re.search(r'&dn=([^&]+)', magnet_url)
                dn_title = ""
                if dn_match:
                    dn_title = urllib.parse.unquote_plus(dn_match.group(1)).replace('.', ' ')

                if dn_title:
                    base_title = dn_title
                elif episode_part or quality_text:
                    lang_part = section_languages.split(',')[0].strip() if section_languages else ""
                    # Usa o 'quality_text' (que tem mais info) em vez do título do ano
                    base_title = f"{title_no_year}{episode_part} {quality_text} {lang_part}"
                else:
                    base_title = f"{title_no_year}{episode_part} Torrent"

                release_title = " ".join(base_title.split())

                # --- 4. Adivinha a Qualidade ---
                # Usa o 'release_title' primeiro (pois o DN= ou o 'span.text' são mais ricos)
                quality = guess_quality_from_name(release_title)
                if not quality or quality == 'HD':
                    # Tenta o 'quality_text' (que pode ser só "1080p")
                    quality = guess_quality_from_name(" ".join(quality_text.split())) or 'HD'

                xbmc.log(f"{log_prefix} Qualidade final: '{quality}' | Texto Link: '{quality_text}' | Título Base: '{base_title}'", xbmc.LOGDEBUG)

                # --- 5. VERIFICAÇÃO DO EPISÓDIO ---
                release_title_norm = normalize_for_compare(release_title)
                episode_match = False
                if media_type == 'movie':
                    episode_match = True
                elif ep_patterns_to_check: # Se estamos procurando um ep específico
                    for pat in ep_patterns_to_check:
                        if pat in release_title_norm:
                            episode_match = True
                            break
                    if not episode_match:
                        # Se o título não contém S02E01, etc., verifica se é um pack
                        if not re.search(r'(s\d+e\d+|e(?!dgein)\d+|ep\d+|\d+x\d+)', release_title_norm):
                            pack_indicators = [' ao ', 'temporada completa', ' pack ', 'completa'] # Adiciona 'completa'
                            
                            # Verifica o texto do <strong> (para 'epsodios') ou o release_title (para 'post-buttons')
                            text_to_check = episode_text_from_html.lower() if episode_text_from_html else release_title.lower()
                            
                            if any(indicator in text_to_check for indicator in pack_indicators):
                                xbmc.log(f"{log_prefix} Link parece ser Season Pack. Aceitando: {release_title}", xbmc.LOGDEBUG)
                                episode_match = True
                else: 
                    episode_match = True

                # --- 6. Adiciona o magnet_info se der match ---
                if episode_match:
                    label = f"{release_title.strip()} [{quality}]"
                    if section_subs:
                        label += f" +{section_subs}"

                    magnet_info = {
                        'url': magnet_url,
                        'quality': quality,
                        'type': 'Torrent',
                        'release_title': release_title.strip(),
                        'label': label,
                        'size': 'N/A',
                        'peers': 'N/A',
                        'seeders': 'N/A',
                        'provider': 'StarckFilmes',
                        'languages': section_languages,
                        **({'subtitles': section_subs} if section_subs else {})
                    }
                    all_magnets.append(magnet_info)
                    xbmc.log(f"{log_prefix} ✅ Link adicionado: {label}", xbmc.LOGDEBUG)
                else:
                    if ep_patterns_to_check:
                        xbmc.log(f"{log_prefix} Ignorando link (não bate o ep {episode}): {release_title}", xbmc.LOGDEBUG)

        xbmc.log(f"{log_prefix} Encontrados {len(all_magnets)} links magnet (filtrados).", xbmc.LOGINFO)
        return all_magnets

    except Exception as e:
        if 'log_prefix' not in locals():
            log_prefix = "[starckfilmes.scrape-ERR]"
        
        xbmc.log(f"{log_prefix} ❌ ERRO GERAL (BS4): {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
        return []