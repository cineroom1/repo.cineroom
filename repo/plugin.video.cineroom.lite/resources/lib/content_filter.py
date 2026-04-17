# -*- coding: utf-8 -*-
"""
Sistema de Filtragem de Conteúdo - VERSÃO 2.2 ULTRA-RIGOROSO KIDS
Changelog v2.2:
- Sistema de WHITELIST de gêneros (só permite gêneros seguros)
- BLOQUEIO de todos os outros gêneros (incluindo Ação, Guerra, etc)
- PG-13 COMPLETAMENTE BLOQUEADO para kids (não importa a whitelist)
- Documentação de como implementar nas queries SQL
"""

import xbmc
import json

# === CERTIFICAÇÕES PERMITIDAS POR FAIXA ETÁRIA (ULTRA-RIGOROSO) ===
CERTIFICATIONS_BY_AGE = {
    'livre': {
        # APENAS conteúdo TOTALMENTE livre (todas as idades)
        'L', 'LIVRE', 'G', 'TV-Y', 'TV-G', 'U', 'ALL'
    },
    '2_6_anos': {
        # Crianças pequenas - apenas conteúdo muito leve
        # ⚠️ ATENÇÃO: Mesmo com "L", precisa passar pelo filtro de segurança adicional
        'L', 'LIVRE', 'G', 'TV-Y', 'TV-G', 'U', 'ALL'
    },
    '7_10_anos': {
        # Crianças - conteúdo leve (SEM PG-13!)
        'L', 'LIVRE', '10', 'G', 'PG', 'TV-Y', 'TV-Y7', 
        'TV-G', 'TV-PG', 'U', 'ALL', 'A', 'ATP'
    },
    '11_14_anos': {
        # Pré-adolescentes - até 12-14 anos (AINDA SEM PG-13)
        'L', 'LIVRE', '10', '12', '12A', '14', 'G', 'PG', 
        'TV-Y', 'TV-Y7', 'TV-G', 'TV-PG', 'TV-14', 'U', 'ALL', 'A', 'ATP'
    },
    # RETROCOMPATIBILIDADE - mapeamentos antigos
    '10_anos': {
        'L', 'LIVRE', '10', 'G', 'PG', 'TV-Y', 'TV-Y7', 
        'TV-G', 'TV-PG', 'U', 'ALL', 'A', 'ATP'
    },
    '12_anos': {
        'L', 'LIVRE', '10', '12', '12A', 'G', 'PG', 
        'TV-Y', 'TV-Y7', 'TV-G', 'TV-PG', 'TV-14', 'U', 'ALL', 'A', 'ATP'
    },
    '14_anos': {
        'L', 'LIVRE', '10', '12', '12A', '14', 'G', 'PG', 
        'TV-Y', 'TV-Y7', 'TV-G', 'TV-PG', 'TV-14', 'U', 'ALL', 'A', 'ATP'
    },
}

# ============================================================
# FILTRO EXTRA PARA 2-6 ANOS (além da certificação)
# ============================================================

# ⚠️ PROBLEMA: Certificação "L" no Brasil é muito ampla
# Exemplos problemáticos: Harry Potter (L), Frozen (L), etc.
# SOLUÇÃO: Sistema de pontuação de segurança

# Títulos e palavras-chave que indicam conteúdo NÃO adequado para 2-6 anos
KEYWORDS_NOT_FOR_TODDLERS = {
    # Palavras assustadoras
    'brux', 'witch', 'assombr', 'haunted', 'medo', 'scary', 'terror', 'horror',
    'monstro', 'monster', 'zumbi', 'zombie', 'fantasma', 'ghost',
    
    # Violência/Luta
    'guerra', 'war', 'luta', 'fight', 'batalha', 'battle', 'combat',
    'espada', 'sword', 'arma', 'weapon', 'sangue', 'blood',
    
    # Temas complexos
    'morte', 'death', 'funeral', 'morre', 'dies', 'kill',
    'veneno', 'poison', 'magia negra', 'dark magic',
    
    # Franchises conhecidas por serem intensas
    'harry potter', 'senhor dos anéis', 'lord of the rings',
    'star wars', 'marvel', 'dc comics', 'batman', 'superman',
}

