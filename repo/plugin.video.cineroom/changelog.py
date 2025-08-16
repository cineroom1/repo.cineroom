import xbmcgui
import xbmcaddon
from datetime import datetime

def show_about():
    """Exibe informações sobre o addon com changelog organizado."""
    addon = xbmcaddon.Addon()
    
    # Dados separados para fácil manutenção
    CHANGELOG = [
    {
        'version': '4.3.2',
        'changes': [
            ("[COLOR yellow]Novidades[/COLOR]", "Opção para salvar coleções a sua lista"),
            ("[COLOR yellow]Novidades[/COLOR]", "Nova aba de recomendações focada em sua lista de favoritos"),
            ("[COLOR yellow]Novidades[/COLOR]", "Nova aba 'Mais buscados', Focada nos filmes e series mais buscados do addon"),
            ("[COLOR yellow]Novidades[/COLOR]", "Novo layout para filmes, deixando o menu mais leve"),
            ("[COLOR yellow]Novidades[/COLOR]", "Cache aprimorado para dispositivos fracos")
        ]
    }
]


    CONTATOS = [
        ("Telegram", "Disponíveis no menu principal"),
        ("E-mail", "cineroom.ofc@gmail.com"),
        ("Doações", "Disponíveis no menu principal")
    ]

    about_text = [
        f"[COLOR gold]╔══════════════════════════════════╗[/COLOR]",
        f"[COLOR gold]║ [B]{addon.getAddonInfo('name').center(30)}[/B] ║",
        f"[COLOR gold]╟──────────────────────────────────╢[/COLOR]",
        f"[COLOR white]║   Versão: [B]{addon.getAddonInfo('version')}[/B]".ljust(33) + "║",
        f"[COLOR white]║   Desenvolvedor: [B]{addon.getAddonInfo('author')}[/B]".ljust(33) + "║",
        f"[COLOR gold]╚══════════════════════════════════╝[/COLOR]",
    ]    

    # Adiciona changelog
    for version_data in CHANGELOG:
        about_text.append(f"\n[COLOR gold]► Versão {version_data['version']}[/COLOR]")
        for change_type, change_text in version_data['changes']:
            about_text.append(f"[COLOR white]• {change_type}:[/COLOR] {change_text}")

    # Adiciona contatos
    about_text.extend([
        "\n[COLOR gold][B]▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬[/B][/COLOR]",
        "[COLOR gold][B]SUPORTE E CONTATO[/B][/COLOR]"
    ])
    
    for contato_type, contato_info in CONTATOS:
        about_text.append(f"[COLOR white]• {contato_type}:[/COLOR] [COLOR lime]{contato_info}[/COLOR]")

    # Rodapé
    about_text.append(
        f"\n[COLOR gray]© {datetime.now().year} {addon.getAddonInfo('name')} - Todos os direitos reservados[/COLOR]"
    )

    # Exibição
    list_item = xbmcgui.ListItem(label='Sobre')
    list_item.setArt({'icon': addon.getAddonInfo('icon'), 'fanart': addon.getAddonInfo('icon')})
    xbmcgui.Dialog().textviewer('Detalhes do Addon', "\n".join(about_text))