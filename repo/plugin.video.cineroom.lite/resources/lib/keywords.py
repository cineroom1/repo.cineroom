# -*- coding: utf-8 -*-
# resources/lib/keywords.py
"""
Categorias temáticas — filtro 100% LOCAL via campo 'keywords' do JSON curado.

Sem chamadas de rede. Sem SQLite de cache. Sem threads de resolução.
Os filmes/séries já têm 'keywords' populados pelo script enrich_keywords.py.
A busca por tema é um simples SELECT WHERE no banco local.
"""

import xbmc

# ---------------------------------------------------------------------------
# MAPA DE TEMAS
# 'keywords': strings que devem aparecer no campo keywords do JSON/DB
#             (lowercase, exatamente como o TMDB retorna)
# 'genres':   genre_ids opcionais para filtro adicional (pode deixar vazio)
# ---------------------------------------------------------------------------
KEYWORDS_MAP = {
    # 🌨️ NATUREZA & CLIMA
    "neve": {
        "name": "Neve",
        "description": "Filmes ambientados na neve e inverno",
        "keywords": ["snow", "winter"],
        "genres": [],
    },
    "praia": {
        "name": "Praia & Verão",
        "description": "Filmes de verão, praia e oceano",
        "keywords": ["beach", "summer"],
        "genres": [],
    },
    "deserto": {
        "name": "Deserto",
        "description": "Ambientados em desertos",
        "keywords": ["desert"],
        "genres": [],
    },
    "floresta": {
        "name": "Floresta & Selva",
        "description": "Aventuras em florestas e selvas",
        "keywords": ["jungle", "forest"],
        "genres": [],
    },
    "oceano": {
        "name": "Oceano",
        "description": "Aventuras submarinas",
        "keywords": ["ocean", "underwater"],
        "genres": [],
    },
    "espacial": {
        "name": "Espaço Sideral",
        "description": "Viagens espaciais e universo",
        "keywords": ["space", "astronaut"],
        "genres": [],
    },

    # 🎮 TECH & GAMES
    "videogame": {
        "name": "Videogames",
        "description": "Filmes sobre games e gamers",
        "keywords": ["video game", "gamer"],
        "genres": [],
    },
    "hacker": {
        "name": "Hackers & Cyber",
        "description": "Hackers e tecnologia",
        "keywords": ["hacker", "cyber"],
        "genres": [],
    },
    "inteligencia_artificial": {
        "name": "Inteligência Artificial",
        "description": "IA e robôs",
        "keywords": ["artificial intelligence", "robot"],
        "genres": [],
    },
    "realidade_virtual": {
        "name": "Realidade Virtual",
        "description": "VR e mundos virtuais",
        "keywords": ["virtual reality"],
        "genres": [],
    },

    # 🧟 CRIATURAS
    "zumbi": {
        "name": "Apocalipse Zumbi",
        "description": "Filmes de zumbis",
        "keywords": ["zombie", "undead"],
        "genres": [],
    },
    "vampiro": {
        "name": "Vampiros",
        "description": "Vampiros e criaturas da noite",
        "keywords": ["vampire"],
        "genres": [],
    },
    "lobisomem": {
        "name": "Lobisomens",
        "description": "Lobisomens e licantropia",
        "keywords": ["werewolf"],
        "genres": [],
    },
    "alienigena": {
        "name": "Alienígenas",
        "description": "Invasões e contatos alienígenas",
        "keywords": ["alien", "extraterrestrial"],
        "genres": [],
    },
    "dinossauro": {
        "name": "Dinossauros",
        "description": "Dinossauros e era pré-histórica",
        "keywords": ["dinosaur"],
        "genres": [],
    },
    "dragao": {
        "name": "Dragões",
        "description": "Dragões e mitologia",
        "keywords": ["dragon"],
        "genres": [],
    },

    # 🎯 TEMAS & AÇÕES
    "vinganca": {
        "name": "Vingança",
        "description": "Filmes de vingança épica",
        "keywords": ["revenge", "vengeance"],
        "genres": [],
    },
    "assalto": {
        "name": "Assaltos & Heist",
        "description": "Grandes assaltos e golpes",
        "keywords": ["heist", "bank robbery"],
        "genres": [],
    },
    "sobrevivencia": {
        "name": "Sobrevivência",
        "description": "Luta pela sobrevivência",
        "keywords": ["survival"],
        "genres": [],
    },
    "apocalipse": {
        "name": "Apocalipse",
        "description": "Fim do mundo e pós-apocalipse",
        "keywords": ["apocalypse", "post-apocalyptic"],
        "genres": [],
    },
    "viagem_tempo": {
        "name": "Viagem no Tempo",
        "description": "Viagens temporais",
        "keywords": ["time travel"],
        "genres": [],
    },
    "distopia": {
        "name": "Distopia",
        "description": "Futuros distópicos",
        "keywords": ["dystopia"],
        "genres": [],
    },

    # 👤 PROFISSÕES
    "assassino": {
        "name": "Assassinos",
        "description": "Assassinos profissionais",
        "keywords": ["assassin", "hitman"],
        "genres": [],
    },
    "detetive": {
        "name": "Detetives",
        "description": "Investigações e detetives",
        "keywords": ["detective", "investigation"],
        "genres": [],
    },
    "policia": {
        "name": "Polícia",
        "description": "Policiais e investigações",
        "keywords": ["police", "cop"],
        "genres": [],
    },
    "espia": {
        "name": "Espiões",
        "description": "Espiões e missões secretas",
        "keywords": ["spy", "espionage"],
        "genres": [],
    },
    "pirata": {
        "name": "Piratas",
        "description": "Piratas e aventuras nos mares",
        "keywords": ["pirate"],
        "genres": [],
    },

    # 🏛️ LUGARES & ÉPOCAS
    "prisao": {
        "name": "Prisão",
        "description": "Filmes de prisão",
        "keywords": ["prison", "jail"],
        "genres": [],
    },
    "escola": {
        "name": "Escola",
        "description": "Ambientados em escolas",
        "keywords": ["school", "high school"],
        "genres": [],
    },
    "hospital": {
        "name": "Hospital",
        "description": "Ambientes hospitalares",
        "keywords": ["hospital", "doctor"],
        "genres": [],
    },
    "medieval": {
        "name": "Era Medieval",
        "description": "Cavaleiros e castelos",
        "keywords": ["medieval", "middle ages"],
        "genres": [],
    },

    # 🎭 ESPECIAIS
    "baseado_fatos": {
        "name": "Baseado em Fatos Reais",
        "description": "Histórias verídicas",
        "keywords": ["based on true story", "true story"],
        "genres": [],
    },
    "baseado_livro": {
        "name": "Baseado em Livros",
        "description": "Adaptações literárias",
        "keywords": ["based on novel", "literary adaptation"],
        "genres": [],
    },
    "super_heroi": {
        "name": "Super-Heróis",
        "description": "Heróis e vilões",
        "keywords": ["superhero", "comic book"],
        "genres": [],
    },
    "natal": {
        "name": "Natal",
        "description": "Filmes de Natal",
        "keywords": ["christmas", "santa claus"],
        "genres": [],
    },
    "halloween": {
        "name": "Halloween",
        "description": "Filmes de Halloween",
        "keywords": ["halloween"],
        "genres": [],
    },

    # 🎬 ESPORTES
    "futebol": {
        "name": "Futebol",
        "description": "Filmes de futebol",
        "keywords": ["football", "soccer"],
        "genres": [],
    },
    "boxe": {
        "name": "Boxe",
        "description": "Lutas e boxe",
        "keywords": ["boxing", "boxer"],
        "genres": [],
    },
    "corrida": {
        "name": "Corridas",
        "description": "Corridas e velocidade",
        "keywords": ["car racing", "racing"],
        "genres": [],
    },
    "artes_marciais": {
        "name": "Artes Marciais",
        "description": "Kung fu e artes marciais",
        "keywords": ["martial arts", "kung fu"],
        "genres": [],
    },
    "danca": {
        "name": "Dança",
        "description": "Filmes de dança",
        "keywords": ["dance", "dancing"],
        "genres": [],
    },
}


