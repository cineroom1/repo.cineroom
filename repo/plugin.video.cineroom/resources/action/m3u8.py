import os
import re
import urllib.parse
import urllib.request
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import sys
import json
import traceback
import unicodedata
import xbmcaddon


HANDLE = int(sys.argv[1])

ADDON_ID = xbmcaddon.Addon().getAddonInfo('id')
FAVORITES_FILE = xbmcvfs.translatePath(f"special://userdata/addon_data/{ADDON_ID}/favorites.json")

if not os.path.exists(ADDON_DATA_PATH):
    os.makedirs(ADDON_DATA_PATH)

CACHE_FILE = os.path.join(ADDON_DATA_PATH, 'grupos.json')  # Mudando para JSON
grupos = {}  # Variável global


def search_canais():
    carregar_grupos()

    teclado = xbmcgui.Dialog().input("Pesquisar Canal", type=xbmcgui.INPUT_ALPHANUM)
    if not teclado:
        # Volta para a lista principal se o usuário cancelar a busca
        # Ajuste: Apenas retorna da função para evitar potencial loop
        return

    termo_busca = sanitize_string(teclado.lower())
    resultados = []

    for grupo, canais in grupos.items():
        for canal in canais:
            titulo = sanitize_string(canal.get('titulo', '').lower())
            if termo_busca in titulo:
                resultados.append(canal)

    if not resultados:
        xbmcgui.Dialog().notification("Pesquisa", "Nenhum canal encontrado", xbmcgui.NOTIFICATION_INFO)
        return

    xbmcplugin.setContent(HANDLE, 'tvchannels')
    for canal in resultados:
        item = xbmcgui.ListItem(label=canal['titulo'])
        if canal.get('logo'):
            item.setArt({'thumb': canal['logo'], 'icon': canal['logo']})
        item.setInfo('video', {'title': canal['titulo'], 'genre': canal.get('grupo', '')})

        play_url = f"{sys.argv[0]}?action=play_channel&channel_url={urllib.parse.quote_plus(canal['url'])}&channel_name={urllib.parse.quote_plus(canal['titulo'])}"

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=play_url,
            listitem=item,
            isFolder=False
        )

    xbmcplugin.endOfDirectory(HANDLE)


def carregar_m3u8(url):
    """Baixa e retorna o conteúdo do arquivo M3U8."""
    xbmc.log(f"[DEBUG] Tentando carregar M3U8 de: {url}", xbmc.LOGINFO)
    try:
        with urllib.request.urlopen(url) as response:
            data = response.read().decode("utf-8")
            xbmc.log(f"[DEBUG] Tamanho do M3U8 recebido: {len(data)} caracteres", xbmc.LOGINFO)
            return data
    except Exception as e:
        xbmc.log(f"[ERRO] Falha ao carregar M3U8: {str(e)}", xbmc.LOGERROR)
        return None


def sanitize_string(text):
    """Remove símbolos especiais e normaliza o texto"""
    if not text:
        return ""
    
    # Remove caracteres de controle e símbolos problemáticos
    cleaned = re.sub(r'[\^~³²´`¨§ªº°¢£¬×÷¦]', '', text)
    
    # Normaliza caracteres Unicode (transforma ç em c, á em a, etc)
    normalized = unicodedata.normalize('NFKD', cleaned)
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    
    return ascii_text.strip()