# Gêneros garantidos para crianças pequenas
GUARANTEED_TODDLER_GENRES = {
    'Animação', 'Animation',
    'Família', 'Family',
    'Infantil', 'Kids', 'Children',
    'Musical', 'Music',
}

# IDs conhecidos de conteúdo NÃO adequado para 2-6 anos (mesmo com "L")
NOT_FOR_TODDLERS_IDS = {
    # Harry Potter (todos) - muito assustador
    671,    # Pedra Filosofal
    672,    # Câmara Secreta
    673,    # Prisioneiro de Azkaban
    674,    # Cálice de Fogo
    675,    # Ordem da Fênix
    767,    # Relíquias da Morte Parte 1
    12444,  # Relíquias da Morte Parte 2
    
    # Frozen - cenas assustadoras para crianças pequenas
    109445, # Frozen 1
    330457, # Frozen 2
    
    # Moana - perigosa para crianças pequenas
    277834,
    
    # Outros filmes "L" mas intensos
    862,    # Toy Story (pode assustar crianças pequenas)
    863,    # Toy Story 2
    10193,  # Toy Story 3
    301528, # Toy Story 4
    
    # Branca de Neve (versões live-action - assustadoras)
    447273, # Snow White (2025) - cenas de bruxa assustadoras
}

# Certificações SEMPRE bloqueadas para perfis infantis
ADULT_CERTIFICATIONS = {
    '16', '18', 'R', 'NC-17', 'TV-MA', 'M', 'MA15+', 'R18+', 'X', 'AO',
    'PG-13',  # ⚠️ BLOQUEADO TOTALMENTE para kids (muito violento)
}

# ============================================================
# NOVO SISTEMA: WHITELIST DE GÊNEROS SEGUROS
# ============================================================

# ✅ APENAS estes gêneros são permitidos para kids
SAFE_KIDS_GENRES = {
    # Gêneros infantis garantidos
    'Animação', 'Animation',
    'Família', 'Family',
    'Infantil', 'Kids', 'Children',
    
    # Gêneros leves permitidos
    'Comédia', 'Comedy',
    'Aventura', 'Adventure',  # ⚠️ CUIDADO: só se combinado com animação/família
    'Fantasia', 'Fantasy',     # ⚠️ CUIDADO: só se combinado com animação/família
    'Musical', 'Music',
    'Documentário', 'Documentary',  # Educativo
    'Educação', 'Educational',
}

# ❌ Gêneros que NUNCA devem aparecer para kids
ALWAYS_BLOCKED_GENRES = {
    # Violência/Terror
    'Terror', 'Horror',
    'Thriller',
    'Suspense',
    
    # Ação/Violência
    'Ação', 'Action',  # ⚠️ NOVO: muito violento (ex: Colombiana, John Wick)
    'Guerra', 'War',
    'Western',
    
    # Crime/Drogas
    'Crime',
    'Noir', 'Film Noir',
    
    # Adulto
    'Romance',  # Pode ter conteúdo adulto
    'Drama',    # ⚠️ CONTROVERSO: muitos dramas pesados (considere bloquear)
}

# Gêneros que DEVEM ter outro gênero seguro junto
# (ex: "Aventura" sozinho = BLOQUEADO, "Aventura + Animação" = OK)
REQUIRES_SAFE_COMPANION = {
    'Aventura', 'Adventure',
    'Fantasia', 'Fantasy',
}

# ============================================================
# BLACKLISTS
# ============================================================

# Blacklist global de IDs (pode ser sobrescrito por whitelist do perfil)
KNOWN_ADULT_CONTENT = {
    # Séries adultas
    60625,  # Rick and Morty
    1438,   # The Wire
    1396,   # Breaking Bad
    1402,   # The Walking Dead
    1399,   # Game of Thrones
    46952,  # The Boys
    60059,  # Better Call Saul
    110492, # Squid Game
    
    # Filmes de ação violentos PG-13
    # (adicione IDs conforme encontrar casos problemáticos)
}


