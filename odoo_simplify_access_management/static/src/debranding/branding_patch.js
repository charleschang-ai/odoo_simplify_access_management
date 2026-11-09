import { TitlePlugin } from "@web/core/browser/title_plugin";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

/**
 * Access Manage Studio 白标:
 * 1. 浏览器标签页标题的 "Odoo" 兜底文字换成品牌名;
 * 2. 用户菜单中移除指向 odoo.com 的项(Odoo 20: "Help" 指向
 *    session.support_url、"My Subscription";documentation / odoo_account 保留兼容)。
 */
const cfg = session.sam_debranding;

if (cfg && cfg.enabled) {
    if (cfg.brand) {
        // Odoo 20 起标题由 TitlePlugin 管理("title" service 只是待移除的兼容层,
        // 无人依赖时不会启动)。各部分用 " - " 拼接,兜底为 document.title;
        // 注册品牌名作为常驻部分:空闲显示品牌名,页面内显示 "页面 - 品牌名"。
        patch(TitlePlugin.prototype, {
            setup() {
                super.setup(...arguments);
                this.setParts({ zopenerp: cfg.brand });
            },
        });
    }

    // mysubscription(Odoo 20 新增,auto_install)的 "My Subscription" 打开
    // Odoo 官方订阅面板,相当于 19 的 "My Odoo.com account"。
    // 它与本模块无依赖关系,资源加载先后不确定:既移除已注册的项,
    // 也监听之后的注册事件,保证无论加载顺序都能移除。
    const BLOCKED_ITEMS = new Set([
        "support", "documentation", "odoo_account", "mysubscription_user_menu",
    ]);
    const userMenu = registry.category("user_menuitems");
    for (const item of BLOCKED_ITEMS) {
        if (userMenu.contains(item)) {
            userMenu.remove(item);
        }
    }
    userMenu.addEventListener("UPDATE", ({ detail }) => {
        if (detail.operation === "add" && BLOCKED_ITEMS.has(detail.key)) {
            userMenu.remove(detail.key);
        }
    });
}
