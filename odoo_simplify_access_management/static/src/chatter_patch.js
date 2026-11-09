import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { session } from "@web/session";

patch(Chatter.prototype, {
    /**
     * Access Manage Studio:按模型判断沟通栏按钮是否允许显示。
     * @param {string} kind hide_send_message | hide_log_note | hide_activities
     * @returns {boolean} true = 允许显示
     */
    samAllow(kind) {
        const rules = (session.sam && session.sam.chatter) || {};
        // 未命中具体模型时回退到全局开关('*');OWL 3 中 props 改为计算信号
        const modelRules = rules[this.threadModel()] || rules["*"];
        if (!modelRules) {
            return true;
        }
        return !modelRules[kind];
    },
});