class ContentFilter:
    """
    Filtro de conteúdo ULTRA-RIGOROSO para perfis kids
    
    MUDANÇAS PRINCIPAIS v2.2:
    - Sistema de whitelist de gêneros (só permite gêneros seguros)
    - Bloqueia TODOS os outros gêneros não listados
    - PG-13 COMPLETAMENTE bloqueado para kids
    """
    
    def __init__(self, profile=None):
        self.profile = profile
        self.is_kids = profile.get('is_kids', False) if profile else False
        
        # Configurações de idade
        self.age_range = profile.get('preferences', {}).get('age_range', '7_10_anos') if profile else '7_10_anos'
        self.allow_uncertified = profile.get('preferences', {}).get('allow_uncertified', False) if profile else False
        
        # ⚠️ PG-13 nunca permitido para kids, independente da config
        self.allow_pg13 = False  # Forçado como False para kids
        
        # Listas personalizadas do perfil
        self.profile_whitelist = set()
        self.profile_blacklist = set()
        
        if profile:
            # Extrair IDs da whitelist
            for item in profile.get('content_whitelist', []):
                self.profile_whitelist.add(item['tmdb_id'])
            
            # Extrair IDs da blacklist
            for item in profile.get('content_blacklist', []):
                self.profile_blacklist.add(item['tmdb_id'])
        
        self.allowed_certs = CERTIFICATIONS_BY_AGE.get(self.age_range, CERTIFICATIONS_BY_AGE['7_10_anos'])
        
    
    def should_filter_content(self):
        """Verifica se filtro está ativo"""
        return self.is_kids
    
    def get_sql_where_clause(self, table_prefix='', media_type='movie'):
        """
        Gera cláusula SQL WHERE para filtrar no banco (ULTRA-RIGOROSO)
        
        IMPORTANTE: Esta função DEVE ser chamada nas queries SQL!
        
        EXEMPLO DE USO:
        ```python
        content_filter = get_content_filter()
        where_clause = content_filter.get_sql_where_clause('m.', 'movie')
        
        query = f'''
            SELECT * FROM movies m
            WHERE 1=1
            {f"AND {where_clause}" if where_clause else ""}
            ORDER BY popularity DESC
        '''
        ```
        
        Args:
            table_prefix: Prefixo da tabela (ex: 'm.', 'tv.')
            media_type: 'movie' ou 'tvshow'
        
        Returns:
            str: Cláusula SQL WHERE (sem 'WHERE' inicial)
        """
        if not self.is_kids:
            return ""

        prefix = table_prefix

        # Campo correto por tipo
        if media_type == 'movie':
            cert_col = f"{prefix}certification"
        elif media_type in ('tvshow', 'tv'):
            cert_col = f"{prefix}classification"
        else:
            return "1=0"  # Tipo desconhecido → BLOQUEIA

        conditions = []

        # 1. WHITELIST DO PERFIL (sempre permitir)
        if self.profile_whitelist:
            whitelist_ids = ','.join(str(i) for i in self.profile_whitelist)
            whitelist_condition = f"{prefix}tmdb_id IN ({whitelist_ids})"
        else:
            whitelist_condition = None

        # 2. BLACKLIST DO PERFIL + GLOBAL
        combined_blacklist = KNOWN_ADULT_CONTENT | self.profile_blacklist
        if combined_blacklist:
            blacklist_ids = ','.join(str(i) for i in combined_blacklist)
            conditions.append(f"{prefix}tmdb_id NOT IN ({blacklist_ids})")

        # 3. CLASSIFICAÇÃO OBRIGATÓRIA (ULTRA-RIGOROSA)
        allowed = [
            f"UPPER({cert_col}) LIKE '%{cert}%'"
            for cert in self.allowed_certs
        ]

        # PG-13 SEMPRE bloqueado para kids
        blocked_certs = ADULT_CERTIFICATIONS.copy()
        
        blocked = [
            f"UPPER({cert_col}) NOT LIKE '%{cert}%'"
            for cert in blocked_certs
        ]

        cert_condition = (
            f"({cert_col} IS NOT NULL "
            f"AND TRIM({cert_col}) != '' "
            f"AND ({' OR '.join(allowed)}) "
            f"AND {' AND '.join(blocked)})"
        )

        # 4. ✅ WHITELIST DE GÊNEROS (NOVO SISTEMA ULTRA-RIGOROSO)
        safe_genre_conditions = []
        for genre in SAFE_KIDS_GENRES:
            safe_genre_conditions.append(
                f"{prefix}genres LIKE '%\"{genre}\"%'"
            )
        
        # Deve ter pelo menos UM gênero seguro
        has_safe_genre = f"({' OR '.join(safe_genre_conditions)})"

        # 5. ❌ BLOQUEAR gêneros perigosos (redundante mas garante)
        blocked_genre_conditions = []
        for genre in ALWAYS_BLOCKED_GENRES:
            blocked_genre_conditions.append(
                f"({prefix}genres IS NULL OR {prefix}genres NOT LIKE '%\"{genre}\"%')"
            )
        
        no_blocked_genres = ' AND '.join(blocked_genre_conditions)

        # MONTAR QUERY FINAL
        # Estrutura: (whitelist_perfil) OU (certificação OK E gênero OK E sem gêneros bloqueados)
        genre_filter = f"({has_safe_genre} AND {no_blocked_genres})"
        
        if whitelist_condition:
            final_condition = f"({whitelist_condition} OR ({cert_condition} AND {genre_filter}))"
        else:
            final_condition = f"({cert_condition} AND {genre_filter})"

        # Adicionar blacklist
        if conditions:
            final_condition = f"{final_condition} AND {' AND '.join(conditions)}"

        return final_condition
    
    def is_content_allowed(self, tmdb_id, item_info=None):
        """
        Verifica se conteúdo é permitido (ULTRA-RIGOROSO)
        
        Para 2-6 anos: Filtro EXTRA além da certificação
        """
        if not self.is_kids:
            return (True, "Perfil adulto")
        
        # 1. Whitelist do perfil (sempre permitir)
        if tmdb_id in self.profile_whitelist:
            return (True, "Na whitelist do perfil")
        
        # 2. Blacklist
        if tmdb_id in self.profile_blacklist:
            return (False, "Na blacklist do perfil")
        
        if tmdb_id in KNOWN_ADULT_CONTENT:
            return (False, "Conteúdo adulto conhecido")
        
        # 3. Se não tem info, BLOQUEAR
        if not item_info:
            return (False, "Sem informações - bloqueado por segurança")
        
        # 🍼 4. FILTRO ESPECIAL PARA 2-6 ANOS (antes da certificação!)
        if self.age_range == '2_6_anos':
            is_safe, reason = self._is_safe_for_toddlers(tmdb_id, item_info)
            if not is_safe:
                return (False, f"❌ 2-6 anos: {reason}")
        
        # 5. Validar certificação
        cert = self._get_certification(item_info, item_info.get('type', 'movie'))
        
        if cert:
            cert_upper = cert.upper().strip()
            
            # PG-13 SEMPRE bloqueado para kids
            if 'PG-13' in cert_upper or 'PG13' in cert_upper:
                return (False, "PG-13 completamente bloqueado para kids")
            
            # Certificação adulta?
            if any(adult_cert in cert_upper for adult_cert in ADULT_CERTIFICATIONS):
                return (False, f"Classificação adulta: {cert}")
            
            # Certificação permitida?
            if not any(allowed in cert_upper for allowed in self.allowed_certs):
                return (False, f"Classificação não apropriada: {cert}")
        
        # 6. ✅ NOVO: Validar gêneros com sistema de whitelist
        genres = self._extract_genres(item_info)
        
        # Tem algum gênero bloqueado?
        if self._has_blocked_genre_strict(genres):
            blocked = self._get_blocked_genres(genres)
            return (False, f"Gênero bloqueado: {', '.join(blocked)}")
        
        # Tem pelo menos um gênero seguro?
        if not self._has_safe_genre(genres):
            return (False, "Sem gêneros seguros para kids")
        
        # Gêneros que precisam de companhia segura (Aventura/Fantasia)
        if self._needs_safe_companion(genres):
            if not self._has_guaranteed_kids_genre(genres):
                return (False, "Aventura/Fantasia sem gênero infantil junto")
        
        # 7. Passou em todos os testes!
        return (True, f"✅ Conteúdo aprovado: {cert or 'sem cert'}, gêneros OK")
    
    def _is_safe_for_toddlers(self, tmdb_id, item_info):
        """
        🍼 FILTRO EXTRA para 2-6 anos
        
        Problema: "L" no Brasil é muito amplo (inclui Harry Potter, Frozen, etc)
        Solução: Análise adicional de segurança
        
        Returns:
            (bool, str): (é_seguro, motivo)
        """
        if not item_info:
            return (False, "Sem informações do item")
        
        # 1. Blacklist específica de IDs
        if tmdb_id in NOT_FOR_TODDLERS_IDS:
            return (False, "Conteúdo conhecido como inadequado para crianças pequenas")
        
        # 2. Análise de título e sinopse
        title = item_info.get('title', '').lower()
        original_title = item_info.get('original_title', '').lower()
        synopsis = item_info.get('synopsis', '').lower()
        
        text_to_check = f"{title} {original_title} {synopsis}"
        
        # Procurar palavras-chave problemáticas
        found_keywords = []
        for keyword in KEYWORDS_NOT_FOR_TODDLERS:
            if keyword in text_to_check:
                found_keywords.append(keyword)
        
        if found_keywords:
            return (False, f"Palavras inadequadas encontradas")
        
        # 3. Deve ter pelo menos UM gênero garantido para crianças pequenas
        genres = self._extract_genres(item_info)
        has_toddler_genre = False
        
        for genre in genres:
            if any(safe.lower() in genre.lower() for safe in GUARANTEED_TODDLER_GENRES):
                has_toddler_genre = True
                break
        
        if not has_toddler_genre:
            return (False, "Sem gênero garantido para crianças pequenas (precisa Animação/Família)")
        
        # 4. Aventura/Fantasia SEM Animação/Família = BLOQUEADO
        has_adventure_fantasy = any(
            g.lower() in ['aventura', 'adventure', 'fantasia', 'fantasy']
            for g in genres
        )
        
        has_animation_family = any(
            g.lower() in ['animação', 'animation', 'família', 'family', 'infantil', 'kids']
            for g in genres
        )
        
        if has_adventure_fantasy and not has_animation_family:
            return (False, "Aventura/Fantasia sem Animação ou Família (muito intenso)")
        
        # 5. Rating muito alto pode indicar conteúdo intenso
        rating = item_info.get('rating', 0)
        vote_count = item_info.get('vote_count', 0)
        
        # Filmes muito aclamados geralmente são intensos (ex: Harry Potter tem 7.9+)
        if rating > 7.8 and vote_count > 10000:
            # Permite apenas se for Animação pura
            if not any(g.lower() in ['animação', 'animation'] for g in genres):
                return (False, "Rating muito alto para não-animação (pode ser intenso)")
        
        # 6. Runtime muito longo pode não ser adequado
        runtime = item_info.get('runtime', 0)
        if runtime > 120:  # Mais de 2 horas
            return (False, "Duração muito longa para crianças pequenas")
        
        # 7. Passou em todos os testes!
        return (True, "Seguro para crianças pequenas")
    
    def filter_items(self, items, media_type='movie'):
        """
        Filtra lista de itens (FALLBACK - use SQL quando possível!)
        
        ⚠️ AVISO: Este método é LENTO. Use get_sql_where_clause() nas queries!
        """
        if not self.is_kids:
            return items
        
        
        filtered = []
        blocked_count = 0
        
        for item in items:
            tmdb_id = item.get('tmdb_id')
            allowed, reason = self.is_content_allowed(tmdb_id, item)
            
            if allowed:
                filtered.append(item)
            else:
                blocked_count += 1
                
                self._log_blocked_attempt(item, reason)
        
        
        return filtered
    
    # ============================================================
    # MÉTODOS AUXILIARES
    # ============================================================
    
    def _log_blocked_attempt(self, item, reason):
        """Registra tentativa de acesso bloqueada"""
        if not self.profile:
            return
        
        try:
            from resources.lib.profile_manager import ProfileManager
            pm = ProfileManager()
            
            item_info = {
                'title': item.get('title', 'Unknown'),
                'tmdb_id': item.get('tmdb_id'),
                'certification': self._get_certification(item, item.get('type', 'movie')),
                'block_reason': reason
            }
            
            pm.log_blocked_attempt(self.profile['id'], item_info)
        except Exception as e:
            pass
    
    def _get_certification(self, item, media_type):
        """Extrai certificação"""
        cert = item.get('certification') or item.get('classification', '')
        return cert if cert else ''
    
    def _extract_genres(self, item):
        """Extrai lista de gêneros"""
        genres = item.get('genres', [])
        
        if isinstance(genres, str):
            try:
                genres = json.loads(genres)
            except:
                return []
        
        if not isinstance(genres, list):
            return []
        
        result = []
        for g in genres:
            if isinstance(g, str):
                result.append(g.strip())
            elif isinstance(g, dict) and 'name' in g:
                result.append(g['name'].strip())
        
        return result
    
    def _has_safe_genre(self, genres):
        """Verifica se tem pelo menos um gênero seguro"""
        for genre in genres:
            if any(safe.lower() in genre.lower() for safe in SAFE_KIDS_GENRES):
                return True
        return False
    
    def _has_guaranteed_kids_genre(self, genres):
        """Verifica se tem gênero GARANTIDO kids (Animação, Família, etc)"""
        guaranteed = {'Animação', 'Animation', 'Família', 'Family', 'Infantil', 'Kids', 'Children'}
        for genre in genres:
            if any(g.lower() in genre.lower() for g in guaranteed):
                return True
        return False
    
    def _has_blocked_genre_strict(self, genres):
        """Verifica se tem algum gênero bloqueado (STRICT)"""
        for genre in genres:
            if any(blocked.lower() in genre.lower() for blocked in ALWAYS_BLOCKED_GENRES):
                return True
        return False
    
    def _get_blocked_genres(self, genres):
        """Retorna lista de gêneros bloqueados encontrados"""
        blocked = []
        for genre in genres:
            for blocked_genre in ALWAYS_BLOCKED_GENRES:
                if blocked_genre.lower() in genre.lower():
                    blocked.append(genre)
                    break
        return blocked
    
    def _needs_safe_companion(self, genres):
        """Verifica se tem gênero que precisa de companhia segura"""
        for genre in genres:
            if any(req.lower() in genre.lower() for req in REQUIRES_SAFE_COMPANION):
                return True
        return False


