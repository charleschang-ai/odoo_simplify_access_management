# -*- coding: utf-8 -*-
from lxml import etree, html
from markupsafe import Markup

from odoo import _, api, models
from odoo.exceptions import AccessError

# views/mail_tracking_templates.xml 给每行追踪值包上的 class 前缀
TRACK_CLASS_PREFIX = 'o_sam_track_'


def _strip_hidden_tracking(body, hidden_fields):
    """从消息正文中移除隐藏字段对应的追踪行(含其后/前的换行)。
    整块追踪全部被移除时,连同外层 div 一起删除。"""
    if not body or TRACK_CLASS_PREFIX not in body:
        return body
    root = html.fragment_fromstring(str(body), create_parent='div')
    changed = False
    for span in root.xpath(
            '//span[starts-with(@class, "%s")]' % TRACK_CLASS_PREFIX):
        if span.get('class')[len(TRACK_CLASS_PREFIX):] not in hidden_fields:
            continue
        container = span.getparent()
        following, preceding = span.getnext(), span.getprevious()
        if following is not None and following.tag == 'br':
            following.drop_tree()
        elif preceding is not None and preceding.tag == 'br':
            preceding.drop_tree()
        span.drop_tree()
        changed = True
        if (container is not root and container.tag == 'div'
                and not container.xpath(
                    './span[starts-with(@class, "%s")]' % TRACK_CLASS_PREFIX)):
            container.drop_tree()
    if not changed:
        return body
    return Markup((root.text or '') + ''.join(
        etree.tostring(child, encoding='unicode', method='html')
        for child in root))


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


class MailMessage(models.Model):
    _inherit = 'mail.message'

    def _store_message_fields(self, res, **kwargs):
        """If a field is set to 'Hidden' by access configuration, its tracked
        value changes (e.g. Price 100 → 200) are also removed from the chatter
        log, preventing sensitive field values from leaking via tracking.

        Odoo 20 no longer keeps tracking values in a separate model at display
        time: they are rendered into the message body when posted. The body is
        therefore filtered per viewer right before it is sent to the client."""
        super()._store_message_fields(res, **kwargs)
        env = self.env
        if env.su or not env.uid or 'sam.profile' not in env:
            return
        Profile = env['sam.profile']
        if not Profile._get_profile_ids():
            return
        hidden_by_model = {}

        def filtered_body(message):
            model = message.model
            if not model:
                return message.body
            if model not in hidden_by_model:
                hidden_by_model[model] = {
                    name for name, invisible, *_rest
                    in Profile._get_field_rules(model) if invisible}
            if not hidden_by_model[model]:
                return message.body
            return _strip_hidden_tracking(message.body, hidden_by_model[model])

        res.attr('body', filtered_body)


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
