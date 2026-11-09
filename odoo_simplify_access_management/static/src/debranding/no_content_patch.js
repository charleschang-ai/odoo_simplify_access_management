import { onWillUpdateProps } from "@odoo/owl";
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

    // 置空用 "" 而非 null/undefined:sale 等模块的 SaleActionHelper 声明了
    // noContentHelp: String(必填),假值以外的类型在 Odoo 19 的 Owl props
    // 校验下都会报错;空字符串既合法又保持假值语义(标准模板不渲染引导内容)。
    // setup 只在首次挂载时执行,搜索条件变化等触发的 props 更新会带来新的
    // props 对象,必须在 onWillUpdateProps 里对每次更新重复置空。
    // 每个 patch 必须用独立的对象字面量:super 绑定跟随方法定义时的宿主对象
    const makeBlankHelpPatch = () => ({
        setup() {
            super.setup(...arguments);
            this.props.noContentHelp = "";
            onWillUpdateProps((nextProps) => {
                nextProps.noContentHelp = "";
            });
        },
    });
    patch(KanbanRenderer.prototype, makeBlankHelpPatch());
    patch(ListRenderer.prototype, makeBlankHelpPatch());
}
