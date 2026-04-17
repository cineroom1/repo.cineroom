# -*- coding: utf-8 -*-
"""
Scraper para AnimesOnlineCC.to - VERSÃO CORRIGIDA v4
Player: Blogger é wrapper do YouTube — resolve via InnerTube API (sem chave).
"""
import re
import json
import xbmc
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote_plus
from .session import USER_AGENT
from .utils import normalize_for_compare
from .scraper_config import get_url


class AnimesOnlineScraper:
    """Scraper para AnimesOnlineCC.to"""

    def __init__(self):
        self.base_url = get_url('animesonline', fallback='https://animesonlinecc.to')
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Referer': self.base_url,
            'DNT': '1'
        }

    # ------------------------------------------------------------------ #
    #  BUSCA
    # ------------------------------------------------------------------ #

    def search_anime(self, title):
        """Busca anime no site"""
        search_attempts = [
            f"{self.base_url}/search/{quote_plus(title)}",
            f"{self.base_url}/?s={quote_plus(title)}",
            f"{self.base_url}/busca/{quote_plus(title)}"
        ]

        for search_url in search_attempts:
            xbmc.log(f"[AnimesOnline-DEBUG] Tentando: {search_url}", xbmc.LOGINFO)
            try:
                response = requests.get(search_url, headers=self.headers,
                                        timeout=15, allow_redirects=True)
                xbmc.log(f"[AnimesOnline-DEBUG] Status: {response.status_code}", xbmc.LOGINFO)
                xbmc.log(f"[AnimesOnline-DEBUG] URL final: {response.url}", xbmc.LOGINFO)

                if response.status_code == 200:
                    html_preview = response.text[:500].replace('\n', ' ').replace('\r', '')
                    xbmc.log(f"[AnimesOnline-DEBUG] HTML preview: {html_preview}", xbmc.LOGDEBUG)

                    if any(k in response.url for k in ("search", "s=", "busca")):
                        return response.text
                    else:
                        xbmc.log(f"[AnimesOnline-DEBUG] Redirecionado para: {response.url}",
                                 xbmc.LOGINFO)
                        return {'type': 'direct', 'url': response.url, 'html': response.text}

            except Exception as e:
                xbmc.log(f"[AnimesOnline-DEBUG] Erro na tentativa {search_url}: {e}",
                         xbmc.LOGERROR)
                continue

        return None

    # ------------------------------------------------------------------ #
    #  PARSE DOS RESULTADOS DE BUSCA
    # ------------------------------------------------------------------ #

    def parse_search_results(self, result, title, season=None):
        """Extrai URLs dos episódios da busca"""
        sources = []

        if isinstance(result, dict) and result.get('type') == 'direct':
            xbmc.log(f"[AnimesOnline] Redirecionamento direto para: {result['url']}", xbmc.LOGINFO)
            sources.append({'url': result['url'], 'title': title, 'type': 'direct'})
            return sources

        html = result if isinstance(result, str) else ''
        if not html:
            return sources

        soup = BeautifulSoup(html, 'html.parser')
        xbmc.log(f"[AnimesOnline-DEBUG] Título da página: "
                 f"{soup.title.string if soup.title else 'N/A'}", xbmc.LOGINFO)

        title_norm = normalize_for_compare(title)
        anime_links = []

        for a in soup.find_all('a', href=True):
            href = a['href']
            match = re.match(r'.*/anime/([^/]+)/?$', href)
            if match and match.group(1) not in ('', 'page'):
                anime_links.append(a)
                xbmc.log(f"[AnimesOnline-DEBUG] Link válido: {href} | "
                         f"Texto: {a.get_text(strip=True)}", xbmc.LOGINFO)

        xbmc.log(f"[AnimesOnline] Links com slug específico: {len(anime_links)}", xbmc.LOGINFO)

        for link in anime_links[:5]:
            anime_url = link['href']
            if not anime_url.startswith('http'):
                anime_url = self.base_url + anime_url

            title_elem = link.find(['h2', 'h3', 'h4', 'strong', 'span']) or link
            result_title = title_elem.get_text(strip=True) if title_elem else ''
            result_norm = normalize_for_compare(result_title)

            slug = anime_url.rstrip('/').split('/')[-1]
            slug_norm = normalize_for_compare(slug.replace('-', ' '))

            xbmc.log(f"[AnimesOnline] Candidato: '{result_title}' | slug='{slug}' -> {anime_url}",
                     xbmc.LOGINFO)

            if (title_norm in result_norm or result_norm in title_norm or
                    title_norm in slug_norm or slug_norm in title_norm):
                sources.append({'url': anime_url, 'title': result_title or slug,
                                'type': 'anime_page'})
                xbmc.log(f"[AnimesOnline] ✓ Match encontrado: {result_title or slug}",
                         xbmc.LOGINFO)

        seen_urls = set()
        unique_sources = []
        for s in sources:
            if s['url'] not in seen_urls:
                seen_urls.add(s['url'])
                unique_sources.append(s)

        return unique_sources

    # ------------------------------------------------------------------ #
    #  EPISÓDIOS
    # ------------------------------------------------------------------ #

    def get_episodes_from_anime_page(self, anime_page, season, episode):
        """Extrai lista de episódios da página do anime"""
        anime_url = anime_page['url']

        try:
            xbmc.log(f"[AnimesOnline] Acessando página do anime: {anime_url}", xbmc.LOGINFO)
            response = requests.get(anime_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')

            xbmc.log(f"[AnimesOnline-DEBUG] Título da página: "
                     f"{soup.title.string if soup.title else 'N/A'}", xbmc.LOGINFO)

            episodes = []

            episode_patterns = [
                ('div.episodios', 'div', 'episodios'),
                ('ul.lista-episodios', 'ul', 'lista-episodios'),
                ('div#episodios', 'div', 'episodios'),
                ('div.episodes', 'div', 'episodes'),
                ('select#episode-select', 'select', None)
            ]

            for pattern_name, tag, class_name in episode_patterns:
                container = (soup.find(tag, class_=class_name) if class_name
                             else soup.find(tag, id=re.compile(r'episod', re.I)))

                if container:
                    xbmc.log(f"[AnimesOnline] Encontrado container: {pattern_name}", xbmc.LOGINFO)

                    if tag == 'select':
                        for opt in container.find_all('option'):
                            ep_num = self._extract_episode_number(opt.get_text())
                            ep_url = opt.get('value', '')
                            if ep_num and ep_url:
                                episodes.append({
                                    'number': ep_num,
                                    'url': ep_url if ep_url.startswith('http')
                                           else self.base_url + ep_url,
                                    'title': opt.get_text()
                                })
                    else:
                        for link in container.find_all('a', href=True):
                            ep_text = link.get_text(strip=True)
                            ep_url = link['href']
                            ep_num = self._extract_episode_number(ep_text)
                            if ep_num:
                                episodes.append({
                                    'number': ep_num,
                                    'url': ep_url if ep_url.startswith('http')
                                           else self.base_url + ep_url,
                                    'title': ep_text
                                })

            if not episodes:
                xbmc.log("[AnimesOnline] Nenhum container específico encontrado, "
                         "procurando em toda a página", xbmc.LOGWARNING)

                for link in soup.find_all('a', href=True):
                    href = link['href']
                    text = link.get_text(strip=True)
                    if ('/episodio/' in href or 'episodio' in text.lower()):
                        ep_num = (self._extract_episode_number(href)
                                  or self._extract_episode_number(text))
                        if ep_num:
                            episodes.append({
                                'number': ep_num,
                                'url': href if href.startswith('http') else self.base_url + href,
                                'title': text
                            })

            seen = set()
            unique_episodes = []
            for ep in episodes:
                if ep['number'] not in seen:
                    seen.add(ep['number'])
                    unique_episodes.append(ep)

            unique_episodes.sort(key=lambda x: x['number'])
            xbmc.log(f"[AnimesOnline] Total de episódios encontrados: {len(unique_episodes)}",
                     xbmc.LOGINFO)

            target_eps = [ep for ep in unique_episodes if ep['number'] == int(episode)]

            if target_eps:
                xbmc.log(f"[AnimesOnline] Episódio {episode} encontrado!", xbmc.LOGINFO)
            else:
                xbmc.log(f"[AnimesOnline] Episódio {episode} NÃO encontrado. "
                         f"Disponíveis: {[ep['number'] for ep in unique_episodes[:10]]}",
                         xbmc.LOGWARNING)

            return target_eps

        except Exception as e:
            xbmc.log(f"[AnimesOnline] Erro ao extrair episódios: {e}", xbmc.LOGERROR)
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
            return []

    def _extract_episode_number(self, text):
        """Extrai número do episódio de um texto"""
        if not text:
            return None
        text = str(text)
        patterns = [
            r'epis[óo]dio\s*(\d+)',
            r'episodio-(\d+)',
            r'ep\.?\s*(\d+)',
            r'#(\d+)',
            r'(\d+)[º°]?\s*epis[óo]dio',
            r'(\d+)\s*$',
            r'^\s*(\d+)',
            r'[^\d](\d+)[^\d]'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    return int(matches[0])
                except Exception:
                    pass
        return None

    # ------------------------------------------------------------------ #
    #  EXTRAÇÃO DE VÍDEO
    # ------------------------------------------------------------------ #

    def extract_video_url(self, episode_url):
        """Extrai URL real do vídeo da página do episódio"""
        try:
            xbmc.log(f"[AnimesOnline] Acessando episódio: {episode_url}", xbmc.LOGINFO)

            response = requests.get(episode_url, headers=self.headers,
                                    timeout=15, allow_redirects=True)
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            xbmc.log(f"[AnimesOnline-DEBUG] Página do episódio: "
                     f"{soup.title.string if soup.title else 'N/A'}", xbmc.LOGINFO)

            # Método 1: Blogger iframe
            iframe_patterns = [
                r'<iframe[^>]*\bsrc=["\']([^"\']*blogger[^"\']*)["\']',
                r'<iframe[^>]*\bsrc=["\']([^"\']*googlevideo[^"\']*)["\']',
                r'<iframe[^>]*\bsrc=["\']([^"\']*youtube[^"\']*embed[^"\']*)["\']'
            ]

            for pattern in iframe_patterns:
                m = re.search(pattern, html, re.IGNORECASE)
                if m:
                    embedded_url = m.group(1)
                    xbmc.log(f"[AnimesOnline] Iframe encontrado: {embedded_url}", xbmc.LOGINFO)

                    if 'blogger' in embedded_url:
                        video_url = self._extract_from_blogger(embedded_url)
                        if video_url:
                            return video_url
                    else:
                        return embedded_url

            # Método 2: googlevideo direto no HTML
            gv_pattern = r'https?://[^"\'<\s]*googlevideo\.com[^"\'<\s]*'
            gv_match = re.search(gv_pattern, html)
            if gv_match:
                xbmc.log("[AnimesOnline] googlevideo direto no HTML", xbmc.LOGINFO)
                return gv_match.group(0)

            # Método 3: Scripts
            for script in soup.find_all('script'):
                if script.string:
                    m = re.search(gv_pattern, script.string)
                    if m:
                        xbmc.log("[AnimesOnline] googlevideo em script", xbmc.LOGINFO)
                        return m.group(0)

            xbmc.log("[AnimesOnline] Nenhuma URL de vídeo encontrada na página do episódio",
                     xbmc.LOGWARNING)
            return None

        except Exception as e:
            xbmc.log(f"[AnimesOnline] Erro ao extrair vídeo: {e}", xbmc.LOGERROR)
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
            return None

    # ------------------------------------------------------------------ #
    #  BLOGGER → YOUTUBE INNERTUBE
    # ------------------------------------------------------------------ #

    def _extract_from_blogger(self, blogger_url):
        """
        O Blogger é apenas um wrapper para YouTube embed.
        Extrai o docid (YouTube video ID) e usa a InnerTube API para obter o stream.
        """
        try:
            token_match = re.search(r'token=([^&\s]+)', blogger_url)
            if not token_match:
                xbmc.log('[AnimesOnline] Token não encontrado na URL do Blogger', xbmc.LOGWARNING)
                return None

            token = token_match.group(1)
            xbmc.log(f'[AnimesOnline] Token Blogger: {token[:40]}...', xbmc.LOGDEBUG)

            video_id = self._get_docid_from_blogger(token)
            if not video_id:
                xbmc.log('[AnimesOnline] docid não encontrado', xbmc.LOGWARNING)
                return None

            xbmc.log(f'[AnimesOnline] YouTube video ID: {video_id}', xbmc.LOGDEBUG)
            return self._innertube_get_stream(video_id)

        except Exception as e:
            xbmc.log(f'[AnimesOnline] Erro em _extract_from_blogger: {e}', xbmc.LOGERROR)
            return None

    def _get_docid_from_blogger(self, token):
        blogger_url = f'https://www.blogger.com/video.g?token={token}'

        try:
            r = requests.get(blogger_url, headers={
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.base_url,
            }, timeout=15, allow_redirects=True)

            html = r.text

            # Extrai o bloco TSDtV completo
            tsdtv = re.search(r'"TSDtV"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
            if tsdtv:
                raw = tsdtv.group(1)
                xbmc.log(f'[AnimesOnline-Blogger] TSDtV raw: {raw[:300]}', xbmc.LOGINFO)

                # Procura sequência hex de 16 chars dentro do TSDtV
                m = re.search(r'([0-9a-f]{16})', raw)
                if m:
                    xbmc.log(f'[AnimesOnline-Blogger] docid via TSDtV hex16: {m.group(1)}', xbmc.LOGINFO)
                    return m.group(1)

            # Fallback: qualquer hex16 no HTML inteiro
            m = re.search(r'\b([0-9a-f]{16})\b', html)
            if m:
                xbmc.log(f'[AnimesOnline-Blogger] docid via hex16 global: {m.group(1)}', xbmc.LOGINFO)
                return m.group(1)

            xbmc.log(f'[AnimesOnline-Blogger] HTML completo (primeiros 1500): {html[:1500].replace(chr(10), " ")}', xbmc.LOGINFO)

        except Exception as e:
            xbmc.log(f'[AnimesOnline] Erro ao obter docid: {e}', xbmc.LOGWARNING)

        return None

    def _innertube_get_stream(self, video_id):
        """
        Usa a InnerTube API interna do YouTube (sem chave) para obter stream MP4.
        Tenta cliente ANDROID primeiro (retorna MP4 direto), depois WEB_EMBEDDED como fallback.
        """
        clients = [
            {
                'name': 'ANDROID',
                'payload': {
                    'videoId': video_id,
                    'context': {
                        'client': {
                            'clientName': 'ANDROID',
                            'clientVersion': '19.09.37',
                            'androidSdkVersion': 30,
                            'hl': 'pt',
                            'gl': 'BR',
                        }
                    }
                },
                'headers': {
                    'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 11)',
                    'Content-Type': 'application/json',
                    'X-YouTube-Client-Name': '3',
                    'X-YouTube-Client-Version': '19.09.37',
                }
            },
            {
                'name': 'WEB_EMBEDDED',
                'payload': {
                    'videoId': video_id,
                    'context': {
                        'client': {
                            'clientName': 'WEB_EMBEDDED_PLAYER',
                            'clientVersion': '1.20260315.08.00',
                            'hl': 'pt',
                            'gl': 'BR',
                        }
                    }
                },
                'headers': {
                    'User-Agent': self.headers['User-Agent'],
                    'Content-Type': 'application/json',
                    'X-YouTube-Client-Name': '56',
                    'X-YouTube-Client-Version': '1.20260315.08.00',
                    'Referer': 'https://www.blogger.com/',
                    'Origin': 'https://www.blogger.com',
                }
            },
        ]

        for client in clients:
            try:
                xbmc.log(f'[AnimesOnline] InnerTube tentando cliente: {client["name"]}',
                         xbmc.LOGDEBUG)
                r = requests.post(
                    'https://www.youtube.com/youtubei/v1/player',
                    json=client['payload'],
                    headers=client['headers'],
                    timeout=15
                )
                data = r.json()

                streaming = data.get('streamingData', {})
                formats = streaming.get('formats', []) + streaming.get('adaptiveFormats', [])

                if not formats:
                    xbmc.log(f'[AnimesOnline] InnerTube {client["name"]}: sem formats',
                             xbmc.LOGDEBUG)
                    continue

                # Prefere 22 (720p), 59 (480p), 18 (360p), 43 (360p webm)
                preferred_itags = [22, 59, 18, 43]
                chosen = None
                for itag in preferred_itags:
                    for f in formats:
                        if f.get('itag') == itag and f.get('url'):
                            chosen = f
                            break
                    if chosen:
                        break

                # Fallback: primeiro formato com URL direta e vídeo
                if not chosen:
                    for f in formats:
                        if f.get('url') and 'video' in f.get('mimeType', ''):
                            chosen = f
                            break

                if chosen:
                    stream_url = chosen['url']
                    quality = self._guess_quality_from_url(stream_url)
                    xbmc.log(
                        f'[AnimesOnline] ✓ Stream via InnerTube {client["name"]}: '
                        f'{quality} itag={chosen.get("itag")}',
                        xbmc.LOGINFO
                    )
                    return stream_url

            except Exception as e:
                xbmc.log(f'[AnimesOnline] InnerTube {client["name"]} erro: {e}', xbmc.LOGWARNING)
                continue

        xbmc.log(f'[AnimesOnline] InnerTube: nenhum cliente retornou stream para {video_id}',
                 xbmc.LOGWARNING)
        return None

    # ------------------------------------------------------------------ #
    #  SCRAPE PRINCIPAL
    # ------------------------------------------------------------------ #

    def scrape(self, provider_url, item_data, season=None, episode=None):
        """Método principal do scraper"""
        title = item_data.get('title', '')
        media_type = item_data.get('media_type', '')

        xbmc.log(f"[AnimesOnline] Iniciando scrape: {title} S{season}E{episode}", xbmc.LOGINFO)

        if media_type != 'tvshow' or season is None or episode is None:
            xbmc.log(f"[AnimesOnline] Tipo inválido: {media_type}", xbmc.LOGWARNING)
            return []

        result = self.search_anime(title)
        if not result:
            xbmc.log("[AnimesOnline] Nenhum resultado na busca", xbmc.LOGWARNING)
            return []

        anime_pages = self.parse_search_results(result, title, season)

        if not anime_pages:
            xbmc.log("[AnimesOnline] Nenhuma página de anime encontrada", xbmc.LOGWARNING)
            return []

        xbmc.log(f"[AnimesOnline] Encontradas {len(anime_pages)} páginas de anime", xbmc.LOGINFO)

        sources = []

        for anime_page in anime_pages:
            episodes = self.get_episodes_from_anime_page(anime_page, season, episode)

            if not episodes:
                continue

            xbmc.log(f"[AnimesOnline] {len(episodes)} episódios encontrados na página",
                     xbmc.LOGINFO)

            for ep in episodes:
                video_url = self.extract_video_url(ep['url'])

                if video_url:
                    quality = self._guess_quality_from_url(video_url)
                    sources.append({
                        'url': video_url,
                        'quality': quality,
                        'type': 'Direto',
                        'provider': 'AnimesOnline',
                        'release_title': f"{title} S{int(season):02d}E{int(episode):02d}",
                        'label': f"AnimesOnline: {quality} | Episódio {episode}",
                        'size': 'N/A',
                        'peers': 0,
                        'seeders': 0
                    })
                    xbmc.log(f"[AnimesOnline] ✓ Fonte encontrada: {quality}", xbmc.LOGINFO)
                    break

            if sources:
                break

        xbmc.log(f"[AnimesOnline] Total de fontes: {len(sources)}", xbmc.LOGINFO)
        return sources

    def _guess_quality_from_url(self, url):
        """Tenta adivinhar qualidade pela URL"""
        url_lower = url.lower()
        if 'itag=37' in url_lower or 'itag=22' in url_lower or '1080' in url_lower:
            return '1080p'
        elif 'itag=59' in url_lower or '480' in url_lower:
            return '480p'
        elif 'itag=18' in url_lower or 'itag=43' in url_lower or '360' in url_lower:
            return '360p'
        return 'HD'


# Função de compatibilidade
def scrape(provider_url, item_data, season=None, episode=None):
    scraper = AnimesOnlineScraper()
    return scraper.scrape(provider_url, item_data, season, episode)