# -*- coding: utf-8 -*-
import logging
import xmlrpc.client

from odoo import SUPERUSER_ID
from odoo.exceptions import AccessDenied
from odoo.http import request, route
from odoo.modules.registry import Registry

from odoo.addons.base.controllers.rpc import RPC

_logger = logging.getLogger(__name__)


def _sam_check_rpc_allowed(db, uid):
    """外部 RPC(object 服务)调用前检查用户是否被禁用 XML-RPC/脚本。"""
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return
    if not uid or uid == SUPERUSER_ID:
        return
    try:
        registry = Registry(db)
        if 'sam.profile' not in registry:
            return
        with registry.cursor() as cr:
            cr.execute("""
                SELECT 1
                  FROM sam_profile p
                 WHERE p.active
                   AND p.restrict_xmlrpc
                   AND (
                        EXISTS (SELECT 1 FROM sam_profile_user_rel r
                                 WHERE r.profile_id = p.id AND r.user_id = %s)
                     OR EXISTS (SELECT 1 FROM sam_profile_group_rel g
                                  JOIN res_groups_users_rel gu ON gu.gid = g.group_id
                                 WHERE g.profile_id = p.id AND gu.uid = %s)
                   )
                 LIMIT 1
            """, (uid, uid))
            if cr.fetchone():
                raise AccessDenied(
                    'XML-RPC/JSON-RPC access is disabled for this user '
                    'by Access Manage Studio.')
    except AccessDenied:
        raise
    except Exception:  # 数据库/表未就绪等情况不拦截
        _logger.debug('Access Manage Studio RPC check skipped', exc_info=True)


class RPCSam(RPC):

    def _xmlrpc(self, service):
        if service == 'object':
            data = request.httprequest.get_data()
            params, _method = xmlrpc.client.loads(data, use_datetime=True)
            if params and len(params) >= 2:
                _sam_check_rpc_allowed(params[0], params[1])
        return super()._xmlrpc(service)

    @route('/jsonrpc', type='json', auth='none', save_session=False)
    def jsonrpc(self, service, method, args):
        if service == 'object' and args and len(args) >= 2:
            _sam_check_rpc_allowed(args[0], args[1])
        return super().jsonrpc(service, method, args)
