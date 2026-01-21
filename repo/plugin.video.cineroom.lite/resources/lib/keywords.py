# -*- coding: utf-8 -*-
# resources/lib/keywords.py

"""
Sistema de Categorias Temáticas com Keywords do TMDb
<<<<<<< HEAD
OTIMIZADO COM CACHE EM DISCO E MEMÓRIA
"""

import xbmc
import xbmcaddon
import xbmcvfs
import requests
import json
import time
import sqlite3
import os
from functools import lru_cache

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')
TMDB_API_KEY = ADDON.getSetting("tmdb_api") or "f0b9cd2de131c900f5bb03a0a5776342"

# Caminho para cache SQLite
CACHE_DB_PATH = xbmcvfs.translatePath(os.path.join(ADDON_PATH, 'resources', 'data', 'keywords_cache.db'))

# Cache em memória (LRU)
_KEYWORD_CACHE_MEMORY = {}
_KEYWORD_BATCH_CACHE = {}

def init_cache_db():
    """Inicializa o banco de cache SQLite"""
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()
    
    # Tabela para cache de keywords (nome -> id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keyword_cache (
            keyword_name TEXT PRIMARY KEY,
            keyword_id INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela para cache de categorias temáticas completas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS theme_cache (
            theme_slug TEXT PRIMARY KEY,
            keyword_ids TEXT,  -- JSON array
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_cached_keyword_id(keyword_name):
    """Busca keyword_id no cache SQLite"""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT keyword_id FROM keyword_cache WHERE keyword_name = ?",
            (keyword_name,)
        )
        result = cursor.fetchone()
        
        conn.close()
        return result[0] if result else None
    except:
        return None

def save_keyword_cache(keyword_name, keyword_id):
    """Salva keyword no cache SQLite"""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT OR REPLACE INTO keyword_cache 
               (keyword_name, keyword_id, last_updated) VALUES (?, ?, datetime('now'))""",
            (keyword_name, keyword_id)
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f"[Keywords] Erro salvando cache: {e}", xbmc.LOGDEBUG)

def get_cached_theme_ids(theme_slug):
    """Busca IDs de uma categoria no cache SQLite"""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT keyword_ids FROM theme_cache WHERE theme_slug = ?",
            (theme_slug,)
        )
        result = cursor.fetchone()
        
        conn.close()
        
        if result and result[0]:
            return json.loads(result[0])
        return None
    except:
        return None

def save_theme_cache(theme_slug, keyword_ids):
    """Salva categoria completa no cache SQLite"""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT OR REPLACE INTO theme_cache 
               (theme_slug, keyword_ids, last_updated) VALUES (?, ?, datetime('now'))""",
            (theme_slug, json.dumps(keyword_ids))
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        xbmc.log(f"[Keywords] Erro salvando theme cache: {e}", xbmc.LOGDEBUG)

def search_keyword_id_batch(keyword_names):
    """
    Busca IDs de múltiplas keywords em uma única requisição
    Retorna dicionário {keyword_name: keyword_id}
    """
    if not keyword_names:
        return {}
    
    # Verifica cache em memória primeiro
    cached_results = {}
    remaining = []
    
    for name in keyword_names:
        # Cache em memória
        if name in _KEYWORD_CACHE_MEMORY:
            cached_results[name] = _KEYWORD_CACHE_MEMORY[name]
        # Cache SQLite
        else:
            cached_id = get_cached_keyword_id(name)
            if cached_id:
                _KEYWORD_CACHE_MEMORY[name] = cached_id
                cached_results[name] = cached_id
            else:
                remaining.append(name)
    
    if not remaining:
        return cached_results
    
    # Busca as restantes no TMDB (em batch onde possível)
    results = cached_results.copy()
    
    for name in remaining:
        try:
            url = "https://api.themoviedb.org/3/search/keyword"
            params = {
                "api_key": TMDB_API_KEY,
                "query": name,
                "page": 1
            }
            
            response = requests.get(url, params=params, timeout=3)
            data = response.json()
            
            if data.get('results'):
                keyword_id = data['results'][0]['id']
                results[name] = keyword_id
                
                # Atualiza caches
                _KEYWORD_CACHE_MEMORY[name] = keyword_id
                save_keyword_cache(name, keyword_id)
                
                xbmc.log(f"[Keywords] '{name}' → ID {keyword_id}", xbmc.LOGDEBUG)
            else:
                results[name] = None
                xbmc.log(f"[Keywords] Keyword '{name}' não encontrada", xbmc.LOGWARNING)
                
        except Exception as e:
            xbmc.log(f"[Keywords] Erro buscando '{name}': {e}", xbmc.LOGERROR)
            results[name] = None
    
    return results

