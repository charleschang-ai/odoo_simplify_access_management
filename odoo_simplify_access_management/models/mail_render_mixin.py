# -*- coding: utf-8 -*-
from odoo import api, models

from ..debranding import const, html_debrand


class MailRenderMixin(models.AbstractModel):
    _inherit = 'mail.render.mixin'

    @api.model
    def _render_template_postprocess(self, model, rendered):
        """白标:所有走渲染后处理的邮件 HTML(模板邮件、群发、digest 等)
        整块移除 "Powered by Odoo" 品牌区块与 Odoo App 推广。

        digest 提示(digest.tip)全部是 Odoo 自身的推广内容(连接 Gmail/Outlook
        插件、下载 Odoo App 等,链接指向 odoo.com),白标启用时不再发送:
        提示在这里清空,digest 正文里因此留下的空行在 digest.digest 渲染时去掉。
        digest 不是本模块依赖,这里只按模型名判断,未安装时不会命中。"""
        rendered = super()._render_template_postprocess(model, rendered)
        if const.is_debranding_enabled(self.env):
            for res_id, html in rendered.items():
                if model == 'digest.tip':
                    rendered[res_id] = html.__class__('')
                    continue
                html = html_debrand.remove_odoo_branding(html)
                if model == 'digest.digest':
                    html = html_debrand.remove_empty_digest_tips(html)
                rendered[res_id] = html
        return rendered
