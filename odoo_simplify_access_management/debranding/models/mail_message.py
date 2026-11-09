# -*- coding: utf-8 -*-
from odoo import api, models

from .. import html_debrand


class MailMessageDebranding(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        """OdooBot 在讨论频道/私聊中发出的消息去品牌。

        mail_bot 的欢迎语与引导回复(_init_odoobot / mail.bot._get_answer)
        都经 message_post 落到这里。本模块不依赖 mail_bot,无法稳定地覆盖
        它的方法(两者加载先后不确定),因此在 mail.message 创建入口统一处理,
        对机器人的任何文案、任何语言都生效。"""
        if 'sam.profile' in self.env:
            profile_model = self.env['sam.profile'].sudo()
            if profile_model._get_debranding().get('enabled'):
                root_id = self.env['ir.model.data']._xmlid_to_res_id(
                    'base.partner_root', raise_if_not_found=False)
                brand = bot_name = None
                for vals in vals_list:
                    if (not root_id or vals.get('author_id') != root_id
                            or vals.get('model') != 'discuss.channel'
                            or not vals.get('body')):
                        continue
                    if brand is None:
                        brand, bot_name = profile_model._sam_bot_branding()
                    vals['body'] = html_debrand.debrand_bot_message(
                        vals['body'], brand, bot_name)
        return super().create(vals_list)
