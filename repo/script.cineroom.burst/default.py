# -*- coding: utf-8 -*-
"""
Cineroom Burst - Script de Teste
=================================
"""

import sys
import os
import xbmc
import xbmcgui

# Adicionar lib ao path
addon_path = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(addon_path, 'lib')
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

def test_import():
    """Testa o import do Burst"""
    try:
        # Testar import via script.cineroom.burst
        import script.cineroom.burst as burst
        
        version = getattr(burst, '__version__', 'desconhecida')
        
        # Teste adicional: verificar se a função existe
        if not hasattr(burst, 'scrape_provider_sources'):
            raise ImportError("Função scrape_provider_sources não encontrada")
        
        xbmcgui.Dialog().ok(
            "Burst - Teste de Import",
            f"[B]✅ SUCESSO![/B]\n\n"
            f"Burst importado corretamente\n"
            f"Versão: {version}\n\n"
            f"Funções disponíveis:\n"
            f"• scrape_provider_sources()\n"
            f"• scrape() [alias]"
        )
        
        xbmc.log("[Burst] Teste de import: SUCESSO", xbmc.LOGINFO)
        xbmc.log(f"[Burst] Versão: {version}", xbmc.LOGINFO)
        return True
        
    except ImportError as e:
        import traceback
        xbmcgui.Dialog().ok(
            "Burst - Erro de Import",
            f"[B]❌ FALHA no import[/B]\n\n"
            f"Erro: {str(e)}\n\n"
            f"Verifique:\n"
            f"1. O addon está instalado?\n"
            f"2. O Kodi foi reiniciado?"
        )
        xbmc.log(f"[Burst] Teste de import FALHOU: {e}", xbmc.LOGERROR)
        xbmc.log(f"[Burst] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
        return False
    except Exception as e:
        import traceback
        xbmcgui.Dialog().ok(
            "Burst - Erro",
            f"[B]❌ ERRO inesperado[/B]\n\n"
            f"Erro: {str(e)}\n\n"
            f"Verifique o log do Kodi"
        )
        xbmc.log(f"[Burst] Erro inesperado: {e}", xbmc.LOGERROR)
        xbmc.log(f"[Burst] Traceback: {traceback.format_exc()}", xbmc.LOGERROR)
        return False

def show_info():
    """Mostra informações do addon"""
    dialog = xbmcgui.Dialog()
    
    options = [
        "ℹ️  Sobre o Cineroom Burst",
        "🧪 Testar Import",
        "❌ Sair"
    ]
    
    selected = dialog.select("Cineroom Burst v2.0", options)
    
    if selected == 0:
        # Sobre
        dialog.ok(
            "Cineroom Burst",
            "[B]Módulo de Scrapers v2.0[/B]\n\n"
            "Provedores suportados:\n"
            "• Stremio (Brazuca, Torrentio, etc)\n"
            "• AnimeZey\n"
            "• Comando Top\n"
            "• Apache Torrent\n"
            "• Filmes Master\n"
            "• Starck Filmes\n\n"
            "Para usar: Instale o Cineroom Lite"
        )
    elif selected == 1:
        # Testar
        test_import()

if __name__ == '__main__':
    show_info()
