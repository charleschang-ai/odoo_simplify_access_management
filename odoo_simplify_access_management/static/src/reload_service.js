import { registry } from "@web/core/registry";

/**
 * Access Manage Studio:管理员保存访问配置后,受影响用户的浏览器
 * 通过 bus 收到 sam_reload 通知,自动整页刷新使新规则立即生效。
 */
export const samReloadService = {
    dependencies: ["bus_service"],
    start(env, { bus_service }) {
        let reloading = false;
        bus_service.subscribe("sam_reload", () => {
            // 一次保存可能触发多条通知,只刷新一次
            if (!reloading) {
                reloading = true;
                window.location.reload();
            }
        });
        bus_service.start();
    },
};

registry.category("services").add("sam_reload", samReloadService);
