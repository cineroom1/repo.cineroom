# -*- coding: utf-8 -*-
# --- Imports Padrões ---
import re
import requests
import json
import xbmc
import traceback
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlencode, parse_qs, quote

# --- Imports do Pacote ---
from .session import USER_AGENT
from .utils import guess_quality_from_name, get_anime_search_codes, format_size, normalize_for_compare

# --- Configurações ---
class ScraperConfig:
    MAX_THREADS = 40
    REQUEST_TIMEOUT = 25
    MAX_RETRIES = 2

# --- Funções Auxiliares ---
def with_retry(max_retries=3, delay=1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.Timeout, 
                       requests.exceptions.ConnectionError) as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator

@with_retry(max_retries=ScraperConfig.MAX_RETRIES, delay=1)
def _post_to_animezey(url, payload):
    headers = {
        "accept": "*/*",
        "accept-language": "pt-BR,pt;q=0.9",
        "content-type": "application/json",
        "Referer": url,
        "User-Agent": USER_AGENT
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, 
                               timeout=ScraperConfig.REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        xbmc.log(f"[animezey] Erro em {url}: {str(e)}", xbmc.LOGWARNING)
        return None

# --- Classe Principal ---
class AnimeZeyScraper:
    def __init__(self, provider_url, item_data):
        self.provider_url = provider_url
        self.item_data = item_data
        self.log_prefix = "[animezey]"
        
        self.setup_item_data()
        self.setup_domains()
        
        self.found_files = []
        self.processed_files = set()
        self.lock = threading.Lock()
    
    def setup_item_data(self):
        self.title = self.item_data.get('title', '').strip()
        self.original_title = self.item_data.get('original_title', '').strip()
        self.media_type = self.item_data.get('media_type', '').lower()
        
        try:
            self.year = int(self.item_data.get('year'))
        except:
            self.year = None
            
        if self.media_type == 'tvshow':
            try:
                self.season = int(self.item_data.get('season', 1))
                self.episode = int(self.item_data.get('episode', 1))
            except:
                self.season = 1
                self.episode = 1
                
        # Debug info - mudado para LOGINFO
        xbmc.log(f"{self.log_prefix} 🎯 Dados recebidos: title='{self.title}', original_title='{self.original_title}', year={self.year}, type={self.media_type}", xbmc.LOGINFO)
    
    def setup_domains(self):
        parsed = urlparse(self.provider_url)
        self.base_domain = parsed.netloc or "1.animezey23112022.workers.dev"
        self.download_domain = "animezey16082023.animezey16082023.workers.dev"
    
    # --- MÉTODO PRINCIPAL SIMPLIFICADO ---
    def scrape(self):
        """Método principal simplificado - foca no que funciona"""
        try:
            if self.media_type == 'movie':
                return self.scrape_movie_simple()
            elif self.media_type == 'tvshow':
                return self.scrape_tvshow_simple()
            else:
                xbmc.log(f"{self.log_prefix} ⚠️ Tipo de mídia desconhecido: {self.media_type}", xbmc.LOGWARNING)
                return []
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro geral: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
            return []
    
    # --- MÉTODO PARA SÉRIES SIMPLIFICADO ---
    def scrape_tvshow_simple(self):
        """Scraper para séries - VERSÃO SIMPLIFICADA QUE FUNCIONA"""
        try:
            xbmc.log(f"{self.log_prefix} 📺 Buscando série: '{self.title}' S{self.season:02d}E{self.episode:02d}", xbmc.LOGINFO)
            
            # Primeiro tentar navegação inteligente
            episodes = self._smart_tvshow_search()
            
            # Se não encontrou, tentar busca direta
            if not episodes:
                xbmc.log(f"{self.log_prefix} 🔄 Tentando busca direta...", xbmc.LOGINFO)
                episodes = self._direct_tvshow_search()
            
            if not episodes:
                xbmc.log(f"{self.log_prefix} ❌ Série não encontrada", xbmc.LOGINFO)
                return []
            
            xbmc.log(f"{self.log_prefix} ✅ {len(episodes)} episódio(s) encontrado(s)", xbmc.LOGINFO)
            
            # Processar resultados
            return self._process_results_simple(episodes)
            
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro em série: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
            return []
    
    def _smart_tvshow_search(self):
        """Busca inteligente que primeiro tenta navegar, depois busca"""
        episodes = []
        
        # Primeiro: tentar navegação básica
        try:
            # Tentar acessar diretamente a pasta Web-DL
            webdl_path = "/1:/Séries/Séries WEB-DL/"
            xbmc.log(f"{self.log_prefix} 🗺️ Tentando acessar: {webdl_path}", xbmc.LOGDEBUG)
            
            items = self._explore_path_direct(webdl_path)
            if items and len(items) > 0:
                xbmc.log(f"{self.log_prefix} ✅ Web-DL acessado. {len(items)} séries encontradas", xbmc.LOGDEBUG)
                
                # Procurar série nas pastas
                series_folder = self._find_series_smart(items)
                if series_folder:
                    series_name = series_folder.get('name', '')
                    xbmc.log(f"{self.log_prefix} 📁 Série encontrada: {series_name}", xbmc.LOGINFO)
                    
                    # Explorar série
                    series_path = f"{webdl_path.rstrip('/')}/{urllib.parse.quote(series_name)}/"
                    series_items = self._explore_path_direct(series_path)
                    
                    if series_items:
                        # Procurar temporada
                        season_folder = self._find_season_smart(series_items)
                        if season_folder:
                            season_name = season_folder.get('name', '')
                            xbmc.log(f"{self.log_prefix} 📂 Temporada encontrada: {season_name}", xbmc.LOGINFO)
                            
                            # Explorar temporada
                            season_path = f"{series_path.rstrip('/')}/{urllib.parse.quote(season_name)}/"
                            season_items = self._explore_path_direct(season_path)
                            
                            if season_items:
                                # Coletar episódios
                                for item in season_items:
                                    if self._is_video_file(item):
                                        name = item.get('name', '')
                                        if self._is_correct_episode(name):
                                            episodes.append(item)
                                            xbmc.log(f"{self.log_prefix}   ✅ Episódio (navegação): {name}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ⚠️ Erro na navegação: {e}", xbmc.LOGDEBUG)
        
        return episodes
    
    def _find_series_smart(self, items):
        """Encontra série de forma inteligente"""
        if not items:
            return None
        
        # Preparar nomes para busca
        search_names = self._get_series_search_names()
        
        for item in items:
            if item.get('mimeType') != 'application/vnd.google-apps.folder':
                continue
            
            item_name = item.get('name', '').lower()
            
            for search_name in search_names:
                if not search_name:
                    continue
                
                search_lower = search_name.lower()
                
                # Verificar correspondências
                if (search_lower in item_name or
                    search_lower.replace(' ', '.') in item_name or
                    search_lower.replace(' ', '-') in item_name):
                    
                    # Se tiver ano, verificar
                    if self.year:
                        if str(self.year) in item_name:
                            return item
                    else:
                        return item
        
        return None
    
    def _get_series_search_names(self):
        """Obtém nomes para busca da série (usado na navegação)"""
        names = []
        
        # Prioridade 1: título original (mais importante para o site)
        if self.original_title:
            original_clean = self.original_title.split(":")[0].strip()
            names.append(original_clean)
            xbmc.log(f"{self.log_prefix} 🎯 Navegação - Usando original_title: '{original_clean}'", xbmc.LOGINFO)
        
        # Prioridade 2: título principal (fallback)
        if self.title:
            title_clean = self.title.split(":")[0].strip()
            if title_clean not in names:
                names.append(title_clean)
                xbmc.log(f"{self.log_prefix} 🎯 Navegação - Usando title: '{title_clean}'", xbmc.LOGINFO)
        
        # Adicionar variações com pontos
        for name in names.copy():
            if ' ' in name:
                names.append(name.replace(' ', '.'))
                names.append(name.replace(' ', '-'))
        
        # Remover duplicatas
        final_names = list(set([n for n in names if n]))
        xbmc.log(f"{self.log_prefix} 🔤 Navegação - Nomes finalizados: {final_names}", xbmc.LOGINFO)
        return final_names
    
    def _find_season_smart(self, items):
        """Encontra temporada de forma inteligente"""
        if not items:
            return None
        
        season_patterns = [
            f"season {self.season:02d}",
            f"season {self.season}",
            f"temporada {self.season:02d}",
            f"temporada {self.season}",
            f"s{self.season:02d}",
            f"s{self.season}",
            f"season{self.season:02d}",
            f"season{self.season}",
            f"temp {self.season:02d}",
            f"temp {self.season}",
            f"Season {self.season:02d}",
            f"Season {self.season}",
            f"Temporada {self.season:02d}",
            f"Temporada {self.season}",
            f"{self.season:02d}",
            f"{self.season}"
        ]
        
        for item in items:
            if item.get('mimeType') != 'application/vnd.google-apps.folder':
                continue
            
            item_name = item.get('name', '').lower()
            
            for pattern in season_patterns:
                if pattern.lower() in item_name:
                    return item
        
        return None
    
    def _direct_tvshow_search(self):
        """Busca direta de episódios - OTIMIZADO"""
        episodes = []
        seen_ids = set()
        
        # Gerar queries OTIMIZADAS
        queries = self._generate_smart_queries()
        
        if not queries:
            xbmc.log(f"{self.log_prefix} ⚠️ Nenhuma query gerada", xbmc.LOGWARNING)
            return []
        
        # URL de busca
        search_url = f"https://{self.base_domain}/1:search"
        
        xbmc.log(f"{self.log_prefix} 🔍 Buscando com {len(queries)} queries otimizadas", xbmc.LOGINFO)
        
        # Tentar cada query (em ordem de prioridade)
        for query in queries:
            try:
                xbmc.log(f"{self.log_prefix} 🔎 Testando query: '{query}'", xbmc.LOGINFO)
                
                payload = {"q": query, "page_token": None, "page_index": 0}
                result = _post_to_animezey(search_url, payload)
                
                if result and 'data' in result and 'files' in result['data']:
                    files = result['data']['files']
                    xbmc.log(f"{self.log_prefix} 📊 Query '{query}' retornou {len(files)} arquivos", xbmc.LOGINFO)
                    
                    for item in files:
                        item_id = item.get('id')
                        if item_id in seen_ids:
                            continue
                        
                        seen_ids.add(item_id)
                        
                        if self._is_video_file(item):
                            name = item.get('name', '')
                            
                            # Verificação rápida
                            if self._is_correct_episode(name):
                                episodes.append(item)
                                xbmc.log(f"{self.log_prefix}   ✅ Episódio encontrado: {name[:60]}...", xbmc.LOGINFO)
                                
                                # Se encontrou resultados bons, continuar com esta query
                                if len(episodes) >= 5:  # Reduzido para 5
                                    xbmc.log(f"{self.log_prefix} 🎯 Encontrados {len(episodes)} episódios - suficiente", xbmc.LOGINFO)
                                    return episodes
                                    
                else:
                    xbmc.log(f"{self.log_prefix} 📭 Query '{query}' não retornou resultados", xbmc.LOGDEBUG)
                    
            except Exception as e:
                xbmc.log(f"{self.log_prefix} ⚠️ Erro na busca com query '{query}': {e}", xbmc.LOGDEBUG)
                continue
        
        xbmc.log(f"{self.log_prefix} 📋 Total encontrado: {len(episodes)} episódios", xbmc.LOGINFO)
        return episodes
    
    def _matches_series_name(self, filename):
        """Verifica se o nome do arquivo corresponde à série procurada"""
        filename_lower = filename.lower()
        
        # Normalizar o filename removendo apóstrofos e caracteres especiais
        normalized_filename = filename_lower.replace("'", "")
        
        # Obter nomes principais da série
        base_names = self._get_base_names()[:3]  # Pegar apenas 3 nomes principais
        
        for base_name in base_names:
            name_lower = base_name.lower()
            normalized_name = name_lower.replace("'", "")
            
            # Verificar correspondência (mais rigorosa)
            if (name_lower in filename_lower or
                normalized_name in normalized_filename or
                name_lower.replace(' ', '.') in filename_lower or
                normalized_name.replace(' ', '.') in normalized_filename or
                name_lower.replace(' ', '') in filename_lower.replace(' ', '') or
                normalized_name.replace(' ', '') in normalized_filename.replace(' ', '')):
                return True
        
        return False
    
    def _generate_smart_queries(self):
        """Gera queries inteligentes para busca - OTIMIZADO"""
        queries = []
        
        # Nomes base (agora já incluem variações sem artigos)
        base_names = self._get_base_names()
        
        if not base_names:
            xbmc.log(f"{self.log_prefix} ⚠️ QUERIES - Nenhum nome base gerado!", xbmc.LOGWARNING)
            return []
        
        # Pegar apenas os 3 MELHORES nomes (os primeiros já estão ordenados por prioridade)
        top_names = base_names[:3]
        
        xbmc.log(f"{self.log_prefix} 🔤 QUERIES - Top 3 nomes: {top_names}", xbmc.LOGINFO)
        
        # APENAS os formatos mais comuns e efetivos
        common_formats = []
        for name in top_names:
            # Formato 1: Serie.S01E02 (MAIS COMUM)
            if '.' in name:  # Se já tem pontos, usar assim
                common_formats.append(f"{name}.S{self.season:02d}E{self.episode:02d}")
                common_formats.append(f"{name}.{self.season:02d}x{self.episode:02d}")
            else:
                # Adicionar versão com pontos
                with_dots = name.replace(' ', '.').replace("'", "")
                if with_dots != name:
                    common_formats.append(f"{with_dots}.S{self.season:02d}E{self.episode:02d}")
                    common_formats.append(f"{with_dots}.{self.season:02d}x{self.episode:02d}")
            
            # Formato 2: Serie S01E02 (com espaço, se tiver)
            if ' ' in name and len(name.split()) <= 4:  # Apenas se for nome razoável
                common_formats.append(f"{name} S{self.season:02d}E{self.episode:02d}")
        
        # Remover duplicatas
        queries = list(set([q for q in common_formats if len(q) > 10]))
        
        # Ordenar: mais curtas primeiro, com pontos primeiro
        queries.sort(key=lambda x: (x.count('.'), -len(x)), reverse=True)
        
        xbmc.log(f"{self.log_prefix} 🔍 QUERIES - {len(queries)} queries otimizadas: {queries}", xbmc.LOGINFO)
        return queries
    
    def _get_base_names(self):
        """Obtém nomes base para busca"""
        names = []
        
        # Título original (PRIMEIRA PRIORIDADE)
        if self.original_title:
            original_clean = self.original_title.split(":")[0].strip()
            names.append(original_clean)
            xbmc.log(f"{self.log_prefix} 🎯 Busca - original_title extraído: '{original_clean}'", xbmc.LOGINFO)
        
        # Título principal (segunda prioridade)
        if self.title:
            title_clean = self.title.split(":")[0].strip()
            if title_clean not in names:
                names.append(title_clean)
                xbmc.log(f"{self.log_prefix} 🎯 Busca - title extraído: '{title_clean}'", xbmc.LOGINFO)
        
        # Se não encontrou nenhum título, usar string vazia
        if not names:
            xbmc.log(f"{self.log_prefix} ⚠️ Busca - Nenhum título encontrado!", xbmc.LOGWARNING)
            return []
        
        # Criar variações SEM artigos e com pontuação correta
        clean_names = []
        for name in names:
            # Adicionar o nome original
            clean_names.append(name)
            xbmc.log(f"{self.log_prefix} 🔤 Busca - Nome original: '{name}'", xbmc.LOGINFO)
            
            # Remover "The", "A", "An" do início (inglês)
            name_lower = name.lower()
            if name_lower.startswith('the '):
                without_the = name[4:].strip()
                clean_names.append(without_the)
                xbmc.log(f"{self.log_prefix} 🔤 Busca - Sem 'The': '{without_the}'", xbmc.LOGINFO)
            if name_lower.startswith('a '):
                without_a = name[2:].strip()
                clean_names.append(without_a)
                xbmc.log(f"{self.log_prefix} 🔤 Busca - Sem 'A': '{without_a}'", xbmc.LOGINFO)
            if name_lower.startswith('an '):
                without_an = name[3:].strip()
                clean_names.append(without_an)
                xbmc.log(f"{self.log_prefix} 🔤 Busca - Sem 'An': '{without_an}'", xbmc.LOGINFO)
            
            # Remover artigos em outras línguas (português)
            if name_lower.startswith('o '):
                clean_names.append(name[2:].strip())
            if name_lower.startswith('a '):
                clean_names.append(name[2:].strip())
        
        # Criar versões com pontos e sem espaços - PRIORIDADE PARA SEM APÓSTROFO
        final_names = []
        for name in clean_names:
            if name:
                # PRIMEIRO: versão SEM apóstrofo
                name_without_apostrophe = name.replace("'", "")
                if name_without_apostrophe != name:
                    final_names.append(name_without_apostrophe)
                    xbmc.log(f"{self.log_prefix} 🔤 Busca - Sem apóstrofo: '{name_without_apostrophe}'", xbmc.LOGINFO)
                
                # SEGUNDO: nome original
                final_names.append(name)
                
                # TERCEIRO: versões formatadas
                if ' ' in name:
                    # Versão com pontos
                    with_dots = name.replace(' ', '.')
                    final_names.append(with_dots)
                    xbmc.log(f"{self.log_prefix} 🔤 Busca - Com pontos: '{with_dots}'", xbmc.LOGINFO)
                    
                    # Versão com pontos SEM apóstrofo
                    if "'" in name:
                        with_dots_no_apostrophe = name_without_apostrophe.replace(' ', '.')
                        final_names.append(with_dots_no_apostrophe)
                        xbmc.log(f"{self.log_prefix} 🔤 Busca - Com pontos sem apóstrofo: '{with_dots_no_apostrophe}'", xbmc.LOGINFO)
                    
                    # Versão com hífens
                    with_hyphens = name.replace(' ', '-')
                    final_names.append(with_hyphens)
                    
                    # Versão com hífens SEM apóstrofo
                    if "'" in name:
                        with_hyphens_no_apostrophe = name_without_apostrophe.replace(' ', '-')
                        final_names.append(with_hyphens_no_apostrophe)
                    
                    # Versão sem espaços
                    without_spaces = name.replace(' ', '')
                    final_names.append(without_spaces)
                    
                    # Versão sem espaços SEM apóstrofo
                    if "'" in name:
                        without_spaces_no_apostrophe = name_without_apostrophe.replace(' ', '')
                        final_names.append(without_spaces_no_apostrophe)
        
        # Remover duplicatas e valores vazios
        unique_names = list(set([n for n in final_names if n]))
        
        # ORDENAR: dar prioridade para nomes SEM apóstrofo e COM pontos
        def name_priority(name):
            priority = 0
            if '.' in name and "'" not in name:  # Com pontos e sem apóstrofo (MAIOR PRIORIDADE)
                priority += 100
            elif '.' in name:  # Com pontos
                priority += 50
            elif "'" not in name:  # Sem apóstrofo
                priority += 30
            return -priority  # Negativo para ordenação descendente
        
        unique_names.sort(key=name_priority)
        
        xbmc.log(f"{self.log_prefix} 🔤 Busca - Todos os nomes gerados (ordenados): {unique_names}", xbmc.LOGINFO)
        
        return unique_names
    
    def _is_correct_episode(self, filename):
        """Verifica se é o episódio correto - OTIMIZADO"""
        # Converter para minúsculas uma vez
        filename_lower = filename.lower()
        
        # Padrões mais comuns primeiro (mais rápidos de verificar)
        patterns_to_try = [
            f"s{self.season:02d}e{self.episode:02d}",
            f"s{self.season}e{self.episode:02d}",
            f"{self.season:02d}x{self.episode:02d}",
        ]
        
        # Verificar padrões simples primeiro (mais rápido)
        for pattern in patterns_to_try:
            if pattern in filename_lower:
                return True
        
        # Se não encontrou com padrões simples, tentar regex (mais lento)
        if self.episode < 10:
            extra_patterns = [
                f"s{self.season:02d}e{self.episode}",
                f"{self.season:02d}x{self.episode}",
            ]
            for pattern in extra_patterns:
                if pattern in filename_lower:
                    return True
        
        return False
    
    # --- MÉTODO PARA FILMES ---
    def scrape_movie_simple(self):
        """Scraper para filmes simplificado"""
        try:
            xbmc.log(f"{self.log_prefix} 🎬 Buscando filme: '{self.title}'", xbmc.LOGINFO)
            
            # Busca direta para filmes
            movies = self._direct_movie_search()
            
            if not movies:
                xbmc.log(f"{self.log_prefix} ❌ Filme não encontrado", xbmc.LOGINFO)
                return []
            
            xbmc.log(f"{self.log_prefix} ✅ {len(movies)} resultado(s) encontrado(s)", xbmc.LOGINFO)
            
            return self._process_results_simple(movies)
            
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro em filme: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
            return []
    
    def _direct_movie_search(self):
        """Busca direta para filmes"""
        movies = []
        seen_ids = set()
        
        # Gerar queries
        queries = self._generate_movie_queries()
        
        # URL de busca
        search_url = f"https://{self.base_domain}/1:search"
        
        for query in queries:
            try:
                payload = {"q": query}
                result = _post_to_animezey(search_url, payload)
                
                if result and 'data' in result and 'files' in result['data']:
                    for item in result['data']['files']:
                        item_id = item.get('id')
                        if item_id in seen_ids:
                            continue
                        
                        seen_ids.add(item_id)
                        
                        if self._is_video_file(item) and self._is_correct_movie(item.get('name', '')):
                            movies.append(item)
                            xbmc.log(f"{self.log_prefix}   ✅ Filme: {item.get('name', '')}", xbmc.LOGINFO)
                            
                            if len(movies) >= 10:
                                return movies
            except Exception as e:
                xbmc.log(f"{self.log_prefix} ⚠️ Erro na busca: {e}", xbmc.LOGDEBUG)
                continue
        
        return movies
    
    def _generate_movie_queries(self):
        """Gera queries para filmes"""
        queries = set()
        
        # Nomes base
        base_names = self._get_base_names()
        
        for base_name in base_names:
            # Com ano
            if self.year:
                queries.add(f"{base_name} {self.year}")
                queries.add(f"{base_name.replace(' ', '.')}.{self.year}")
                queries.add(f"{base_name}({self.year})")
            
            # Sem ano
            queries.add(base_name)
            queries.add(base_name.replace(' ', '.'))
        
        return list(queries)
    
    def _is_correct_movie(self, filename):
        """Verifica se é o filme correto"""
        filename_lower = filename.lower()
        
        # Verificar se contém o título
        base_names = self._get_base_names()
        
        for base_name in base_names:
            name_lower = base_name.lower()
            
            if (name_lower in filename_lower or
                name_lower.replace(' ', '.') in filename_lower or
                name_lower.replace(' ', '-') in filename_lower):
                
                # Verificar ano se disponível
                if self.year:
                    if str(self.year) in filename_lower:
                        return True
                else:
                    return True
        
        return False
    
    # --- FUNÇÕES AUXILIARES ---
    
    def _explore_path_direct(self, path):
        """Explora um caminho específico diretamente"""
        explore_url = f"https://{self.base_domain}{path}"
        
        payload = {
            "id": "",
            "type": "folder",
            "password": "",
            "page_token": "",
            "page_index": 0
        }
        
        result = _post_to_animezey(explore_url, payload)
        if result and 'data' in result and 'files' in result['data']:
            return result['data']['files']
        
        return []
    
    def _is_video_file(self, item):
        """Verifica se é um arquivo de vídeo"""
        name = item.get('name', '')
        mime_type = item.get('mimeType', '')
        
        return ('video' in mime_type or 
                name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm')))
    
    def _process_results_simple(self, items):
        """Processa resultados de forma simples"""
        results = []
        seen_links = set()
        
        for item in items:
            download_url = self.build_download_link(item.get('link'))
            if not download_url or download_url in seen_links:
                continue
            
            seen_links.add(download_url)
            results.append(self._create_result_item(item, download_url))
        
        # Ordenar por qualidade
        quality_order = {'4K': 0, '2160p': 0, '1080p': 1, '720p': 2, 'HD': 3, 'SD': 4}
        results.sort(key=lambda x: quality_order.get(x['quality'], 99))
        
        return results
    
    def build_download_link(self, link_part):
        """Constrói link de download"""
        if not link_part or not link_part.startswith('/'):
            return None
            
        try:
            path_part, query_string = link_part.split('?', 1)
            params = parse_qs(query_string)
            
            file_id = params.get('file', [None])[0]
            if not file_id:
                return None
                
            query_params = {'file': file_id}
            
            for param in ['expiry', 'mac']:
                value = params.get(param, [None])[0]
                if value:
                    query_params[param] = value
            
            encoded_query = urlencode(query_params)
            return f"https://{self.download_domain}{path_part}?{encoded_query}"
            
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ⚠️ Erro construindo link: {e}", xbmc.LOGWARNING)
            return None
    
    def _create_result_item(self, file_data, download_url):
        """Cria item de resultado padrão"""
        file_name = file_data.get('name', '')
        
        # Detectar qualidade
        quality = guess_quality_from_name(file_name) or "HD"
        
        # Detectar idioma
        fn_lower = file_name.lower()
        if any(x in fn_lower for x in ['dual', 'multi']):
            language = 'DUAL'
        elif any(x in fn_lower for x in ['dublado', 'dub ', 'pt-br', 'dublado']):
            language = 'PT-BR'
        elif any(x in fn_lower for x in ['legendado', 'leg', 'sub', 'eng']):
            language = 'LEG'
        else:
            language = 'PT-BR'
        
        return {
            'url': download_url,
            'quality': quality,
            'type': 'Direto',
            'title': file_name,
            'release_title': file_name,
            'label': f"{file_name} [{quality}]",
            'size': format_size(file_data.get('size', 0)),
            'peers': 'N/A',
            'seeders': 'N/A',
            'provider': 'AnimeZey',
            'languages': language
        }

# --- Função de Interface ---
def scrape(provider_url, item_data):
    """Interface para compatibilidade"""
    try:
        scraper = AnimeZeyScraper(provider_url, item_data)
        return scraper.scrape()
    except Exception as e:
        xbmc.log(f"[animezey.scrape] ❌ Erro: {e}", xbmc.LOGERROR)
        return []