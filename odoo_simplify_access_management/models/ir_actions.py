# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.http import request


class IrActionsActions(models.Model):
    _inherit = 'ir.actions.actions'

    @api.model
    def get_bindings(self, model_name):
        """Filter hidden reports (print menu) and actions (action menu)."""
        result = super().get_bindings(model_name)
        env = self.env
        if env.su or not env.uid or 'sam.profile' not in env:
            return result
        hidden = env['sam.profile']._get_hidden_binding_action_ids()
        if not hidden:
            return result
        filtered = {}
        for binding_type, actions in result.items():
            filtered[binding_type] = [
                action for action in actions if action.get('id') not in hidden]
        return filtered


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    def _get_action_dict(self):
        """Hide view types (list/kanban/pivot etc.) per user config, and strip
        help field when white-label debranding is enabled."""
        result = super()._get_action_dict()

        # White label: clear action help (remove Odoo branding guide videos/links in empty states)
        if 'sam.profile' in self.env:
            if self.env['sam.profile']._get_debranding().get('enabled'):
                result.pop('help', None)

        res_model = result.get('res_model')
        if not res_model:
            return result
        # 动作加载走 sudo,需要回到真实请求用户的环境判断规则
        env = self.env
        if env.su:
            # request 是 werkzeug LocalProxy,永远不为 None;无 HTTP 请求时
            # (定时任务、邮件网关、脚本)其真值为 False,访问属性会抛
            # RuntimeError: request not bound
            if not request or not request.session or not request.session.uid:
                return result
            env = request.env
        if env.su or not env.uid or 'sam.profile' not in env:
            return result
        hidden = env['sam.profile']._get_hidden_view_types(res_model)
        if not hidden:
            return result

        views = result.get('views') or []
        kept = [(vid, vtype) for vid, vtype in views if vtype not in hidden]
        if views and not kept:
            # 全部被隐藏时至少保留第一个,避免动作无法打开
            kept = views[:1]
        result['views'] = kept
        if result.get('view_mode'):
            modes = [m for m in result['view_mode'].split(',') if m not in hidden]
            if not modes:
                modes = result['view_mode'].split(',')[:1]
            result['view_mode'] = ','.join(modes)
        return result
