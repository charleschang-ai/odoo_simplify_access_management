import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { HomeMenu } from "@web_enterprise/webclient/home_menu/home_menu";

const cfg = session.sam_debranding || {};
const PREFIX = cfg.enabled && cfg.prefix;

if (PREFIX) {
    /**
     * 白标:企业版首页 App 图标网格的 href 中硬编码的 /odoo/ 替换为自定义前缀。
     * home_menu_service.js 通过 computeAppsAndMenuItems 生成 app 数据，
     * 其中 href 固定为 /odoo/...，在此将 props 中的 href 统一改写。
     */
    patch(HomeMenu.prototype, {
        setup() {
            super.setup(...arguments);
            for (const app of this.props.apps) {
                if (app.href && app.href.startsWith("/odoo/")) {
                    app.href = app.href.replace("/odoo/", `/${PREFIX}/`);
                }
            }
        },
    });
}
