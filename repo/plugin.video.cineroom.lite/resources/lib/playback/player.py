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
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def play_url(url, item_info):
    """
    Reproduz URL com detecção automática de formato e configuração otimizada
    """
    if not url:
        xbmc.log("[Player] URL vazia", xbmc.LOGERROR)
        return False

    try:
        handle = int(sys.argv[1])
    except (IndexError, ValueError) as e:
        xbmc.log(f"[Player] Erro: handle inválido: {e}", xbmc.LOGERROR)
        return False

    # Detecta tipo de stream
    stream_config = _detect_stream_type(url)
    xbmc.log(f"[Player] Tipo detectado: {stream_config['type']}", xbmc.LOGINFO)

    # Processa URL baseado no tipo
    final_url = _process_url(url, item_info, stream_config)
    
    if not final_url:
        xbmc.log("[Player] Falha ao processar URL", xbmc.LOGERROR)
        return False

    # Cria ListItem
    play_item = xbmcgui.ListItem(path=final_url)
    
    # Configura metadados
    _set_metadata(play_item, item_info)
    
    # Configura player apropriado
    if stream_config['player'] == 'inputstream':
        _configure_inputstream(play_item, final_url, stream_config)
    elif stream_config['player'] == 'native':
        _configure_native_player(play_item, final_url, stream_config)
    
    # Aplica headers
    if stream_config.get('needs_headers'):
        final_url = _apply_headers(play_item, final_url, stream_config)
        play_item.setPath(final_url)
    
    play_item.setProperty('IsPlayable', 'true')
    
    # Resolve playback
    xbmcplugin.setResolvedUrl(handle=handle, succeeded=True, listitem=play_item)
    
    # Inicia monitoramento
    if stream_config.get('needs_watchdog'):
        threading.Thread(
            target=_smart_watchdog,
            args=(final_url, stream_config),
            daemon=True
        ).start()
    
    # Scrobble automático
    if ADDON.getSettingBool('trakt_auto_scrobble'):
        threading.Timer(
            3.0,
            _intelligent_scrobble,
            args=(item_info, stream_config)
        ).start()
    
    xbmc.log(f"[Player] Playback iniciado com sucesso: {stream_config['type']}", xbmc.LOGINFO)
    return True


def _detect_stream_type(url):
    """
<<<<<<< HEAD
    Detecta corretamente o tipo de stream.
    Regras:
    - InputStream Adaptive SOMENTE para HLS (.m3u8) e DASH (.mpd)
    - MP4 / MKV / AVI / URLs sem extensão -> player nativo
    - URLs tipo download.aspx (Animezey) -> player nativo
    """

    if not url:
        return {
            'type': 'unknown',
            'player': 'native',
            'needs_headers': True,
            'needs_watchdog': False,
        }

    url_lower = url.lower()

    if (
        url_lower.startswith('magnet:')
        or url_lower.startswith('plugin://plugin.video.elementum')
        or (len(url) == 40 and ' ' not in url and not url_lower.startswith('http'))
    ):
