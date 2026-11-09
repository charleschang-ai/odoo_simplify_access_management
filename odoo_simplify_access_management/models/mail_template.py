# -*- coding: utf-8 -*-
from odoo import api, models

from ..debranding import const, html_debrand


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    @api.model
    def _generate_template(self, res_ids, render_fields,
                           find_or_create_partners=False):
        """统一出口:邮件模板渲染(发送+选中记录的预览)经此方法,
        白标启用时整块移除正文中的 "Powered by Odoo" 品牌区块。"""
        result = super()._generate_template(
            res_ids, render_fields,
            find_or_create_partners=find_or_create_partners,
        )
        if const.is_debranding_enabled(self.env):
            for values in result.values():
                if values.get('body_html'):
                    values['body_html'] = html_debrand.remove_odoo_branding(
                        values['body_html'])
        return result
