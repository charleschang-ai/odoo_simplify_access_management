# -*- coding: utf-8 -*-
from odoo import models

from ..const import get_configured_prefixes, get_url_prefix


class IrHttpDebranding(models.AbstractModel):
    _inherit = 'ir.http'

    def _generate_routing_rules(self, modules, converters):
        """Duplicate /odoo/* routes for all configured url_prefix values.
        The routing table is cached (cache='routing'); config changes trigger
        a cache clear rebuild via sync. Note: routes always include the custom
        prefix (whether white-label is enabled or not); only the session → JS
        controls whether the custom prefix is actually used."""
        prefixes = get_configured_prefixes(self.env)
        for url, endpoint in super()._generate_routing_rules(modules, converters):
            yield url, endpoint
            if url == '/odoo' or url.startswith('/odoo/'):
                for prefix in prefixes:
                    yield '/%s%s' % (prefix, url[len('/odoo'):]), endpoint

    def session_info(self):
        info = super().session_info()
        if 'sam.profile' not in self.env:
            return info
        cfg = self.env['sam.profile'].sudo()._get_debranding()
        if cfg.get('enabled'):
            info['sam_debranding'] = {
                'enabled': True,
                'brand': cfg.get('brand') or self.env.company.sudo().name or '',
                'prefix': cfg.get('prefix') or '',
            }
        return info

    def webclient_rendering_context(self):
        """Override browser tab title and icon (web.layout title / x_icon vars)
        for backend pages."""
        ctx = super().webclient_rendering_context()
        if 'sam.profile' in self.env:
            cfg = self.env['sam.profile'].sudo()._get_debranding()
            if cfg.get('enabled'):
                ctx['title'] = cfg.get('brand') or self.env.company.sudo().name or ''
                if cfg.get('favicon'):
                    ctx['x_icon'] = '/sam/favicon'
        return ctx
