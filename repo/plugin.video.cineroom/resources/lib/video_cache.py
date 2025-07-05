import xbmcvfs
from datetime import datetime, timedelta

# Configurações do Cache
CACHE_DIR = xbmcvfs.translatePath(f"special://profile/addon_data/{get_addon_id()}/video_cache/")
CACHE_TTL_HOURS = 24  # Cache válido por 24 horas
MAX_CACHE_SIZE = 50   # Máximo de 50 URLs cacheadas

class VideoCache:
    def __init__(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.cache_index = self._load_index()

    def _get_cache_path(self, url):
        return os.path.join(CACHE_DIR, f"{hashlib.md5(url.encode()).hexdigest()}.json")

    def _load_index(self):
        index_path = os.path.join(CACHE_DIR, "index.json")
        try:
            if os.path.exists(index_path):
                with open(index_path, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def _save_index(self):
        index_path = os.path.join(CACHE_DIR, "index.json")
        with open(index_path, 'w') as f:
            json.dump(self.cache_index, f)

    def get(self, url):
        """Obtém dados do cache se ainda forem válidos"""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        if cache_key not in self.cache_index:
            return None

        entry = self.cache_index[cache_key]
        if datetime.now() > datetime.fromisoformat(entry['expires']):
            self.delete(url)
            return None

        try:
            with open(self._get_cache_path(url), 'r') as f:
                return json.load(f)
        except:
            return None

    def set(self, url, data):
        """Armazena dados no cache"""
        if len(self.cache_index) >= MAX_CACHE_SIZE:
            self._clean_oldest()

        cache_key = hashlib.md5(url.encode()).hexdigest()
        expires = datetime.now() + timedelta(hours=CACHE_TTL_HOURS)
        
        self.cache_index[cache_key] = {
            'url': url,
            'expires': expires.isoformat(),
            'size': len(str(data))
        }

        try:
            with open(self._get_cache_path(url), 'w') as f:
                json.dump(data, f)
            self._save_index()
            return True
        except Exception as e:
            xbmc.log(f"Erro ao salvar cache: {e}", xbmc.LOGERROR)
            return False

    def delete(self, url):
        """Remove um item específico do cache"""
        try:
            os.remove(self._get_cache_path(url))
            del self.cache_index[hashlib.md5(url.encode()).hexdigest()]
            self._save_index()
        except:
            pass

    def clear(self):
        """Limpa completamente o cache"""
        for filename in os.listdir(CACHE_DIR):
            file_path = os.path.join(CACHE_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                xbmc.log(f"Erro ao limpar cache: {e}", xbmc.LOGERROR)
        self.cache_index = {}
        self._save_index()

    def _clean_oldest(self):
        """Remove os itens mais antigos do cache"""
        sorted_items = sorted(
            self.cache_index.items(),
            key=lambda x: x[1]['expires']
        )
        for key, _ in sorted_items[:5]:  # Remove os 5 mais antigos
            try:
                os.remove(self._get_cache_path(self.cache_index[key]['url']))
                del self.cache_index[key]
            except:
                pass
        self._save_index()

# Instância global do cache
VIDEO_CACHE = VideoCache()