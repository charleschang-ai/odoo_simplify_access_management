# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import AccessError


class BaseImportImport(models.TransientModel):
    _inherit = 'base_import.import'

    def execute_import(self, fields, columns, options, dryrun=False):
        env = self.env
        if not env.su and env.uid and 'sam.profile' in env and self.res_model:
            rules = env['sam.profile']._get_model_rules(self.res_model)
            if rules.get('hide_import') or rules.get('hide_create'):
                raise AccessError(
                    _('Import of %s is blocked by Access Manage Studio restrictions. '
                      'Contact your administrator if you have questions.') % self.res_model)
        return super().execute_import(fields, columns, options, dryrun=dryrun)
