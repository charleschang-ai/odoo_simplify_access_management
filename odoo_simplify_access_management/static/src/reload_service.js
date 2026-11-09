import { onWillDestroy, Plugin, usePlugin } from "@odoo/owl";
import { BusPlugin } from "@bus/services/bus_plugin";
import { services } from "@web/core/services";

/**
 * Access Manage Studio:管理员保存访问配置后,受影响用户的浏览器
 * 通过 bus 收到 sam_reload 通知,自动整页刷新使新规则立即生效。
 * Odoo 20 起 bus 以 Plugin 提供(bus_service 只是待移除的兼容层)。
 */
export class SamReloadPlugin extends Plugin {
    bus = usePlugin(BusPlugin);

    setup() {
        let reloading = false;
        const unsubscribe = this.bus.subscribe("sam_reload", () => {
            // 一次保存可能触发多条通知,只刷新一次
            if (!reloading) {
                reloading = true;
                window.location.reload();
            }
        });
        this.bus.start();
        onWillDestroy(unsubscribe);
    }
}

services.add(SamReloadPlugin);
