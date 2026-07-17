# -*- coding: utf-8 -*-
import re

from odoo import api, models

# 仅抹除 "Powered by Odoo" 文字与链接,不动任何 HTML 结构,
# 避免嵌套 <tr>/<table> 场景下正则误吞整个 body 导致预览空白。
_POWERED_BY_TEXT_RE = re.compile(
    r'Powered by\s+<a\b[^>]*href="https?://(?:www\.)?odoo\.com[^"]*"[^>]*>Odoo</a>\.?',
    re.IGNORECASE,
)


class MailTemplatePreview(models.TransientModel):
    _inherit = 'mail.template.preview'

    def _set_mail_attributes(self, values=None):
        super()._set_mail_attributes(values)
        if 'sam.profile' not in self.env:
            return
        if not self.env['sam.profile'].sudo()._get_debranding().get('enabled'):
            return
        body = self.body_html or ''
        if not body:
            return
        cleaned = _POWERED_BY_TEXT_RE.sub('', body)
        if cleaned != body:
            self.body_html = cleaned