# ---------------------------------------------------------------------------
# API pública — mesma interface de antes
# ---------------------------------------------------------------------------

def get_all_theme_categories():
    """Retorna lista de categorias para exibir no menu."""
    return [
        {'slug': slug, 'name': data['name'], 'description': data['description']}
        for slug, data in KEYWORDS_MAP.items()
    ]


def get_theme_config(theme_slug):
    """Retorna config completa do tema (name, description, keywords, genres)."""
    return KEYWORDS_MAP.get(theme_slug)


def get_theme_keywords(theme_slug):
    """
    Retorna lista de strings de keywords para filtro local no DB.
    Ex: 'assalto' → ['heist', 'bank robbery']

    Zero chamadas de rede — leitura direta do dict em memória.
    """
    cfg = KEYWORDS_MAP.get(theme_slug)
    if not cfg:
        return []
    kws = cfg.get("keywords", [])
    return kws


# Mantido para compatibilidade com código que ainda chame a versão antiga.
# Retorna strings (não IDs numéricos) — movies.py e tvshows.py já foram atualizados.
def get_theme_keyword_ids(theme_slug):
    return get_theme_keywords(theme_slug)


def search_theme_slug(query):
    """Busca slug pelo nome ou slug parcial."""
    q = (query or "").lower()
    if q in KEYWORDS_MAP:
        return q
    for slug, data in KEYWORDS_MAP.items():
        if q in slug or q in data['name'].lower():
            return slug
    return None


def preload_common_themes():
    """Não-op: IDs já estão em memória, nada para pré-carregar."""
    pass