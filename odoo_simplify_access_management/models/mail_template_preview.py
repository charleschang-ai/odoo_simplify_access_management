# -*- coding: utf-8 -*-
from odoo import models

from ..debranding import const, html_debrand


class MailTemplatePreview(models.TransientModel):
    _inherit = 'mail.template.preview'

    def _set_mail_attributes(self, values=None):
        """未选中记录的预览直接拷贝模板原始 body_html,不经渲染管道,
        这里单独兜底移除 "Powered by Odoo" 品牌区块。"""
        super()._set_mail_attributes(values)
        if self.body_html and const.is_debranding_enabled(self.env):
            cleaned = html_debrand.remove_odoo_branding(self.body_html)
            if cleaned != self.body_html:
                self.body_html = cleaned
