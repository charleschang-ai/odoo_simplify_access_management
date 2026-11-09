# -*- coding: utf-8 -*-
from odoo import models

from ..debranding import const, html_debrand


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def _prepare_outgoing_body(self):
        """所有外发邮件的最终出口(含不经 mail.template 的 QWeb 渲染邮件:
        digest 摘要、登录安全提醒等),白标启用时兜底移除
        "Powered by Odoo" 品牌区块。"""
        body = super()._prepare_outgoing_body()
        if body and const.is_debranding_enabled(self.env):
            body = html_debrand.remove_odoo_branding(body)
        return body