@lru_cache(maxsize=50)
def resolve_keywords_cached(keyword_names_tuple):
    """
    Versão com cache LRU da função resolve_keywords
    Aceita tuple para ser cacheable
    """
    keyword_names = list(keyword_names_tuple)
    results = search_keyword_id_batch(keyword_names)
    return [results[name] for name in keyword_names if results.get(name)]

def resolve_keywords(keyword_names):
    """
    Converte lista de nomes em lista de IDs com cache inteligente
    """
    # Converte para tuple para usar com lru_cache
    names_tuple = tuple(keyword_names)
    return resolve_keywords_cached(names_tuple)
=======
Busca keywords por NOME (mais flexível e legível)
"""

import xbmc
import requests
from functools import lru_cache

TMDB_API_KEY = "f0b9cd2de131c900f5bb03a0a5776342"

# Cache de IDs já resolvidos (evita requisições repetidas)
_KEYWORD_CACHE = {}

@lru_cache(maxsize=100)
def search_keyword_id(keyword_name):
    """
    Busca o ID de uma keyword pelo nome no TMDb
    Usa cache para não repetir requisições
    """
    # Verifica cache em memória
    if keyword_name in _KEYWORD_CACHE:
        return _KEYWORD_CACHE[keyword_name]
    
    url = f"https://api.themoviedb.org/3/search/keyword"
    params = {
        "api_key": TMDB_API_KEY,
        "query": keyword_name
    }
    
    try:
        response = requests.get(url, params=params, timeout=3)
        data = response.json()
        
        if data.get('results'):
            keyword_id = data['results'][0]['id']
            _KEYWORD_CACHE[keyword_name] = keyword_id
            xbmc.log(f"[Keywords] '{keyword_name}' → ID {keyword_id}", xbmc.LOGDEBUG)
            return keyword_id
        else:
            xbmc.log(f"[Keywords] Keyword '{keyword_name}' não encontrada", xbmc.LOGWARNING)
            return None
            
    except Exception as e:
        xbmc.log(f"[Keywords] Erro buscando '{keyword_name}': {e}", xbmc.LOGERROR)
        return None

def resolve_keywords(keyword_names):
    """
    Converte lista de nomes em lista de IDs
    Exemplo: ["snow", "winter"] → [2238, 10683]
    """
    ids = []
    for name in keyword_names:
        keyword_id = search_keyword_id(name)
        if keyword_id:
            ids.append(keyword_id)
    return ids
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260

# Mapeamento PT-BR → Keyword Names (inglês)
KEYWORDS_MAP = {
    # 🌨️ NATUREZA & CLIMA
    "neve": {
        "keywords": ["snow", "winter"],
        "name": "Neve",
        "genres": [],
        "description": "Filmes ambientados na neve e inverno"
    },
    "praia": {
        "keywords": ["beach", "summer"],
        "name": "Praia & Verão",
        "genres": [],
        "description": "Filmes de verão, praia e oceano"
    },
    "deserto": {
        "keywords": ["desert"],
        "name": "Deserto",
        "genres": [],
        "description": "Ambientados em desertos"
    },
    "floresta": {
        "keywords": ["jungle", "forest"],
        "name": "Floresta & Selva",
        "genres": [],
        "description": "Aventuras em florestas e selvas"
    },
    "oceano": {
        "keywords": ["ocean", "underwater"],
        "name": "Oceano",
        "genres": [],
        "description": "Aventuras submarinas"
    },
    "espacial": {
        "keywords": ["space", "astronaut"],
        "name": "Espaço Sideral",
        "genres": [],
        "description": "Viagens espaciais e universo"
    },
    
    # 🎮 TECH & GAMES
    "videogame": {
        "keywords": ["video game", "gamer"],
        "name": "Videogames",
        "genres": [],
        "description": "Filmes sobre games e gamers"
    },
    "hacker": {
        "keywords": ["hacker", "cyber"],
        "name": "Hackers & Cyber",
        "genres": [],
        "description": "Hackers e tecnologia"
    },
    "inteligencia_artificial": {
        "keywords": ["artificial intelligence", "robot"],
        "name": "Inteligência Artificial",
        "genres": [],
        "description": "IA e robôs"
    },
    "realidade_virtual": {
        "keywords": ["virtual reality"],
        "name": "Realidade Virtual",
        "genres": [],
        "description": "VR e mundos virtuais"
    },
    
    # 🧟 CRIATURAS
    "zumbi": {
        "keywords": ["zombie", "undead"],
        "name": "Apocalipse Zumbi",
        "genres": [],
        "description": "Filmes de zumbis"
    },
    "vampiro": {
        "keywords": ["vampire"],
        "name": "Vampiros",
        "genres": [],
        "description": "Vampiros e criaturas da noite"
    },
    "lobisomem": {
        "keywords": ["werewolf"],
        "name": "Lobisomens",
        "genres": [],
        "description": "Lobisomens e licantropia"
    },
    "alienigena": {
        "keywords": ["alien", "extraterrestrial"],
        "name": "Alienígenas",
        "genres": [],
        "description": "Invasões e contatos alienígenas"
    },
    "dinossauro": {
        "keywords": ["dinosaur"],
        "name": "Dinossauros",
        "genres": [],
        "description": "Dinossauros e era pré-histórica"
    },
    "dragao": {
        "keywords": ["dragon"],
        "name": "Dragões",
        "genres": [],
        "description": "Dragões e mitologia"
    },
    
    # 🎯 TEMAS & AÇÕES
    "vinganca": {
        "keywords": ["revenge", "vengeance"],
        "name": "Vingança",
        "genres": [],
        "description": "Filmes de vingança épica"
    },
    "assalto": {
        "keywords": ["heist", "bank robbery"],
        "name": "Assaltos & Heist",
        "genres": [],
        "description": "Grandes assaltos e golpes"
    },
    "sobrevivencia": {
        "keywords": ["survival"],
        "name": "Sobrevivência",
        "genres": [],
        "description": "Luta pela sobrevivência"
    },
    "apocalipse": {
        "keywords": ["apocalypse", "post-apocalyptic"],
        "name": "Apocalipse",
        "genres": [],
        "description": "Fim do mundo e pós-apocalipse"
    },
    "viagem_tempo": {
        "keywords": ["time travel"],
        "name": "Viagem no Tempo",
        "genres": [],
        "description": "Viagens temporais"
    },
    "distopia": {
        "keywords": ["dystopia"],
        "name": "Distopia",
        "genres": [],
        "description": "Futuros distópicos"
    },
    
    # 👤 PROFISSÕES
    "assassino": {
        "keywords": ["assassin", "hitman"],
        "name": "Assassinos",
        "genres": [],
        "description": "Assassinos profissionais"
    },
    "detetive": {
        "keywords": ["detective", "investigation"],
        "name": "Detetives",
        "genres": [],
        "description": "Investigações e detetives"
    },
    "policia": {
        "keywords": ["police", "cop"],
        "name": "Polícia",
        "genres": [],
        "description": "Policiais e investigações"
    },
    "espia": {
        "keywords": ["spy", "espionage"],
        "name": "Espiões",
        "genres": [],
        "description": "Espiões e missões secretas"
    },
    "pirata": {
        "keywords": ["pirate"],
        "name": "Piratas",
        "genres": [],
        "description": "Piratas e aventuras nos mares"
    },
    
    # 🏛️ LUGARES & ÉPOCAS
    "prisao": {
        "keywords": ["prison", "jail"],
        "name": "Prisão",
        "genres": [],
        "description": "Filmes de prisão"
    },
    "escola": {
        "keywords": ["school", "high school"],
        "name": "Escola",
        "genres": [],
        "description": "Ambientados em escolas"
    },
    "hospital": {
        "keywords": ["hospital", "doctor"],
        "name": "Hospital",
        "genres": [],
        "description": "Ambientes hospitalares"
    },
    "medieval": {
        "keywords": ["medieval", "middle ages"],
        "name": "Era Medieval",
        "genres": [],
        "description": "Cavaleiros e castelos"
    },
    
    # 🎭 ESPECIAIS
    "baseado_fatos": {
        "keywords": ["based on true story", "true story"],
        "name": "Baseado em Fatos Reais",
        "genres": [],
        "description": "Histórias verídicas"
    },
    "baseado_livro": {
        "keywords": ["based on novel", "literary adaptation"],
        "name": "Baseado em Livros",
        "genres": [],
        "description": "Adaptações literárias"
    },
    "super_heroi": {
        "keywords": ["superhero", "comic book"],
        "name": "Super-Heróis",
        "genres": [],
        "description": "Heróis e vilões"
    },
    "natal": {
        "keywords": ["christmas", "santa claus"],
        "name": "Natal",
        "genres": [],
        "description": "Filmes de Natal"
    },
    "halloween": {
        "keywords": ["halloween"],
        "name": "Halloween",
        "genres": [],
        "description": "Filmes de Halloween"
    },
    
    # 🎬 ESPORTES
    "futebol": {
        "keywords": ["football", "soccer"],
        "name": "Futebol",
        "genres": [],
        "description": "Filmes de futebol"
    },
    "boxe": {
        "keywords": ["boxing", "boxer"],
        "name": "Boxe",
        "genres": [],
        "description": "Lutas e boxe"
    },
    "corrida": {
        "keywords": ["car racing", "racing"],
        "name": "Corridas",
        "genres": [],
        "description": "Corridas e velocidade"
    },
    "artes_marciais": {
        "keywords": ["martial arts", "kung fu"],
        "name": "Artes Marciais",
        "genres": [],
        "description": "Kung fu e artes marciais"
    },
    "danca": {
        "keywords": ["dance", "dancing"],
        "name": "Dança",
        "genres": [],
        "description": "Filmes de dança"
    },
}

def get_all_theme_categories():
    """Retorna todas as categorias temáticas disponíveis"""
    return [
        {
            'slug': slug,
            'name': data['name'],
            'description': data['description']
        }
        for slug, data in KEYWORDS_MAP.items()
    ]

def get_theme_config(theme_slug):
    """Retorna configuração de uma categoria temática"""
    return KEYWORDS_MAP.get(theme_slug)

def get_theme_keyword_ids(theme_slug):
    """
    Retorna IDs das keywords de uma categoria
