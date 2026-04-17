# -*- coding: utf-8 -*-
"""
Templates de providers Stremio.
Apenas modo manual (URL direta).
"""

import copy


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _clean_base_url(url):
    return (url or '').strip().rstrip('/')


def build_manual_url(values):
    return _clean_base_url(values.get('url') or '')


# ─────────────────────────────────────────────────────────────────────────────
# Templates — apenas manual
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        'id': 'manual',
        'name': 'URL Personalizada',
        'provider_type': 'direct',
        'builder': 'manual',
        'fields': [
            {
                'key': 'url',
                'label': 'URL do Provider',
                'type': 'text',
                'default': '',
            },
        ]
    },
]

PRESETS = []


# ─────────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────────

def list_templates():
    return copy.deepcopy(TEMPLATES)


def list_presets():
    return []


def get_template(template_id):
    for t in TEMPLATES:
        if t['id'] == template_id:
            return copy.deepcopy(t)
    return None


def get_preset(preset_id):
    return None


def build_provider_from_template(template_id, values, custom_name=None):
    """
    Retorna dict pronto para salvar em providers_db.add_provider()
    {
        name: str,
        url: str,
        provider_type: 'torrent'|'direct'
    }
    """
    tpl = get_template(template_id)
    if not tpl:
        return None

    final_url = build_manual_url(values)

    if not final_url.startswith('http'):
        return None

    return {
        'name': (custom_name or tpl['name']).strip(),
        'url': final_url,
        'provider_type': tpl.get('provider_type', 'direct'),
    }


def build_provider_from_preset(preset_id, custom_name=None):
    return None