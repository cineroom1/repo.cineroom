# Em: resources/lib/favorites.py

import xbmcgui
from .db import db

def add_item_to_favorites(tmdb_id, media_type):
    """Chama o banco de dados para adicionar um item e notifica o usuário."""
    db.add_to_favorites(tmdb_id, media_type)
    xbmcgui.Dialog().notification("Minha Lista", "Adicionado à sua lista!", xbmcgui.NOTIFICATION_INFO)

def remove_item_from_favorites(tmdb_id, media_type):
    """Chama o banco de dados para remover um item e notifica o usuário."""
    db.remove_from_favorites(tmdb_id, media_type)
    xbmcgui.Dialog().notification("Minha Lista", "Removido da sua lista.", xbmcgui.NOTIFICATION_INFO)