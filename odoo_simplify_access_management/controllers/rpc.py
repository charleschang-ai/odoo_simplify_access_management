# -*- coding: utf-8 -*-
import logging
import xmlrpc.client

from odoo import SUPERUSER_ID
from odoo.exceptions import AccessDenied
from odoo.http import request, route
from odoo.modules.registry import Registry

# Odoo 19: RPC 控制器从 odoo.addons.base.controllers.rpc 移到了独立的 rpc 模块
from odoo.addons.rpc.controllers import RPC
from odoo.addons.rpc.controllers.json2 import WebJson2Controller

_logger = logging.getLogger(__name__)


def _sam_check_rpc_allowed(db, uid):
    """外部 RPC(object 服务)调用前检查用户是否被禁用 XML-RPC/脚本。"""
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return
    if not db or not uid or uid == SUPERUSER_ID:
        return
    try:
        registry = Registry(db)
        if 'sam.profile' not in registry:
            return
        with registry.cursor() as cr:
            # Odoo 19: res_groups_users_rel 仅存显式成员,隐含组不再物化,
            # 需沿 res_groups_implied_rel 递归展开用户的全部组
            cr.execute("""
                WITH RECURSIVE user_groups(gid) AS (
                    SELECT gid FROM res_groups_users_rel WHERE uid = %s
                     UNION
                    SELECT r.hid
                      FROM res_groups_implied_rel r
                      JOIN user_groups ug ON ug.gid = r.gid
                )
                SELECT 1
                  FROM sam_profile p
                 WHERE p.active
                   AND p.restrict_xmlrpc
                   AND (
                        EXISTS (SELECT 1 FROM sam_profile_user_rel r
                                 WHERE r.profile_id = p.id AND r.user_id = %s)
                     OR EXISTS (SELECT 1 FROM sam_profile_group_rel g
                                 WHERE g.profile_id = p.id
                                   AND g.group_id IN (SELECT gid FROM user_groups))
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
    """拦截旧版 /xmlrpc、/xmlrpc/2、/jsonrpc 入口(Odoo 19 中已标记弃用)。"""

    def _xmlrpc(self, service):
        if service == 'object':
            data = request.httprequest.get_data()
            params, _method = xmlrpc.client.loads(data, use_datetime=True)
            if params and len(params) >= 2:
                _sam_check_rpc_allowed(params[0], params[1])
        return super()._xmlrpc(service)

    # 无参 @route() 继承父类路由(Odoo 19 中 type 已由 'json' 改为 'jsonrpc')
    @route()
    def jsonrpc(self, service, method, args):
        if service == 'object' and args and len(args) >= 2:
            _sam_check_rpc_allowed(args[0], args[1])
        return super().jsonrpc(service, method, args)


class WebJson2Sam(WebJson2Controller):
    """拦截 Odoo 19 新增的 /json/2/<model>/<method> 外部 API(bearer 认证)。"""

    @route()
    def web_json_2_rpc(self, __model__, __method__, **kwargs):
        _sam_check_rpc_allowed(request.db, request.env.uid)
        return super().web_json_2_rpc(__model__, __method__, **kwargs)
