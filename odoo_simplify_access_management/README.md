# Access Manage Studio | Odoo Simplify Access Management

## 简介

一体化访问权限管理:在一个地方按 **用户 / 用户组 / 公司** 控制 Odoo 中用户能看到什么、能做什么。
无需技术技能,几次点击即可完成配置。

菜单入口:**Access Manage Studio**(仅 "Access Manage Studio / 管理员" 组可见,admin 默认已加入)。

## 功能

在一条「访问配置」(sam.profile) 中,通过各页签集中设置:

| 页签 / 选项 | 能力 |
|---|---|
| 隐藏菜单 | 隐藏任意菜单,子菜单自动一并隐藏 |
| 模型权限 | 按模型禁止 创建 / 编辑 / 删除 / 复制 / 归档 / 导出 / 导入,或一键整体只读 |
| 字段权限 | 按字段设置 隐藏 / 只读 / 必填(含内嵌子视图,服务端同步强制);关系字段可 去除内部链接、禁止「新建/创建并编辑」选项 |
| 记录权限 | 按域(Domain)限制可见与可操作的记录,自动同步为真正的 `ir.rule` 记录规则(数据级强制,已知 id 直接读取同样被拦截),读/写/建/删可分别勾选,支持 `user` / `uid` / `company_id` / `company_ids` / `time` 变量 |
| 按钮/页签 | 按技术名称或显示文字隐藏任意按钮、智能按钮、页签 |
| 筛选/分组 | 隐藏搜索视图中的任意筛选与分组项 |
| 隐藏视图 | 按模型隐藏视图类型(列表/看板/透视/图表等) |
| 沟通栏 | 按模型或全局(所有模型)隐藏整个沟通栏,或单独禁止 发送消息 / 记录备注 / 安排活动(前端隐藏 + 服务端强制) |
| 报表/动作 | 从打印菜单 / 操作菜单中隐藏指定报表与动作 |
| 全局限制 | 全部只读、禁用开发者模式(含 `?debug=1`)、禁止安装/升级/卸载模块、禁用导入/导出、禁用 XML-RPC / 外部脚本、禁止登录、隐藏个人资料中的通知设置(浏览器"通知被阻止"横幅与通知处理方式,含 API 写入拦截) |
| 白标 | 全局隐藏 Odoo 品牌:登录页 "Powered by Odoo"、浏览器标签页标题与图标(Favicon)、通知邮件底部品牌、用户菜单 odoo.com 链接、PWA 应用名、门户侧栏品牌、设置页 About 区块;销售/采购门户单据页的 "Connect with your software!" 按钮与推广弹窗(sale/purchase 非本模块依赖,由 `static/debranding/portal_debrand.css` 按元素 id 隐藏,对应 `ir.asset` 随开关启停);导入界面的 "Import FAQ" / "Go to Import FAQ" 文档链接(`static/debranding/backend_debrand.css`);隐藏导入界面的 Excel 模板下载按钮与右侧栏 Help 区块(部分模板如会计凭证在末页 Instructions 里写死了大段 Odoo 说明,文件无法改写;CSS 隐藏,不动 `get_import_templates()` 接口,外部集成不受影响);可将网址中的 /odoo 前缀替换为自定义词(旧链接自动 301 跳转);白标逻辑独立存放于 `debranding/` 目录 |
| 邮件去品牌 | 白标启用时,所有外发邮件与模板预览自动整块移除正文中的 "Powered by Odoo" 区块(灰色横带一并去除,支持所有语言翻译,如中文"由Odoo驱动");另提供"一键移除所有邮件模板中的 Powered by Odoo"按钮,把存量模板正文(含各语言)也清理干净,模板编辑器里看到的即为最终效果;实现见 `debranding/html_debrand.py`(渲染/发送/预览四个公共出口统一拦截) |

要点:

- 应用范围支持多用户、多用户组、多公司;公司留空表示全部公司生效。
- 全部限制在**服务端强制**(ORM 层拦截),绕过界面直接调用接口同样被拒绝。
- 超级用户(SUPERUSER)始终不受限制;未列入配置的用户完全不受影响。
- 配置修改即时生效(自动清理缓存),无需重启。

## 版本

- Odoo 18.0
- 模块版本 18.0.1.0.1
- 依赖:`web`、`mail`、`base_import`

## 安装

1. 将本模块放入 Odoo 的 addons 路径。
2. 更新应用列表并安装 **Access Manage Studio | Odoo Simplify Access Management**。
3. 打开菜单 **Access Manage Studio**,创建访问配置并选择应用用户即可。

## 作者

Don Shan
