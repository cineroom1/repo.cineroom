# -*- coding: utf-8 -*-

import sys
import json
import xbmc
import xbmcgui
import xbmcaddon
import time
from .processors import process_single_stream
from ..resolver import CineroomResolverWindow
from ..resolver import CineroomSearchWindow

ADDON = xbmcaddon.Addon()

_BURST_MIN_VERSION = "1.0.0"

_Q_MAP = {'4K': 4, '2160P': 4, '1080P': 3, '720P': 2, '480P': 1}
_LANG_ANY = ('', 'QUALQUER', 'IGUAL AO AUTOPLAY')
_TYPE_DIRECT  = ('DIRECT', 'HTTP', 'HTTPS', 'HLS', 'DASH')
_TYPE_TORRENT = ('TORRENT', 'MAGNET')


def _source_type(source):
    """
    Retorna 'torrent' ou 'direct' baseado no campo 'type' ou na URL.
    """
    t = (source.get('type') or '').upper()
    if t in _TYPE_TORRENT:
        return 'torrent'
    if t in _TYPE_DIRECT:
        return 'direct'
    url = (source.get('url') or '').lower()
    if url.startswith('magnet:') or url.endswith('.torrent'):
        return 'torrent'
    return 'direct'


def _get_lang_pref(setting_key):
    """
    Lê a setting de idioma e devolve o código interno (PT-BR, DUAL, LEG)
    ou '' se for "Qualquer" / "Igual ao Autoplay" / vazio.
    """
    raw = ADDON.getSetting(setting_key).strip().upper()
    return '' if raw in _LANG_ANY else raw


def _lang_score(source_lang, pref_language):
    """
    Calcula score de idioma (menor = melhor match).
      0 → match perfeito
      1 → match parcial (PT-BR↔DUAL)
      2 → não bate
    """
    if not pref_language:
        return 0
    src = source_lang.upper() if source_lang else ''
    if src == pref_language:
        return 0
    if pref_language == 'PT-BR' and src == 'DUAL':
        return 1
    if pref_language == 'DUAL' and src == 'PT-BR':
        return 1
    return 2


def _type_score(source, pref_type):
    """
    Calcula score de tipo de fonte (menor = melhor).
      0 → match exato  |  1 → fallback  |  ignorado se pref_type=''
    """
    if not pref_type:
        return 0
    return 0 if _source_type(source) == pref_type else 1


def _pick_best(sources, pref_quality, pref_language, pref_source_type=''):
    """
    Escolhe a melhor fonte da lista.
    Critério (menor = melhor):
      1. Tipo     — 0 match (direct/torrent), 1 fallback
      2. Idioma   — 0 exato, 1 parcial (PT-BR↔DUAL), 2 não bate
      3. Qualidade — distância ao alvo
      4. Seeders  — maior é melhor (negativo para inverter)
    """
    def score(s):
        return (
            _type_score(s, pref_source_type),
            _lang_score(s.get('languages', ''), pref_language),
            abs(s['q_score'] - _Q_MAP.get(pref_quality, 3)),
            -s['s_score']
        )

    return min(sources, key=score)


def _fetch_local_streams(item_data):
    
    streams = item_data.get('streams') or []
    if isinstance(streams, str):
        try:
            streams = json.loads(streams)
        except Exception:
            streams = []

    if streams:
        return streams

    # 2. Busca no banco pelo tmdb_id
    tmdb_id = item_data.get('tmdb_id')
    if not tmdb_id:
        return []

    try:
        from ..db import db
        media_type = item_data.get('media_type')
        local = (
            db.get_movie_by_id(tmdb_id)
            if media_type == 'movie'
            else db.get_tvshow_by_id(tmdb_id)
        )
        if not local:
            return []

        streams = local.get('streams') or []
        if isinstance(streams, str):
            try:
                streams = json.loads(streams)
            except Exception:
                streams = []

        return streams if isinstance(streams, list) else []

    except Exception as e:
        xbmc.log(f"[Sources] Erro ao buscar streams locais: {e}", xbmc.LOGERROR)
        return []


