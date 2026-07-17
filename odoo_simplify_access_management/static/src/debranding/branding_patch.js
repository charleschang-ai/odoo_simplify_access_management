import { registry } from "@web/core/registry";
import { session } from "@web/session";

/**
 * Access Manage Studio 白标:
 * 1. 浏览器标签页标题的 "Odoo" 兜底文字换成品牌名;
 * 2. 用户菜单中移除指向 odoo.com 的项(文档、支持、My Odoo.com account)。
 */
const cfg = session.sam_debranding;

if (cfg && cfg.enabled) {
    const serviceRegistry = registry.category("services");

    if (cfg.brand && serviceRegistry.contains("title")) {
        const titleService = serviceRegistry.get("title");
        const originalStart = titleService.start;
        titleService.start = function (...args) {
            const api = originalStart.apply(this, args);
            // title service 将各部分用 " - " 拼接,兜底为 "Odoo";
            // 注册品牌名作为常驻部分:空闲显示品牌名,页面内显示 "页面 - 品牌名"。
            api.setParts({ zopenerp: cfg.brand });
            return api;
        };
    }

    const userMenu = registry.category("user_menuitems");
    for (const item of ["documentation", "support", "odoo_account"]) {
        if (userMenu.contains(item)) {
            userMenu.remove(item);
        }
    }
}
