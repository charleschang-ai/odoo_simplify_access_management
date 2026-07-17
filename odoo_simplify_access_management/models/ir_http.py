# -*- coding: utf-8 -*-
import logging

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _handle_debug(cls):
        """每次请求都强制清除被限制用户的开发者模式(含 ?debug=1 激活)。"""
        super()._handle_debug()
        try:
            env = request.env
            if (request.session.debug and env and env.uid
                    and 'sam.profile' in env):
                flags = env['sam.profile']._get_global_flags()
                if flags.get('disable_developer_mode'):
                    request.session.debug = ''
        except Exception:
            _logger.debug('Access Manage Studio debug check skipped', exc_info=True)

    def session_info(self):
        result = super().session_info()
        env = self.env
        if env.su or not env.uid or 'sam.profile' not in env:
            return result
        Profile = env['sam.profile']
        flags = Profile._get_global_flags()
        if flags.get('disable_developer_mode'):
            if request and request.session.debug:
                request.session.debug = ''
            result.get('bundle_params', {}).pop('debug', None)
        result['sam'] = {
            'chatter': Profile._get_all_chatter_rules(),
            'no_search': list(Profile._get_no_search_models()),
            'disable_developer_mode': flags.get('disable_developer_mode', False),
        }
        return result
