import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { ActionHelper } from "@web/views/action_helper";

const cfg = session.sam_debranding || {};

if (cfg.enabled) {
    /**
     * 白标:隐藏 kanban / list 视图空状态下的 Odoo 引导 demo video。
     *
     * - Python 层已剥离 action.help → 标准 ActionHelper 走纯文本默认提示
     * - CSS 注入强制隐藏硬编码视频元素（SaleActionHelper 等自定义组件无法被
     *   Python 覆盖的部分）
     * - ActionHelper 始终显示默认提示作为兜底(动作 help 来自其他途径时)
     *
     * Odoo 20 / OWL 3 的 props 是只读 getter,不能再像 19 那样在渲染器
     * setup 里给 this.props.noContentHelp 赋值(严格模式下会直接抛错)。
     */
    // 选择器必须保持两级(0,2,0)以上的优先级:视频缩略图 <a> 上带有
    // Bootstrap 的 d-inline-block(display:inline-block !important),
    // 单类选择器与它同优先级时生效与否取决于样式表顺序,不可靠。
    // a[class*="_action_preview"] 兼容 sale 之外同命名习惯的模块。
    const style = document.createElement("style");
    style.textContent = [
        ".o_view_nocontent .o_sale_action_preview",
        '.o_view_nocontent a[class*="_action_preview"]',
        ".o_view_nocontent iframe",
        ".o_view_nocontent video",
    ].join(", ") + " { display: none !important; }";
    document.head.appendChild(style);

    patch(ActionHelper.prototype, {
        get showDefaultHelper() {
            return true;
        },
    });
}