def _get_active_profile_id():
    """Retorna o profile_id ativo se VIP, ou None para free."""
    try:
        from ..vip_auth import is_session_valid
        if is_session_valid():
            from ..profile_manager import ProfileManager
            profile = ProfileManager().get_current_profile()
            return profile.get('id') if profile else None
    except Exception:
        pass
    return None


def find_and_play_sources(item_data, season=None, episode=None,
                          force_select=False, is_autonext=False):
    
    xbmc.log(f'[Sources] find_and_play_sources chamado tmdb={item_data.get("tmdb_id")}', xbmc.LOGINFO)

    if not item_data.get('media_type'):
        xbmcgui.Dialog().ok("Erro", "Dados insuficientes.")
        return

    # ── Verifica VIP ──────────────────────────────────────────────────────────
    try:
        from ..vip_auth import is_session_valid
        is_vip = is_session_valid()
    except Exception:
        is_vip = False

    # ── Retomada rápida (crash / fechamento inesperado) ───────────────────────
    # Só oferece retomada se não for autonext e não for seleção forçada,
    # pois nesses casos o usuário já está escolhendo conscientemente.
    if not force_select and not is_autonext:
        try:
            from ..db.history_db import history_db
            profile_id = _get_active_profile_id()
            last_url = history_db.get_last_stream_url(
                tmdb_id    = item_data.get('tmdb_id'),
                media_type = item_data.get('media_type'),
                profile_id = profile_id,
                season     = item_data.get('season'),
                episode    = item_data.get('episode'),
            )
            if last_url:
                resp = xbmcgui.Dialog().yesno(
                    "Retomar reprodução",
                    "Deseja continuar de onde parou?\n[COLOR grey](usando a última fonte)[/COLOR]"
                )
                if resp:
                    xbmc.log(f'[Sources] Retomada rápida: {last_url[:80]}', xbmc.LOGINFO)
                    resolver = CineroomResolverWindow(
                        "resolver_window.xml",
                        ADDON.getAddonInfo('path'),
                        source_url=last_url,
                        item_data=item_data,
                        handle=int(sys.argv[1])
                    )
                    resolver.doModal()
                    return
        except Exception as e:
            xbmc.log(f'[Sources] Erro ao verificar last_stream_url: {e}', xbmc.LOGWARNING)

    # ── Busca streams VIP remotos ANTES do Burst ──────────────────────────────
    final_list = []
    seen_urls  = set()

    if is_vip:
        try:
            from ..vip_auth import fetch_vip_streams_cached
            remote_streams = fetch_vip_streams_cached(
                tmdb_id    = item_data.get('tmdb_id'),
                media_type = item_data.get('media_type', 'movie'),
            )
            if remote_streams:
                for s in remote_streams:
                    p = process_single_stream(s, is_local=True, item_data=item_data)
                    if p:
                        p['p_priority'] = 0
                        final_list.append(p)
                        seen_urls.add(p['url'])
                xbmc.log(f'[Sources] {len(remote_streams)} stream(s) VIP remoto(s) adicionado(s).', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[Sources] Erro streams VIP remotos: {e}', xbmc.LOGWARNING)

    # ── SearchWindow custom (XML) ─────────────────────────────────────────────
    pDialog    = None
    start_time = time.time()

    def _on_progress(completed, total, provider_name):
        nonlocal pDialog

        if not pDialog and time.time() - start_time > 0.7:
            addon_path = ADDON.getAddonInfo('path')
            pDialog = CineroomSearchWindow("Searchwindow.xml", addon_path, "Default", "1080i")
            pDialog.set_art(
                fanart=item_data.get('backdrop') or item_data.get('fanart') or '',
                clearlogo=item_data.get('clearlogo') or '',
                title=item_data.get('title') or item_data.get('name') or 'Buscando fontes'
            )
            pDialog.show()

        if pDialog:
            try:
                pDialog.update_progress(completed, total, provider_name)
            except Exception:
                pass

    # ── Busca (FREE vs VIP) ───────────────────────────────────────────────────
    provider_results = {}

    try:
        if is_vip:
            try:
                import script.cineroom.burst as scrapers
            except ImportError:
                scrapers = None

            if scrapers and hasattr(scrapers, 'scrape_all_sources'):
                provider_results = scrapers.scrape_all_sources(
                    item_data=item_data,
                    progress_callback=_on_progress
                )
            else:
                xbmcgui.Dialog().ok(
                    "Burst Necessário",
                    "O addon [B]Cineroom Burst[/B] não está instalado.\n\n"
                    f"VIP requer [B]Burst {_BURST_MIN_VERSION}+[/B]"
                )
                return
        else:
            try:
                from ..scrapers.stremio_custom import scrape_all_stremio, has_providers_configured
                if has_providers_configured():
                    all_sources = scrape_all_stremio(item_data, _on_progress)
                    provider_results = {'Custom': {'sources': all_sources, 'priority': 1}}
                else:
                    provider_results = {}
            except ImportError as e:
                xbmc.log(f"[Cineroom] Erro ao importar stremio_custom: {e}", xbmc.LOGERROR)
                provider_results = {}
    finally:
        if pDialog:
            try:
                pDialog.close()
            except Exception:
                pass

    
    if is_vip:
        local_streams = _fetch_local_streams(item_data)
        for s in local_streams:
            p = process_single_stream(s, is_local=True, item_data=item_data)
            if p and p['url'] not in seen_urls:
                p['p_priority'] = 0
                final_list.append(p)
                seen_urls.add(p['url'])

        if local_streams:
            xbmc.log(f"[Sources] {len(local_streams)} stream(s) local(is) encontrado(s).", xbmc.LOGINFO)

    
    for provider_name, result in provider_results.items():
        priority = result.get('priority', 999)
        for s in result.get('sources', []):
            real_provider = s.get('provider') or provider_name
            p = process_single_stream(s, False, real_provider, priority, item_data)
            if p and p['url'] not in seen_urls:
                final_list.append(p)
                seen_urls.add(p['url'])

    if not final_list:
        if not is_vip:
            from ..scrapers.stremio_custom import has_providers_configured
            if not has_providers_configured():
                msg = "Nenhum provider configurado.\n\nAdicione um em [B]Configurações → Addons Stremio[/B] ou adquira o [COLOR gold][B]PLUS[/B][/COLOR] e acesse fontes sem configurar nada."
            else:
                msg = "Nenhuma fonte encontrada.\n\nTente outro provider ou adquira o [COLOR gold][B]PLUS[/B][/COLOR] para acessar mais fontes automaticamente."
        else:
            msg = "Nenhuma fonte encontrada."
        xbmcgui.Dialog().ok("Sem fontes", msg)
        return

    # ── Filtro de categoria 4K ────────────────────────────────────────────────
    if item_data.get('quality_filter') == '4k':
        filtered = [s for s in final_list if s['q_score'] == 4]
        if filtered:
            final_list = filtered

    # Ordenação: p_priority=0 (local/remoto) sempre antes de p_priority=1+ (scrapers)
    final_list.sort(key=lambda x: (x['p_priority'], -x['q_score'], -x['s_score']))

    # ── Decide modo de reprodução ─────────────────────────────────────────────
    url_escolhida = None

    if not force_select:
        pref_quality = ADDON.getSetting('autoplay.quality').strip().upper() or '1080P'

        if is_autonext:
            # Próximo episódio — sempre escolhe automaticamente, sem depender do autoplay
            # Usa preferências do autonext se configuradas, senão herda do autoplay
            pref_lang = _get_lang_pref('autonext.language')
            if not pref_lang:
                pref_lang = _get_lang_pref('autoplay.language')

            pref_type = ADDON.getSetting('autonext.source_type').strip().lower()
            if pref_type in ('', 'igual ao autoplay'):
                pref_type = ADDON.getSetting('autoplay.source_type').strip().lower()

            melhor        = _pick_best(final_list, pref_quality, pref_lang, pref_type)
            url_escolhida = melhor['url']
            xbmc.log(
                f"[Sources] Autonext: {melhor['quality_label']} "
                f"{melhor['languages']} {_source_type(melhor)} — {melhor['provider']} "
                f"(lang={pref_lang or 'qualquer'}, type={pref_type or 'qualquer'})",
                xbmc.LOGINFO
            )

        elif ADDON.getSettingBool('playback.autoplay'):
            # Clique manual com autoplay ativo
            pref_lang = _get_lang_pref('autoplay.language')
            pref_type = ADDON.getSetting('autoplay.source_type').strip().lower()

            melhor        = _pick_best(final_list, pref_quality, pref_lang, pref_type)
            url_escolhida = melhor['url']
            xbmc.log(
                f"[Sources] Autoplay: {melhor['quality_label']} "
                f"{melhor['languages']} {_source_type(melhor)} — {melhor['provider']} "
                f"(lang={pref_lang or 'qualquer'}, type={pref_type or 'qualquer'})",
                xbmc.LOGINFO
            )

    # Nenhum autoplay ativo → abre tela de seleção
    if url_escolhida is None:
        try:
            from resources.lib.dialog.dialogs import DialogSelecaoFontes
            dialog = DialogSelecaoFontes(
                'dialog_cineroom_fullscreen.xml',
                ADDON.getAddonInfo('path'),
                fontes=final_list,
                item_data=item_data
            )
            dialog.doModal()
            url_escolhida = dialog.escolha
            del dialog
        except Exception:
            labels = [
                f"{s['quality_label']} | {s['seeders_label']} | {s['size']} | {s['provider']}"
                for s in final_list
            ]
            sel = xbmcgui.Dialog().select(
                f"Fontes: {final_list[0]['display_title']}", labels
            )
            if sel >= 0:
                url_escolhida = final_list[sel]['url']

    # ── Resolver ──────────────────────────────────────────────────────────────
    if url_escolhida:
        # Injeta o languages da fonte escolhida no item_data para que o player
        # consiga filtrar legendas corretamente (ex: só exibir dialog em LEG)
        fonte_escolhida = next((s for s in final_list if s['url'] == url_escolhida), None)
        if fonte_escolhida:
            item_data['languages']     = fonte_escolhida.get('languages', '')
            item_data['manifest_type'] = fonte_escolhida.get('manifest_type', '')
            item_data['stream_headers'] = fonte_escolhida.get('headers', '')
            xbmc.log(
                f"[Sources] languages={item_data['languages']} manifest_type={item_data['manifest_type']}",
                xbmc.LOGINFO
            )

        # ── Salva progresso inicial (last_stream_url só será salvo pelo player
        # após confirmar que o stream abriu com sucesso — evita cachear URL expirada) ──
        try:
            from ..db.history_db import history_db
            profile_id = _get_active_profile_id()
            history_db.add_to_history(
                tmdb_id    = item_data.get('tmdb_id'),
                media_type = item_data.get('media_type'),
                profile_id = profile_id,
                season     = item_data.get('season'),
                episode    = item_data.get('episode'),
                progress   = item_data.get('progress', 0.0),
            )
        except Exception as e:
            xbmc.log(f'[Sources] Erro ao salvar history: {e}', xbmc.LOGWARNING)

        # Injeta a URL escolhida no item_data para o player confirmar e salvar após 2%
        item_data['_pending_stream_url'] = url_escolhida

        resolver = CineroomResolverWindow(
            "resolver_window.xml",
            ADDON.getAddonInfo('path'),
            source_url=url_escolhida,
            item_data=item_data,
            handle=int(sys.argv[1])
        )
        resolver.doModal()