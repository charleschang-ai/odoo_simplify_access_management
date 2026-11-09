# -*- coding: utf-8 -*-
################################################################################
#
#    Author: Da Lei
#
################################################################################
{
    'name': 'Access Manage Studio | Odoo Simplify Access Management',
    'version': '19.0.1.9.0',
    'category': 'Extra Tools',
    'summary': 'All in one access management: hide/readonly fields, models, '
               'menus, records, filters, buttons/tabs, views, actions, '
               'reports, chatter; disable developer mode, import/export, '
               'module install and XML-RPC per user.Remove white label: '
               'The most comprehensive guide to removing the "odoo" label from the system.',
    'description': """
Access Manage Studio
====================
Integrated Access Control: Control by user/user group/company in one place:

* Model: Prohibit creation/editing/deletion/copying/archiving/exporting/importing, or make the entire model read-only.

* Field: Hide/read-only/required.

* Record: Restrict visibility and operability of records by domain.

* Menu: Hide any menu and its submenus.

* Buttons/tabs, filters/groups, view types, reports/actions.

* Communication Bar: Hide sending messages/record notes/activities.

* Global: Disable developer mode, prohibit module installation/upgrade/uninstallation, disable import/export, disable XML-RPC scripts.

* Remove white label: The most comprehensive guide to removing the "odoo" label from the system.
一体化访问权限管理:在一个地方按用户/用户组/公司控制:

* 模型:禁止创建 / 编辑 / 删除 / 复制 / 归档 / 导出 / 导入,或整体只读
* 字段:隐藏 / 只读 / 必填
* 记录:按域(Domain)限制可见与可操作的记录
* 菜单:隐藏任意菜单与其子菜单
* 按钮 / 页签、筛选 / 分组、视图类型、报表 / 动作
* 沟通栏:隐藏发送消息 / 记录备注 / 活动
* 全局:禁用开发者模式、禁止安装/升级/卸载模块、禁用导入导出、禁用 XML-RPC 脚本
* 去除白标： 最全的移除系统中的odoo字眼
""",
    'author': 'Don Shan',
    'maintainer': 'Don Shan',
    'website': '',
    'license': 'LGPL-3',
    # portal: debranding_templates.xml 继承 portal.portal_record_sidebar,
    # 缺少该依赖时在未装 portal 的新库上安装会失败
    # rpc: Odoo 19 起 /xmlrpc、/jsonrpc 控制器位于独立的 rpc 模块
    # base_setup: 白标需隐藏设置页的 About 区块(res_config_edition)
    'depends': ['web', 'mail', 'base_import', 'bus', 'portal', 'rpc',
                'base_setup'],
    'data': [
        'security/sam_security.xml',
        'security/ir.model.access.csv',
        'views/sam_profile_views.xml',
        'debranding/views/debranding_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo_simplify_access_management/static/src/**/*',
        ],
    },
    'uninstall_hook': 'uninstall_hook',
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'price': 99,
    'currency': "USD",
}
