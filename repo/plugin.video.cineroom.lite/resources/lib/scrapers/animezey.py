# -*- coding: utf-8 -*-
# --- Imports Padrões ---
import re
import requests
import json
import xbmc
import traceback
import time
from urllib.parse import urlparse, urlencode, parse_qs
from bs4 import BeautifulSoup

# --- Imports do Pacote ---
from .session import USER_AGENT
from .utils import guess_quality_from_name, get_anime_search_codes, format_size, normalize_for_compare

# --- Configurações ---
class ScraperConfig:
    REQUEST_TIMEOUT = 20
    MAX_RETRIES = 2
    MAX_RESULTS_PER_QUERY = 2  # Reduzido para acelerar

# --- Funções Auxiliares ---
def with_retry(max_retries=2, delay=1):
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
    
    def setup_item_data(self):
        self.title = (self.item_data.get('title') or '').strip()
        self.original_title = (self.item_data.get('original_title') or '').strip()
        self.romaji_title = (self.item_data.get('romaji_title') or '').strip()
        self.media_type = (self.item_data.get('media_type') or '').lower()
        
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
                
        xbmc.log(f"{self.log_prefix} 🎯 Busca: title='{self.title}', original='{self.original_title}', romaji='{self.romaji_title}'", xbmc.LOGINFO)
    
    def setup_domains(self):
        parsed = urlparse(self.provider_url)
        self.base_domain = parsed.netloc or "1.animezey23112022.workers.dev"
        self.download_domain = "animezey16082023.animezey16082023.workers.dev"
    
    # --- MÉTODO PRINCIPAL ---
    def scrape(self):
        """Método principal - APENAS BUSCA DIRETA"""
        try:
            if self.media_type == 'movie':
                return self._search_movies()
            elif self.media_type == 'tvshow':
                return self._search_episodes()
            else:
                xbmc.log(f"{self.log_prefix} ⚠️ Tipo desconhecido: {self.media_type}", xbmc.LOGWARNING)
                return []
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
            return []
    
    # --- BUSCA DE EPISÓDIOS (OTIMIZADA) ---
    def _search_episodes(self):
        """Busca direta de episódios - OTIMIZADA"""
        xbmc.log(f"{self.log_prefix} 📺 Buscando S{self.season:02d}E{self.episode:02d}", xbmc.LOGINFO)
        
        episodes = []
        seen_ids = set()
        
        # Gerar queries otimizadas
        queries = self._generate_episode_queries()
        
        if not queries:
            xbmc.log(f"{self.log_prefix} ⚠️ Nenhuma query gerada", xbmc.LOGWARNING)
            return []
        
        search_url = f"https://{self.base_domain}/1:search"
        
        # Limitar queries para acelerar (testar apenas as 10 melhores)
        queries = queries[:10]
        
        xbmc.log(f"{self.log_prefix} 🔍 Testando {len(queries)} queries", xbmc.LOGINFO)
        
        for query in queries:
            try:
                xbmc.log(f"{self.log_prefix} 🔎 Query: '{query}'", xbmc.LOGDEBUG)
                
                payload = {"q": query, "page_token": None, "page_index": 0}
                result = _post_to_animezey(search_url, payload)
                
                if result and 'data' in result and 'files' in result['data']:
                    files = result['data']['files']
                    
                    for item in files:
                        item_id = item.get('id')
                        if item_id in seen_ids:
                            continue
                        
                        seen_ids.add(item_id)
                        
                        if self._is_video_file(item):
                            name = item.get('name', '')
                            
                            if self._is_correct_episode(name):
                                episodes.append(item)
                                xbmc.log(f"{self.log_prefix}   ✅ {name[:50]}...", xbmc.LOGINFO)
                                
                                # Se encontrou resultados suficientes, parar
                                if len(episodes) >= ScraperConfig.MAX_RESULTS_PER_QUERY:
                                    xbmc.log(f"{self.log_prefix} 🎯 {len(episodes)} episódios - suficiente", xbmc.LOGINFO)
                                    return self._process_results(episodes)
                                    
            except Exception as e:
                xbmc.log(f"{self.log_prefix} ⚠️ Erro query '{query}': {e}", xbmc.LOGDEBUG)
                continue
        
        if episodes:
            xbmc.log(f"{self.log_prefix} ✅ Total: {len(episodes)} episódios", xbmc.LOGINFO)
            return self._process_results(episodes)
        else:
            xbmc.log(f"{self.log_prefix} ❌ Nenhum episódio encontrado", xbmc.LOGINFO)
            return []
    
    def _generate_episode_queries(self):
        """Gera queries otimizadas para episódios - FORMATO ANIMEZEY"""
        queries = []
        
        # Obter nomes principais
        base_names = self._get_base_names()
        
        if not base_names:
            return []
        
        # Limitar a 4 nomes principais para acelerar
        top_names = base_names[:4]
        
        # Obter códigos de busca do utils.py
        search_codes = get_anime_search_codes(self.season, self.episode)
        
        xbmc.log(f"{self.log_prefix} 📝 Nomes: {top_names}", xbmc.LOGDEBUG)
        xbmc.log(f"{self.log_prefix} 📝 Códigos: {search_codes}", xbmc.LOGDEBUG)
        
        # PRIORIDADE 1: Padrão AnimezZey para animes (Season 1)
        # Formato: [Grupo] Nome - 01
        if self.season == 1:
            for name in top_names:
                name_clean = name.replace("'", "")
                name_with_dots = name_clean.replace(' ', '.')
                
                # Padrão com travessão (MAIS COMUM NO ANIMEZEY)
                queries.append(f"{name_clean} - {self.episode:02d}")      # "Chainsaw Man - 01"
                queries.append(f"{name_clean} - {self.episode:03d}")      # "Chainsaw Man - 001"
                queries.append(f"{name_with_dots} - {self.episode:02d}")  # "Chainsaw.Man - 01"
                queries.append(f"{name_with_dots}-{self.episode:02d}")    # "Chainsaw.Man-01"
        
        # PRIORIDADE 2: Padrões com códigos do utils
        for name in top_names:
            name_clean = name.replace("'", "")
            name_with_dots = name_clean.replace(' ', '.')
            
            # Apenas códigos numéricos para Season 1 (animes)
            codes_to_use = [c for c in search_codes if c.isdigit()] if self.season == 1 else search_codes[:3]
            
            for code in codes_to_use:
                # Nome.Codigo
                queries.append(f"{name_with_dots}.{code}")
                
                # Nome Codigo (com espaço)
                if not code.startswith('S'):  # Evitar "Nome S01E01" duplicado
                    queries.append(f"{name_clean} {code}")
        
        # PRIORIDADE 3: Queries com ano (apenas 2 nomes principais)
        if self.year and self.year > 1900:
            for name in top_names[:2]:
                name_clean = name.replace("'", "")
                name_with_dots = name_clean.replace(' ', '.')
                
                if self.season == 1:
                    # Anime com ano: "Nome (2022) - 01"
                    queries.append(f"{name_clean} {self.year} - {self.episode:02d}")
                    queries.append(f"{name_clean} ({self.year}) - {self.episode:02d}")
                
                # Formato tradicional com ano
                for code in search_codes[:2]:
                    queries.append(f"{name_with_dots}.{self.year}.{code}")
        
        # Remover duplicatas mantendo ordem
        seen = set()
        unique_queries = []
        for q in queries:
            q_stripped = q.strip()
            if q_stripped and q_stripped not in seen:
                seen.add(q_stripped)
                unique_queries.append(q_stripped)
        
        xbmc.log(f"{self.log_prefix} 📋 {len(unique_queries)} queries: {unique_queries[:8]}", xbmc.LOGINFO)
        return unique_queries
    
    def _get_base_names(self):
        """Obtém nomes base - CORRIGIDO: mantém nome completo"""
        names = []
    
        # PRIORIDADE 1: Romaji (melhor para animes)
        if self.romaji_title:
            # NÃO remover subtítulo - manter completo!
            clean = self.romaji_title.strip()
            names.append(clean)
            # Versão sem subtítulo apenas como fallback
            if ":" in clean:
                names.append(clean.split(":")[0].strip())
    
        # PRIORIDADE 2: Original
        if self.original_title:
            clean = self.original_title.strip()
            if clean not in names:
                names.append(clean)
            if ":" in clean:
                short = clean.split(":")[0].strip()
                if short not in names:
                    names.append(short)
    
        # PRIORIDADE 3: Title
        if self.title:
            clean = self.title.strip()
            if clean not in names:
                names.append(clean)
            if ":" in clean:
                short = clean.split(":")[0].strip()
                if short not in names:
                    names.append(short)
    
        if not names:
            return []
    
        # Criar variações
        final_names = []
        for name in names:
            # Original
            final_names.append(name)
        
            # Sem apóstrofo (prioridade)
            if "'" in name:
                final_names.append(name.replace("'", ""))
        
            # Sem artigos (apenas se não for subtítulo)
            if ":" not in name:
                name_lower = name.lower()
                if name_lower.startswith(('the ', 'a ', 'an ', 'o ', 'os ')):
                    words = name.split(' ', 1)
                    if len(words) > 1:
                        final_names.append(words[1])
    
        # Remover duplicatas
        seen = set()
        unique = []
        for n in final_names:
            if n and n not in seen:
                seen.add(n)
                unique.append(n)
    
        return unique
    
    def _is_correct_episode(self, filename):
        """Verifica se é o episódio correto - OTIMIZADO COM PADRÕES ANIMEZEY"""
        filename_lower = filename.lower()
        
        # Primeiro: verificar se o nome da série está no arquivo
        if not self._matches_series_in_filename(filename_lower):
            return False
        
        # Usar utils para gerar códigos
        search_codes = get_anime_search_codes(self.season, self.episode)
        
        # Verificar cada código
        for code in search_codes:
            if code.lower() in filename_lower:
                return True
        
        # Padrões extras para animes (Season 1)
        # FORMATO ANIMEZEY: [Grupo] Nome - 01.mkv
        if self.season == 1:
            extra_patterns = [
                # Padrão principal: " - 01"
                f" - {self.episode:02d}",       # " - 01"
                f" - {self.episode:03d}",       # " - 001"
                f"- {self.episode:02d}",        # "- 01" (sem espaço antes)
                f"- {self.episode:03d}",        # "- 001"
                f" - {self.episode:02d} ",      # " - 01 " (com espaço depois)
                f" - {self.episode:03d} ",      # " - 001 "
                
                # Sem travessão
                f" {self.episode:02d}.",        # " 01."
                f" {self.episode:03d}.",        # " 001."
                f" {self.episode:02d} ",        # " 01 "
                f" {self.episode:03d} ",        # " 001 "
                
                # Entre colchetes/parênteses (menos comum mas existe)
                f"[{self.episode:02d}]",
                f"[{self.episode:03d}]",
                f"({self.episode:02d})",
                f"({self.episode:03d})",
            ]
            
            for pattern in extra_patterns:
                if pattern in filename_lower:
                    xbmc.log(f"{self.log_prefix} ✅ Match pattern '{pattern}' em '{filename[:60]}'", xbmc.LOGDEBUG)
                    return True
        
        return False
    
    def _matches_series_in_filename(self, filename_lower):
        """Verifica se o nome da série está no arquivo - CORRIGIDO: verificação mais rigorosa"""
        # Obter nomes para verificação (priorizar nomes completos)
        base_names = self._get_base_names()[:8]  # Aumentar para incluir mais variações
    
        for name in base_names:
            name_lower = name.lower()
            name_normalized = normalize_for_compare(name)
            filename_normalized = normalize_for_compare(filename_lower)
        
            # VERIFICAÇÃO MAIS RIGOROSA:
            # Se o nome tem subtítulo (ex: "Transformers: Rescue Bots")
            # então AMBAS as partes devem estar no arquivo
            if ":" in name:
                parts = [p.strip().lower() for p in name.split(":")]
            
                # Verificar se TODAS as partes significativas estão presentes
                all_parts_present = True
                for part in parts:
                    if len(part) > 2:  # Ignorar partes muito curtas
                        part_normalized = normalize_for_compare(part)
                    
                        # O arquivo deve conter esta parte
                        if not (part in filename_lower or 
                               part_normalized in filename_normalized or
                               part.replace(' ', '.') in filename_lower or
                               part.replace(' ', '') in filename_lower):
                            all_parts_present = False
                            break
            
                if all_parts_present:
                    xbmc.log(f"{self.log_prefix} ✅ Match completo: '{name}' em '{filename_lower[:80]}'", xbmc.LOGDEBUG)
                    return True
        
            else:
                # Nome sem subtítulo - verificação normal
                if (name_lower in filename_lower or
                    name_normalized in filename_normalized or
                    name_lower.replace(' ', '.') in filename_lower or
                    name_lower.replace(' ', '') in filename_lower.replace('[', '').replace(']', '')):
                    xbmc.log(f"{self.log_prefix} ✅ Match simples: '{name}' em '{filename_lower[:80]}'", xbmc.LOGDEBUG)
                    return True
    
        return False
    
    # --- BUSCA DE FILMES (OTIMIZADA) ---
    def _search_movies(self):
        """Busca direta de filmes - OTIMIZADA"""
        xbmc.log(f"{self.log_prefix} 🎬 Buscando filme", xbmc.LOGINFO)
        
        movies = []
        seen_ids = set()
        
        queries = self._generate_movie_queries()
        search_url = f"https://{self.base_domain}/1:search"
        
        # Limitar queries
        queries = queries[:8]
        
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
                            xbmc.log(f"{self.log_prefix}   ✅ {item.get('name', '')[:50]}...", xbmc.LOGINFO)
                            
                            if len(movies) >= 5:
                                return self._process_results(movies)
            except Exception as e:
                xbmc.log(f"{self.log_prefix} ⚠️ Erro: {e}", xbmc.LOGDEBUG)
                continue
        
        if movies:
            xbmc.log(f"{self.log_prefix} ✅ {len(movies)} filmes encontrados", xbmc.LOGINFO)
            return self._process_results(movies)
        else:
            xbmc.log(f"{self.log_prefix} ❌ Nenhum filme encontrado", xbmc.LOGINFO)
            return []
    
    def _generate_movie_queries(self):
        """Gera queries para filmes"""
        queries = []
        base_names = self._get_base_names()[:3]
        
        for name in base_names:
            name_clean = name.replace("'", "")
            name_with_dots = name_clean.replace(' ', '.')
            
            if self.year:
                queries.append(f"{name_with_dots}.{self.year}")
                queries.append(f"{name_clean} {self.year}")
            
            queries.append(name_with_dots)
            queries.append(name_clean)
        
        # Remover duplicatas
        seen = set()
        unique = []
        for q in queries:
            if q and q not in seen:
                seen.add(q)
                unique.append(q)
        
        return unique
    
    def _is_correct_movie(self, filename):
        """Verifica se é o filme correto"""
        filename_lower = filename.lower()
        base_names = self._get_base_names()
        
        for name in base_names:
            name_lower = name.lower()
            name_normalized = normalize_for_compare(name)
            filename_normalized = normalize_for_compare(filename)
            
            # Verificar correspondência
            if (name_lower in filename_lower or
                name_normalized in filename_normalized or
                name_lower.replace(' ', '.') in filename_lower):
                
                # Se tem ano, verificar
                if self.year:
                    if str(self.year) in filename_lower:
                        return True
                else:
                    return True
        
        return False
    
    # --- FUNÇÕES AUXILIARES ---
    def _is_video_file(self, item):
        """Verifica se é vídeo"""
        name = item.get('name', '')
        mime = item.get('mimeType', '')
        
        return ('video' in mime or 
                name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm')))
    
    def _process_results(self, items):
        """Processa e retorna resultados"""
        results = []
        seen_links = set()
        
        for item in items:
            # NOVO: Extrai URL do player Video.js
            download_url = self._extract_player_url(item)
            
            if not download_url or download_url in seen_links:
                continue
            
            seen_links.add(download_url)
            results.append(self._create_result_item(item, download_url))
        
        # Ordenar por qualidade
        quality_order = {'4K': 0, '2160p': 0, '1080p': 1, '720p': 2, 'HD': 3, 'SD': 4}
        results.sort(key=lambda x: quality_order.get(x['quality'], 99))
        
        return results
    
    def _extract_player_url(self, item):
        """
        NOVO: Extrai URL do player Video.js (com expiry e mac válidos)
        """
        try:
            # Constrói URL de visualização (?a=view)
            link_part = item.get('link', '')
            if not link_part:
                xbmc.log(f"{self.log_prefix} ⚠️ Item sem link", xbmc.LOGDEBUG)
                return None
            
            # URL completa do visualizador
            view_url = f"https://{self.base_domain}{link_part}"
            if '?a=' not in view_url:
                view_url += '?a=view'
            
            xbmc.log(f"{self.log_prefix} 🔍 Buscando player em: {view_url[:100]}", xbmc.LOGDEBUG)
            
            # Fazer request para página do player
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'pt-BR,pt;q=0.9',
            }
            
            response = requests.get(view_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Procurar tag <source> do Video.js
            source_tag = soup.find('source', {'src': True})
            
            if source_tag:
                player_url = source_tag['src']
                xbmc.log(f"{self.log_prefix} ✅ URL do player extraída: {player_url[:150]}", xbmc.LOGINFO)
                return player_url
            else:
                xbmc.log(f"{self.log_prefix} ⚠️ Tag <source> não encontrada", xbmc.LOGWARNING)
                
                # Fallback: tentar construir link manualmente (método antigo)
                return self._build_download_link(link_part)
                
        except Exception as e:
            xbmc.log(f"{self.log_prefix} ❌ Erro ao extrair URL do player: {e}", xbmc.LOGERROR)
            # Fallback
            return self._build_download_link(item.get('link'))
    
    def _build_download_link(self, link_part):
        """Constrói link de download (FALLBACK - método antigo)"""
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
        """Cria item de resultado"""
        file_name = file_data.get('name', '')
        
        # Detectar qualidade
        quality = guess_quality_from_name(file_name) or "HD"
        
        # Detectar idioma
        fn_lower = file_name.lower()
        if any(x in fn_lower for x in ['dual', 'multi']):
            language = 'DUAL'
        elif any(x in fn_lower for x in ['dublado', 'dub ', 'pt-br']):
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
    """Interface de compatibilidade"""
    try:
        scraper = AnimeZeyScraper(provider_url, item_data)
        return scraper.scrape()
    except Exception as e:
        xbmc.log(f"[animezey.scrape] ❌ Erro: {e}", xbmc.LOGERROR)
        return []