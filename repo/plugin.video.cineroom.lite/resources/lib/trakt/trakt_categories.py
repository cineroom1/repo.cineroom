# -*- coding: utf-8 -*-
"""
Sistema Modular de Categorias Trakt
✅ Adicione novas categorias em 3 linhas
✅ Código limpo e mantível
✅ Suporte a listas públicas e autenticadas
"""

import xbmc
import xbmcgui
import xbmcplugin
import sys

# ============================================
# CONFIGURAÇÃO DE CATEGORIAS
# ============================================

TRAKT_CATEGORIES = {
    # === LISTAS PÚBLICAS (sem autenticação) ===
    'trending': {
        'title': 'Em Alta',
        'emoji': '🔥',
        'handler': 'get_trending',
        'requires_auth': False,
        'supports_movies': True,
        'supports_shows': True
    },
    
    'popular': {
        'title': 'Populares',
        'emoji': '⭐',
        'handler': 'get_popular',
        'requires_auth': False,
        'supports_movies': True,
        'supports_shows': True
    },
    
    'most_watched': {
        'title': 'Mais Assistidos',
        'emoji': '👁️',
        'handler': 'get_most_watched',
        'requires_auth': False,
        'supports_movies': True,
        'supports_shows': True,
        'params': {'period': 'weekly'}
    },
    
    'most_collected': {
        'title': 'Mais Coletados',
        'emoji': '💾',
        'handler': 'get_most_collected',
        'requires_auth': False,
        'supports_movies': True,
        'supports_shows': True,
        'params': {'period': 'weekly'}
    },
    
    'most_anticipated': {
        'title': 'Mais Aguardados',
        'emoji': '🎬',
        'handler': 'get_most_anticipated',
        'requires_auth': False,
        'supports_movies': True,
        'supports_shows': True
    },
    
    'box_office': {
        'title': 'Bilheteria',
        'emoji': '🎟️',
        'handler': 'get_box_office',
        'requires_auth': False,
        'supports_movies': True,
        'supports_shows': False  # Só filmes
    },
    
    'top_rated': {
        'title': 'Melhor Avaliados',
        'emoji': '🏆',
        'handler': 'get_top_rated',
        'requires_auth': False,
        'supports_movies': True,
        'supports_shows': True
    },
    
    'most_played': {
        'title': 'Mais Reproduzidos',
        'emoji': '▶️',
        'handler': 'get_most_played',
        'requires_auth': False,
        'supports_movies': True,
        'supports_shows': True,
        'params': {'period': 'weekly'}
    },
    
    # === NOVO: RECOMENDAÇÕES (requer auth) ===
    'recommended': {
        'title': 'Recomendados Para Você',
        'emoji': '💡',
        'handler': 'get_recommended',
        'requires_auth': True,
        'supports_movies': True,
        'supports_shows': True
    },
    
    # === LISTAS PESSOAIS (requer auth) ===
    'watchlist': {
        'title': 'Minha Lista',
        'emoji': '📝',
        'handler': 'list_trakt_watchlist',
        'requires_auth': True,
        'supports_movies': True,
        'supports_shows': True,
        'is_personal': True
    },
    
    'collection': {
        'title': 'Minha Coleção',
        'emoji': '📀',
        'handler': 'list_trakt_collection',
        'requires_auth': True,
        'supports_movies': True,
        'supports_shows': True,
        'is_personal': True
    },
    
    'watched': {
        'title': 'Assistidos',
        'emoji': '✅',
        'handler': 'list_trakt_watched',
        'requires_auth': True,
        'supports_movies': True,
        'supports_shows': True,
        'is_personal': True
    }
}


# ============================================
# MOTOR DE CATEGORIAS - GENÉRICO
# ============================================

