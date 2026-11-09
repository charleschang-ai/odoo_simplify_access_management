import { markup } from "@odoo/owl";
import { RedirectWarningDialog, WarningDialog } from "@web/core/errors/error_dialogs";
import { LazyTranslatedString } from "@web/core/l10n/translation";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";
import { isMarkup } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";

/**
 * Access Manage Studio 白标:后台界面文字中的 "Odoo" 统一换成品牌名。
 *
 * 1. 翻译出口(LazyTranslatedString.translate):JS 里的 _t() 与 OWL 模板
 *    中的静态文字/可翻译属性都经此处取译文(未翻译时返回原文),一处覆盖
 *    整个后台界面的所有语言;
 * 2. 服务端抛出的业务提示(UserError 等 → WarningDialog / RedirectWarningDialog);
 * 3. 通知(右上角弹出的 notification)的标题与正文。
 *
 * 只替换独立的 "Odoo" 单词:不动 "odoo.com" 等域名、"OdooBot" 等组合词,
 * 也不碰用户录入的业务数据(记录字段值不经过以上出口)。
 */
const cfg = session.sam_debranding;
const BRAND = cfg && cfg.enabled ? cfg.brand : "";
const ODOO_WORD_RE = /\bOdoo\b(?!\.(?:com|sh)\b)/g;

export function samDebrandText(value) {
    if (!BRAND || !value || !(typeof value === "string" || value instanceof String)) {
        return value;
    }
    const text = String(value);
    ODOO_WORD_RE.lastIndex = 0;
    if (!ODOO_WORD_RE.test(text)) {
        return value;
    }
    const replaced = text.replace(ODOO_WORD_RE, () => BRAND);
    return isMarkup(value) ? markup(replaced) : replaced;
}

if (BRAND) {
    patch(LazyTranslatedString.prototype, {
        translate() {
            return samDebrandText(super.translate(...arguments));
        },
    });

    for (const DialogClass of [WarningDialog, RedirectWarningDialog]) {
        patch(DialogClass.prototype, {
            setup() {
                super.setup(...arguments);
                this.message = samDebrandText(this.message);
            },
        });
    }

    patch(NotificationPlugin.prototype, {
        add(message, options = {}) {
            if (options.title) {
                options = { ...options, title: samDebrandText(options.title) };
            }
            return super.add(samDebrandText(message), options);
        },
    });
}