def parse_m3u8(m3u8_content):
    """Parser alternativo com tratamento de erros linha por linha"""
    xbmc.log(f"[DEBUG] Conteúdo problemático:\n{m3u8_content[140:160]}", xbmc.LOGDEBUG)
    from ast import literal_eval
    
    grupos = {}
    buffer = ""
    canal_atual = {}
    
    for linha in m3u8_content.splitlines():
        try:
            linha = linha.strip()
            if not linha:
                continue
                
            if linha.startswith("#EXTINF"):
                # Técnica de parsing alternativa
                parts = linha.split(',', 1)
                if len(parts) == 2:
                    atributos, titulo = parts
                    canal_atual = {
                        "titulo": titulo.strip(),
                        "grupo": "Sem Grupo",
                        "logo": ""
                    }
                    
                    # Extração segura de atributos
                    for attr in ['group-title', 'tvg-logo']:
                        match = re.search(f'{attr}="([^"]*)"', atributos)
                        if match:
                            canal_atual["grupo" if attr == "group-title" else "logo"] = match.group(1)
                            
            elif linha.startswith(('http', 'rtmp', 'rtsp')):
                if canal_atual:
                    canal_atual["url"] = linha
                    grupo = canal_atual["grupo"]
                    
                    if grupo not in grupos:
                        grupos[grupo] = []
                    grupos[grupo].append(canal_atual)
                    
                canal_atual = {}
                
        except Exception as e:
            xbmc.log(f"[ERRO IGNORADO] Linha: {linha[:100]}... | Erro: {str(e)}", xbmc.LOGERROR)
            continue
    
    return grupos



def is_valid_url(url):
    """Verificação robusta de URL com logging"""
    try:
        if not url or not isinstance(url, str):
            xbmc.log("[DEBUG URL] URL vazia ou inválida", xbmc.LOGDEBUG)
            return False
            
        # Verifica caracteres problemáticos
        if re.search(r'[(){}<>\[\]]', url):
            xbmc.log(f"[DEBUG URL WARN] URL contém caracteres especiais: {url[:200]}", xbmc.LOGWARNING)
            
        # Verificação básica de formato
        regex = re.compile(
            r'^(https?|ftp)://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S*)$', re.IGNORECASE)
            
        is_valid = bool(re.match(regex, url))
        xbmc.log(f"[DEBUG URL] URL {'válida' if is_valid else 'inválida'}: {url[:200]}...", xbmc.LOGDEBUG)
        return is_valid
        
    except Exception as e:
        xbmc.log(f"[ERRO URL] Erro ao validar URL: {str(e)}", xbmc.LOGERROR)
        return False

def parse_extinf_line(line):
    """Extrai informações do canal da linha EXTINF."""
    result = {'title': '', 'logo': '', 'group': ''}
    
    try:
        parts = line.split(',', 1)
        if len(parts) < 2:
            return result

        attributes_part, title = parts[0], parts[1].strip()
        result['title'] = title

        match_logo = re.search(r'tvg-logo="([^"]+)"', attributes_part)
        match_group = re.search(r'group-title="([^"]+)"', attributes_part)

        if match_logo:
            result['logo'] = match_logo.group(1)
        if match_group:
            result['group'] = match_group.group(1)

    except Exception as e:
        xbmc.log(f"Erro ao processar linha EXTINF: {str(e)}", xbmc.LOGERROR)

    return result

def load_m3u_file(filepath):
    """Carrega um arquivo M3U8 local e retorna os canais agrupados."""
    if not os.path.exists(filepath):
        xbmc.log(f"Arquivo M3U8 não encontrado: {filepath}", xbmc.LOGERROR)
        return

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('#EXTINF:'):
                channel_info = parse_extinf_line(line)
                if channel_info and i+1 < len(lines):
                    stream_url = lines[i+1].strip()
                    if is_valid_url(stream_url):
                        grupo = channel_info['group'] if channel_info['group'] else 'SEM GRUPO'
                        if grupo not in grupos:
                            grupos[grupo] = []
                        grupos[grupo].append({
                            'title': channel_info['title'],
                            'logo': channel_info['logo'],
                            'url': stream_url
                        })
                        i += 1  # Pula a URL
            i += 1

    except Exception as e:
        xbmc.log(f"Erro ao carregar arquivo M3U8: {str(e)}", xbmc.LOGERROR)

