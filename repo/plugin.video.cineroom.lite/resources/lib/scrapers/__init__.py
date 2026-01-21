# Em: resources/lib/scrapers/__init__.py
import xbmc

# --- Importa os módulos de scraper ---
from . import stremio
from . import animezey

# --- Função Roteadora Principal ---
def scrape_provider_sources(provider_name, provider_data, item_data):
    """
    Função "Roteadora" Principal.
    Verifica o nome do provedor e chama a função 'scrape' do módulo correto.
    """
    xbmc.log(f"[SCRAPER] Roteando para o provedor: {provider_name}", xbmc.LOGINFO)

    # Extrai season e episode AQUI, uma única vez
    season = item_data.get('season')
    episode = item_data.get('episode')
    
    # Lista de resultados
    sources = []

    try:
        
        if provider_name in ["Brazuca", "Torrentio", "SkyFlix", "Mico-Leão","CDFlix"]:
            # Chama a função 'scrape' do módulo 'stremio.py'
            sources = stremio.scrape(
                provider_url=provider_data.get('url'),
                is_configurable=provider_data.get('configurable', False),
                imdb_id=item_data.get('imdb_id'),
                media_type=item_data.get('media_type'),
                season=season,
                episode=episode
            )
        
        elif provider_name == "AnimeZey":
            # Chama a função 'scrape' do módulo 'animezey.py'
            sources = animezey.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data
            )
            
        elif provider_name in ["ComandoTop"]:
            from . import comando
            sources = comando.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )  
            
        elif provider_name == "ApacheTorrent":
            from . import apachetorrent
            sources = apachetorrent.scrape_apache(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )
            
        elif provider_name == "Filmesmaster":
            from . import filmesmaster
            sources = filmesmaster.scrape_filmesmaster(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )
            
        elif provider_name == "StarckFilmes":
            # NOVO: Scraper do Starck Filmes
            from . import starckfilmes
            sources = starckfilmes.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )
        
        elif provider_name == "CMD1":
            from . import cmd1
            sources = cmd1.scrape(
                provider_url=provider_data.get('url'),
                item_data=item_data,
                season=season,
                episode=episode
            )     
            
        else:
            xbmc.log(f"[SCRAPER] Provedor '{provider_name}' não reconhecido.", xbmc.LOGWARNING)
            return []
            
    except Exception as e:
        import traceback
        xbmc.log(f"[SCRAPER] Erro catastrófico ao chamar o scraper '{provider_name}': {e}", xbmc.LOGERROR)
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        return []

    # Retorna as fontes encontradas
    return sources