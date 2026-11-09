import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { HomeMenu } from "@web_enterprise/webclient/home_menu/home_menu";

const cfg = session.sam_debranding || {};
const PREFIX = cfg.enabled && cfg.prefix;

if (PREFIX) {
    /**
     * 白标:企业版首页 App 图标网格的 href 中硬编码的 /odoo/ 替换为自定义前缀。
     * apps 由 computeAppsAndMenuItems 生成,菜单变化时会整体重新计算,
     * 因此不在 setup 中改写数据,而由 home_menu_patch.xml 在渲染时调用本方法。
     */
    patch(HomeMenu.prototype, {
        samAppHref(href) {
            return href && href.startsWith("/odoo/")
                ? href.replace("/odoo/", `/${PREFIX}/`)
                : href;
        },
    });
}
