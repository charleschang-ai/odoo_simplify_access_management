import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

/**
 * Access Manage Studio 白标:弹窗标题中的 "Odoo" 换成品牌名。
 *
 * - Dialog 的 title 属性默认值硬编码为 "Odoo"(如"修改密码"弹窗);
 * - 错误类弹窗标题 "Odoo Error" / "Odoo Server Error" / "Odoo Warning" 等。
 * 只替换独立的 "Odoo" 单词(不动 "OdooBot" 之类的组合词)。
 */
const cfg = session.sam_debranding;
const ODOO_WORD_RE = /\bOdoo\b/g;

patch(Dialog.prototype, {
    samTitle(title) {
        const text = String(title ?? "");
        if (!cfg || !cfg.enabled || !cfg.brand) {
            return text;
        }
        return text.replace(ODOO_WORD_RE, cfg.brand);
    },
});
