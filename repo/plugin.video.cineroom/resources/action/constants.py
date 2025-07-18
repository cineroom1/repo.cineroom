PROVEDORES = [
    {"name": "Netflix", "icon": "https://logopng.com.br/logos/netflix-94.png"},
    {"name": "Amazon Prime Video", "icon": "https://upload.wikimedia.org/wikipedia/commons/f/f1/Prime_Video.png"},
    {"name": "Disney Plus", "icon": "https://logospng.org/wp-content/uploads/disneyplus.png"},
    {"name": "Max", "icon": "https://logospng.org/wp-content/uploads/hbo-max.png"},
    {"name": "Globoplay", "icon": "https://logospng.org/wp-content/uploads/globoplay.png"},
    {"name": "Star Plus", "icon": "https://logospng.org/wp-content/uploads/star-plus.png"},
    {"name": "Paramount Plus", "icon": "https://logospng.org/wp-content/uploads/paramount-plus.png"},
    {"name": "Apple TV", "icon": "https://w7.pngwing.com/pngs/911/587/png-transparent-apple-tv-hd-logo.png"},
    {"name": "Telecine Amazon Channel", "icon": "https://logospng.org/wp-content/uploads/telecine.png"},
    {"name": "MUBI", "icon": "https://upload.wikimedia.org/wikipedia/commons/3/3c/Mubi_logo.svg"},
    {"name": "Crunchyroll", "icon": "https://upload.wikimedia.org/wikipedia/commons/1/1e/Crunchyroll_Logo.svg"},
    {"name": "YouTube Premium", "icon": "https://logospng.org/wp-content/uploads/youtube-premium.png"},
    {"name": "Pluto TV", "icon": "https://logospng.org/wp-content/uploads/pluto-tv.png"},
    {"name": "Tubi", "icon": "https://upload.wikimedia.org/wikipedia/commons/5/58/Tubi_logo.svg"},
    {"name": "MGM+ Apple TV Channel", "icon": "https://logodownload.org/wp-content/uploads/2021/10/MGM+logo.png"},
    {"name": "Looke", "icon": "https://seeklogo.com/images/L/looke-logo-4146BCD25D-seeklogo.com.png"}
]


# Lista de estúdios predefinidos
ESTUDIOS_FILMES = [
    "Universal Pictures", "Warner Bros.", "Paramount Pictures", "Sony Pictures",
    "20th Century Studios", "Walt Disney Pictures", "Pixar", "DreamWorks Animation",
    "Columbia Pictures", "Legendary Pictures", "DC Comics", "A24", "Marvel Studios",
    "MGM", "Lionsgate", "New Line Cinema", "Original Film", "Fox 2000 Pictures",
    "Sunday Night Productions", "Blue Sky Studios", "Lucasfilm Ltd.",
    "Blumhouse Productions", "Skydance Media", "Studio Ghibli"
]

GENRES = [
    {'name': 'Ação', 'key': 'Ação'},
    {'name': 'Animação', 'key': 'Animação'},
    {'name': 'Aventura', 'key': 'Aventura'}, 
    {'name': 'Cinema TV', 'key': 'Cinema TV'},
    {'name': 'Comédia', 'key': 'Comédia'},
    {'name': 'Crime', 'key': 'Crime'},
    {'name': 'Documentário', 'key': 'Documentário'},
    {'name': 'Drama', 'key': 'Drama'},
    {'name': 'Fantasia', 'key': 'Fantasia'}, 
    {'name': 'Faroeste', 'key': 'Faroeste'},
    {'name': 'Ficção Científica', 'key': 'Ficção científica'},
    {'name': 'Família', 'key': 'Família'},
    {'name': 'Guerra', 'key': 'Guerra'},
    {'name': 'História', 'key': 'História'},
    {'name': 'Mistério', 'key': 'Mistério'}, 
    {'name': 'Música', 'key': 'Música'},
    {'name': 'Romance', 'key': 'Romance'},
    {'name': 'Terror', 'key': 'Terror'},
    {'name': 'Thriller', 'key': 'Thriller'}
]


KEYWORDS = [
    {'name': 'Alienígena',     'key': 'alien'},
    {'name': 'Anime',          'key': 'anime'},
    {'name': 'Artes Marciais', 'key': 'martial arts'},
    {'name': 'Apocalipse',     'key': 'apocalypse'},
    {'name': 'Assassinato',    'key': 'murder'},
    {'name': 'Católico',       'key': 'catholic'},
    {'name': 'Cristão',        'key': 'religion'},
    {'name': 'Distopia',       'key': 'dystopia'},
    {'name': 'Dublados',       'key': 'dublado'},
    {'name': 'Escravidão',     'key': 'slavery'},
    {'name': 'Fantasma',       'key': 'ghost'},
    {'name': 'Games',          'key': 'video game'},
    {'name': 'Gelo',           'key': 'snow'},
    {'name': 'Lgbtqia+',       'key': 'lgbt'},
    {'name': 'Loop Temporal',  'key': 'time loop'},
    {'name': 'Luta',           'key': 'fight'},
    {'name': 'Magia',          'key': 'magic'},
    {'name': 'Natal',          'key': 'christmas'},
    {'name': 'Pós-Apocalíptico','key': 'post-apocalyptic future'},
    {'name': 'Paródia',        'key': 'parody'},
    {'name': 'Robôs',          'key': 'robot'},
    {'name': 'Samurai',        'key': 'samurai'},
    {'name': 'Sátira',         'key': 'satire'},
    {'name': 'Serial Killer',  'key': 'serial killer'},
    {'name': 'Slash',          'key': 'slasher'},
    {'name': 'Super-Herói',    'key': 'superhero'},
    {'name': 'Vampiro',        'key': 'vampire'},
    {'name': 'Viagem no Tempo','key': 'time travel'},
    {'name': 'Vingança',       'key': 'rape and revenge'},
    {'name': 'Zumbi',          'key': 'zombie'},
]



# Mapeamento de códigos de idioma para nomes amigáveis
IDIOMA_NOMES = {
    "en": "EUA",
    "pt": "Brasil",
    "es": "Espanha",
    "fr": "França",
    "de": "Alemanha",
    "ja": "Japão",
    "ko": "Coreia do Sul",
    "it": "Itália",
    "ru": "Rússia",
    "zh": "China",
    "hi": "Índia",
    # Adicione mais conforme necessário.
}

IDIOMA_PARA_PAIS = {
    "en": "us",
    "pt": "br",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "ja": "jp",
    "ko": "kr",
    "it": "it",
    "ru": "ru",
    "zh": "cn",
    "hi": "in",
}

# Lista de anos pré-programados (últimos 20 anos, por exemplo)
ANOS_FILMES = [str(year) for year in range(2024, 1939, -1)] 