def list_canais(url='', force_refresh=False):
    if not url:
        xbmcgui.Dialog().notification("Erro", "URL da playlist não especificada", xbmcgui.NOTIFICATION_ERROR)
        xbmc.log("Erro: URL não especificada para refresh", xbmc.LOGERROR)
        return
    global grupos
    
    # Se não tiver URL, tenta obter a padrão
    if not url:
        url = get_default_playlist_url()
        if not url:
            xbmcgui.Dialog().notification("Erro", "URL da playlist não configurada", xbmcgui.NOTIFICATION_ERROR)
            return

    # Forçar atualização se necessário
    if force_refresh:
        xbmcgui.Dialog().notification("Atualizando", "Carregando nova lista de canais...", xbmcgui.NOTIFICATION_INFO)
        grupos = {}
        if os.path.exists(CACHE_FILE):
            try:
                os.remove(CACHE_FILE)
                xbmc.log("[INFO] Cache removido para atualização", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"[ERRO] Falha ao remover cache: {str(e)}", xbmc.LOGERROR)
    
    # Tenta carregar do cache primeiro
    if not grupos:
        carregar_grupos()
    
    # Se ainda não tem dados ou cache expirado, baixa novo
    if not grupos or force_refresh:
        m3u8_content = carregar_m3u8(url)
        if not m3u8_content:
            xbmcgui.Dialog().notification("Erro", "Falha ao carregar lista", xbmcgui.NOTIFICATION_ERROR)
            return
            
        grupos = parse_m3u8(m3u8_content)
        if not grupos:
            xbmcgui.Dialog().notification("Aviso", "Nenhum canal encontrado", xbmcgui.NOTIFICATION_WARNING)
            return
            
        salvar_grupos()
    
    # Ordena os grupos alfabeticamente
    sorted_groups = sorted(grupos.keys(), key=lambda x: x.lower())
    
    for grupo in sorted_groups:
        canais = grupos[grupo]
        grupo_url = f"{sys.argv[0]}?action=list_group&group={urllib.parse.quote_plus(grupo)}"
        
        # Cria item com informações adicionais
        grupo_item = xbmcgui.ListItem(label=f"[B]{grupo}[/B]")
        grupo_item.setArt({
            "icon": "DefaultFolder.png",
            "fanart": "special://home/addons/plugin.video.cineroom/fanart.jpg"
        })
        grupo_item.setInfo("video", {
            "plot": f"{len(canais)} canais disponíveis",
            "mediatype": "video"
        })

        
        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=grupo_url,
            listitem=grupo_item,
            isFolder=True,
            totalItems=len(canais)
        )
    

    
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)

def get_default_playlist_url():
    addon = xbmcaddon.Addon()
    return addon.getSetting('playlist_url')  # Configurável pelo usuário

