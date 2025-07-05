# resources/lib/encryption_utils.py
import base64

def obfuscate_string(data_string):
    if not data_string: return data_string
    return base64.b64encode(data_string.encode('utf-8')[::-1]).decode('utf-8')

def deobfuscate_string(obfuscated_string):
    if not obfuscated_string: return obfuscated_string
    try:
        return base64.b64decode(obfuscated_string.encode('utf-8'))[::-1].decode('utf-8')
    except:
        return obfuscated_string # Em caso de erro, retorna a string original