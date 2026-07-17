# -*- coding: utf-8 -*-
from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug=debug)
        env = self.env
        if env.su or not env.uid or 'sam.profile' not in env:
            return visible
        hidden = env['sam.profile']._get_hidden_menu_ids()
        if hidden:
            # 不能修改 super 返回的缓存对象,必须生成新集合
            visible = set(visible) - set(hidden)
        return visible
