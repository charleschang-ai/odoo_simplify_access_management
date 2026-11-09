# -*- coding: utf-8 -*-
import re

# Words already occupied by Odoo core routes. Using them as prefixes
# would shadow core routes (e.g. /web/assets). Rejected at validation.
RESERVED_PREFIXES = {
    'web', 'odoo', 'scoped_app', 'website', 'my', 'shop', 'web_editor',
    'base', 'bus', 'mail', 'calendar', 'im_livechat', 'longpolling',
}

PREFIX_RE = re.compile(r'^[A-Za-z0-9_-]+$')


def is_valid_prefix(prefix):
    return bool(prefix) and prefix not in RESERVED_PREFIXES and bool(PREFIX_RE.match(prefix))


def is_debranding_enabled(env):
    """站点级白标开关是否启用(与当前用户无关)。"""
    if 'sam.profile' not in env:
        return False
    return bool(env['sam.profile'].sudo()._get_debranding().get('enabled'))


def get_url_prefix(env):
    """Currently active URL prefix (validated), or None if not enabled."""
    if 'sam.profile' not in env:
        return None
    return env['sam.profile'].sudo()._get_debranding().get('prefix') or None


def get_configured_prefixes(env):
    """All configured url_prefix values (regardless of enabled state), used
    for route generation. Ensures old prefix routes remain reachable after
    disabling white-label, avoiding 404s."""
    if 'sam.profile' not in env:
        return set()
    prefixes = set()
    for rec in env['sam.profile'].sudo().search_read(
            [('url_prefix', '!=', False)], ['url_prefix']):
        p = (rec['url_prefix'] or '').strip().strip('/')
        if p and is_valid_prefix(p):
            prefixes.add(p)
    return prefixes
