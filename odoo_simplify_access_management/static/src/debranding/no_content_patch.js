import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { ListRenderer } from "@web/views/list/list_renderer";

const cfg = session.sam_debranding || {};

if (cfg.enabled) {
    /**
     * 白标:隐藏 kanban / list 视图空状态下的 Odoo 引导 demo video。
     *
     * - Python 层已剥离 action.help → 标准模板走 web.NoContentHelper（纯文本）
     * - CSS 注入强制隐藏硬编码视频元素（SaleActionHelper 等自定义模板无法被
     *   Python 覆盖的部分）
     * - setup() 中再次置空 noContentHelp 作为兜底
     */
    const style = document.createElement("style");
    style.textContent = [
        ".o_sale_action_preview",
        ".o_view_nocontent iframe",
    ].join(", ") + " { display: none !important; }";
    document.head.appendChild(style);

    patch(KanbanRenderer.prototype, {
        setup() {
            super.setup(...arguments);
            this.props.noContentHelp = null;
        },
    });
    patch(ListRenderer.prototype, {
        setup() {
            super.setup(...arguments);
            this.props.noContentHelp = null;
        },
    });
}