class TraktCategoryEngine:
    """Motor genérico para exibir qualquer categoria Trakt"""
    
    def __init__(self):
        from resources.lib.trakt_client import TraktLists, TraktPresentation
        from resources.lib.trakt_sync import (
            _enrich_item_with_tmdb_batch,
            _fetch_trakt_paginated,
            _build_source_url
        )
        
        self.trakt_lists = TraktLists()
        self.presentation = TraktPresentation
        self.enrich = _enrich_item_with_tmdb_batch
        self.fetch_paginated = _fetch_trakt_paginated
        self.build_url = _build_source_url
    
    def get_items(self, category_key, media_type='movies', page=1, limit=20):
        """
        Busca itens de qualquer categoria
        
        Args:
            category_key: Chave da categoria (ex: 'trending', 'recommended')
            media_type: 'movies' ou 'shows'
            page: Página atual
            limit: Itens por página
        """
        config = TRAKT_CATEGORIES.get(category_key)
        if not config:
            xbmc.log(f"[Trakt] Categoria inválida: {category_key}", xbmc.LOGERROR)
            return []
        
        handler_name = config['handler']
        params = config.get('params', {})
        is_personal = config.get('is_personal', False)
        
        try:
            # Listas pessoais (watchlist, collection, etc)
            if is_personal:
                endpoint_map = {
                    'watchlist': '/sync/watchlist',
                    'collection': '/sync/collection',
                    'watched': '/sync/watched'
                }
                
                base_endpoint = endpoint_map.get(category_key, f'/sync/{category_key}')
                endpoint = f"{base_endpoint}/{media_type}"
                
                items = self.fetch_paginated(
                    endpoint,
                    f'{category_key}_{media_type}',
                    page,
                    limit
                )
                
                return self.enrich(items)
            
            # Listas públicas (trending, popular, etc)
            else:
                handler = getattr(self.trakt_lists, handler_name)
                
                # Monta argumentos dinamicamente
                args = [media_type, page, limit]
                
                # Adiciona parâmetros extras (ex: period='weekly')
                if params:
                    for key, value in params.items():
                        args.insert(1, value)  # Insere após media_type
                
                data = handler(*args)
                
                if not data:
                    return []
                
                # Normaliza itens
                items = []
                for item in data:
                    try:
                        normalized = self.presentation.normalize_item(item)
                        if normalized['tmdb_id']:
                            items.append(normalized)
                    except Exception as e:
                        xbmc.log(f"[Trakt] Erro normalizando: {e}", xbmc.LOGERROR)
                        continue
                
                return self.enrich(items)
        
        except Exception as e:
            xbmc.log(f"[Trakt] Erro buscando {category_key}: {e}", xbmc.LOGERROR)
            return []
    
    def show_menu(self, filter_public=True, filter_personal=False):
        """
        Exibe menu de categorias
        
        Args:
            filter_public: Mostrar categorias públicas?
            filter_personal: Mostrar categorias pessoais?
        """
        import xbmcplugin
        from resources.lib.trakt_sync import get_trakt_settings, refresh_trakt_token
        
        handle = int(sys.argv[1])
        
        # Verifica autenticação se necessário
        settings = get_trakt_settings()
        is_authenticated = settings.get('access_token') and refresh_trakt_token()
        
        for category_key, config in TRAKT_CATEGORIES.items():
            # Filtra por tipo
            is_personal = config.get('is_personal', False)
            
            if filter_public and is_personal:
                continue
            if filter_personal and not is_personal:
                continue
            
            # Requer autenticação?
            if config.get('requires_auth') and not is_authenticated:
                continue
            
            # Monta label
            emoji = config.get('emoji', '📋')
            title = config['title']
            label = f"{emoji} {title}"
            
            li = xbmcgui.ListItem(label=label)
            li.setProperty('IsPlayable', 'false')
            li.setInfo('video', {'title': title})
            
            url = f"plugin://plugin.video.cineroom.lite/?action=trakt_category&category={category_key}"
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
        
        xbmcplugin.endOfDirectory(handle, succeeded=True)
    
    def show_media_type_menu(self, category_key):
        """Exibe submenu Filmes/Séries"""
        import xbmcplugin
        
        handle = int(sys.argv[1])
        config = TRAKT_CATEGORIES.get(category_key)
        
        if not config:
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return
        
        title = config['title']
        emoji = config.get('emoji', '📋')
        
        options = []
        
        if config.get('supports_movies'):
            options.append(('movies', f'🎬 {title} - Filmes'))
        
        if config.get('supports_shows'):
            options.append(('shows', f'📺 {title} - Séries'))
        
        for media_type, label in options:
            li = xbmcgui.ListItem(label=label)
            li.setProperty('IsPlayable', 'false')
            li.setInfo('video', {'title': label})
            
            url = f"plugin://plugin.video.cineroom.lite/?action=trakt_category_list&category={category_key}&media_type={media_type}&page=1"
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=True)
        
        xbmcplugin.endOfDirectory(handle, succeeded=True)
    
    def show_items(self, category_key, media_type, page=1):
        """Exibe itens de uma categoria com paginação"""
        import xbmcplugin
        
        handle = int(sys.argv[1])
        config = TRAKT_CATEGORIES.get(category_key)
        
        if not config:
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return
        
        items = self.get_items(category_key, media_type, page)
        
        xbmcplugin.setContent(handle, 'movies')
        
        if not items:
            if page == 1:
                xbmcgui.Dialog().notification(
                    "Trakt",
                    f"{config['title']} vazio ou erro de conexão",
                    xbmcgui.NOTIFICATION_WARNING,
                    3000
                )
            xbmcplugin.endOfDirectory(handle, succeeded=False)
            return
        
        # Adiciona itens
        for item in items:
            label = self._format_label(item, config)
            
            li = xbmcgui.ListItem(label=label)
            is_folder = (item['media_type'] == 'tvshow')
            li.setProperty('IsPlayable', 'false' if is_folder else 'true')
            
            li.setInfo('video', {
                'title': item['title'],
                'mediatype': item['media_type'],
                'year': item.get('year', 0),
                'genre': ' / '.join(item.get('genres', [])),
                'plot': item.get('synopsis', ''),
                'rating': item.get('rating', 0),
            })
            
            if item.get('poster'):
                li.setArt({'poster': item['poster'], 'thumb': item['poster']})
            if item.get('backdrop'):
                li.setArt({'fanart': item['backdrop']})
            
            url = self.build_url(item)
            xbmcplugin.addDirectoryItem(handle, url, li, isFolder=is_folder)
        
        # Próxima página
        if len(items) >= 20:
            li_next = xbmcgui.ListItem(label="[B]→ Próxima Página[/B]")
            url_next = f"plugin://plugin.video.cineroom.lite/?action=trakt_category_list&category={category_key}&media_type={media_type}&page={page+1}"
            xbmcplugin.addDirectoryItem(handle, url_next, li_next, isFolder=True)
        
        xbmcplugin.endOfDirectory(handle, succeeded=True)
    
    def _format_label(self, item, config):
        """Formata label do item baseado na categoria"""
        label = item['title']
        
        stats = []
        
        if item.get('year'):
            stats.append(f"({item['year']})")
        
        if item.get('rating', 0) > 0:
            stats.append(f"⭐ {item['rating']:.1f}")
        
        # Stats específicas por categoria
        category_key = config.get('handler', '')
        
        if 'watched' in category_key.lower():
            plays = item.get('plays', 1)
            if plays > 1:
                stats.append(f"▶️ {plays}x")
        
        elif 'trending' in category_key.lower():
            watchers = item.get('watchers', 0)
            if watchers > 0:
                stats.append(f"👁️ {watchers}")
        
        elif 'collected' in category_key.lower():
            count = item.get('collector_count', 0)
            if count > 0:
                stats.append(f"💾 {count}")
        
        if stats:
            label += f" [{' '.join(stats)}]"
        
        return label


