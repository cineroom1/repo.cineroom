# resources/lib/scrapers/__init__.py
# -*- coding: utf-8 -*-
"""
Scrapers integrados para usuários FREE
"""
from .stremio_custom import scrape_all_stremio, has_providers_configured
 
__all__ = ['scrape_all_stremio', 'has_providers_configured']