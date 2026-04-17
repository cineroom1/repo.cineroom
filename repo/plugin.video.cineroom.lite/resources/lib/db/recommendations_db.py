# -*- coding: utf-8 -*-
"""
Recommendations Database — Para Você
✅ Cruza histórico (≥75%) com metadados do banco local
✅ Filtra por gêneros + keywords + coleções do histórico (≥75% assistido)
✅ Exclui o que o usuário já assistiu
✅ Ordena por relevância de gênero × keywords × rating × popularidade
✅ Peso por progresso: filmes assistidos até o fim valem mais
✅ Penalidade de saturação: log(peso) evita mono-gênero
✅ Boost de coleção: mesma franquia sobe no ranking
✅ Decay por antiguidade: histórico recente pesa mais
✅ Boost de rating do usuário: Gostei amplifica, Não Gostei penaliza e pode excluir
✅ Só VIP
"""

import json
import math
import xbmc
from datetime import datetime, timezone
from .base_db import BaseDatabase, DB_FILE, ConnectionPool, SmartCache

# ── Pesos do sistema de avaliação ──────────────────────────────────────────────
# Quando o usuário avalia via dialog de 80%, os gêneros/keywords do conteúdo
# avaliado recebem um multiplicador adicional no perfil do usuário.
LIKED_WEIGHT_MULTIPLIER    = 2.0   # gêneros de filmes Gostados valem 2× mais
DISLIKED_WEIGHT_MULTIPLIER = 0.25  # gêneros de filmes Não Gostados valem 4× menos
DISLIKED_GENRE_PENALTY     = -0.5  # penalidade direta no score final por gênero em comum
DISLIKED_EXCLUDE_THRESHOLD = 3     # se candidato compartilha ≥N gêneros com Não Gostei → exclui


