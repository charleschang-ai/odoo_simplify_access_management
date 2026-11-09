import { registry } from "@web/core/registry";
import { session } from "@web/session";

const cfg = session.sam_debranding || {};
const PREFIX = cfg.enabled && cfg.prefix;

if (PREFIX) {
    /**
     * 白标:将 Ctrl+K 命令面板中菜单项的 href 里硬编码的 /odoo/ 替换为自定义前缀。
     * menu_helpers.js 的 computeAppsAndMenuItems 是纯函数无法 patch，
     * 因此在其唯一调用方 menu_providers.js 的 provide 结果中后处理。
     * Odoo 20: provide(options) 为同步函数,且内部调用 useService/usePlugin,
     * 必须在同一调用栈内同步执行原函数。
     */
    const commandProviderRegistry = registry.category("command_provider");
    const provider = commandProviderRegistry.get("menu", null);
    if (provider) {
        const originalProvide = provider.provide;
        provider.provide = function (options) {
            const result = originalProvide.call(this, options);
            for (const item of result) {
                if (item.href && item.href.startsWith("/odoo/")) {
                    item.href = item.href.replace("/odoo/", `/${PREFIX}/`);
                }
            }
            return result;
        };
    }
}
