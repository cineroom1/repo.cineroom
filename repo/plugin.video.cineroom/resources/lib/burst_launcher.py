import sys
import xbmc
from urllib.parse import quote_plus

def launch_burst_search(tmdb_id, title):
    if tmdb_id and tmdb_id != "None":
        burst_url = f'plugin://script.elementum.rajada?tmdb={tmdb_id}'
    elif title:
        title = quote_plus(title)
        burst_url = f'plugin://script.elementum.rajada?search={title}'
    else:
        burst_url = 'plugin://script.elementum.rajada?search=Filme'

    xbmc.executebuiltin(f'RunPlugin({burst_url})')

if __name__ == '__main__':
    try:
        tmdb_id = sys.argv[1] if len(sys.argv) > 1 else ''
        title = sys.argv[2] if len(sys.argv) > 2 else ''
        launch_burst_search(tmdb_id, title)
    except Exception as e:
        xbmc.log(f"[burst_launcher] Erro ao lançar busca Burst: {e}", xbmc.LOGERROR)