# ============================================================
# HELPERS PÚBLICOS
# ============================================================

def get_content_filter(profile_manager=None):
    """Factory para criar filtro"""
    if profile_manager:
        current_profile = profile_manager.get_current_profile()
    else:
        try:
            from resources.lib.profile_manager import ProfileManager
            pm = ProfileManager()
            current_profile = pm.get_current_profile()
        except Exception as e:
            current_profile = None
    
    return ContentFilter(current_profile)


def apply_profile_filter_to_list(items, media_type='movie'):
    """
    ⚠️ DEPRECATED: Use get_sql_where_clause() nas queries SQL!
    
    Este método é mantido apenas para compatibilidade, mas é LENTO.
    
    COMO MIGRAR:
    
    ANTES (LENTO):
    ```python
    movies = db.get_all_movies()
    movies = apply_profile_filter_to_list(movies, 'movie')
    ```
    
    DEPOIS (RÁPIDO):
    ```python
    content_filter = get_content_filter()
    db.set_content_filter(content_filter)  # Passa filtro pro DB
    movies = db.get_all_movies()  # Já vem filtrado
    ```
    """
    content_filter = get_content_filter()
    
    if content_filter.should_filter_content():
        return content_filter.filter_items(items, media_type)
    
    return items


def check_content_allowed_before_play(tmdb_id, item_info=None):
    """
    Verifica se conteúdo pode ser reproduzido (ULTRA-RIGOROSO)
    
    Use antes de iniciar reprodução para bloquear conteúdo inadequado.
    """
    content_filter = get_content_filter()
    
    if not content_filter.should_filter_content():
        return True
    
    allowed, reason = content_filter.is_content_allowed(tmdb_id, item_info)
    
    if not allowed:
        # Log da tentativa
        if item_info:
            content_filter._log_blocked_attempt(item_info, reason)
        
        # Mostrar dialog SIMPLES para kids
        import xbmcgui
        xbmcgui.Dialog().ok(
            'Conteúdo Bloqueado',
            'Este conteúdo não está disponível para este perfil.'
        )
        
        return False
    
    return True