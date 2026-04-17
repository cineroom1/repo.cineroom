# -*- coding: utf-8 -*-
"""
Reprodução de vídeos com suporte a InputStream Adaptive e scrobble automático
"""
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import sys
import urllib.parse
import threading
import time
import re

ADDON = xbmcaddon.Addon()

# Detecta plataforma uma vez no import
_IS_ANDROID = bool(xbmc.getCondVisibility('System.Platform.Android'))

_active_monitors: set = set()
_active_monitors_lock = threading.Lock()


def _try_resolveurl(url):
    """
    Tenta resolver via resolveurl (fork instalado no Kodi).
    Só age em URLs que claramente não são streams diretos (.m3u8, .mpd, .mp4 etc).
    Retorna a URL resolvida ou a original se falhar/não aplicável.
    """
    url_lower = url.lower().split('|')[0]  # ignora headers
    direct_exts = ('.m3u8', '.mpd', '.mp4', '.mkv', '.avi', '.flv', '.ts')
    if any(ext in url_lower for ext in direct_exts):
        return url  # já é stream direto, não precisa resolver

    if url_lower.startswith('magnet:') or url_lower.startswith('plugin://'):
        return url  # torrent/plugin, não resolve

    try:
        import resolveurl
        if resolveurl.HostedMediaFile(url).valid_url():
            resolved = resolveurl.resolve(url)
            if resolved:
                xbmc.log(f'[Player] resolveurl resolveu: {resolved[:80]}', xbmc.LOGINFO)
                return resolved
    except Exception as e:
        xbmc.log(f'[Player] resolveurl falhou para {url[:80]}: {e}', xbmc.LOGWARNING)

    return url


def _sanitize_url(url):
    """
    Garante que a URL está corretamente encoded para o Android.
    - Preserva a parte de headers após o pipe (|)
    - Re-encodifica apenas o PATH com caracteres Unicode soltos (ex: ç, ã)
    - A QUERY STRING é preservada intacta — não faz unquote/requote nela,
      pois URLs assinadas (HMAC, tokens) têm %3D, %2B etc que não devem
      ser decodificados (quebraria a validação do servidor no Android)
    """
    if not url:
        return url

    pipe_idx = url.find('|')
    if pipe_idx != -1:
        raw_url      = url[:pipe_idx]
        headers_part = url[pipe_idx:]
    else:
        raw_url      = url
        headers_part = ''

    try:
        parsed = urllib.parse.urlsplit(raw_url)
        safe_path = urllib.parse.quote(
            urllib.parse.unquote(parsed.path),
            safe='/:@!\'()*+,;='
        )
        # Query string preservada INTACTA — não faz unquote para não quebrar
        # parâmetros assinados como expiry=%3D%3D ou tokens com %2B
        safe_query = parsed.query

        sanitized = urllib.parse.urlunsplit((
            parsed.scheme,
            parsed.netloc,
            safe_path,
            safe_query,
            parsed.fragment,
        ))
        return sanitized + headers_part
    except Exception as e:
        xbmc.log(f"[Player] Erro ao sanitizar URL: {e}", xbmc.LOGWARNING)
        return url


USER_AGENT = (
    'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
    if _IS_ANDROID else
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)


# ============================================================
# DIALOG DE AVALIAÇÃO (80%)
# ============================================================

