# -*- coding: utf-8 -*-
from odoo import models, SUPERUSER_ID
from odoo.exceptions import AccessDenied


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _check_credentials(self, credential, env):
        result = super()._check_credentials(credential, env)
        self._sam_check_login_allowed()
        return result

    def _sam_check_login_allowed(self):
        """密码校验通过后再检查:该用户是否被访问配置禁止登录。"""
        user = self.env.user
        if not user or user.id == SUPERUSER_ID or 'sam.profile' not in self.env:
            return
        Profile = self.env['sam.profile'].sudo()
        blocked = Profile.search([
            ('disable_login', '=', True),
            '|', ('user_ids', 'in', user.id),
            ('group_ids', 'in', user.groups_id.ids or [0]),
        ], limit=1)
        if blocked:
            raise AccessDenied()
