# -*- coding: utf-8 -*-
from . import models
from . import controllers
from . import debranding


def uninstall_hook(env):
    """卸载清理:恢复模块在核心数据上留下的运行时修改。

    - 记录权限行(sam.domain.line)运行时创建的全局 ir.access 限制没有
      XML id,卸载不会自动删除;残留限制会继续对所有用户生效,必须手工清掉。
      (自有模型的表由卸载流程直接 DROP,不走 ORM unlink,Python 里的
      级联删除逻辑不会被触发。)
    - 白标写入的 PWA 应用名参数(web.web_app_name)恢复默认。
    - 白标改过名的机器人(base.partner_root)恢复为 OdooBot。
    - 白标改过名的 Odoo 自带数据记录(AI 助手、用户组)恢复原名称。
    模块自带的 XML 数据(用户组、privilege、白标继承视图等)由卸载流程
    按 ir.model.data 自动删除,无需处理。
    """
    from .models.sam_profile import _sam_restore_bot_name, _sam_unset_web_app_name

    # 钩子在 module_uninstall() 之前执行,模块模型仍可用:
    # 优先按 access_id 精确删除,名称前缀匹配兜底清理历史孤儿记录
    accesses = env['ir.access'].sudo().with_context(active_test=False).search(
        [('name', '=like', 'Access Manage Studio:%')])
    if 'sam.domain.line' in env:
        lines = env['sam.domain.line'].sudo().with_context(
            active_test=False).search([])
        accesses |= lines.access_id.sudo()
    if accesses:
        accesses.unlink()
    _sam_unset_web_app_name(env)
    _sam_restore_bot_name(env)
    if 'sam.profile' in env:
        env['sam.profile'].sudo()._sam_sync_record_branding(False)
