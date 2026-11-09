# -*- coding: utf-8 -*-
from odoo import api, models

from ..debranding import const, html_debrand


class MailRenderMixin(models.AbstractModel):
    _inherit = 'mail.render.mixin'

    @api.model
    def _render_template_postprocess(self, model, rendered):
        """白标:所有走渲染后处理的邮件 HTML(模板邮件、群发等)
        整块移除 "Powered by Odoo" 品牌区块。"""
        rendered = super()._render_template_postprocess(model, rendered)
        if const.is_debranding_enabled(self.env):
            for res_id, html in rendered.items():
                rendered[res_id] = html_debrand.remove_odoo_branding(html)
        return rendered
