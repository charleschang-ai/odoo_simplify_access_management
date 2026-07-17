import { registry } from "@web/core/registry";
import { session } from "@web/session";

const cfg = session.sam_debranding || {};
const PREFIX = cfg.enabled && cfg.prefix;

if (PREFIX) {
    /**
     * 白标:将 Ctrl+K 命令面板中菜单项的 href 里硬编码的 /odoo/ 替换为自定义前缀。
     * menu_helpers.js 的 computeAppsAndMenuItems 是纯函数无法 patch，
     * 因此在其唯一调用方 menu_providers.js 的 provide 结果中后处理。
     */
    const commandProviderRegistry = registry.category("command_provider");
    const provider = commandProviderRegistry.get("menu");
    if (provider) {
        const originalProvide = provider.provide;
        provider.provide = async function (env, options) {
            const result = await originalProvide.call(this, env, options);
            for (const item of result) {
                if (item.href && item.href.startsWith("/odoo/")) {
                    item.href = item.href.replace("/odoo/", `/${PREFIX}/`);
                }
            }
            return result;
        };
    }
}
