# -*- coding: utf-8 -*-
from . import models
from . import controllers
from . import debranding


def uninstall_hook(env):
    """卸载清理:恢复模块在核心数据上留下的运行时修改。

    - 记录权限行(sam.domain.line)运行时创建的全局 ir.rule 没有 XML id,
      卸载不会自动删除;残留规则会继续对所有用户生效,必须手工清掉。
      (自有模型的表由卸载流程直接 DROP,不走 ORM unlink,Python 里的
      级联删除逻辑不会被触发。)
    - 白标写入的 PWA 应用名参数(web.web_app_name)恢复默认。
      (set_param 传假值即删除该参数。)
    模块自带的 XML 数据(用户组、privilege、白标继承视图等)由卸载流程
    按 ir.model.data 自动删除,无需处理。
    """
    # 钩子在 module_uninstall() 之前执行,模块模型仍可用:
    # 优先按 rule_id 精确删除,名称前缀匹配兜底清理历史孤儿规则
    rules = env['ir.rule'].sudo().with_context(active_test=False).search(
        [('name', '=like', 'Access Manage Studio:%')])
    if 'sam.domain.line' in env:
        lines = env['sam.domain.line'].sudo().with_context(
            active_test=False).search([])
        rules |= lines.rule_id.sudo()
    if rules:
        rules.unlink()
    env['ir.config_parameter'].sudo().set_param('web.web_app_name', False)
