# -*- coding: utf-8 -*-
"""Access Manage Studio 白标(Debranding)子模块。

集中存放隐藏 Odoo 品牌痕迹的全部服务端逻辑:
- 登录页 "Powered by Odoo"
- 浏览器标签页标题 / PWA 应用名
- 通知邮件底部 "Powered by Odoo"
- 用户菜单中的 odoo.com 链接(前端 static/src/debranding/)
- URL 中的 /odoo 前缀替换
"""
from . import models
from . import controllers
