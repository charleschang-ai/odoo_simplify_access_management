# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, models

_logger = logging.getLogger(__name__)

# 仅抹除 "Powered by Odoo" 文字与链接,不动 HTML 结构。
# 避免嵌套表格场景下正则误吞整个 body。
_POWERED_BY_TEXT_RE = re.compile(
    r'Powered by\s+<a\b[^>]*href="https?://(?:www\.)?odoo\.com[^"]*"[^>]*>Odoo</a>\.?',
    re.IGNORECASE,
)


class MailRenderMixin(models.AbstractModel):
    _inherit = 'mail.render.mixin'

    @api.model
    def _render_template_postprocess(self, model, rendered):
        rendered = super()._render_template_postprocess(model, rendered)
        if 'sam.profile' not in self.env:
            return rendered
        if not self.env['sam.profile'].sudo()._get_debranding().get('enabled'):
            return rendered
        # 白标:从所有发出邮件的 HTML 中移除 "Powered by Odoo" 品牌文字与链接
        for res_id, html in rendered.items():
            cleaned = _POWERED_BY_TEXT_RE.sub('', html)
            if cleaned != html:
                _logger.info("debrand: stripped 'Powered by Odoo' from mail for res_id=%s", res_id)
            rendered[res_id] = cleaned
        return rendered
