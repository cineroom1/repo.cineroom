# Em: resources/lib/scrapers/animezey.py
import re
import requests
import json
import xbmc
import traceback
import threading
import unicodedata
import time
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, quote_plus, quote, urljoin, urlencode, parse_qs

# --- Imports do Pacote ---
from .session import USER_AGENT
from .utils import guess_quality_from_name, get_anime_search_codes, format_size, normalize_for_compare

# --- Configurações e Exceções Personalizadas ---
class AnimeZeyScraperError(Exception):
    """Exceção base para o scraper AnimeZey"""
    pass

class RateLimitError(AnimeZeyScraperError):
    """Exceção para limite de requisições"""
    pass

class ScraperConfig:
    """Configurações centralizadas do scraper"""
    MAX_THREADS = 8  # Reduzido para ser mais conservador
    REQUEST_TIMEOUT = 25
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    STOP_WORDS = {
        'a', 'an', 'the', 'e', 'o', 'as', 'os', 'um', 'uma', 'uns', 'umas',
        'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
        'por', 'para', 'com', 'sem', 'sob', 'sobre', 'to', 'of', 'in', 'on',
        'at', 'for', 'from', 'with', 'by', 'and', 'or', 'but', 'até'
    }

# --- Decorators para Retry e Cache ---
def with_retry(max_retries=3, delay=1):
    """Decorator para retry automático em falhas de rede"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.Timeout, 
                       requests.exceptions.ConnectionError,
                       requests.exceptions.ChunkedEncodingError) as e:
                    if attempt == max_retries - 1:
                        raise
                    xbmc.log(f"🔄 Tentativa {attempt + 1}/{max_retries} falhou, aguardando {delay}s...", xbmc.LOGWARNING)
                    time.sleep(delay * (attempt + 1))
                except Exception as e:
                    # Para outros tipos de erro, não faz retry
                    raise
            return None
        return wrapper
    return decorator

# --- Funções Auxiliares Melhoradas ---
@with_retry(max_retries=ScraperConfig.MAX_RETRIES, delay=ScraperConfig.RETRY_DELAY)
def _post_to_animezey(url, payload):
    """Função melhorada para POST requests com retry"""
    headers = {
        "accept": "*/*",
        "accept-language": "pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,mt;q=0.5",
        "content-type": "application/json",
        "sec-ch-ua": "\"Microsoft Edge\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "Referer": url,
        "User-Agent": USER_AGENT
    }
    
    try:
        # Limpar cookie se existir
        headers.pop("Cookie", None)
        
        response = requests.post(url, headers=headers, json=payload, 
                               timeout=ScraperConfig.REQUEST_TIMEOUT)
        response.raise_for_status()
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            xbmc.log(f"[animezey] ❌ Resposta não é JSON de {url}: {e}", xbmc.LOGERROR)
            return None
            
    except requests.exceptions.HTTPError as http_err:
        status = getattr(http_err.response, 'status_code', 'N/A')
        text = getattr(http_err.response, 'text', str(http_err))[:500]
        xbmc.log(f"[animezey] ⚠️ HTTP Error {status} em {url}: {text}", xbmc.LOGWARNING)
        return None
    except requests.exceptions.RequestException as e:
        xbmc.log(f"[animezey] ⚠️ Request Error em {url}: {str(e)}", xbmc.LOGWARNING)
        return None
    except Exception as e:
        xbmc.log(f"[animezey] ❌ Erro Geral em {url}: {str(e)}\n{traceback.format_exc()}", xbmc.LOGERROR)
        return None

def remove_accents(input_str):
    """Remove acentos de forma segura"""
    if not input_str:
        return ""
    try:
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    except Exception:
        return input_str

# --- Classe Principal do Scraper ---
class AnimeZeyScraper:
    """Scraper AnimeZey melhorado com todas as otimizações"""
    
    def __init__(self, provider_url, item_data):
        self.provider_url = provider_url
        self.item_data = item_data
        self.log_prefix = "[animezey.scraper]"
        self.found_files = []
        self.processed_files = set()
        self.lock = threading.Lock()
        
        # Configurações
        self.setup_domains()
        self.setup_item_data()
        
    def setup_domains(self):
        """Configura domínios de forma robusta"""
        try:
            parsed = urlparse(self.provider_url)
            self.search_domain = parsed.netloc or "1.animezey23112022.workers.dev"
            self.download_domain = "animezey16082023.animezey16082023.workers.dev"
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ⚠️ Erro configurando domínios: {e}", xbmc.LOGWARNING)
            self.search_domain = "1.animezey23112022.workers.dev"
            self.download_domain = "animezey16082023.animezey16082023.workers.dev"
    
    def setup_item_data(self):
        """Prepara e valida os dados do item"""
        self.title = self.item_data.get('title', '').strip()
        self.original_title = self.item_data.get('original_title', '').strip()
        self.media_type = self.item_data.get('media_type', '').lower()
        self.year = self.item_data.get('year')
        
        if not self.title:
            raise AnimeZeyScraperError("Item data sem 'title'")
            
        # Preparar dados de episódio se for série
        self.season = self.episode = None
        if self.media_type == 'tvshow':
            try:
                self.season = int(self.item_data.get('season', 1))
                self.episode = int(self.item_data.get('episode', 1))
            except (ValueError, TypeError):
                raise AnimeZeyScraperError("Season/episode inválidos")
    
    def log_performance(self, start_time, step_name, details=""):
        """Log de performance para debugging"""
        elapsed = time.time() - start_time
        message = f"⏱️ {step_name} levou {elapsed:.2f}s"
        if details:
            message += f" | {details}"
        xbmc.log(f"{self.log_prefix} {message}", xbmc.LOGDEBUG)
    
    def _get_base_titles(self):
        """Obtém títulos base para busca"""
        titles = []
        
        title_no_year = re.sub(r'\s*\(\d{4}\)$', '', self.title).strip()
        if title_no_year:
            titles.append(title_no_year)
            
        if self.original_title:
            original_no_year = re.sub(r'\s*\(\d{4}\)$', '', self.original_title).strip()
            if (original_no_year and title_no_year and 
                original_no_year.lower() != title_no_year.lower()):
                titles.append(original_no_year)
            elif not title_no_year and original_no_year:
                titles.append(original_no_year)
                
        return titles
    
    def _remove_stop_words(self, text):
        """Remove stop words do texto"""
        if not text:
            return ""
        words = text.split()
        cleaned = [word for word in words if word.lower() not in ScraperConfig.STOP_WORDS]
        return " ".join(cleaned)
    
    def _process_single_variant(self, variant):
        """Processa uma única variante do título"""
        results = set()
        
        if not variant:
            return results
            
        # Sem pontuação
        no_punct = re.sub(r"[:!',?-]", "", variant)
        no_punct = ' '.join(no_punct.split())
        if no_punct and no_punct != variant:
            results.add(no_punct)
        
        # Com pontos
        if no_punct:
            with_dots = no_punct.replace(" ", ".")
            if with_dots != no_punct:
                results.add(with_dots)
        
        # Sem stop words
        no_stop = self._remove_stop_words(no_punct)
        if no_stop and no_stop != no_punct:
            results.add(no_stop)
            
            # Sem stop words com pontos
            no_stop_dots = no_stop.replace(" ", ".")
            if no_stop_dots != no_stop:
                results.add(no_stop_dots)
        
        return results
    
    def _generate_title_combinations(self, title):
        """Gera combinações para um título específico"""
        variants = set()
        
        if not title:
            return variants
            
        # Original
        variants.add(title)
        
        # Sem acentos
        no_accent = remove_accents(title)
        if no_accent and no_accent != title:
            variants.add(no_accent)
        
        # Processar cada variante base
        for base_variant in list(variants):
            processed = self._process_single_variant(base_variant)
            variants.update(processed)
        
        return variants
    
    def generate_search_variations(self):
        """Gera variações de busca de forma eficiente"""
        start_time = time.time()
        variations = set()
        
        base_titles = self._get_base_titles()
        
        for base_title in base_titles:
            if not base_title:
                continue
                
            title_variants = self._generate_title_combinations(base_title)
            variations.update(title_variants)
        
        # Remover entradas vazias e duplicatas
        final_variations = list(filter(None, variations))
        
        self.log_performance(start_time, "Geração de variações", 
                           f"{len(final_variations)} variações")
        
        return final_variations
    
    def _fetch_page(self, search_query):
        """Busca uma página individual"""
        try:
            search_url = f"https://{self.search_domain}/1:search"
            payload = {"q": search_query}
            
            response = _post_to_animezey(search_url, payload)
            
            if response and 'data' in response and 'files' in response['data']:
                files = response['data'].get('files', [])
                return files
                
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro buscando '{search_query}': {e}", xbmc.LOGERROR)
        
        return []
    
    def _add_new_files(self, files):
        """Adiciona novos arquivos à lista global"""
        new_files = []
        for file_data in files:
            file_id = file_data.get('id')
            if file_id and file_id not in self.processed_files:
                self.processed_files.add(file_id)
                new_files.append(file_data)
                self.found_files.append(file_data)
        return new_files
    
    def generate_search_queries(self, search_names):
        """Gera queries de busca baseadas no tipo de mídia"""
        queries = set()
        
        if self.media_type == 'tvshow':
            ep_codes = get_anime_search_codes(self.season, self.episode)
            
            for search_name in search_names:
                for ep_code in ep_codes:
                    if len(search_name) > 2 and len(search_name) < 50:
                        queries.add(f"{search_name} {ep_code}")
                    elif len(ep_code) > 2:
                        queries.add(ep_code)
                        
        else:  # movie
            for search_name in search_names:
                query = search_name
                if self.year:
                    query += f" {self.year}"
                queries.add(query)
        
        return list(queries)
    
    def parallel_search(self, queries):
        """Busca paralela usando ThreadPoolExecutor"""
        start_time = time.time()
        
        def process_query(query):
            try:
                files = self._fetch_page(query)
                if files:
                    with self.lock:
                        new_files = self._add_new_files(files)
                        if new_files and xbmc.getCondVisibility('System.LogLevel(2)'):
                            xbmc.log(f"{self.log_prefix} ✅ {len(new_files)} novos de '{query}'", xbmc.LOGDEBUG)
                return len(files)
            except Exception as e:
                xbmc.log(f"{self.log_prefix} ❌ Erro em '{query}': {e}", xbmc.LOGERROR)
                return 0
        
        total_files = 0
        with ThreadPoolExecutor(max_workers=ScraperConfig.MAX_THREADS) as executor:
            future_to_query = {executor.submit(process_query, query): query for query in queries}
            
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    file_count = future.result()
                    total_files += file_count
                except Exception as exc:
                    xbmc.log(f"{self.log_prefix} ❌ Query '{query}' gerou exceção: {exc}", xbmc.LOGERROR)
        
        self.log_performance(start_time, "Busca paralela", 
                           f"{len(queries)} queries, {total_files} arquivos")
        
        return total_files
    
    def create_filter_patterns(self):
        """Cria padrões de filtro eficientes"""
        title_no_year = re.sub(r'\s*\(\d{4}\)$', '', self.title).strip()
        original_no_year = re.sub(r'\s*\(\d{4}\)$', '', self.original_title).strip()
        
        filters = {
            'title_strict': normalize_for_compare(title_no_year),
            'original_strict': normalize_for_compare(original_no_year),
            'title_no_stop': normalize_for_compare(self._remove_stop_words(title_no_year)),
            'original_no_stop': normalize_for_compare(self._remove_stop_words(original_no_year)),
            'episode_patterns': []
        }
        
        # Remover filtros vazios
        filters = {k: v for k, v in filters.items() if v}
        
        if self.media_type == 'tvshow':
            filters['episode_patterns'] = [
                normalize_for_compare(pattern) 
                for pattern in get_anime_search_codes(self.season, self.episode)
            ]
        
        return filters
    
    def matches_filters(self, file_name, filters):
        """Verifica se o arquivo corresponde aos filtros"""
        if not file_name:
            return False
            
        file_norm = normalize_for_compare(file_name)
        file_no_stop = normalize_for_compare(self._remove_stop_words(file_name))
        
        # Verificar match de título
        title_filters = [
            filters.get('title_strict'),
            filters.get('original_strict'), 
            filters.get('title_no_stop'),
            filters.get('original_no_stop')
        ]
        title_filters = [f for f in title_filters if f]
        
        title_match = any(file_norm.startswith(filt) or filt in file_norm for filt in title_filters)
        
        if self.media_type == 'tvshow':
            pattern_match = any(pattern in file_norm for pattern in filters['episode_patterns'])
            return pattern_match and title_match
        else:  # movie
            if not title_match:
                return False
            if len(filters.get('title_strict', '')) < 4:
                return False    
                
            if not self.year:
                return True
                
            year_str = str(self.year)
            return year_str in file_name or year_str in file_norm
    
    def build_download_link(self, link_part):
        """Constrói link de download completo"""
        if not link_part or not link_part.startswith('/'):
            return None
            
        try:
            path_part, query_string = link_part.split('?', 1)
            params = parse_qs(query_string)
            
            file_id = params.get('file', [None])[0]
            if not file_id:
                return None
                
            query_params = {'file': file_id}
            
            # Adicionar parâmetros opcionais
            optional_params = ['expiry', 'mac']
            for param in optional_params:
                value = params.get(param, [None])[0]
                if value:
                    query_params[param] = value
            
            encoded_query = urlencode(query_params)
            return f"https://{self.download_domain}{path_part}?{encoded_query}"
            
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ⚠️ Erro construindo link {link_part}: {e}", xbmc.LOGWARNING)
            return None
    
    def filter_and_process_files(self, filters):
        """Filtra e processa os arquivos encontrados"""
        matched_results = []
        seen_links = set()
        valid_extensions = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts')
        
        for file_data in self.found_files:
            file_name = file_data.get('name', '').strip()
            
            # Pular se não for arquivo de vídeo válido
            if (not file_name or 
                file_data.get('mimeType') == 'application/vnd.google-apps.folder' or
                not any(file_name.lower().endswith(ext) for ext in valid_extensions)):
                continue
            
            # Aplicar filtros
            if not self.matches_filters(file_name, filters):
                continue
            
            # Construir link de download
            link_part = file_data.get('link')
            download_link = self.build_download_link(link_part)
            
            if download_link and download_link not in seen_links:
                seen_links.add(download_link)
                
                # Preparar metadados do resultado
                quality = guess_quality_from_name(file_name) or "HD"
                
                if self.media_type == 'tvshow':
                    label = self.item_data.get('episode_title') or file_name
                else:
                    label = file_name
                
                matched_results.append({
                    'url': download_link,
                    'quality': quality,
                    'type': 'Direto',
                    'release_title': file_name,
                    'label': f"{label} [{quality}]",
                    'size': format_size(file_data.get('size', 0)),
                    'peers': 'N/A',
                    'seeders': 'N/A', 
                    'provider': 'Animes Totais',
                    'languages': 'PT-BR'
                })
                
                if xbmc.getCondVisibility('System.LogLevel(2)'):
                    xbmc.log(f"{self.log_prefix} ➡️ Match: {file_name[:60]}...", xbmc.LOGDEBUG)
        
        return matched_results
    
    def scrape(self):
        """Método principal do scraper"""
        start_time = time.time()
        
        try:
            # 1. Gerar variações de busca
            search_names = self.generate_search_variations()
            
            # Log informativo
            search_suffix = f" S{self.season:02d}E{self.episode:02d}" if self.media_type == 'tvshow' else f" ({self.year})" if self.year else ""
            xbmc.log(f"{self.log_prefix} 🔍 Buscando '{self.title}'{search_suffix} - {len(search_names)} variações", xbmc.LOGINFO)
            
            if xbmc.getCondVisibility('System.LogLevel(1)'):
                xbmc.log(f"{self.log_prefix} Variações: {search_names}", xbmc.LOGDEBUG)
            
            # 2. Gerar queries de busca
            queries = self.generate_search_queries(search_names)
            xbmc.log(f"{self.log_prefix} 📊 {len(queries)} queries únicas geradas", xbmc.LOGINFO)
            
            # 3. Busca paralela
            total_files = self.parallel_search(queries)
            
            if not self.found_files:
                xbmc.log(f"{self.log_prefix} ⚠️ Nenhum arquivo encontrado", xbmc.LOGINFO)
                return []
            
            xbmc.log(f"{self.log_prefix} 📁 {len(self.found_files)} arquivos únicos encontrados", xbmc.LOGINFO)
            
            # 4. Filtragem
            filters = self.create_filter_patterns()
            matched_results = self.filter_and_process_files(filters)
            
            # 5. Ordenar resultados por qualidade
            if matched_results:
                quality_order = {'4K': 0, '1080p': 1, '720p': 2, 'HD': 3, 'SD': 4}
                matched_results.sort(key=lambda x: quality_order.get(x['quality'], 99))
                
                result_suffix = f" S{self.season:02d}E{self.episode:02d}" if self.media_type == 'tvshow' else ""
                xbmc.log(f"{self.log_prefix} ✅ {len(matched_results)} links válidos para '{self.title}'{result_suffix}", xbmc.LOGINFO)
            else:
                xbmc.log(f"{self.log_prefix} ❌ Nenhum arquivo correspondeu aos filtros", xbmc.LOGINFO)
            
            self.log_performance(start_time, "Scraping completo", 
                               f"{len(matched_results)} resultados")
            
            return matched_results
            
        except AnimeZeyScraperError as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro do Scraper: {e}", xbmc.LOGERROR)
            return []
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro Geral: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
            return []

# --- Função de Interface Mantida para Compatibilidade ---
def scrape(provider_url, item_data):
    """
    Função de interface para compatibilidade com o sistema existente.
    (VERSÃO MELHORADA) Scraper AnimeZey com todas as otimizações.
    """
    try:
        scraper = AnimeZeyScraper(provider_url, item_data)
        return scraper.scrape()
    except Exception as e:
        xbmc.log(f"[animezey.scrape] ❌ Erro inicializando scraper: {e}", xbmc.LOGERROR)
        return []