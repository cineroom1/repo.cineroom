# -*- coding: utf-8 -*-
# resources/lib/keywords.py

"""
Sistema de Categorias Temáticas com Keywords do TMDb
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
        "genres": [878],
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
        "genres": [878],
        "description": "IA e robôs"
    },
    "realidade_virtual": {
        "keywords": ["virtual reality"],
        "name": "Realidade Virtual",
        "genres": [878],
        "description": "VR e mundos virtuais"
    },
    
    # 🧟 CRIATURAS
    "zumbi": {
        "keywords": ["zombie", "undead"],
        "name": "Apocalipse Zumbi",
        "genres": [27],
        "description": "Filmes de zumbis"
    },
    "vampiro": {
        "keywords": ["vampire"],
        "name": "Vampiros",
        "genres": [27, 14],
        "description": "Vampiros e criaturas da noite"
    },
    "lobisomem": {
        "keywords": ["werewolf"],
        "name": "Lobisomens",
        "genres": [27, 14],
        "description": "Lobisomens e licantropia"
    },
    "alienigena": {
        "keywords": ["alien", "extraterrestrial"],
        "name": "Alienígenas",
        "genres": [878],
        "description": "Invasões e contatos alienígenas"
    },
    "dinossauro": {
        "keywords": ["dinosaur"],
        "name": "Dinossauros",
        "genres": [878, 12],
        "description": "Dinossauros e era pré-histórica"
    },
    "dragao": {
        "keywords": ["dragon"],
        "name": "Dragões",
        "genres": [14],
        "description": "Dragões e mitologia"
    },
    
    # 🎯 TEMAS & AÇÕES
    "vinganca": {
        "keywords": ["revenge", "vengeance"],
        "name": "Vingança",
        "genres": [28, 53],
        "description": "Filmes de vingança épica"
    },
    "assalto": {
        "keywords": ["heist", "bank robbery"],
        "name": "Assaltos & Heist",
        "genres": [80, 28],
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
        "genres": [28, 878],
        "description": "Fim do mundo e pós-apocalipse"
    },
    "viagem_tempo": {
        "keywords": ["time travel"],
        "name": "Viagem no Tempo",
        "genres": [878],
        "description": "Viagens temporais"
    },
    "distopia": {
        "keywords": ["dystopia"],
        "name": "Distopia",
        "genres": [878, 18],
        "description": "Futuros distópicos"
    },
    
    # 👤 PROFISSÕES
    "assassino": {
        "keywords": ["assassin", "hitman"],
        "name": "Assassinos",
        "genres": [28, 53],
        "description": "Assassinos profissionais"
    },
    "detetive": {
        "keywords": ["detective", "investigation"],
        "name": "Detetives",
        "genres": [9648, 80],
        "description": "Investigações e detetives"
    },
    "policia": {
        "keywords": ["police", "cop"],
        "name": "Polícia",
        "genres": [28, 80],
        "description": "Policiais e investigações"
    },
    "espia": {
        "keywords": ["spy", "espionage"],
        "name": "Espiões",
        "genres": [28, 53],
        "description": "Espiões e missões secretas"
    },
    "pirata": {
        "keywords": ["pirate"],
        "name": "Piratas",
        "genres": [12, 28],
        "description": "Piratas e aventuras nos mares"
    },
    
    # 🏛️ LUGARES & ÉPOCAS
    "prisao": {
        "keywords": ["prison", "jail"],
        "name": "Prisão",
        "genres": [18],
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
        "genres": [18],
        "description": "Ambientes hospitalares"
    },
    "medieval": {
        "keywords": ["medieval", "middle ages"],
        "name": "Era Medieval",
        "genres": [36, 14],
        "description": "Cavaleiros e castelos"
    },
    "segunda_guerra": {
        "keywords": ["world war ii", "ww2"],
        "name": "Segunda Guerra",
        "genres": [10752, 36],
        "description": "Segunda Guerra Mundial"
    },
    "faroeste": {
        "keywords": ["western", "cowboy"],
        "name": "Faroeste",
        "genres": [37],
        "description": "Western e cowboys"
    },
    "nova_york": {
        "keywords": ["new york city"],
        "name": "Nova York",
        "genres": [],
        "description": "Filmes ambientados em NYC"
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
        "genres": [28, 878],
        "description": "Heróis e vilões"
    },
    "natal": {
        "keywords": ["christmas", "santa claus"],
        "name": "Natal",
        "genres": [35, 10751],
        "description": "Filmes de Natal"
    },
    "halloween": {
        "keywords": ["halloween"],
        "name": "Halloween",
        "genres": [27],
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
        "genres": [18],
        "description": "Lutas e boxe"
    },
    "corrida": {
        "keywords": ["car racing", "racing"],
        "name": "Corridas",
        "genres": [28],
        "description": "Corridas e velocidade"
    },
    "artes_marciais": {
        "keywords": ["martial arts", "kung fu"],
        "name": "Artes Marciais",
        "genres": [28],
        "description": "Kung fu e artes marciais"
    },
    
    # 🎨 ADICIONAIS
    "musica": {
        "keywords": ["musician", "rock band"],
        "name": "Música",
        "genres": [10402],
        "description": "Filmes sobre música"
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
    Busca dinamicamente no TMDb se necessário
    """
    config = KEYWORDS_MAP.get(theme_slug)
    if not config:
        return []
    
    keyword_names = config['keywords']
    return resolve_keywords(keyword_names)

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
    
    return None