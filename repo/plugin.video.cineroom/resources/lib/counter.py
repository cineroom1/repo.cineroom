import urllib.request
import json
import xbmc
import xbmcaddon
import time
import hashlib
from uuid import getnode as get_mac
import xbmcvfs

# --- Configuração do Firebase ---
FIREBASE_URL = ""

# --- Cache e Decaimento ---
COUNTERS_CACHE = None
LAST_UPDATE = 0
LAST_RESET_DATE = None

def get_firebase_counters(force_update=False):
    """Busca contadores SEM CACHE para sempre obter valores atualizados"""
    try:
        with urllib.request.urlopen(FIREBASE_URL) as response:
            data = json.loads(response.read().decode())
            
            # Garante valores padrão se faltantes
            for key in ["Filmes", "Séries", "Explorar", "Visitas_menu"]:
                if key not in data:
                    data[key] = 5 if key != "Visitas_menu" else 0
            
            # Converte para inteiros
            for key in data:
                if key in ["Filmes", "Séries", "Explorar", "Visitas_menu"]:
                    try:
                        data[key] = int(data[key])
                    except (ValueError, TypeError):
                        data[key] = 5 if key != "Visitas_menu" else 0
            
            return data
            
    except Exception as e:
        xbmc.log(f"ERRO Firebase: {str(e)}", xbmc.LOGERROR)
        return {
            "Filmes": 5,
            "Séries": 5,
            "Explorar": 5,
            "Visitas_menu": 1
        }

import datetime

def update_firebase_counter(category):
    """Atualização SÍNCRONA e VERIFICADA"""
    try:
        # 1. Obtém valor ATUAL diretamente do Firebase
        current_data = get_firebase_counters(force_update=True)
        current_value = current_data.get(category, 5 if category != "Visitas_menu" else 0)

        # 2. Calcula novo valor
        new_value = current_value + 1

        # 3. Prepara dados para atualização
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        update_payload = {
            category: new_value,
            "last_updated": now
        }

        # 4. Envia atualização
        req = urllib.request.Request(
            FIREBASE_URL,
            data=json.dumps(update_payload).encode('utf-8'),
            method="PATCH",
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req) as response:
            updated_data = json.loads(response.read().decode())
            if str(updated_data.get(category)) != str(new_value):
                raise ValueError("Valor não foi atualizado corretamente")

            xbmc.log(f"Contador {category} atualizado CONFIRMADO: {new_value}", xbmc.LOGINFO)
            return new_value

    except Exception as e:
        xbmc.log(f"FALHA CRÍTICA: {category} não atualizado: {str(e)}", xbmc.LOGERROR)
        return None


# ... (mantenha as outras funções como get_decayed_counters, register_menu_access, etc.)

# --- Funções Auxiliares (Mantidas do Original) ---
def get_user_unique_id():
    raw_id = f"{get_mac()}-{xbmc.getInfoLabel('System.ScreenResolution')}-{xbmc.getLanguage()}"
    return hashlib.sha256(raw_id.encode()).hexdigest()[:16]

import os
import json
import time
import xbmcaddon

def register_menu_access():
    addon = xbmcaddon.Addon()
    user_id = get_user_unique_id()
    today = time.strftime('%Y-%m-%d')
    current_time = time.time()

    # Caminho do arquivo persistente
    data_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    stats_file = os.path.join(data_path, 'menu_access.json')

    # Lê os dados salvos
    try:
        with open(stats_file, 'r') as f:
            data = json.load(f)
    except:
        data = {}

    last_access = data.get('last_menu_access')
    last_user = data.get('last_user_id')
    last_timestamp = data.get('last_timestamp', 0)

    # Verifica se já passou pelo menos 1 hora desde o último registro
    if (last_access != today or 
        last_user != user_id or 
        (current_time - last_timestamp) > 3600):  # 3600 segundos = 1 hora
        
        update_firebase_counter("Visitas_menu")
        data['last_menu_access'] = today
        data['last_user_id'] = user_id
        data['last_timestamp'] = current_time

        # Salva novamente
        os.makedirs(data_path, exist_ok=True)
        with open(stats_file, 'w') as f:
            json.dump(data, f)


def get_decayed_counters():
    """Retorna contadores com decaimento diário automático"""
    global LAST_RESET_DATE, COUNTERS_CACHE
    
    current_date = time.strftime('%Y-%m-%d')
    counters = get_firebase_counters()
    
    if LAST_RESET_DATE != current_date:
        LAST_RESET_DATE = current_date
        decayed_counters = {}
        
        for key, value in counters.items():
            # Verifica se o valor é numérico antes de aplicar decaimento
            if key in ["Filmes", "Séries", "Explorar"]:
                try:
                    # Converte para int se for string e aplica decaimento
                    num_value = int(value) if isinstance(value, (str, int, float)) else 0
                    decayed_value = max(5, int(num_value * 0.8))
                    decayed_counters[key] = decayed_value
                except (ValueError, TypeError):
                    decayed_counters[key] = 5  # Valor padrão se conversão falhar
            else:
                decayed_counters[key] = value
        
        # Atualiza apenas uma vez por dia
        update_all_firebase_counters(decayed_counters)
        COUNTERS_CACHE = decayed_counters
        return decayed_counters
    
    return counters

def update_all_firebase_counters(data):
    """Atualiza todos os contadores de uma vez"""
    try:
        req = urllib.request.Request(
            FIREBASE_URL,
            data=json.dumps(data).encode("utf-8"),
            method="PUT",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as response:
            xbmc.log("Contadores atualizados com decaimento", xbmc.LOGINFO)
            return True
    except Exception as e:
        xbmc.log(f"Erro ao atualizar todos os contadores: {str(e)}", xbmc.LOGERROR)
        return False