=======
    Detecta tipo de stream e retorna configuração ideal
    """
    url_lower = url.lower()
    
    # Torrent/Magnet
    if url.startswith('magnet:') or 'elementum' in url or (len(url) == 40 and not url.startswith('http')):
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
        return {
            'type': 'torrent',
            'player': 'elementum',
            'needs_headers': False,
            'needs_watchdog': False,
        }
<<<<<<< HEAD
        
    if '.m3u8' in url_lower:
=======
    
    # HLS (melhor com InputStream)
    if '.m3u8' in url_lower or 'm3u8' in url_lower:
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
        return {
            'type': 'hls',
            'player': 'inputstream',
            'manifest_type': 'hls',
            'needs_headers': True,
            'needs_watchdog': True,
        }
<<<<<<< HEAD
        
=======
    
    # DASH (requer InputStream)
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
    if '.mpd' in url_lower:
        return {
            'type': 'dash',
            'player': 'inputstream',
            'manifest_type': 'mpd',
            'needs_headers': True,
            'needs_watchdog': True,
        }
<<<<<<< HEAD

    if '.mp4' in url_lower:
        return {
            'type': 'mp4',
            'player': 'native',
            'needs_headers': True,
            'needs_watchdog': False,
        }

    if any(ext in url_lower for ext in ('.mkv', '.avi', '.flv')):
=======
    
    # MP4 direto (pode usar InputStream ou nativo)
    if '.mp4' in url_lower:
        # Se tem domínios problemáticos, usa InputStream
        problematic_domains = ['animezey', 'workers.dev', 'cloudflare']
        needs_inputstream = any(domain in url_lower for domain in problematic_domains)
        
        return {
            'type': 'mp4',
            'player': 'inputstream' if needs_inputstream else 'native',
            'manifest_type': 'hls' if needs_inputstream else None,
            'needs_headers': True,
            'needs_watchdog': needs_inputstream,
        }
    
    # MKV/AVI (sempre nativo)
    if any(ext in url_lower for ext in ['.mkv', '.avi', '.flv']):
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
        return {
            'type': 'video',
            'player': 'native',
            'needs_headers': True,
            'needs_watchdog': False,
        }
<<<<<<< HEAD
        
    return {
        'type': 'video',
        'player': 'native',
        'needs_headers': True,
        'needs_watchdog': False,
    }



=======
    
    # Fallback: trata como MP4 com InputStream
    return {
        'type': 'unknown',
        'player': 'inputstream',
        'manifest_type': 'hls',
        'needs_headers': True,
        'needs_watchdog': True,
    }


>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
def _process_url(url, item_info, stream_config):
    """
    Processa URL baseado no tipo detectado
    """
    # Torrents/Magnets
    if stream_config['type'] == 'torrent':
        return _build_elementum_url(url, item_info)
    
    # URLs diretas
    return url


def _build_elementum_url(url, item_info):
    """
    Constrói URL do Elementum para torrents
    """
    # Já é plugin URL
    if url.startswith('plugin://'):
        return url
    
    # Magnet link
    if url.startswith('magnet:'):
        magnet_uri = url
    # Info hash
    elif len(url) == 40 and not url.startswith('http') and ' ' not in url:
        magnet_uri = f"magnet:?xt=urn:btih:{url}"
    else:
        magnet_uri = url
    
    encoded_uri = urllib.parse.quote_plus(magnet_uri)
    elementum_url = f"plugin://plugin.video.elementum/play?uri={encoded_uri}"
    
    # Adiciona TMDB ID
    tmdb_id = item_info.get('tmdb_id')
    if tmdb_id:
        elementum_url += f"&tmdb={tmdb_id}"
    
    # Adiciona season/episode para séries
    if item_info.get('media_type') == 'tvshow':
        season = item_info.get('season')
        episode = item_info.get('episode')
        
        if season is not None and episode is not None:
            elementum_url += f"&season={season}&episode={episode}"
    
    return elementum_url


def _set_metadata(play_item, item_info):
    """
    Configura metadados do ListItem
    """
    info_labels = {
        'title': item_info.get('episode_title', item_info.get('title', 'Playback')),
        'originaltitle': item_info.get('original_title'),
        'year': item_info.get('year'),
        'plot': item_info.get('plot', item_info.get('overview', '')),
        'season': item_info.get('season'),
        'episode': item_info.get('episode'),
        'tvshowtitle': item_info.get('title') if item_info.get('media_type') == 'tvshow' else '',
        'mediatype': item_info.get('media_type', 'video'),
        'imdbnumber': item_info.get('imdb_id'),
        'duration': int(item_info.get('runtime', 0)) * 60,
        'genre': " / ".join(item_info.get('genres', [])),
        'rating': item_info.get('rating'),
        'votes': item_info.get('votes'),
    }
    
    # Remove valores None
    info_labels = {k: v for k, v in info_labels.items() if v is not None}
    
    play_item.setInfo('video', info_labels)
    
    # Arte
    play_item.setArt({
        'thumb': item_info.get('episode_poster') or item_info.get('poster') or '',
        'poster': item_info.get('poster') or '',
        'fanart': item_info.get('backdrop') or '',
        'banner': item_info.get('banner') or '',
        'clearlogo': item_info.get('clearlogo') or '',
    })


def _configure_inputstream(play_item, url, stream_config):
    """
    Configura InputStream Adaptive (melhor para HLS/DASH/streams problemáticos)
    """
    xbmc.log("[Player] Configurando InputStream Adaptive", xbmc.LOGINFO)
    
    play_item.setProperty('inputstream', 'inputstream.adaptive')
    
    manifest_type = stream_config.get('manifest_type', 'hls')
    play_item.setProperty('inputstream.adaptive.manifest_type', manifest_type)
    
    # Mime type apropriado
    mime_types = {
        'hls': 'application/vnd.apple.mpegurl',
        'dash': 'application/dash+xml',
        'mp4': 'video/mp4',
    }
    play_item.setMimeType(mime_types.get(stream_config['type'], 'video/mp4'))
    
    # Configurações de buffer otimizadas
    play_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
    
    xbmc.log(f"[Player] InputStream configurado: {manifest_type}", xbmc.LOGDEBUG)


def _configure_native_player(play_item, url, stream_config):
    """
    Configura player nativo do Kodi
    """
    xbmc.log("[Player] Usando player nativo", xbmc.LOGINFO)
    
    # Mime type
    mime_types = {
        'mp4': 'video/mp4',
        'mkv': 'video/x-matroska',
        'avi': 'video/x-msvideo',
    }
    play_item.setMimeType(mime_types.get(stream_config['type'], 'video/mp4'))
    
    # Desabilita lookup de conteúdo (mais rápido)
    play_item.setContentLookup(False)


def _apply_headers(play_item, url, stream_config):
    """
    Aplica headers HTTP de forma robusta
    """
    # Extrai domínio para Referer
    domain_match = re.search(r'https?://([^/]+)', url)
    domain = domain_match.group(1) if domain_match else ''
    
    headers = {
        'User-Agent': USER_AGENT,
        'Referer': f"https://{domain}/" if domain else url,
        'Origin': f"https://{domain}" if domain else '',
        'Accept': '*/*',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
<<<<<<< HEAD
        'Connection': 'keep-alive',
        # REMOVIDO: 'Range': 'bytes=0-'  # <-- ESTE É O PROBLEMA!
=======
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
    }
    
    # Remove headers vazios
    headers = {k: v for k, v in headers.items() if v}
    
    # Método 1: InputStream (via property - PREFERENCIAL)
    if play_item.getProperty('inputstream'):
        header_string = '&'.join([
            f"{k}={urllib.parse.quote(v)}" 
            for k, v in headers.items()
        ])
        play_item.setProperty('inputstream.adaptive.stream_headers', header_string)
        xbmc.log(f"[Player] Headers aplicados via InputStream", xbmc.LOGDEBUG)
        return url
    
    # Método 2: Pipe na URL (fallback para player nativo)
    else:
        if '|' not in url:
            header_string = '&'.join([
                f"{k}={urllib.parse.quote(v)}" 
                for k, v in headers.items()
            ])
            url_with_headers = f"{url}|{header_string}"
            xbmc.log(f"[Player] Headers aplicados via pipe", xbmc.LOGDEBUG)
            return url_with_headers
    
    return url


def _smart_watchdog(url, stream_config):
    """
    Monitora player com detecção inteligente de travamentos
    """
    xbmc.log("[Watchdog] Iniciando monitoramento inteligente", xbmc.LOGINFO)
    
    # Aguarda inicialização
    time.sleep(8)
    
    player = xbmc.Player()
    
    state = {
        'frozen_checks': 0,
        'network_errors': 0,
        'last_time': -1,
        'last_check': time.time(),
        'start_time': time.time(),
        'recovery_attempts': 0,
    }
    
    max_monitoring_time = 600  # 10 minutos de monitoramento ativo
    
    while time.time() - state['start_time'] < max_monitoring_time:
        if not player.isPlaying():
            xbmc.log("[Watchdog] Playback parou naturalmente", xbmc.LOGINFO)
            break
        
        try:
            current_time = player.getTime()
            total_time = player.getTotalTime()
            
            # Verifica se está congelado
            time_delta = abs(current_time - state['last_time'])
            
            if time_delta < 0.5 and current_time > 5:  # Ignorar primeiros 5s
                state['frozen_checks'] += 1
                
                # Verifica se está bufferizando (normal) ou travado
                is_buffering = _check_if_buffering(player, current_time)
                
                if state['frozen_checks'] >= 6 and not is_buffering:  # 30s travado
                    xbmc.log(
                        f"[Watchdog] ⚠ Travamento detectado em {current_time:.1f}s / {total_time:.1f}s",
                        xbmc.LOGWARNING
                    )
                    
                    # Tenta recuperar
                    if state['recovery_attempts'] < 2:
                        if _attempt_recovery(player, current_time):
                            state['frozen_checks'] = 0
                            state['recovery_attempts'] += 1
                            state['last_time'] = -1
                            xbmc.log("[Watchdog] ✓ Stream recuperado", xbmc.LOGINFO)
                            time.sleep(10)  # Aguarda estabilizar
                            continue
                    
                    # Se não recuperou, para
                    xbmc.log("[Watchdog] ✖ Forçando parada do player", xbmc.LOGERROR)
                    player.stop()
                    
                    xbmcgui.Dialog().notification(
                        'Player',
                        'Stream travou e foi parado automaticamente',
                        xbmcgui.NOTIFICATION_WARNING,
                        5000
                    )
                    break
            else:
                # Resetar contadores se o vídeo está progredindo
                state['frozen_checks'] = 0
                state['network_errors'] = 0
            
            state['last_time'] = current_time
            
        except Exception as e:
            state['network_errors'] += 1
            xbmc.log(f"[Watchdog] Erro ao verificar status: {e}", xbmc.LOGDEBUG)
            
            if state['network_errors'] > 10:
                xbmc.log("[Watchdog] Muitos erros consecutivos, abortando", xbmc.LOGERROR)
                break
        
        time.sleep(5)
    
    xbmc.log("[Watchdog] Monitoramento finalizado", xbmc.LOGINFO)


def _check_if_buffering(player, current_time):
    """
    Verifica se o player está bufferizando (normal) ou realmente travado
    """
    try:
        # Se está nos primeiros segundos, provavelmente é buffer inicial
        if current_time < 10:
            return True
        
        # Tenta verificar cache
        cache_info = player.getCachePercentage()
        if cache_info < 100:
            return True
        
        return False
        
    except Exception:
        return False


def _attempt_recovery(player, position):
    """
    Tenta recuperar stream travado
    """
    try:
        xbmc.log(f"[Watchdog] Tentando recuperar stream em {position:.1f}s...", xbmc.LOGINFO)
        
        # Estratégia 1: Seek para trás
        if position > 10:
            player.seekTime(position - 8)
            time.sleep(3)
            
            if player.isPlaying():
                new_time = player.getTime()
                if abs(new_time - (position - 8)) < 5:
                    return True
        
        # Estratégia 2: Pause/Resume
        player.pause()
        time.sleep(1)
        player.pause()
        time.sleep(2)
        
        return player.isPlaying()
        
    except Exception as e:
        xbmc.log(f"[Watchdog] Falha na recuperação: {e}", xbmc.LOGDEBUG)
        return False


def _intelligent_scrobble(item_info, stream_config):
    """
    Scrobble com detecção inteligente de progresso
    """
    xbmc.log("[Trakt Scrobble] Iniciando monitoramento inteligente", xbmc.LOGINFO)
    
    # Tempo de espera baseado no tipo de stream
    max_wait = 60 if stream_config['type'] == 'torrent' else 20
    
    # Aguarda player iniciar
    player = xbmc.Player()
    for i in range(max_wait):
        if player.isPlaying():
            xbmc.log(f"[Trakt Scrobble] Player detectado após {i}s", xbmc.LOGINFO)
            break
        time.sleep(1)
    else:
        xbmc.log("[Trakt Scrobble] Timeout: player não iniciou", xbmc.LOGWARNING)
        return
    
    # Validação de dados
    media_type = item_info.get('media_type')
    tmdb_id = item_info.get('tmdb_id')
    
    if not tmdb_id:
        xbmc.log("[Trakt Scrobble] TMDB ID não encontrado", xbmc.LOGWARNING)
        return
    
    # Sistema de amostragem de posições
    positions = []
    check_interval = 10  # Verifica a cada 10s
    start_monitor = time.time()
    
    try:
        # Aguarda 15s para garantir que começou
        time.sleep(15)
        
        # Monitora enquanto está tocando
        while player.isPlaying():
            try:
                current_pos = player.getTime()
                total_time = player.getTotalTime()
                timestamp = time.time()
                
                positions.append({
                    'position': current_pos,
                    'total': total_time,
                    'timestamp': timestamp
                })
                
                # Log de progresso a cada 5 minutos
                if len(positions) % 30 == 0:
                    progress = (current_pos / total_time * 100) if total_time > 0 else 0
                    xbmc.log(
                        f"[Trakt Scrobble] Progresso: {progress:.1f}% ({current_pos:.0f}s / {total_time:.0f}s)",
                        xbmc.LOGDEBUG
                    )
                
            except Exception as e:
                xbmc.log(f"[Trakt Scrobble] Erro ao capturar tempo: {e}", xbmc.LOGDEBUG)
            
            time.sleep(check_interval)
        
        # Análise final
        if not positions or len(positions) < 2:
            xbmc.log("[Trakt Scrobble] Dados insuficientes para scrobble", xbmc.LOGINFO)
            return
        
        # Calcula métricas
        max_position = max(p['position'] for p in positions)
        avg_total = sum(p['total'] for p in positions) / len(positions)
        watch_duration = positions[-1]['timestamp'] - positions[0]['timestamp']
        
        # Progresso efetivo
        effective_progress = (max_position / avg_total * 100) if avg_total > 60 else 0
        
        xbmc.log(
            f"[Trakt Scrobble] Análise: {effective_progress:.1f}% "
            f"(max: {max_position:.0f}s, total: {avg_total:.0f}s, duração: {watch_duration:.0f}s)",
            xbmc.LOGINFO
        )
        
        # Critérios de scrobble mais flexíveis
        should_scrobble = (
            effective_progress >= 75 or  # Assistiu 75%+
            max_position >= 900 or       # Assistiu 15+ minutos
            (effective_progress >= 50 and watch_duration >= 1800)  # 50%+ em 30+ min
        )
        
        if not should_scrobble:
            xbmc.log(
                f"[Trakt Scrobble] Critérios não atingidos - não enviando "
                f"(progresso: {effective_progress:.1f}%, tempo: {max_position:.0f}s)",
                xbmc.LOGINFO
            )
            return
        
        # Envia para Trakt
        _send_to_trakt(item_info, effective_progress, max_position, avg_total)
        
<<<<<<< HEAD
        from resources.lib.trakt_rating import ask_rating_after_playback
        ask_rating_after_playback(item_info, effective_progress, delay=3)
        
=======
>>>>>>> 927d3c6445ca543ef8b5e72dbdf7c6efafc9b260
    except Exception as e:
        xbmc.log(f"[Trakt Scrobble] Erro crítico: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)


def _send_to_trakt(item_info, progress, watched_time, total_time):
    """
    Envia dados de visualização para o Trakt
    """
    try:
        from resources.lib.trakt_sync import trakt_request
        
        media_type = item_info.get('media_type')
        tmdb_id = item_info.get('tmdb_id')
        watched_at = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
        
        # Monta payload baseado no tipo
        if media_type == 'movie':
            payload = {
                'movies': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'watched_at': watched_at
                }]
            }
            title_display = item_info.get('title', 'Filme')
            
        elif media_type == 'tvshow':
            season = item_info.get('season')
            episode = item_info.get('episode')
            
            if not season or not episode:
                xbmc.log("[Trakt Scrobble] Season/Episode não encontrados", xbmc.LOGWARNING)
                return
            
            payload = {
                'shows': [{
                    'ids': {'tmdb': int(tmdb_id)},
                    'seasons': [{
                        'number': int(season),
                        'episodes': [{
                            'number': int(episode),
                            'watched_at': watched_at
                        }]
                    }]
                }]
            }
            title_display = f"{item_info.get('title', 'Série')} S{season:02d}E{episode:02d}"
            
        else:
            xbmc.log(f"[Trakt Scrobble] Tipo de mídia inválido: {media_type}", xbmc.LOGWARNING)
            return
        
        # Envia para Trakt
        xbmc.log(f"[Trakt Scrobble] Enviando para Trakt: {title_display}", xbmc.LOGINFO)
        xbmc.log(f"[Trakt Scrobble] Payload: {payload}", xbmc.LOGDEBUG)
        
        response = trakt_request('POST', '/sync/history', payload)
        
        if response:
            xbmc.log(
                f"[Trakt Scrobble] ✓ '{title_display}' marcado como assistido "
                f"({progress:.1f}% - {watched_time:.0f}s / {total_time:.0f}s)",
                xbmc.LOGINFO
            )
            
            # Notificação opcional
            if ADDON.getSettingBool('trakt_show_notifications'):
                xbmcgui.Dialog().notification(
                    'Trakt',
                    f"✓ {title_display}",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
        else:
            xbmc.log("[Trakt Scrobble] ✖ Falha ao enviar para Trakt", xbmc.LOGERROR)
            
    except Exception as e:
        xbmc.log(f"[Trakt Scrobble] Erro ao enviar: {e}", xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)


def play_url_with_retry(url, item_info, max_retries=2):
    """
    Wrapper com retry para maior confiabilidade
    """
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                xbmc.log(f"[Player] Tentativa {attempt + 1}/{max_retries + 1}", xbmc.LOGINFO)
                
                xbmcgui.Dialog().notification(
                    'Player',
                    f'Tentando novamente ({attempt + 1}/{max_retries + 1})...',
                    xbmcgui.NOTIFICATION_INFO,
                    2000
                )
                
                time.sleep(3)
            
            success = play_url(url, item_info)
            
            if success:
                return True
            
        except Exception as e:
            xbmc.log(f"[Player] Erro na tentativa {attempt + 1}: {e}", xbmc.LOGERROR)
            
            if attempt == max_retries:
                xbmcgui.Dialog().notification(
                    'Player',
                    f'Falha após {max_retries + 1} tentativas',
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )
                return False
    
    return False