<<<<<<< HEAD
    COM CACHE INTELIGENTE (SQLite + Memória)
    """
    # Verifica cache SQLite primeiro
    cached_ids = get_cached_theme_ids(theme_slug)
    if cached_ids:
        xbmc.log(f"[Keywords] Cache HIT para tema: {theme_slug}", xbmc.LOGDEBUG)
        return cached_ids
    
=======
    Busca dinamicamente no TMDb se necessário
    """
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
    config = KEYWORDS_MAP.get(theme_slug)
    if not config:
        return []
    
    keyword_names = config['keywords']
<<<<<<< HEAD
    
    # Busca IDs (com cache LRU)
    keyword_ids = resolve_keywords(keyword_names)
    
    # Filtra None values
    valid_ids = [kid for kid in keyword_ids if kid is not None]
    
    # Salva no cache SQLite
    if valid_ids:
        save_theme_cache(theme_slug, valid_ids)
    
    return valid_ids
=======
    return resolve_keywords(keyword_names)
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260

def search_theme_slug(query):
    """Busca categoria por termo em português"""
    query_lower = query.lower()
    
    # Busca exata
    if query_lower in KEYWORDS_MAP:
        return query_lower
    
    # Busca parcial no nome
    for slug, data in KEYWORDS_MAP.items():
        if query_lower in slug or query_lower in data['name'].lower():
            return slug
    
<<<<<<< HEAD
    return None

def preload_common_themes():
    """Pré-carrega temas comuns em segundo plano para cache"""
    common_themes = ["neve", "praia", "zumbi", "vampiro", "natal", "espacial"]
    
    for theme in common_themes:
        get_theme_keyword_ids(theme)  # Isso vai popular o cache

# Inicializa o banco de cache na primeira importação
try:
    init_cache_db()
    xbmc.log("[Keywords] Cache DB inicializado", xbmc.LOGINFO)
except Exception as e:
    xbmc.log(f"[Keywords] Erro inicializando cache DB: {e}", xbmc.LOGERROR)
=======
    return None
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
