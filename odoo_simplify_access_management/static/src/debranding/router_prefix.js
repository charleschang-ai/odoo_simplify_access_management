import { browser } from "@web/core/browser/browser";
import { router, startRouter } from "@web/core/browser/router";
import { session } from "@web/session";

/**
 * Access Manage Studio 白标:地址栏 URL 中的 /odoo 前缀替换为自定义前缀。
 * 服务端由 ir.http._generate_routing_rules 复制路由,这里让前端 router
 * 生成/解析新前缀的 URL。
 */
const cfg = session.sam_debranding || {};
const PREFIX = cfg.enabled && cfg.prefix;
const RESERVED = ["web", "odoo", "scoped_app"];

if (PREFIX && !RESERVED.includes(PREFIX)) {
    const PREFIX_PATH = `/${PREFIX}`;
    const { stateToUrl, urlToState } = router;

    router.stateToUrl = function (state) {
        const url = stateToUrl.call(this, state);
        return url === "/odoo" || url.startsWith("/odoo/") || url.startsWith("/odoo?")
            ? PREFIX_PATH + url.slice("/odoo".length)
            : url;
    };

    router.urlToState = function (urlObj) {
        // 原解析器只认识 "odoo" 与 "scoped_app" 前缀:先换回旧路径再解析。
        if (urlObj.pathname === PREFIX_PATH || urlObj.pathname.startsWith(`${PREFIX_PATH}/`)) {
            urlObj = new URL(urlObj.href);
            urlObj.pathname = "/odoo" + urlObj.pathname.slice(PREFIX_PATH.length);
        }
        return urlToState.call(this, urlObj);
    };

    // router.js 加载时已用未打补丁的函数解析过初始 URL:此时重新解析。
    startRouter();

    // router.js 的点击拦截只处理以 /odoo 开头的内部链接,对自定义前缀
    // 不生效:在这里补一份等价逻辑。
    browser.addEventListener("click", (ev) => {
        if (ev.defaultPrevented || ev.target.closest("[contenteditable]")) {
            return;
        }
        const a = ev.target.closest("a");
        const href = a?.getAttribute("href");
        if (href && !href.startsWith("#")) {
            let url;
            try {
                url = new URL(a.href);
            } catch {
                return;
            }
            if (
                browser.location.host === url.host &&
                browser.location.pathname.startsWith(PREFIX_PATH) &&
                (["/web", "/odoo", PREFIX_PATH].includes(url.pathname) ||
                    url.pathname.startsWith("/odoo/") ||
                    url.pathname.startsWith(`${PREFIX_PATH}/`)) &&
                a.target !== "_blank"
            ) {
                ev.preventDefault();
                // 旧地址的链接改写后再入栈,地址栏始终显示新前缀。
                if (url.pathname === "/odoo" || url.pathname.startsWith("/odoo/")) {
                    url.pathname = PREFIX_PATH + url.pathname.slice("/odoo".length);
                }
                browser.history.pushState({}, "", url.href);
                window.dispatchEvent(new PopStateEvent("popstate", { state: {} }));
            }
        }
    });
}
