import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { WebClient } from "@web/webclient/webclient";

/**
 * Access Manage Studio 白标:PWA / Service Worker 的 /odoo 硬编码替换。
 */
const cfg = session.sam_debranding || {};
const PREFIX = cfg.enabled && cfg.prefix;
const RESERVED = ["web", "odoo", "scoped_app"];

if (PREFIX && !RESERVED.includes(PREFIX)) {
    const PREFIX_PATH = `/${PREFIX}`;
    const serviceRegistry = registry.category("services");

    // webclient.js 以硬编码 { scope: "/odoo" } 注册 service worker:
    // 拦截 register() 调用改写 scope。
    patch(WebClient.prototype, {
        registerServiceWorker() {
            if (!navigator.serviceWorker) {
                return;
            }
            const container = navigator.serviceWorker;
            const originalRegister = container.register.bind(container);
            container.register = (url, options) =>
                originalRegister(url, { ...options, scope: PREFIX_PATH });
            try {
                super.registerServiceWorker();
            } finally {
                delete container.register;
            }
        },
    });

    // pwa_service.js 硬编码 startUrl: "/odoo"(PWA 安装状态与安装后跳转)。
    if (serviceRegistry.contains("pwa")) {
        const pwaService = serviceRegistry.get("pwa");
        const originalStart = pwaService.start;
        pwaService.start = function (env, deps) {
            const state = originalStart.call(this, env, deps);
            if (state.startUrl === "/odoo") {
                state.startUrl = PREFIX_PATH;
            }
            return state;
        };
    }
}
