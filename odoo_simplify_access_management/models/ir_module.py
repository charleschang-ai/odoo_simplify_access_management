# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import AccessError


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def _sam_check_module_actions(self):
        env = self.env
        if env.su or not env.uid or 'sam.profile' not in env:
            return
        flags = env['sam.profile']._get_global_flags()
        if flags.get('disable_module_actions'):
            raise AccessError(
                _('You are not allowed to install/upgrade/uninstall modules '
                  'due to Access Manage Studio restrictions. '
                  'Contact your administrator if you have questions.'))

    def button_install(self):
        self._sam_check_module_actions()
        return super().button_install()

    def button_immediate_install(self):
        self._sam_check_module_actions()
        return super().button_immediate_install()

    def button_upgrade(self):
        self._sam_check_module_actions()
        return super().button_upgrade()

    def button_immediate_upgrade(self):
        self._sam_check_module_actions()
        return super().button_immediate_upgrade()

    def button_uninstall(self):
        self._sam_check_module_actions()
        return super().button_uninstall()

    def button_immediate_uninstall(self):
        self._sam_check_module_actions()
        return super().button_immediate_uninstall()
