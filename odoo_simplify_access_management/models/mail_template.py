# -*- coding: utf-8 -*-
import re

from odoo import api, models

_POWERED_BY_TEXT_RE = re.compile(
    r'Powered by\s+<a\b[^>]*odoo\.com[^>]*>Odoo</a>\.?',
    re.IGNORECASE,
)


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    @api.model
    def _generate_template(self, res_ids, render_fields,
                           find_or_create_partners=False):
        """统一出口:所有邮件模板渲染(预览+发送)经此方法,
        白标启用时从 body_html / subject 中抹除品牌文字。"""
        result = super()._generate_template(
            res_ids, render_fields,
            find_or_create_partners=find_or_create_partners,
        )
        if 'sam.profile' not in self.env:
            return result
        if not self.env['sam.profile'].sudo()._get_debranding().get('enabled'):
            return result
        for res_id, values in result.items():
            for key in ('body_html', 'subject'):
                val = values.get(key)
                if val:
                    values[key] = _POWERED_BY_TEXT_RE.sub('', val)
        return result
