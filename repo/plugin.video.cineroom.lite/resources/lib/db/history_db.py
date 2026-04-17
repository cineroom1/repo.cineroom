# -*- coding: utf-8 -*-


import xbmc
from .base_db import BaseDatabase, SmartCache, ConnectionPool, DB_FILE


class HistoryDatabase(BaseDatabase):

    def __init__(self):
        BaseDatabase.__init__(self)
        self._ensure_ratings_table()
        self._migrate_watch_history_nulls()
        self._migrate_add_stream_url()  # ← NOVO: adiciona coluna last_stream_url

    # ── SCHEMA DE RATINGS ─────────────────────────────────────────────────────

    def _ensure_ratings_table(self):
        """
        Cria a tabela user_ratings se ainda não existir.
        Separada do watch_history para não poluir o histórico de progresso.

        Colunas:
            liked   INTEGER  1 = Gostei · 0 = Não gostei
            score   INTEGER  pontuação numérica (4 ou 8) usada no Trakt
            rated_at         quando foi avaliado
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_ratings (
                    tmdb_id    INTEGER  NOT NULL,
                    media_type TEXT     NOT NULL,
                    profile_id TEXT,
                    season     INTEGER,
                    episode    INTEGER,
                    liked      INTEGER  NOT NULL DEFAULT 1,
                    score      INTEGER  NOT NULL DEFAULT 8,
                    rated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tmdb_id, media_type, profile_id, season, episode)
                )
            """)
            conn.commit()
        except Exception as e:
            xbmc.log(f"[HistoryDB] Erro ao criar user_ratings: {e}", xbmc.LOGERROR)
        finally:
            self._release_conn(conn)

    # ── MIGRAÇÃO — NULL → -1 ──────────────────────────────────────────────────

    def _migrate_watch_history_nulls(self):
        """
        Migração única: corrige registros antigos que usavam NULL em season/episode.

        Problema: NULL != NULL no SQLite, então filmes assistidos mais de uma vez
        geravam linhas duplicadas (o ON CONFLICT nunca disparava).

        Solução:
          1. Remove duplicatas de filmes, mantendo o registro com maior progresso.
          2. Normaliza NULL → -1 em todos os registros restantes.

        Idempotente: verifica se ainda existem NULLs antes de rodar.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # Checa se ainda há NULLs — evita rodar toda vez desnecessariamente
            cursor.execute(
                "SELECT 1 FROM watch_history WHERE season IS NULL OR episode IS NULL LIMIT 1"
            )
            if not cursor.fetchone():
                return  # já migrado, nada a fazer

            xbmc.log("[HistoryDB] Migrando watch_history: removendo duplicatas e normalizando NULLs...", xbmc.LOGINFO)

            # 1. Remove duplicatas de filmes, fica só o de maior progresso
            cursor.execute("""
                DELETE FROM watch_history
                WHERE media_type = 'movie'
                  AND rowid NOT IN (
                      SELECT MAX(rowid)
                      FROM watch_history
                      WHERE media_type = 'movie'
                      GROUP BY tmdb_id, media_type, profile_id
                  )
            """)

            # 2. Normaliza NULL → -1
            cursor.execute("UPDATE watch_history SET season  = -1 WHERE season  IS NULL")
            cursor.execute("UPDATE watch_history SET episode = -1 WHERE episode IS NULL")

            conn.commit()
            xbmc.log("[HistoryDB] Migração concluída.", xbmc.LOGINFO)

        except Exception as e:
            xbmc.log(f"[HistoryDB] Erro na migração de NULLs: {e}", xbmc.LOGERROR)
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            self._release_conn(conn)

    # ── MIGRAÇÃO — Adiciona coluna last_stream_url ────────────────────────────

    def _migrate_add_stream_url(self):
        """
        Migração idempotente: adiciona a coluna last_stream_url à watch_history.
        Guarda a última URL reproduzida para permitir retomada rápida sem nova busca.
        Ignora silenciosamente se a coluna já existir.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE watch_history ADD COLUMN last_stream_url TEXT")
            conn.commit()
            xbmc.log("[HistoryDB] Coluna last_stream_url adicionada ao watch_history.", xbmc.LOGINFO)
        except Exception:
            pass  # coluna já existe — erro esperado, ignorar
        finally:
            self._release_conn(conn)

    def save_rating(self, tmdb_id, media_type, rating, profile_id=None,
                    season=None, episode=None):
        """
        Salva ou atualiza avaliação do usuário.

        Args:
            tmdb_id:    ID do conteúdo
            media_type: 'movie' ou 'tvshow'
            rating:     score numérico (ex: 8 = Gostei, 4 = Não gostei)
            profile_id: None (free) ou UUID do perfil VIP
            season:     temporada (só séries)
            episode:    episódio (só séries)
        """
        liked = 1 if rating >= 6 else 0
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO user_ratings
                    (tmdb_id, media_type, profile_id, season, episode, liked, score, rated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(tmdb_id, media_type, profile_id, season, episode)
                DO UPDATE SET
                    liked    = excluded.liked,
                    score    = excluded.score,
                    rated_at = CURRENT_TIMESTAMP
            """, (tmdb_id, media_type, profile_id, season, episode, liked, rating))
            conn.commit()
            self._cache_delete_prefix(f"ratings:{profile_id or 'global'}")
            xbmc.log(f"[HistoryDB] Rating salvo: tmdb={tmdb_id} liked={liked} score={rating}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[HistoryDB] Erro ao salvar rating: {e}", xbmc.LOGERROR)
        finally:
            self._release_conn(conn)

    # ── RATINGS — LEITURA ─────────────────────────────────────────────────────

    def get_liked(self, media_type, profile_id=None, limit=100):
        """
        Retorna filmes/séries marcados como 'Gostei' com metadados completos.
        Ordenados do mais recente para o mais antigo.
        """
        cache_key = f"ratings:{profile_id or 'global'}:liked:{media_type}:{limit}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        table = 'movies' if media_type == 'movie' else 'tvshows'
        # Para tvshow não há colunas runtime/collection — usar literais sem prefixo t.
        runtime_col    = 't.runtime'     if media_type == 'movie' else '0 as runtime'
        collection_col = 't.collection'  if media_type == 'movie' else "'' as collection"

        if profile_id:
            sql = f"""
                SELECT
                    t.tmdb_id, t.title, t.original_title, t.year, t.rating,
                    t.poster, t.backdrop, t.synopsis, t.imdb_id,
                    t.clearlogo, t.genres, {runtime_col}, {collection_col},
                    '{media_type}' as media_type,
                    r.score, r.rated_at
                FROM user_ratings r
                JOIN {table} t ON r.tmdb_id = t.tmdb_id
                WHERE r.media_type = ? AND r.profile_id = ? AND r.liked = 1
                ORDER BY r.rated_at DESC
                LIMIT ?
            """
            results = self._execute_query(sql, (media_type, profile_id, limit))
        else:
            sql = f"""
                SELECT
                    t.tmdb_id, t.title, t.original_title, t.year, t.rating,
                    t.poster, t.backdrop, t.synopsis, t.imdb_id,
                    t.clearlogo, t.genres, {runtime_col}, {collection_col},
                    '{media_type}' as media_type,
                    r.score, r.rated_at
                FROM user_ratings r
                JOIN {table} t ON r.tmdb_id = t.tmdb_id
                WHERE r.media_type = ? AND r.liked = 1
                ORDER BY r.rated_at DESC
                LIMIT ?
            """
            results = self._execute_query(sql, (media_type, limit))

        self._cache_set(cache_key, results, ttl=120)
        return results

    def get_disliked(self, media_type, profile_id=None, limit=100):
        """
        Retorna filmes/séries marcados como 'Não gostei' com metadados completos.
        Ordenados do mais recente para o mais antigo.
        """
        cache_key = f"ratings:{profile_id or 'global'}:disliked:{media_type}:{limit}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        table = 'movies' if media_type == 'movie' else 'tvshows'
        runtime_col    = 't.runtime'     if media_type == 'movie' else '0 as runtime'
        collection_col = 't.collection'  if media_type == 'movie' else "'' as collection"

        if profile_id:
            sql = f"""
                SELECT
                    t.tmdb_id, t.title, t.original_title, t.year, t.rating,
                    t.poster, t.backdrop, t.synopsis, t.imdb_id,
                    t.clearlogo, t.genres, {runtime_col}, {collection_col},
                    '{media_type}' as media_type,
                    r.score, r.rated_at
                FROM user_ratings r
                JOIN {table} t ON r.tmdb_id = t.tmdb_id
                WHERE r.media_type = ? AND r.profile_id = ? AND r.liked = 0
                ORDER BY r.rated_at DESC
                LIMIT ?
            """
            results = self._execute_query(sql, (media_type, profile_id, limit))
        else:
            sql = f"""
                SELECT
                    t.tmdb_id, t.title, t.original_title, t.year, t.rating,
                    t.poster, t.backdrop, t.synopsis, t.imdb_id,
                    t.clearlogo, t.genres, {runtime_col}, {collection_col},
                    '{media_type}' as media_type,
                    r.score, r.rated_at
                FROM user_ratings r
                JOIN {table} t ON r.tmdb_id = t.tmdb_id
                WHERE r.media_type = ? AND r.liked = 0
                ORDER BY r.rated_at DESC
                LIMIT ?
            """
            results = self._execute_query(sql, (media_type, limit))

        self._cache_set(cache_key, results, ttl=120)
        return results

    def get_all_rated_ids(self, media_type, profile_id=None):
        """
        Retorna dict {tmdb_id: liked} para todos os itens avaliados.
        Usado pelo recommendations_db para boosting/penalidade.
        """
        cache_key = f"ratings:{profile_id or 'global'}:ids:{media_type}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        if profile_id:
            sql = "SELECT tmdb_id, liked FROM user_ratings WHERE media_type = ? AND profile_id = ?"
            rows = self._execute_query(sql, (media_type, profile_id))
        else:
            sql = "SELECT tmdb_id, liked FROM user_ratings WHERE media_type = ?"
            rows = self._execute_query(sql, (media_type,))

        result = {row['tmdb_id']: row['liked'] for row in rows}
        self._cache_set(cache_key, result, ttl=120)
        return result

    def delete_rating(self, tmdb_id, media_type, profile_id=None,
                      season=None, episode=None):
        """Remove avaliação de um item específico."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            if profile_id:
                cursor.execute(
                    "DELETE FROM user_ratings WHERE tmdb_id=? AND media_type=? AND profile_id=?",
                    (tmdb_id, media_type, profile_id)
                )
            else:
                cursor.execute(
                    "DELETE FROM user_ratings WHERE tmdb_id=? AND media_type=?",
                    (tmdb_id, media_type)
                )
            conn.commit()
            self._cache_delete_prefix(f"ratings:{profile_id or 'global'}")
        except Exception as e:
            xbmc.log(f"[HistoryDB] Erro ao remover rating: {e}", xbmc.LOGERROR)
        finally:
            self._release_conn(conn)

    # ── ESCRITA — HISTÓRICO ───────────────────────────────────────────────────

    def add_to_history(self, tmdb_id, media_type, profile_id=None,
                       season=None, episode=None, progress=0.0,
                       last_stream_url=None):
        """
        Registra ou atualiza visualização.
        Para filmes: season e episode são None.
        Para séries: season e episode identificam o episódio.
        progress: float 0-100 (% assistido).
        last_stream_url: URL do stream reproduzido — salva para retomada rápida.
        Free: profile_id sempre None.
        VIP: profile_id identifica o perfil.

        Nota: season/episode usam -1 como sentinela para filmes porque
        NULL != NULL no SQLite, o que impede o ON CONFLICT de funcionar.

        Nota sobre last_stream_url: usa COALESCE para não apagar uma URL já
        salva quando o player atualiza só o progresso (ex: tick periódico sem URL).
        """
        # NULL quebra o ON CONFLICT da PK (NULL != NULL no SQLite)
        # Filmes usam -1 como sentinela para garantir upsert correto
        _season  = season  if season  is not None else -1
        _episode = episode if episode is not None else -1

        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO watch_history
                    (tmdb_id, media_type, profile_id, season, episode, progress, watched_at, last_stream_url)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(tmdb_id, media_type, profile_id, season, episode)
                DO UPDATE SET
                    progress        = excluded.progress,
                    watched_at      = CURRENT_TIMESTAMP,
                    last_stream_url = COALESCE(excluded.last_stream_url, last_stream_url)
            """, (tmdb_id, media_type, profile_id, _season, _episode, progress, last_stream_url))
            conn.commit()
            self._cache_delete_prefix(f"history:{profile_id or 'global'}")
        except Exception as e:
            xbmc.log(f"[HistoryDB] Erro ao registrar: {e}", xbmc.LOGERROR)
        finally:
            self._release_conn(conn)

    # ── LEITURA — ÚLTIMA URL ──────────────────────────────────────────────────

    def get_last_stream_url(self, tmdb_id, media_type, profile_id=None,
                            season=None, episode=None):
        """
        Retorna a última URL de stream reproduzida para este conteúdo, ou None.
        Usado por sources.py para oferecer retomada rápida sem nova busca de fontes.

        Args:
            tmdb_id:    ID do conteúdo no TMDB
            media_type: 'movie' ou 'tvshow'
            profile_id: None (free) ou UUID do perfil VIP
            season:     temporada (só séries)
            episode:    episódio (só séries)

        Returns:
            str com a URL ou None se não houver registro.
        """
        _season  = season  if season  is not None else -1
        _episode = episode if episode is not None else -1

        if profile_id:
            sql = """
                SELECT last_stream_url FROM watch_history
                WHERE tmdb_id = ? AND media_type = ? AND profile_id = ?
                  AND season = ? AND episode = ?
                LIMIT 1
            """
            result = self._execute_query(
                sql, (tmdb_id, media_type, profile_id, _season, _episode), fetch_one=True
            )
        else:
            sql = """
                SELECT last_stream_url FROM watch_history
                WHERE tmdb_id = ? AND media_type = ?
                  AND season = ? AND episode = ?
                LIMIT 1
            """
            result = self._execute_query(
                sql, (tmdb_id, media_type, _season, _episode), fetch_one=True
            )

        if not result:
            return None
        url = result.get('last_stream_url')
        return url if url else None

    # ── LEITURA — HISTÓRICO ───────────────────────────────────────────────────

    def get_history(self, profile_id=None, limit=50):
        """
        Retorna histórico completo com dados de filmes/séries,
        ordenado do mais recente para o mais antigo.
        Filmes são deduplicados — retorna apenas o registro de maior progresso.
        """
        cache_key = f"history:{profile_id or 'global'}:all:{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        if profile_id:
            profile_filter_m  = "AND h.profile_id = ?"
            profile_filter_t  = "AND h.profile_id = ?"
            params = (profile_id, profile_id, limit)
        else:
            profile_filter_m  = "AND h.profile_id IS NULL"
            profile_filter_t  = "AND h.profile_id IS NULL"
            params = (limit,)

        sql = f"""
            SELECT
                m.tmdb_id, m.title, m.original_title, m.year, m.rating,
                m.poster, m.backdrop, m.synopsis, m.imdb_id,
                m.clearlogo, m.genres, m.runtime, m.collection,
                'movie' as media_type,
                h.progress, h.watched_at,
                NULL as season, NULL as episode
            FROM watch_history h
            JOIN movies m ON h.tmdb_id = m.tmdb_id
            WHERE h.media_type = 'movie' {profile_filter_m}
              AND h.rowid = (
                  SELECT MAX(h2.rowid) FROM watch_history h2
                  WHERE h2.tmdb_id = h.tmdb_id
                    AND h2.media_type = 'movie'
                    AND h2.profile_id IS h.profile_id
              )

            UNION ALL

            SELECT
                t.tmdb_id, t.title, t.original_title, t.year, t.rating,
                t.poster, t.backdrop, t.synopsis, t.imdb_id,
                t.clearlogo, t.genres, 0 as runtime, '' as collection,
                'tvshow' as media_type,
                h.progress, h.watched_at,
                h.season, h.episode
            FROM watch_history h
            JOIN tvshows t ON h.tmdb_id = t.tmdb_id
            WHERE h.media_type = 'tvshow' {profile_filter_t}

            ORDER BY watched_at DESC
            LIMIT ?
        """

        results = self._execute_query(sql, params)
        self._cache_set(cache_key, results, ttl=120)
        return results

    def get_movie_progress(self, tmdb_id, profile_id=None):
        """Retorna progresso (0-100) de um filme, ou 0 se nunca assistiu."""
        cache_key = f"history:prog:{tmdb_id}:movie:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        if profile_id:
            sql = """SELECT progress FROM watch_history
                     WHERE tmdb_id = ? AND media_type = 'movie' AND profile_id = ?
                     ORDER BY watched_at DESC LIMIT 1"""
            result = self._execute_query(sql, (tmdb_id, profile_id), fetch_one=True)
        else:
            sql = """SELECT progress FROM watch_history
                     WHERE tmdb_id = ? AND media_type = 'movie'
                     ORDER BY watched_at DESC LIMIT 1"""
            result = self._execute_query(sql, (tmdb_id,), fetch_one=True)

        progress = float(result.get('progress', 0)) if result else 0.0
        self._cache_set(cache_key, progress, ttl=120)
        return progress

    def get_watched_episodes(self, tmdb_id, profile_id=None):
        """Retorna set de (season, episode) assistidos de uma série."""
        cache_key = f"history:eps:{tmdb_id}:{profile_id or 'global'}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        if profile_id:
            sql = """SELECT season, episode FROM watch_history
                     WHERE tmdb_id = ? AND media_type = 'tvshow' AND profile_id = ?"""
            results = self._execute_query(sql, (tmdb_id, profile_id))
        else:
            sql = """SELECT season, episode FROM watch_history
                     WHERE tmdb_id = ? AND media_type = 'tvshow'"""
            results = self._execute_query(sql, (tmdb_id,))

        # Exclui o sentinela -1 usado por filmes (season/episode None → -1 no banco)
        watched = {(r['season'], r['episode']) for r in results
                   if r['season'] != -1 and r['episode'] != -1}
        self._cache_set(cache_key, watched, ttl=120)
        return watched

    def is_watched(self, tmdb_id, media_type, profile_id=None,
                   season=None, episode=None, min_progress=75.0):
        """
        Retorna True se o item foi assistido (progress >= min_progress).
        Para séries, requer season e episode.
        """
        if media_type == 'movie':
            return self.get_movie_progress(tmdb_id, profile_id) >= min_progress

        if season is not None and episode is not None:
            watched = self.get_watched_episodes(tmdb_id, profile_id)
            return (season, episode) in watched

        return False

    def get_history_count(self, profile_id=None):
        """Conta total de itens no histórico."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            if profile_id:
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN media_type = 'movie'  THEN 1 ELSE 0 END) as movies,
                        SUM(CASE WHEN media_type = 'tvshow' THEN 1 ELSE 0 END) as tvshows,
                        COUNT(*) as total
                    FROM watch_history WHERE profile_id = ?
                """, (profile_id,))
            else:
                cursor.execute("""
                    SELECT
                        SUM(CASE WHEN media_type = 'movie'  THEN 1 ELSE 0 END) as movies,
                        SUM(CASE WHEN media_type = 'tvshow' THEN 1 ELSE 0 END) as tvshows,
                        COUNT(*) as total
                    FROM watch_history
                """)
            row = cursor.fetchone()
            return {
                'movies':  row[0] or 0,
                'tvshows': row[1] or 0,
                'total':   row[2] or 0,
            }
        finally:
            self._release_conn(conn)

    def clear_history(self, profile_id=None):
        """Limpa histórico do perfil ou todo."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            if profile_id:
                cursor.execute("DELETE FROM watch_history WHERE profile_id = ?", (profile_id,))
            else:
                cursor.execute("DELETE FROM watch_history")
            conn.commit()
            self._cache_delete_prefix("history:")
        finally:
            self._release_conn(conn)

    def get_completed_count(self, profile_id, min_progress=85.0):
        """
        Conta filmes e séries concluídos (progress >= min_progress).

        Returns:
            dict: {'movies': int, 'tvshows': int, 'total': int}
        """
        cache_key = f"history:completed:{profile_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        sql = """
            SELECT
                SUM(CASE WHEN media_type = 'movie'  AND progress >= ? THEN 1 ELSE 0 END) as movies,
                SUM(CASE WHEN media_type = 'tvshow' AND progress >= ? THEN 1 ELSE 0 END) as tvshows
            FROM watch_history
            WHERE profile_id = ?
        """
        result = self._execute_query(sql, (min_progress, min_progress, profile_id), fetch_one=True)
        out = {
            'movies':  int(result.get('movies',  0) or 0) if result else 0,
            'tvshows': int(result.get('tvshows', 0) or 0) if result else 0,
        }
        out['total'] = out['movies'] + out['tvshows']
        self._cache_set(cache_key, out, ttl=300)
        return out

    def get_total_watch_time(self, profile_id):
        """
        Calcula tempo total assistido em minutos.
        Filmes: usa runtime real x (progress/100).
        Séries: usa 45min por episódio como fallback.

        Returns:
            dict: {'total_minutes': int, 'movies_minutes': int, 'tvshows_minutes': int}
        """
        cache_key = f"history:watchtime:{profile_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        sql_movies = """
            SELECT COALESCE(SUM(m.runtime * (h.progress / 100.0)), 0) as minutes
            FROM watch_history h
            JOIN movies m ON h.tmdb_id = m.tmdb_id
            WHERE h.media_type = 'movie' AND h.profile_id = ? AND m.runtime > 0
        """
        r_movies = self._execute_query(sql_movies, (profile_id,), fetch_one=True)
        movies_min = int(r_movies.get('minutes', 0) or 0) if r_movies else 0

        sql_tvshows = """
            SELECT COALESCE(SUM(45 * (h.progress / 100.0)), 0) as minutes
            FROM watch_history h
            WHERE h.media_type = 'tvshow' AND h.profile_id = ?
        """
        r_tvshows = self._execute_query(sql_tvshows, (profile_id,), fetch_one=True)
        tvshows_min = int(r_tvshows.get('minutes', 0) or 0) if r_tvshows else 0

        out = {
            'movies_minutes':  movies_min,
            'tvshows_minutes': tvshows_min,
            'total_minutes':   movies_min + tvshows_min,
        }
        self._cache_set(cache_key, out, ttl=300)
        return out

    def get_top_genres(self, profile_id, limit=5):
        """
        Retorna os gêneros mais assistidos pelo perfil.

        Returns:
            list of dict: [{'genre': str, 'count': int}, ...]
        """
        cache_key = f"history:genres:{profile_id}:{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        sql = """
            SELECT m.genres
            FROM watch_history h
            JOIN movies m ON h.tmdb_id = m.tmdb_id
            WHERE h.media_type = 'movie' AND h.profile_id = ? AND m.genres IS NOT NULL

            UNION ALL

            SELECT t.genres
            FROM watch_history h
            JOIN tvshows t ON h.tmdb_id = t.tmdb_id
            WHERE h.media_type = 'tvshow' AND h.profile_id = ? AND t.genres IS NOT NULL
        """
        rows = self._execute_query(sql, (profile_id, profile_id))

        import json
        genre_counts = {}
        for row in rows:
            raw = row.get('genres', '[]')
            try:
                genres = json.loads(raw) if isinstance(raw, str) else raw
                for g in genres:
                    if isinstance(g, str) and g.strip():
                        genre_counts[g] = genre_counts.get(g, 0) + 1
            except Exception:
                continue

        sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
        out = [{'genre': g, 'count': c} for g, c in sorted_genres[:limit]]
        self._cache_set(cache_key, out, ttl=300)
        return out

    def get_streak(self, profile_id):
        """
        Calcula streak atual e recorde de dias seguidos assistindo.

        Returns:
            dict: {'current': int, 'best': int}
        """
        cache_key = f"history:streak:{profile_id}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        sql = """
            SELECT DISTINCT DATE(watched_at) as day
            FROM watch_history
            WHERE profile_id = ?
            ORDER BY day DESC
        """
        rows = self._execute_query(sql, (profile_id,))
        days = [row['day'] for row in rows if row.get('day')]

        if not days:
            return {'current': 0, 'best': 0}

        from datetime import date, timedelta

        def parse_day(s):
            try:
                y, m, d = s.split('-')
                return date(int(y), int(m), int(d))
            except Exception:
                return None

        date_objs = sorted(filter(None, (parse_day(d) for d in days)), reverse=True)

        if not date_objs:
            return {'current': 0, 'best': 0}

        today = date.today()

        current = 0
        if date_objs[0] in (today, today - timedelta(days=1)):
            current = 1
            for i in range(1, len(date_objs)):
                if date_objs[i - 1] - date_objs[i] == timedelta(days=1):
                    current += 1
                else:
                    break

        best = 1
        run  = 1
        for i in range(1, len(date_objs)):
            if date_objs[i - 1] - date_objs[i] == timedelta(days=1):
                run += 1
                best = max(best, run)
            else:
                run = 1

        out = {'current': current, 'best': best}
        self._cache_set(cache_key, out, ttl=300)
        return out


# Instância global
history_db = HistoryDatabase()