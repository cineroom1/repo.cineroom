import xbmcaddon
import xbmcgui
import urllib.request
import json
from resources.lib.configs.urls import credenciais
import xbmc

MAX_ATTEMPTS = 2  # Número máximo de tentativas

def fetch_credentials():
    """Obtém a lista de usuários e status de ativação do login a partir do JSON remoto."""
    try:
        with urllib.request.urlopen(credenciais) as response:
            data = json.load(response)

            enabled = data.get("enabled", False)
            users = data.get("users", [])

            if enabled and isinstance(users, list):
                return enabled, users
            elif not enabled:
                return False, []  # Login desativado
            else:
                xbmcgui.Dialog().ok("Erro", "Formato inválido do arquivo de credenciais.")
    except urllib.error.URLError as e:
        xbmcgui.Dialog().ok("Erro de Rede", f"Erro ao conectar ao servidor: {e}")
    except json.JSONDecodeError as e:
        xbmcgui.Dialog().ok("Erro de JSON", f"Erro ao decodificar o arquivo de credenciais: {e}")
    except Exception as e:
        xbmcgui.Dialog().ok("Erro", f"Erro inesperado: {e}")

    return False, []

def login():
    """Solicita login ao usuário e valida com as credenciais remotas."""
    addon = xbmcaddon.Addon()
    
    saved_user = addon.getSetting("saved_user")
    saved_password = addon.getSetting("saved_password")

    enabled, users = fetch_credentials()
    if not enabled:
        return True  # Login desativado, acesso liberado

    # Se credenciais salvas forem válidas, permite acesso direto
    for user in users:
        if saved_user == user["user"] and saved_password == user["password"]:
            return True

    # Caso contrário, solicitar login
    for attempt in range(MAX_ATTEMPTS):
        user_input = xbmcgui.Dialog().input("Digite o nome de usuário:", type=xbmcgui.INPUT_ALPHANUM)
        pass_input = xbmcgui.Dialog().input("Digite a senha:", type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)

        for user in users:
            if user_input == user["user"] and pass_input == user["password"]:
                addon.setSetting("saved_user", user_input)
                addon.setSetting("saved_password", pass_input)
                return True

        xbmcgui.Dialog().ok("Erro", "Credenciais inválidas. Tente novamente.")

    xbmcgui.Dialog().ok("Erro", "Número máximo de tentativas atingido. Acesso negado.")
    return False