# ============================================
# FUNÇÕES DE COMPATIBILIDADE (mantém API antiga)
# ============================================

_engine = None

def get_engine():
    """Singleton do motor de categorias"""
    global _engine
    if _engine is None:
        _engine = TraktCategoryEngine()
    return _engine


# Mantém funções antigas para compatibilidade
def show_trakt_public_lists_menu():
    """Menu de listas públicas"""
    get_engine().show_menu(filter_public=True, filter_personal=False)


def show_trakt_public_category(category):
    """Submenu de categoria pública"""
    get_engine().show_media_type_menu(category)


def show_trakt_public_list(category, media_type, page=1):
    """Lista de itens"""
    get_engine().show_items(category, media_type, page)


# ============================================
# ATALHOS DIRETOS (para compatibilidade)
# ============================================

def trakt_movies_trending(page=1):
    get_engine().show_items('trending', 'movies', page)

def trakt_movies_popular(page=1):
    get_engine().show_items('popular', 'movies', page)

def trakt_movies_recommended(page=1):
    get_engine().show_items('recommended', 'movies', page)

def trakt_tv_trending(page=1):
    get_engine().show_items('trending', 'shows', page)

def trakt_tv_popular(page=1):
    get_engine().show_items('popular', 'shows', page)

def trakt_tv_recommended(page=1):
    get_engine().show_items('recommended', 'shows', page)


# ============================================
# EXEMPLO: COMO ADICIONAR NOVA CATEGORIA
# ============================================

"""
Para adicionar "Filmes Recentes" (exemplo):

1. Adicione em TRAKT_CATEGORIES:

'recent': {
    'title': 'Lançamentos Recentes',
    'emoji': '🆕',
    'handler': 'get_recent',
    'requires_auth': False,
    'supports_movies': True,
    'supports_shows': True
}

2. Implemente o handler em TraktLists (trakt_client.py):

def get_recent(self, media_type='movies', page=1, limit=20):
    return self.request(f'/{media_type}/recent', page, limit)

3. PRONTO! O menu aparecerá automaticamente.

Opcionalmente, crie atalho direto:

def trakt_movies_recent(page=1):
    get_engine().show_items('recent', 'movies', page)
"""