def list_group(handle, group):
    xbmcplugin.setContent(HANDLE, 'tvchannels')  # Específico para canais de TV
    global grupos
    
    # Carrega os grupos primeiro
    carregar_grupos()
    
    xbmc.log(f'[DEBUG] list_group chamado com handle: {handle}, group: "{group}"', xbmc.LOGINFO)
    
    # Decodifica o nome do grupo corretamente
    try:
        group_decoded = urllib.parse.unquote_plus(group)
    except:
        group_decoded = group
    
    # Se vier uma tupla, pegar apenas o primeiro valor
    if isinstance(group_decoded, tuple):
        group_decoded = group_decoded[0]

    group_decoded = group_decoded.strip()  # Remover espaços extras

    xbmc.log(f"[DEBUG] Grupos disponíveis: {list(grupos.keys())}", xbmc.LOGINFO)
    xbmc.log(f"[DEBUG] Procurando por grupo: '{group_decoded}'", xbmc.LOGINFO)

    if group_decoded not in grupos:
        xbmc.log(f"[ERRO] Grupo '{group_decoded}' não encontrado! Grupos disponíveis: {list(grupos.keys())}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok("Erro", f"Grupo '{group_decoded}' não encontrado!")
        return

    for canal in grupos[group_decoded]:
        url = f"{sys.argv[0]}?action=play_channel&channel_url={urllib.parse.quote_plus(canal['url'])}"
        li = xbmcgui.ListItem(label=canal['titulo'])
        li.setArt({'icon': canal['logo'], 'thumb': canal['logo']})
        xbmcplugin.addDirectoryItem(handle=handle, url=url, listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(handle)

import base64

def encode_url(url):
    return base64.b64encode(url.encode('utf-8')).decode('utf-8')

def decode_url(encoded_url):
    return base64.b64decode(encoded_url.encode('utf-8')).decode('utf-8')


def salvar_grupos():
    """Salva os grupos em um arquivo JSON com as URLs codificadas."""
    global grupos
    try:
        grupos_codificados = {}

        for grupo, canais in grupos.items():
            canais_codificados = []
            for canal in canais:
                canal_copy = canal.copy()
                if 'url' in canal_copy:
                    canal_copy['url'] = encode_url(canal_copy['url'])
                canais_codificados.append(canal_copy)
            grupos_codificados[grupo] = canais_codificados

        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(grupos_codificados, f, ensure_ascii=False, indent=4)

        xbmc.log("[DEBUG] Grupos salvos com sucesso!", xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f"[ERRO] Falha ao salvar grupos: {str(e)}", xbmc.LOGERROR)

def carregar_grupos():
    """Carrega os grupos do arquivo JSON e decodifica as URLs."""
    global grupos
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                grupos_carregados = json.load(f)

            for grupo, canais in grupos_carregados.items():
                for canal in canais:
                    if 'url' in canal:
                        canal['url'] = decode_url(canal['url'])
            grupos = grupos_carregados

            xbmc.log("[DEBUG] Grupos carregados com sucesso!", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[ERRO] Falha ao carregar grupos: {str(e)}", xbmc.LOGERROR)
    else:
        xbmc.log("[DEBUG] Nenhum cache de grupos encontrado, iniciando vazio.", xbmc.LOGINFO)


def play_channel(channel_url, channel_name="Canal"):
    """Inicia a reprodução do canal usando F4mTester ou reprodução direta (quando aplicável)."""
    try:
        import re, urllib.parse, xbmc, xbmcgui, xbmcplugin, sys, traceback

        # Pré-processamento da URL
        clean_url = re.sub(r'[(){}<>\[\]\^~]', '', urllib.parse.unquote(channel_url)).strip()
        xbmc.log(f"[PLAY] URL processada: {clean_url[:200]}...", xbmc.LOGDEBUG)

        # Verificação de URL
        if not clean_url.startswith(('http', 'rtmp', 'rtsp')):
            raise Exception("Protocolo não suportado")

        # REPRODUÇÃO DIRETA: Apenas arquivos .mp4 ou .mkv
        if clean_url.lower().endswith(('.mp4', '.mkv')):
            if "|User-Agent=" not in clean_url:
                clean_url += "|User-Agent=Android"

            xbmc.log(f"[PLAY] Reprodução direta com InputStream: {clean_url}", xbmc.LOGINFO)

            list_item = xbmcgui.ListItem(label=channel_name)
            list_item.setPath(clean_url)
            list_item.setProperty("IsPlayable", "true")
            list_item.setContentLookup(False)

            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, list_item)
        else:
            
            if "|User-Agent=" not in clean_url:
                clean_url += "|User-Agent=Android"
            plugin_url = (
                f"plugin://plugin.video.f4mTester/?"
                f"streamtype=HLSRETRY&"
                f"name={urllib.parse.quote(channel_name)}&"
                f"url={urllib.parse.quote(clean_url)}"
            )
            xbmc.log(f"[PLAY] Usando F4mTester: {plugin_url}", xbmc.LOGINFO)
            xbmc.executebuiltin(f'RunPlugin("{plugin_url}")')

    except Exception as e:
        xbmc.log(f"[DEBUG PLAY] Erro:\n{traceback.format_exc()}", xbmc.LOGDEBUG)
        xbmcgui.Dialog().notification("Falha na reprodução", f"Erro: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 5000)

