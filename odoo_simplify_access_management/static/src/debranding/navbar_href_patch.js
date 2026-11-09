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
        /**
         * 导航栏左上角"返回主界面"按钮(o_menu_toggle,企业版九宫格图标)与
         * 移动端 All Apps 按钮的 href:模板里硬编码 /odoo,由
         * navbar_home_patch.xml 改为读取此 getter(未启用白标时模板回退 /odoo)。
         */
        get samHomeHref() {
            return `/${PREFIX}`;
        },
    });
}
