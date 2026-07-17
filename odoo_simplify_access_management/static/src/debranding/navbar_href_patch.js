import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { NavBar } from "@web/webclient/navbar/navbar";

const cfg = session.sam_debranding || {};
const PREFIX = cfg.enabled && cfg.prefix;

if (PREFIX) {
    /**
     * 白标:将菜单/应用图标的 href 中硬编码的 /odoo/ 替换为自定义前缀。
     * 浏览器状态栏与右键复制链接地址不再显示 odoo 字样。
     */
    patch(NavBar.prototype, {
        getMenuItemHref(payload) {
            const original = super.getMenuItemHref(payload);
            return original.replace("/odoo/", `/${PREFIX}/`);
        },
    });
}
