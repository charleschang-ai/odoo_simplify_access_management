# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import AccessError


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _sam_chatter_rules(self):
        env = self.env
        if env.su or not env.uid or 'sam.profile' not in env:
            return {}
        return env['sam.profile']._get_chatter_rules(self._name)

    def message_post(self, **kwargs):
        rules = self._sam_chatter_rules()
        if rules:
            subtype_xmlid = kwargs.get('subtype_xmlid')
            subtype_id = kwargs.get('subtype_id')
            comment_id = self.env['ir.model.data']._xmlid_to_res_id(
                'mail.mt_comment', raise_if_not_found=False)
            is_comment = subtype_xmlid == 'mail.mt_comment' or (
                subtype_id and subtype_id == comment_id)
            if is_comment and rules.get('hide_send_message'):
                raise AccessError(_('You are not allowed to send messages on %s.') % self._description)
            if not is_comment and rules.get('hide_log_note'):
                raise AccessError(_('You are not allowed to log notes on %s.') % self._description)
        return super().message_post(**kwargs)


class MailTrackingValue(models.Model):
    _inherit = 'mail.tracking.value'

    def _filter_has_field_access(self, env):
        """If a field is set to 'Hidden' by access configuration, its tracked
        value changes (e.g. Price 100 → 200) are also removed from the chatter
        log, preventing sensitive field values from leaking via tracking."""
        result = super()._filter_has_field_access(env)
        if env.su or not env.uid or 'sam.profile' not in env:
            return result
        Profile = env['sam.profile']
        hidden_by_model = {}

        def is_visible(tracking):
            if tracking.field_id:
                model, fname = tracking.field_id.model, tracking.field_id.name
            else:
                info = tracking.field_info or {}
                model, fname = tracking.mail_message_id.model, info.get('name')
            if not model or not fname:
                return True
            if model not in hidden_by_model:
                hidden_by_model[model] = {
                    name for name, invisible, *_rest
                    in Profile._get_field_rules(model) if invisible}
            return fname not in hidden_by_model[model]

        return result.filtered(is_visible)


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model_create_multi
    def create(self, vals_list):
        env = self.env
        if not env.su and env.uid and 'sam.profile' in env:
            Profile = env['sam.profile']
            for vals in vals_list:
                model = vals.get('res_model')
                if not model and vals.get('res_model_id'):
                    model = env['ir.model'].sudo().browse(vals['res_model_id']).model
                if model and Profile._get_chatter_rules(model).get('hide_activities'):
                    raise AccessError(_('You are not allowed to schedule activities on %s.') % model)
        return super().create(vals_list)