class RecommendationsDatabase(BaseDatabase):

    def __init__(self):
        BaseDatabase.__init__(self)

    # ── PÚBLICO ───────────────────────────────────────────────────────────────

    def get_recommendations(self, media_type, profile_id=None,
                            min_progress=75.0, limit=50, min_rating=5.0):
        """
        Retorna recomendações baseadas no histórico + avaliações do usuário.

        Algoritmo v3 (com ratings):
        1. Busca itens assistidos >= min_progress com watched_at
        2. Busca avaliações (Gostei / Não Gostei) do usuário
        3. Extrai gêneros e keywords do histórico, ponderando por:
           - progresso assistido
           - decay temporal
           - saturação via log
           - Gostei: multiplica peso dos gêneros por LIKED_WEIGHT_MULTIPLIER
           - Não Gostei: multiplica peso dos gêneros por DISLIKED_WEIGHT_MULTIPLIER
        4. Busca candidatos NÃO assistidos com rating mínimo
        5. Pontua cada candidato:
           - genre_score:       gêneros em comum (peso log-saturado + influência de ratings)
           - keyword_score:     keywords em comum (peso menor, 0.5×)
           - collection_boost:  mesma franquia do histórico (+0.4)
           - quality_bonus:     rating normalizado (×0.3)
           - popularity_bonus:  popularidade com cap (max 0.2)
           - dislike_penalty:   gêneros de "Não Gostei" reduzem o score
        6. Exclui candidatos com muitos gêneros em comum com "Não Gostei"
        7. Ordena por score total DESC

        Returns: list of dicts prontos para exibição, ou [] se histórico insuficiente
        """
        cache_key = f"rec:{media_type}:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # 1. Perfil do usuário: gêneros, keywords e coleções do histórico
        watched_ids, genre_weights, keyword_weights, watched_collections = \
            self._build_user_profile(media_type, profile_id, min_progress)

        if len(watched_ids) < 3:
            self._cache_set(cache_key, [], ttl=300)
            return []

        # 2. Perfil de gêneros negativos (Não Gostei)
        disliked_genre_weights = self._build_dislike_profile(media_type, profile_id)

        # 3. Candidatos não assistidos com rating mínimo
        candidates = self._get_candidates(
            media_type, watched_ids, min_rating, limit * 4
        )

        if not candidates:
            self._cache_set(cache_key, [], ttl=300)
            return []

        # 4. Pontua e ordena
        scored = self._score_candidates(
            candidates, genre_weights, keyword_weights,
            watched_collections, disliked_genre_weights
        )
        scored.sort(key=lambda x: x['_rec_score'], reverse=True)

        # 5. Remove campo interno e limita
        results = []
        for item in scored[:limit]:
            item.pop('_rec_score', None)
            results.append(item)

        self._cache_set(cache_key, results, ttl=600)
        return results

    def has_enough_history(self, media_type, profile_id=None, min_progress=75.0, min_items=3):
        """Verifica se usuário tem histórico suficiente para receber recomendações."""
        if profile_id:
            sql = """
                SELECT COUNT(DISTINCT tmdb_id) FROM watch_history
                WHERE media_type = ? AND profile_id = ? AND progress >= ?
            """
            result = self._execute_query(sql, (media_type, profile_id, min_progress), fetch_one=True)
        else:
            sql = """
                SELECT COUNT(DISTINCT tmdb_id) FROM watch_history
                WHERE media_type = ? AND progress >= ?
            """
            result = self._execute_query(sql, (media_type, min_progress), fetch_one=True)

        count = list(result.values())[0] if result else 0
        return count >= min_items

    # ── PRIVADO ───────────────────────────────────────────────────────────────

    def _build_user_profile(self, media_type, profile_id, min_progress):
        """
        Constrói o perfil de preferências do usuário a partir do histórico.
        Agora incorpora ratings do usuário (Gostei / Não Gostei) como multiplicadores.

        Fluxo:
        1. Busca histórico de visualizações
        2. Para cada item, calcula peso base = progress_factor × time_decay
        3. Se o item foi avaliado positivamente  → peso × LIKED_WEIGHT_MULTIPLIER
        4. Se o item foi avaliado negativamente  → peso × DISLIKED_WEIGHT_MULTIPLIER
        5. Aplica saturação logarítmica nos pesos finais
        """
        table = 'movies' if media_type == 'movie' else 'tvshows'
        collection_col = ', t.collection' if media_type == 'movie' else ", '' as collection"

        if profile_id:
            sql = f"""
                SELECT t.tmdb_id, t.genres, t.keywords{collection_col},
                       h.progress, h.watched_at
                FROM watch_history h
                JOIN {table} t ON h.tmdb_id = t.tmdb_id
                WHERE h.media_type = ? AND h.profile_id = ? AND h.progress >= ?
                GROUP BY t.tmdb_id
            """
            rows = self._execute_query(sql, (media_type, profile_id, min_progress))
        else:
            sql = f"""
                SELECT t.tmdb_id, t.genres, t.keywords{collection_col},
                       h.progress, h.watched_at
                FROM watch_history h
                JOIN {table} t ON h.tmdb_id = t.tmdb_id
                WHERE h.media_type = ? AND h.progress >= ?
                GROUP BY t.tmdb_id
            """
            rows = self._execute_query(sql, (media_type, min_progress))

        # Carrega mapa de ratings: {tmdb_id: liked (1=gostei, 0=nao gostei)}
        try:
            from .history_db import history_db
            rated_map = history_db.get_all_rated_ids(media_type, profile_id)
        except Exception:
            rated_map = {}

        now = datetime.now(timezone.utc)
        DECAY_LAMBDA = 0.005  # meia-vida ~140 dias

        watched_ids         = set()
        genre_weights       = {}
        keyword_weights     = {}
        watched_collections = set()

        for row in rows:
            watched_ids.add(row['tmdb_id'])

            progress_factor = float(row.get('progress') or 0) / 100.0

            time_decay = 1.0
            watched_at_raw = row.get('watched_at')
            if watched_at_raw:
                try:
                    dt = datetime.fromisoformat(str(watched_at_raw).replace(' ', 'T'))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    days_ago = max((now - dt).days, 0)
                    time_decay = math.exp(-DECAY_LAMBDA * days_ago)
                except Exception:
                    time_decay = 1.0

            item_weight = progress_factor * time_decay

            # ── Aplica multiplicador de rating ──────────────────────────────
            liked_val = rated_map.get(row['tmdb_id'])
            if liked_val == 1:
                item_weight *= LIKED_WEIGHT_MULTIPLIER
            elif liked_val == 0:
                item_weight *= DISLIKED_WEIGHT_MULTIPLIER
            # ────────────────────────────────────────────────────────────────

            genres = self._parse_json_field(row.get('genres'))
            for g in genres:
                if g:
                    genre_weights[g] = genre_weights.get(g, 0) + item_weight

            keywords = self._parse_json_field(row.get('keywords'))
            for kw in keywords:
                if kw:
                    keyword_weights[kw] = keyword_weights.get(kw, 0) + item_weight

            collection = row.get('collection')
            if collection:
                watched_collections.add(collection)

        genre_weights   = {g:  math.log1p(w) for g, w in genre_weights.items()}
        keyword_weights = {kw: math.sqrt(w)  for kw, w in keyword_weights.items()}

        return watched_ids, genre_weights, keyword_weights, watched_collections

    def _build_dislike_profile(self, media_type, profile_id):
        """
        Constrói o perfil de gêneros negativos a partir dos itens "Não Gostei".

        Retorna dict {gênero: contagem} para uso como penalidade no scoring.
        Itens com muitos gêneros desse perfil serão penalizados ou excluídos.
        """
        try:
            from .history_db import history_db
            disliked_items = history_db.get_disliked(media_type, profile_id, limit=200)
        except Exception:
            return {}

        dislike_genre_counts = {}
        for item in disliked_items:
            genres = self._parse_json_field(item.get('genres'))
            for g in genres:
                if g:
                    dislike_genre_counts[g] = dislike_genre_counts.get(g, 0) + 1

        return dislike_genre_counts

    def _get_candidates(self, media_type, exclude_ids, min_rating, limit):
        """
        Busca itens não assistidos com rating mínimo.
        Traz todos os campos necessários para exibição + keywords e collection.
        """
        table = 'movies' if media_type == 'movie' else 'tvshows'

        exclude_clause = ""
        exclude_params = []
        if exclude_ids:
            placeholders = ','.join('?' * len(exclude_ids))
            exclude_clause = f"AND tmdb_id NOT IN ({placeholders})"
            exclude_params = list(exclude_ids)

        if media_type == 'movie':
            sql = f"""
                SELECT
                    tmdb_id, title, original_title, year, rating, popularity,
                    poster, backdrop, synopsis, imdb_id, clearlogo,
                    genres, runtime, collection, keywords,
                    'movie' as media_type
                FROM movies
                WHERE rating >= ? {exclude_clause}
                ORDER BY popularity DESC
                LIMIT ?
            """
        else:
            sql = f"""
                SELECT
                    tmdb_id, title, original_title, year, rating, popularity,
                    poster, backdrop, synopsis, imdb_id, clearlogo,
                    genres, 0 as runtime, '' as collection, keywords,
                    'tvshow' as media_type
                FROM tvshows
                WHERE rating >= ? {exclude_clause}
                ORDER BY popularity DESC
                LIMIT ?
            """

        params = [min_rating] + exclude_params + [limit]
        return self._execute_query(sql, params)

    def _score_candidates(self, candidates, genre_weights, keyword_weights,
                           watched_collections, disliked_genre_weights):
        """
        Pontua cada candidato combinando múltiplos sinais, incluindo ratings.

        Score final:
            genre_score      — gêneros em comum com histórico (normalizado 0-1, boosted por Gostei)
            keyword_score    — keywords em comum × 0.5
            collection_boost — +0.4 se é da mesma franquia/coleção
            quality_bonus    — rating / 10 × 0.3
            popularity_bonus — min(popularity / 1000, 0.2)
            dislike_penalty  — penalidade por gêneros compartilhados com "Não Gostei"

        Candidatos excluídos se compartilharem >= DISLIKED_EXCLUDE_THRESHOLD gêneros
        que aparecem no perfil de "Não Gostei" do usuário.
        """
        scored = []

        max_genre_weight   = max(genre_weights.values())   if genre_weights   else 1.0
        max_keyword_weight = max(keyword_weights.values()) if keyword_weights else 1.0

        for item in candidates:
            item_genres   = self._parse_json_field(item.get('genres'))
            item_keywords = self._parse_json_field(item.get('keywords'))

            # ── Filtro duro: muitos gêneros em comum com Não Gostei → descarta ──
            if disliked_genre_weights:
                dislike_genre_hits = sum(
                    1 for g in item_genres
                    if g in disliked_genre_weights and disliked_genre_weights[g] >= 2
                )
                if dislike_genre_hits >= DISLIKED_EXCLUDE_THRESHOLD:
                    continue
            # ────────────────────────────────────────────────────────────────────

            # ── Gêneros ──────────────────────────────────────────────────────
            genre_score = sum(
                genre_weights.get(g, 0) / max_genre_weight
                for g in item_genres
                if g in genre_weights
            )

            if genre_score == 0:
                continue

            # ── Keywords ─────────────────────────────────────────────────────
            keyword_score = sum(
                keyword_weights.get(kw, 0) / max_keyword_weight
                for kw in item_keywords
                if kw in keyword_weights
            ) * 0.5

            # ── Boost de coleção ─────────────────────────────────────────────
            collection_boost = 0.0
            item_collection = item.get('collection')
            if item_collection and item_collection in watched_collections:
                collection_boost = 0.4

            # ── Qualidade ────────────────────────────────────────────────────
            rating     = float(item.get('rating', 0) or 0)
            popularity = float(item.get('popularity', 0) or 0)
            quality_bonus    = (rating / 10.0) * 0.3
            popularity_bonus = min(popularity / 1000.0, 0.2)

            # ── Penalidade de "Não Gostei" (suave, por gênero) ───────────────
            dislike_penalty = 0.0
            if disliked_genre_weights:
                max_dislike = max(disliked_genre_weights.values()) if disliked_genre_weights else 1.0
                dislike_penalty = sum(
                    (disliked_genre_weights.get(g, 0) / max_dislike) * abs(DISLIKED_GENRE_PENALTY)
                    for g in item_genres
                    if g in disliked_genre_weights
                )
            # ────────────────────────────────────────────────────────────────

            item['_rec_score'] = (
                genre_score
                + keyword_score
                + collection_boost
                + quality_bonus
                + popularity_bonus
                - dislike_penalty       # subtrai penalidade de Não Gostei
            )
            scored.append(item)

        return scored

    # ── HELPERS ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json_field(value):
        """Deserializa campo JSON (string ou lista) de forma segura."""
        if not value:
            return []
        if isinstance(value, list):
            return value
        try:
            return json.loads(value)
        except Exception:
            return []


# Instância global
recommendations_db = RecommendationsDatabase()