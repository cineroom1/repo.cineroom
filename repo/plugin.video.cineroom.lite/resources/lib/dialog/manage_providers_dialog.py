# manage_providers_dialog.py
import xbmcgui
from resources.lib.providers_db import (
    load_providers, add_provider, remove_provider,
    toggle_provider, save_providers
)


def open_manage_providers_dialog():
    while True:
        providers = load_providers()

        items = []
        for p in providers:
            status = '[COLOR 00BB00]✔[/COLOR]' if p['enabled'] else '[COLOR 888888]✘[/COLOR]'
            tipo = 'DIRETO' if p['type'] == 'direct' else 'TORRENT'
            items.append(f'{status}  {p["name"]}  |  {tipo}')

        items.append('+ Adicionar provider')

        sel = xbmcgui.Dialog().select('Providers Stremio', items)

        if sel < 0:
            break

        if sel == len(providers):
            _add_provider_manual()
            continue

        provider = providers[sel]
        _item_menu(provider, sel, providers)


def _add_provider_manual():
    """Adiciona provider por URL digitada diretamente."""
    dialog = xbmcgui.Dialog()

    url = dialog.input('URL do Provider', type=xbmcgui.INPUT_ALPHANUM).strip()
    if not url or not url.startswith('http'):
        if url:
            dialog.notification('Erro', 'URL inválida. Deve começar com http(s).', xbmcgui.NOTIFICATION_ERROR)
        return

    # Detecta tipo automaticamente pela URL
    url_lower = url.lower()
    if any(k in url_lower for k in ('torrentio', 'torrent', 'brazuca', 'mico', 'wolfmax')):
        provider_type = 'torrent'
    else:
        provider_type = 'direct'

    name = dialog.input('Nome do Provider (deixe em branco para usar a URL)', type=xbmcgui.INPUT_ALPHANUM).strip()
    if not name:
        # Usa o hostname como nome
        try:
            from urllib.parse import urlparse
            name = urlparse(url).netloc or url
        except Exception:
            name = url

    result = add_provider(name, url, provider_type)
    if result is None:
        dialog.notification('Aviso', 'URL já cadastrada ou inválida.', xbmcgui.NOTIFICATION_WARNING)
    else:
        dialog.notification('Provider adicionado', name, xbmcgui.NOTIFICATION_INFO, 2000)


def _item_menu(provider, pos, providers):
    toggle_label = 'Desativar' if provider['enabled'] else 'Ativar'
    options = [toggle_label]
    if pos > 0:
        options.append('Mover para cima')
    if pos < len(providers) - 1:
        options.append('Mover para baixo')
    options.append('Remover')

    sel = xbmcgui.Dialog().contextmenu(options)
    if sel < 0:
        return

    action = options[sel]

    if 'tivar' in action:
        toggle_provider(provider['id'])
    elif 'cima' in action:
        providers[pos], providers[pos - 1] = providers[pos - 1], providers[pos]
        for i, p in enumerate(providers):
            p['priority'] = i + 1
        save_providers(providers)
    elif 'baixo' in action:
        providers[pos], providers[pos + 1] = providers[pos + 1], providers[pos]
        for i, p in enumerate(providers):
            p['priority'] = i + 1
        save_providers(providers)
    elif 'Remover' in action:
        if xbmcgui.Dialog().yesno('Remover', f'Remover [B]{provider["name"]}[/B]?'):
            remove_provider(provider['id'])