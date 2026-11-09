# -*- coding: utf-8 -*-
from odoo import _, models, SUPERUSER_ID
from odoo.exceptions import AccessDenied, AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, vals):
        # "隐藏个人资料通知设置"的写入拦截必须在这里做:核心 res.users.write
        # 对用户改自己的偏好字段(SELF_WRITEABLE_FIELDS 含 notification_type)
        # 会先 sudo 提权再进写链路,base 层的通用字段拦截(遇 su 放行)拦不到。
        if ('notification_type' in vals and not self.env.su and self.env.uid
                and 'sam.profile' in self.env
                and self.env['sam.profile']._get_global_flags().get(
                    'hide_notification_settings')):
            raise AccessError(
                _('Changing the notification handling setting is restricted '
                  'by Access Manage Studio. Contact your administrator if '
                  'you have questions.'))
        return super().write(vals)

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
            ('group_ids', 'in', user.all_group_ids.ids or [0]),
        ], limit=1)
        if blocked:
            raise AccessDenied()