class RatingDialog(xbmcgui.WindowXMLDialog):
    """
    Dialog de avaliação exibido ao atingir 80% do conteúdo.
    Fecha automaticamente após 'timeout' segundos se o usuário não interagir.
      rating = True  → Gostei   (botão 9301)
      rating = False → Não gostei (botão 9302)
      rating = None  → Fechado sem interação / timeout
    """

    def __init__(self, *args, **kwargs):
        self.title      = kwargs.pop('title', '')
        self.rating     = None
        self._item_info = kwargs.pop('item_info', {})
        self._timeout   = kwargs.pop('timeout', 5)  # segundos; 0 = sem timeout
        self._timer     = None
        super().__init__(*args, **kwargs)

    def onInit(self):
        try:
            self.getControl(9310).setLabel(self.title)
        except Exception as e:
            xbmc.log(f"[RatingDialog] Erro ao setar título: {e}", xbmc.LOGERROR)
        self.setFocus(self.getControl(9301))

        # Auto-close após timeout
        if self._timeout > 0:
            self._timer = threading.Timer(self._timeout, self._auto_close)
            self._timer.daemon = True
            self._timer.start()

    def _auto_close(self):
        xbmc.log("[RatingDialog] Timeout — fechando automaticamente.", xbmc.LOGINFO)
        self.close()

    def _cancel_timer(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def onClick(self, control_id):
        self._cancel_timer()
        if control_id == 9301:
            self.rating = True
            self._save_rating(8)
            self.close()
        elif control_id == 9302:
            self.rating = False
            self._save_rating(4)
            self.close()

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_PREVIOUS_MENU,
                               xbmcgui.ACTION_NAV_BACK,
                               xbmcgui.ACTION_STOP):
            self._cancel_timer()
            self.close()

    def _save_rating(self, score):
        try:
            from resources.lib.db.history_db import history_db
            from resources.lib.history import _get_active_profile_id

            tmdb_id    = self._item_info.get('tmdb_id')
            media_type = self._item_info.get('media_type', 'movie')
            season     = self._item_info.get('season')
            episode    = self._item_info.get('episode')

            profile_id = _get_active_profile_id()

            if tmdb_id:
                history_db.save_rating(
                    tmdb_id    = int(tmdb_id),
                    media_type = media_type,
                    rating     = score,
                    profile_id = profile_id,
                    season     = int(season)  if season  else None,
                    episode    = int(episode) if episode else None,
                )
        except Exception as e:
            xbmc.log(f"[RatingDialog] Erro ao salvar rating local: {e}", xbmc.LOGERROR)

        threading.Thread(
            target=self._send_trakt_rating,
            args=(score,),
            daemon=True
        ).start()

    def _send_trakt_rating(self, score):
        try:
            if not ADDON.getSettingBool('trakt_auto_scrobble'):
                return
            from resources.lib.trakt.trakt_sync import trakt_request
            tmdb_id    = self._item_info.get('tmdb_id')
            media_type = self._item_info.get('media_type', 'movie')
            season     = self._item_info.get('season')
            episode    = self._item_info.get('episode')
            rated_at   = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())

            if media_type == 'movie':
                payload = {'movies': [{'ids': {'tmdb': int(tmdb_id)},
                                        'rating': score, 'rated_at': rated_at}]}
            elif media_type == 'tvshow' and season and episode:
                payload = {'episodes': [{'ids': {'tmdb': int(tmdb_id)},
                                          'rating': score, 'rated_at': rated_at}]}
            else:
                return

            trakt_request('POST', '/sync/ratings', payload)
            xbmc.log(f"[RatingDialog] Trakt rating {score} enviado.", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[RatingDialog] Erro ao enviar Trakt rating: {e}", xbmc.LOGERROR)



class NextEpisodeDialog(xbmcgui.WindowXMLDialog):
    """
    Dialog de próximo episódio exibido ao atingir trigger_pct% — COM o vídeo ainda rodando.
    Mesmo padrão do RatingDialog — usa arquivo XML da skin.
    Fecha automaticamente após timeout se o usuário não interagir (equivale a Não).
      play_next = True  → Sim  (botão 9401) → para o vídeo e inicia o próximo
      play_next = False → Não  (botão 9402) → fecha, vídeo continua normalmente
      play_next = None  → Timeout sem interação → vídeo continua normalmente
    """

    def __init__(self, *args, **kwargs):
        self.label     = kwargs.pop('label', '')
        self.play_next = None
        self._timeout  = kwargs.pop('timeout', 15)
        self._timer    = None
        super().__init__(*args, **kwargs)

    def onInit(self):
        try:
            self.getControl(9410).setLabel(self.label)
        except Exception as e:
            xbmc.log(f"[NextEpisodeDialog] Erro ao setar label: {e}", xbmc.LOGERROR)
        try:
            self.setFocus(self.getControl(9401))
        except Exception:
            pass

        if self._timeout > 0:
            self._timer = threading.Timer(self._timeout, self._auto_close)
            self._timer.daemon = True
            self._timer.start()

    def _auto_close(self):
        xbmc.log("[NextEpisodeDialog] Timeout — fechando, vídeo continua.", xbmc.LOGINFO)
        self.close()

    def _cancel_timer(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def onClick(self, control_id):
        self._cancel_timer()
        if control_id == 9401:    # Pular — inicia próximo imediatamente
            self.play_next = True
            self.close()

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_PREVIOUS_MENU,
                               xbmcgui.ACTION_NAV_BACK,
                               xbmcgui.ACTION_STOP):
            # Fechar/voltar = aguarda o fim do vídeo (play_next permanece None)
            self._cancel_timer()
            self.close()


def _show_rating_dialog(item_info):
    """
    Instancia e exibe o RatingDialog em thread separada para não bloquear
    o loop de monitoramento.
    Lê timeout de 'rating_dialog.timeout' nas settings.
    """
    try:
        if not ADDON.getSettingBool('rating_dialog.enabled'):
            return None

        try:
            timeout = int(ADDON.getSetting('rating_dialog.timeout') or 5)
        except Exception:
            timeout = 5

        media_type = item_info.get('media_type', 'movie')
        if media_type == 'tvshow':
            season  = item_info.get('season', 0)
            episode = item_info.get('episode', 0)
            title   = f"{item_info.get('title', '')} S{int(season):02d}E{int(episode):02d}"
        else:
            title = item_info.get('title', 'este filme')

        dialog = RatingDialog(
            'Ratingdialog.xml',
            ADDON.getAddonInfo('path'),
            'default',
            '1080i',
            title=title,
            item_info=item_info,
            timeout=timeout,
        )
        dialog.doModal()
        rating = dialog.rating
        del dialog
        xbmc.log(f"[RatingDialog] Resultado: {rating}", xbmc.LOGINFO)
        return rating
    except Exception as e:
        xbmc.log(f"[RatingDialog] Falha ao exibir dialog: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        return None


# ============================================================
# PRÓXIMO EPISÓDIO
# ============================================================

def _get_next_episode_info(item_info):
    """
    Busca dados do próximo episódio no cache local.
    Avança de temporada automaticamente se necessário.
    Retorna None se não houver próximo episódio.
    """
    try:
        from resources.lib.db import db

        tmdb_id = item_info.get('tmdb_id')
        season  = int(item_info.get('season', 0))
        episode = int(item_info.get('episode', 0))

        if not tmdb_id or not season or not episode:
            return None

        try:
            cache_hours = int(ADDON.getSetting('cache_age_hours') or 72)
        except Exception:
            cache_hours = 72

        # Tenta próximo ep na mesma temporada
        episodes = db.get_cached_episodes(tmdb_id, season, cache_hours)
        next_ep  = next(
            (e for e in (episodes or []) if e.get('episode_number') == episode + 1),
            None
        )
        next_season = season

        # Se não achou, tenta ep 1 da próxima temporada
        if not next_ep:
            next_season     = season + 1
            next_season_eps = db.get_cached_episodes(tmdb_id, next_season, cache_hours)
            next_ep = next(
                (e for e in (next_season_eps or []) if e.get('episode_number') == 1),
                None
            )

        if not next_ep:
            xbmc.log("[NextEpisode] Nenhum episódio seguinte encontrado.", xbmc.LOGINFO)
            return None

        next_info = dict(item_info)
        next_info['season']        = next_season
        next_info['episode']       = next_ep.get('episode_number')
        next_info['episode_title'] = next_ep.get('name', '')
        next_info['plot']          = next_ep.get('overview', '')
        next_info['runtime']       = next_ep.get('runtime', 0)
        next_info['premiered']     = next_ep.get('air_date', '')

        if next_ep.get('still_path'):
            next_info['episode_poster'] = (
                f"https://image.tmdb.org/t/p/w780{next_ep['still_path']}"
            )

        xbmc.log(
            f"[NextEpisode] Próximo: S{next_season:02d}E{next_ep.get('episode_number'):02d} "
            f"— {next_ep.get('name', '')}",
            xbmc.LOGINFO
        )
        return next_info

    except Exception as e:
        xbmc.log(f"[NextEpisode] Erro ao buscar próximo ep: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        return None


def _show_next_episode_dialog(next_ep_info, result_container=None):
    """
    Exibe NextEpisodeDialog COM o vídeo ainda rodando (disparado ao atingir trigger_pct%).
    - Clicou "Pular" (9401) → para o vídeo atual e inicia o próximo imediatamente
    - Fechou / Timeout      → vídeo continua até o fim; o loop principal
                              reproduzirá o próximo automaticamente ao terminar

    result_container: lista de 1 elemento onde o resultado será armazenado:
                      True  = pulou agora | None = aguarda o fim
    """
    try:
        season   = int(next_ep_info.get('season', 0))
        episode  = int(next_ep_info.get('episode', 0))
        ep_title = next_ep_info.get('episode_title', '')
        label    = f"S{season:02d}E{episode:02d}"
        if ep_title:
            label += f" — {ep_title}"

        try:
            timeout = int(ADDON.getSetting('next_episode.timeout') or 15)
        except Exception:
            timeout = 15

        xbmc.log(f"[NextEpisode] Exibindo dialog para: {label}", xbmc.LOGINFO)

        # doModal() bloqueia esta thread mas NÃO o vídeo — ele continua rodando
        dialog = NextEpisodeDialog(
            'NextEpisodedialog.xml',
            ADDON.getAddonInfo('path'),
            'default',
            '1080i',
            label=label,
            timeout=timeout,
        )
        dialog.doModal()
        play_next = dialog.play_next
        del dialog

        xbmc.log(f"[NextEpisode] Resultado: {play_next}", xbmc.LOGINFO)

        # Armazena resultado para o loop principal consultar após o vídeo terminar
        if result_container is not None:
            result_container[0] = play_next

        # Não / Timeout → vídeo continua; o loop principal reproduzirá o próximo ao terminar
        if not play_next:
            return

        # Sim → para o vídeo atual e inicia o próximo imediatamente
        player = xbmc.Player()
        if player.isPlaying():
            player.stop()
        for _ in range(10):
            if not player.isPlaying():
                break
            time.sleep(1)

        time.sleep(1)

        import json
        item_data = urllib.parse.quote(json.dumps(next_ep_info))
        addon_id  = ADDON.getAddonInfo('id')
        run_url   = f"plugin://{addon_id}/?action=find_and_play_episode&item_data={item_data}"
        xbmc.executebuiltin(f"RunPlugin({run_url})")

    except Exception as e:
        xbmc.log(f"[NextEpisode] Erro no dialog: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)


# ============================================================
# PLAYER PRINCIPAL
# ============================================================

def _should_show_subtitles(item_info):
    """
    Decide se o dialog de legendas deve ser exibido para este conteúdo.
    Respeita as settings:
      opensubtitles.enabled   — legenda ativada globalmente
      opensubtitles.only_leg  — exibe legenda apenas em fontes LEG (legendado)
    """
    if not ADDON.getSetting('opensubtitles.token').strip():
        return False
    if not ADDON.getSettingBool('opensubtitles.enabled'):
        return False
    if ADDON.getSettingBool('opensubtitles.only_leg'):
        lang = (item_info.get('languages') or '').upper()
        if 'LEG' not in lang:
            return False
    return True


def play_url(url, item_info):
    if not url:
        xbmc.log("[Player] URL vazia", xbmc.LOGERROR)
        return False

    try:
        handle = int(sys.argv[1])
    except (IndexError, ValueError) as e:
        xbmc.log(f"[Player] Erro: handle inválido: {e}", xbmc.LOGERROR)
        return False

    url = _try_resolveurl(url)

    # Hint de tipo vindo do scraper via item_info (ex: 'hls' para URLs .php do NetCine)
    hint = (item_info.get('manifest_type') or '').lower()
    stream_config = _detect_stream_type(url, hint=hint)

    # Separa URL limpa dos headers do pipe ANTES de qualquer coisa
    pipe_idx = url.find('|')
    if pipe_idx != -1:
        clean_url   = url[:pipe_idx]
        piped_hdrs  = url[pipe_idx+1:]
    else:
        clean_url   = url
        # Usa headers pré-montados pelo scraper se disponíveis
        piped_hdrs  = item_info.get('stream_headers', '')

    final_url = _process_url(clean_url, item_info, stream_config)

    if not final_url:
        xbmc.log("[Player] Falha ao processar URL", xbmc.LOGERROR)
        return False

    # ListItem sempre recebe URL limpa
    play_item = xbmcgui.ListItem(path=final_url)
    _set_metadata(play_item, item_info)

    if stream_config['player'] == 'inputstream':
        _configure_inputstream(play_item, final_url, stream_config)
        # Monta stream_headers fundindo headers do pipe + headers padrão
        headers = _build_headers_dict(final_url, piped_hdrs)
        header_string = '&'.join(
            f"{k}={urllib.parse.quote(v)}" for k, v in headers.items()
        )
        play_item.setProperty('inputstream.adaptive.stream_headers', header_string)
        play_item.setProperty('inputstream.adaptive.manifest_headers', header_string)
        

    elif stream_config['player'] == 'native':
        _configure_native_player(play_item, final_url, stream_config)
        if piped_hdrs:
            final_url = f"{final_url}|{piped_hdrs}"
        else:
            headers = _build_headers_dict(final_url, '')
            header_string = '&'.join(
                f"{k}={urllib.parse.quote(v)}" for k, v in headers.items()
            )
            final_url = f"{final_url}|{header_string}"
        play_item.setPath(final_url)

    play_item.setProperty('IsPlayable', 'true')

    if handle != -1:
        # Fluxo normal: usuário clicou em item — handle válido
        xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=play_item)

        # ── Legendas (OpenSubtitles) ──────────────────────────────
        if _should_show_subtitles(item_info):
            def _subtitle_thread():
                try:
                    from ..subtitles import show_subtitle_dialog, apply_subtitle_to_player
                    subtitle_path = show_subtitle_dialog(item_info)
                    if subtitle_path:
                        apply_subtitle_to_player(subtitle_path)
                except Exception as e:
                    xbmc.log(f'[Player] Erro no dialog de legendas: {e}', xbmc.LOGWARNING)
            threading.Thread(target=_subtitle_thread, daemon=True).start()

    else:
        # Fluxo próximo episódio: RunPlugin gera handle=-1
        # setResolvedUrl seria ignorado pelo Kodi — usa player.play() diretamente
        xbmc.log("[Player] handle=-1 detectado → usando xbmc.Player().play()", xbmc.LOGINFO)
        _kodi_player = xbmc.Player()
        _kodi_player.play(item=final_url, listitem=play_item)

        # Aguarda o player iniciar e força atualização dos metadados na OSD
        # (xbmc.Player().play() fora de lista pode herdar título do episódio anterior)
        def _update_info_tag():
            player = xbmc.Player()
            for _ in range(20):
                if player.isPlaying():
                    try:
                        tag = player.getVideoInfoTag()
                        tag.setTitle(item_info.get('episode_title') or item_info.get('title', ''))
                        tag.setSeason(int(item_info.get('season', 0)))
                        tag.setEpisode(int(item_info.get('episode', 0)))
                        tag.setTvShowTitle(item_info.get('title', ''))
                        tag.setPlot(item_info.get('plot', ''))
                    except Exception as ex:
                        xbmc.log(f"[Player] Erro ao atualizar InfoTag: {ex}", xbmc.LOGWARNING)
                    return
                time.sleep(0.5)
        threading.Thread(target=_update_info_tag, daemon=True).start()

        # ── Legendas (OpenSubtitles) — autonext ───────────────────
        if _should_show_subtitles(item_info):
            def _subtitle_thread_autonext():
                try:
                    from ..subtitles import show_subtitle_dialog, apply_subtitle_to_player
                    subtitle_path = show_subtitle_dialog(item_info)
                    if subtitle_path:
                        apply_subtitle_to_player(subtitle_path)
                except Exception as e:
                    xbmc.log(f'[Player] Erro no dialog de legendas (autonext): {e}', xbmc.LOGWARNING)
            threading.Thread(target=_subtitle_thread_autonext, daemon=True).start()

    if stream_config.get('needs_watchdog'):
        threading.Thread(
            target=_smart_watchdog,
            args=(final_url, stream_config),
            daemon=True
        ).start()

    # Histórico + Rating dialog + Próximo episódio
    # Passa a URL original (antes de processar) para o monitor confirmar após 2%
    _pending_url = item_info.get('_pending_stream_url') or url
    t1 = threading.Timer(3.0, _history_monitor, args=(item_info, stream_config, _pending_url))
    t1.daemon = True
    t1.start()

    if ADDON.getSettingBool('trakt_auto_scrobble'):
        t2 = threading.Timer(3.0, _intelligent_scrobble, args=(item_info, stream_config))
        t2.daemon = True
        t2.start()

    return True

def _build_headers_dict(url, piped_hdrs_str):
    """Monta dict de headers fundindo padrão + pipe."""
    domain_match = re.search(r'https?://([^/]+)', url)
    domain = domain_match.group(1) if domain_match else ''

    headers = {
        'User-Agent':      USER_AGENT,
        'Accept':          '*/*',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        'Connection':      'keep-alive',
    }
    if not _IS_ANDROID and domain:
        headers['Referer'] = f'https://{domain}/'
        headers['Origin']  = f'https://{domain}'

    # Headers do pipe sobrescrevem os padrão
    if piped_hdrs_str:
        for part in piped_hdrs_str.split('&'):
            if '=' in part:
                k, v = part.split('=', 1)
                try:
                    headers[urllib.parse.unquote(k)] = urllib.parse.unquote(v)
                except Exception:
                    pass

    return {k: v for k, v in headers.items() if v}

def _detect_stream_type(url, hint=None):
    if not url:
        return {'type': 'unknown', 'player': 'native', 'needs_headers': True, 'needs_watchdog': False}

    # Hint do scraper tem prioridade — URL pode ser .php sem extensão reveladora
    if hint:
        h = hint.lower()
        if h == 'hls':
            return {'type': 'hls', 'player': 'inputstream', 'manifest_type': 'hls', 'needs_headers': True, 'needs_watchdog': True}
        if h in ('dash', 'mpd'):
            return {'type': 'dash', 'player': 'inputstream', 'manifest_type': 'mpd', 'needs_headers': True, 'needs_watchdog': True}

    url_lower = url.lower()

    if (
        url_lower.startswith('magnet:')
        or url_lower.startswith('plugin://plugin.video.elementum')
        or (len(url) == 40 and ' ' not in url and not url_lower.startswith('http'))
    ):
        return {'type': 'torrent', 'player': 'elementum', 'needs_headers': False, 'needs_watchdog': False}

    if '.m3u8' in url_lower:
        return {'type': 'hls', 'player': 'inputstream', 'manifest_type': 'hls', 'needs_headers': True, 'needs_watchdog': True}

    if '.mpd' in url_lower:
        return {'type': 'dash', 'player': 'inputstream', 'manifest_type': 'mpd', 'needs_headers': True, 'needs_watchdog': True}

    if '.mp4' in url_lower:
        return {'type': 'mp4', 'player': 'native', 'needs_headers': True, 'needs_watchdog': False}

    if any(ext in url_lower for ext in ('.mkv', '.avi', '.flv')):
        return {'type': 'video', 'player': 'native', 'needs_headers': True, 'needs_watchdog': False}

    return {'type': 'video', 'player': 'native', 'needs_headers': True, 'needs_watchdog': False}


def _process_url(url, item_info, stream_config):
    if stream_config['type'] == 'torrent':
        return _build_elementum_url(url, item_info)
    if _IS_ANDROID:
        url = _sanitize_url(url)
    return url


def _build_elementum_url(url, item_info):
    if url.startswith('plugin://'):
        return url

    if url.startswith('magnet:'):
        magnet_uri = url
    elif len(url) == 40 and not url.startswith('http') and ' ' not in url:
        magnet_uri = f"magnet:?xt=urn:btih:{url}"
    else:
        magnet_uri = url

    encoded_uri   = urllib.parse.quote_plus(magnet_uri)
    elementum_url = f"plugin://plugin.video.elementum/play?uri={encoded_uri}"

    tmdb_id = item_info.get('tmdb_id')
    if tmdb_id:
        elementum_url += f"&tmdb={tmdb_id}"

    if item_info.get('media_type') == 'tvshow':
        season  = item_info.get('season')
        episode = item_info.get('episode')
        if season is not None and episode is not None:
            elementum_url += f"&season={season}&episode={episode}"

    return elementum_url


def _set_metadata(play_item, item_info):
    info_labels = {
        'title':         item_info.get('episode_title', item_info.get('title', 'Playback')),
        'originaltitle': item_info.get('original_title'),
        'year':          item_info.get('year'),
        'plot':          item_info.get('plot', item_info.get('overview', '')),
        'season':        item_info.get('season'),
        'episode':       item_info.get('episode'),
        'tvshowtitle':   item_info.get('title') if item_info.get('media_type') == 'tvshow' else '',
        'mediatype':     item_info.get('media_type', 'video'),
        'imdbnumber':    item_info.get('imdb_id'),
        'duration':      int(item_info.get('runtime', 0)) * 60,
        'genre':         " / ".join(item_info.get('genres', [])),
        'rating':        item_info.get('rating'),
        'votes':         item_info.get('votes'),
    }
    info_labels = {k: v for k, v in info_labels.items() if v is not None}
    play_item.setInfo('video', info_labels)
    play_item.setArt({
        'thumb':     item_info.get('episode_poster') or item_info.get('poster') or '',
        'poster':    item_info.get('poster') or '',
        'fanart':    item_info.get('backdrop') or '',
        'banner':    item_info.get('banner') or '',
        'clearlogo': item_info.get('clearlogo') or '',
    })


def _configure_inputstream(play_item, url, stream_config):
    play_item.setProperty('inputstream', 'inputstream.adaptive')
    manifest_type = stream_config.get('manifest_type', 'hls')
    play_item.setProperty('inputstream.adaptive.manifest_type', manifest_type)
    mime_types = {
        'hls':  'application/vnd.apple.mpegurl',
        'dash': 'application/dash+xml',
        'mp4':  'video/mp4',
    }
    play_item.setMimeType(mime_types.get(stream_config['type'], 'video/mp4'))
    play_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')


def _configure_native_player(play_item, url, stream_config):
    mime_types = {
        'mp4':   'video/mp4',
        'video': 'video/x-matroska',
        'mkv':   'video/x-matroska',
        'avi':   'video/x-msvideo',
        'flv':   'video/x-flv',
    }
    play_item.setMimeType(mime_types.get(stream_config['type'], 'video/x-matroska'))
    play_item.setContentLookup(False)


def _apply_headers(play_item, url, stream_config):
    # Separa URL dos headers embutidos (formato pipe)
    pipe_idx = url.find('|')
    if pipe_idx != -1:
        clean_url    = url[:pipe_idx]
        piped_hdrs   = dict(
            part.split('=', 1)
            for part in url[pipe_idx+1:].split('&')
            if '=' in part
        )
    else:
        clean_url  = url
        piped_hdrs = {}

    domain_match = re.search(r'https?://([^/]+)', clean_url)
    domain = domain_match.group(1) if domain_match else ''

    # CDN/Storage direto — retorna URL limpa sem headers para evitar HTTP 400
    is_storage = (
        any(x in domain for x in ('r2.cloudflarestorage.com', 's3.amazonaws.com', 'cloudfront.net'))
        and 'X-Amz-Signature' not in clean_url
    )
    if is_storage and not piped_hdrs:
        return clean_url

    headers = {
        'User-Agent':      USER_AGENT,
        'Accept':          '*/*',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        'Connection':      'keep-alive',
    }
    if not _IS_ANDROID and domain and not is_storage:
        headers['Referer'] = f"https://{domain}/"
        headers['Origin']  = f"https://{domain}"

    # Headers do pipe têm prioridade (Referer/Origin específicos do scraper)
    for k, v in piped_hdrs.items():
        try:
            headers[urllib.parse.unquote(k)] = urllib.parse.unquote(v)
        except Exception:
            pass

    headers = {k: v for k, v in headers.items() if v}

    if play_item.getProperty('inputstream'):
        header_string = '&'.join(
            f"{k}={urllib.parse.quote(v)}" for k, v in headers.items()
        )
        play_item.setProperty('inputstream.adaptive.stream_headers', header_string)
        play_item.setProperty('inputstream.adaptive.manifest_headers', header_string)
        return clean_url  # ← URL sem pipe!
    else:
        header_string = '&'.join(
            f"{k}={urllib.parse.quote(v)}" for k, v in headers.items()
        )
        return f"{clean_url}|{header_string}"


def _smart_watchdog(url, stream_config):
    time.sleep(8)
    player = xbmc.Player()
    state  = {
        'frozen_checks':     0,
        'network_errors':    0,
        'last_time':         -1,
        'start_time':        time.time(),
        'recovery_attempts': 0,
    }

    while time.time() - state['start_time'] < 600:
        if not player.isPlaying():
            break

        try:
            current_time = player.getTime()
            time_delta   = abs(current_time - state['last_time'])

            if time_delta < 0.5 and current_time > 5:
                state['frozen_checks'] += 1
                is_buffering = _check_if_buffering(player, current_time)

                if state['frozen_checks'] >= 6 and not is_buffering:
                    if state['recovery_attempts'] < 2:
                        if _attempt_recovery(player, current_time):
                            state['frozen_checks']     = 0
                            state['recovery_attempts'] += 1
                            state['last_time']          = -1
                            time.sleep(10)
                            continue

                    xbmc.log("[Watchdog] ✖ Forçando parada do player", xbmc.LOGERROR)
                    player.stop()
                    xbmcgui.Dialog().notification(
                        'Player', 'Stream travou e foi parado automaticamente',
                        xbmcgui.NOTIFICATION_WARNING, 5000
                    )
                    break
            else:
                state['frozen_checks']  = 0
                state['network_errors'] = 0

            state['last_time'] = current_time

        except Exception:
            state['network_errors'] += 1
            if state['network_errors'] > 10:
                break

        time.sleep(5)


def _check_if_buffering(player, current_time):
    try:
        if current_time < 10:
            return True
        return player.getCachePercentage() < 100
    except Exception:
        return False


def _attempt_recovery(player, position):
    try:
        if position > 10:
            player.seekTime(position - 8)
            time.sleep(3)
            if player.isPlaying():
                return abs(player.getTime() - (position - 8)) < 5
        player.pause()
        time.sleep(1)
        player.pause()
        time.sleep(2)
        return player.isPlaying()
    except Exception:
        return False


# ============================================================
# HISTÓRICO + RATING DIALOG + PRÓXIMO EPISÓDIO
# ============================================================

def _history_monitor(item_info, stream_config, stream_url=''):
    tmdb_id    = item_info.get('tmdb_id')
    media_type = item_info.get('media_type', 'movie')
    season     = item_info.get('season')
    episode    = item_info.get('episode')

    if not tmdb_id:
        return

    monitor_key = (tmdb_id, media_type, season, episode)
    with _active_monitors_lock:
        if monitor_key in _active_monitors:
            xbmc.log(f"[History] Monitor já ativo para {monitor_key}, abortando duplicata.", xbmc.LOGINFO)
            return
        _active_monitors.add(monitor_key)

    try:
        _history_monitor_inner(item_info, stream_config, stream_url)
    finally:
        with _active_monitors_lock:
            _active_monitors.discard(monitor_key)


def _history_monitor_inner(item_info, stream_config, stream_url=''):
    """
    Monitora progresso e:
      1. Salva no histórico local periodicamente (a cada 60s) e ao terminar
      2. Salva last_stream_url após 2% (confirma que o stream funcionou)
      3. Exibe RatingDialog ao atingir 80%
      4. Exibe NextEpisodeDialog se autonext estiver ativo
    """
    max_wait = 60 if stream_config['type'] == 'torrent' else 20
    player   = xbmc.Player()

    for _ in range(max_wait):
        if player.isPlaying():
            break
        time.sleep(1)
    else:
        return

    tmdb_id    = item_info.get('tmdb_id')
    media_type = item_info.get('media_type', 'movie')
    season     = item_info.get('season')
    episode    = item_info.get('episode')

    if not tmdb_id:
        return

    # Resolve profile_id (VIP)
    profile_id = None
    try:
        from resources.lib.vip_auth import is_session_valid
        if is_session_valid():
            from resources.lib.profile_manager import ProfileManager
            profile    = ProfileManager().get_current_profile()
            profile_id = profile.get('id') if profile else None
    except Exception:
        pass

    # Próximo episódio
    next_ep_enabled = False
    next_ep_trigger = 90
    next_ep_info    = None

    if media_type == 'tvshow' and season and episode:
        next_ep_enabled = ADDON.getSettingBool('playback.autonext_episode')
        if next_ep_enabled:
            try:
                next_ep_trigger = int(ADDON.getSetting('next_episode.trigger_pct') or 90)
            except Exception:
                next_ep_trigger = 90
            next_ep_info = _get_next_episode_info(item_info)

    rating_shown          = False
    next_ep_triggered     = False
    next_ep_dialog_result = [None]
    positions             = []
    _last_save_time       = time.time()
    _last_saved_progress  = 0.0
    _stream_url_saved     = False  # só salva last_stream_url após confirmar 2%

    try:
        time.sleep(10)

        while player.isPlaying():
            try:
                current_pos = player.getTime()
                total_time  = player.getTotalTime()

                if total_time > 0:
                    positions.append((current_pos, total_time))
                    progress = current_pos / total_time * 100

                    # Confirma stream funcionando → salva last_stream_url (uma vez)
                    if not _stream_url_saved and stream_url and progress >= 2.0:
                        _stream_url_saved = True
                        try:
                            from resources.lib.db.history_db import history_db
                            history_db.add_to_history(
                                tmdb_id         = int(tmdb_id),
                                media_type      = media_type,
                                profile_id      = profile_id,
                                season          = int(season)  if season  else None,
                                episode         = int(episode) if episode else None,
                                progress        = round(progress, 1),
                                last_stream_url = stream_url,
                            )
                            xbmc.log(f'[History] last_stream_url confirmado após {progress:.1f}%', xbmc.LOGINFO)
                        except Exception as e:
                            xbmc.log(f'[History] Erro ao salvar stream_url: {e}', xbmc.LOGWARNING)

                    # Rating dialog aos 80%
                    if not rating_shown and not next_ep_enabled and progress >= 80.0:
                        rating_shown = True
                        xbmc.log("[History] 80% — exibindo dialog de avaliação.", xbmc.LOGINFO)
                        threading.Thread(
                            target=_show_rating_dialog,
                            args=(item_info,),
                            daemon=True
                        ).start()

                    # Próximo episódio
                    if (next_ep_enabled and not next_ep_triggered
                            and next_ep_info and progress >= next_ep_trigger):
                        next_ep_triggered = True
                        xbmc.log(f"[History] {next_ep_trigger}% — disparando próximo episódio.", xbmc.LOGINFO)
                        threading.Thread(
                            target=_show_next_episode_dialog,
                            args=(next_ep_info, next_ep_dialog_result),
                            daemon=True
                        ).start()

                    # Save periódico a cada 60s
                    now = time.time()
                    if now - _last_save_time >= 60 and progress >= 2.0:
                        _last_save_time      = now
                        _last_saved_progress = round(progress, 1)
                        from resources.lib.db.history_db import history_db
                        history_db.add_to_history(
                            tmdb_id    = int(tmdb_id),
                            media_type = media_type,
                            profile_id = profile_id,
                            season     = int(season)  if season  else None,
                            episode    = int(episode) if episode else None,
                            progress   = _last_saved_progress,
                        )
                        xbmc.log(f"[History] Save periódico: {_last_saved_progress}%", xbmc.LOGINFO)

            except Exception:
                pass

            time.sleep(10)

        # ── Salva ao terminar ──────────────────────────────────────────────────
        if not positions:
            return

        max_pos        = max(p[0] for p in positions)
        avg_tot        = sum(p[1] for p in positions) / len(positions)
        progress       = (max_pos / avg_tot * 100) if avg_tot > 0 else 0.0
        final_progress = round(progress, 1)

        # Salva se: nunca houve save periódico OU progresso avançou mais de 1%
        if _last_saved_progress == 0.0 or final_progress > _last_saved_progress + 1.0:
            from resources.lib.db.history_db import history_db
            history_db.add_to_history(
                tmdb_id    = int(tmdb_id),
                media_type = media_type,
                profile_id = profile_id,
                season     = int(season)  if season  else None,
                episode    = int(episode) if episode else None,
                progress   = final_progress,
            )
            xbmc.log(f"[History] Save final: {final_progress}%", xbmc.LOGINFO)
        else:
            xbmc.log(f"[History] Save final ignorado (já salvo em {_last_saved_progress}%)", xbmc.LOGINFO)

        # ── Autoplay próximo episódio após fim ────────────────────────────────
        dialog_was_shown = next_ep_triggered
        user_said_yes    = (next_ep_dialog_result[0] is True)
        if (next_ep_enabled and next_ep_info and dialog_was_shown
                and not user_said_yes and progress >= 75.0):
            xbmc.log("[NextEpisode] Usuário escolheu Não — reproduzindo próximo após o fim.", xbmc.LOGINFO)
            import json
            item_data = urllib.parse.quote(json.dumps(next_ep_info))
            addon_id  = ADDON.getAddonInfo('id')
            run_url   = f"plugin://{addon_id}/?action=find_and_play_episode&item_data={item_data}"
            time.sleep(1)
            xbmc.executebuiltin(f"RunPlugin({run_url})")

    except Exception as e:
        xbmc.log(f"[History] Erro: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)


def _intelligent_scrobble(item_info, stream_config):
    """Scrobble Trakt com detecção inteligente de progresso. Não toca no DB local."""
    max_wait = 60 if stream_config['type'] == 'torrent' else 20
    player   = xbmc.Player()

    for _ in range(max_wait):
        if player.isPlaying():
            break
        time.sleep(1)
    else:
        return

    if not item_info.get('tmdb_id'):
        return

    positions = []

    try:
        time.sleep(15)

        while player.isPlaying():
            try:
                positions.append({
                    'position':  player.getTime(),
                    'total':     player.getTotalTime(),
                    'timestamp': time.time()
                })
            except Exception:
                pass
            time.sleep(10)

        if not positions or len(positions) < 2:
            return

        max_position       = max(p['position'] for p in positions)
        avg_total          = sum(p['total'] for p in positions) / len(positions)
        watch_duration     = positions[-1]['timestamp'] - positions[0]['timestamp']
        effective_progress = (max_position / avg_total * 100) if avg_total > 60 else 0

        should_scrobble = (
            effective_progress >= 75
            or max_position >= 900
            or (effective_progress >= 50 and watch_duration >= 1800)
        )

        if not should_scrobble:
            return

        _send_to_trakt(item_info, effective_progress, max_position, avg_total)

    except Exception as e:
        xbmc.log(f"[Trakt Scrobble] Erro crítico: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)


def _send_to_trakt(item_info, progress, watched_time, total_time):
    try:
        from resources.lib.trakt.trakt_sync import trakt_request

        media_type = item_info.get('media_type')
        tmdb_id    = item_info.get('tmdb_id')
        watched_at = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())

        if media_type == 'movie':
            payload = {'movies': [{'ids': {'tmdb': int(tmdb_id)}, 'watched_at': watched_at}]}
            title_display = item_info.get('title', 'Filme')

        elif media_type == 'tvshow':
            season  = item_info.get('season')
            episode = item_info.get('episode')
            if not season or not episode:
                return
            payload = {
                'shows': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'seasons': [{
                        'number':   int(season),
                        'episodes': [{'number': int(episode), 'watched_at': watched_at}]
                    }]
                }]
            }
            title_display = f"{item_info.get('title', 'Série')} S{season:02d}E{episode:02d}"
        else:
            return

        response = trakt_request('POST', '/sync/history', payload)

        if response:
            if ADDON.getSettingBool('trakt_show_notifications'):
                xbmcgui.Dialog().notification(
                    'Trakt', f"✓ {title_display}", xbmcgui.NOTIFICATION_INFO, 3000
                )
        else:
            xbmc.log("[Trakt Scrobble] ✖ Falha ao enviar para Trakt", xbmc.LOGERROR)

    except Exception as e:
        xbmc.log(f"[Trakt Scrobble] Erro ao enviar: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)


def play_url_with_retry(url, item_info, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                xbmcgui.Dialog().notification(
                    'Player', f'Tentando novamente ({attempt + 1}/{max_retries + 1})...',
                    xbmcgui.NOTIFICATION_INFO, 2000
                )
                time.sleep(3)

            if play_url(url, item_info):
                return True

        except Exception as e:
            xbmc.log(f"[Player] Erro na tentativa {attempt + 1}: {e}", xbmc.LOGERROR)
            if attempt == max_retries:
                xbmcgui.Dialog().notification(
                    'Player', f'Falha após {max_retries + 1} tentativas',
                    xbmcgui.NOTIFICATION_ERROR, 5000
                )
                return False

    return False