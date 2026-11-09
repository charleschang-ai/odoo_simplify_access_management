// 普通前台脚本(非 odoo-module,无依赖):随 web.assets_frontend 直接执行。
// 白标(前台):web.assets_backend 里的导航栏 href 补丁改写不到 portal / website
// 前台页面。这些前台页面(用户菜单 "Apps"、website 编辑条 "Go to your Odoo
// Apps" / 应用网格等)里有硬编码的 /odoo 链接,鼠标悬停时浏览器状态栏会露出
// odoo。这里读取由 debrand_frontend_prefix_meta 模板注入到 <head> 的 meta,
// 把 /odoo 链接改成自定义前缀,并去掉可见的 "Odoo" 文案。
//
// 说明:纯 DOM 改写,不参与页面渲染,即使匹配不到元素也只是静默无操作,
// 不会像坏的继承视图那样让前台页面报错。用 IIFE 包裹避免污染 bundle 全局作用域。
(function () {
    "use strict";
    var prefixMeta = document.querySelector('meta[name="sam-debrand-prefix"]');
    var brandMeta = document.querySelector('meta[name="sam-debrand-brand"]');
    var PREFIX = prefixMeta && prefixMeta.getAttribute("content");
    if (!PREFIX) {
        return; // 白标关闭或未配置前缀:静默无操作
    }
    var BRAND = (brandMeta && brandMeta.getAttribute("content")) || "";

    function rewrite(root) {
        // 1) /odoo、/odoo/xxx、/odoo?xxx 前缀改写为 /<prefix>...
        var links = root.querySelectorAll('a[href^="/odoo"]');
        for (var i = 0; i < links.length; i++) {
            var a = links[i];
            var href = a.getAttribute("href");
            if (
                href === "/odoo" ||
                href.indexOf("/odoo/") === 0 ||
                href.indexOf("/odoo?") === 0
            ) {
                a.setAttribute("href", "/" + PREFIX + href.slice("/odoo".length));
            }
        }
        // 2) "Go to your Odoo Apps" 等 title 提示去 odoo 化
        var titled = root.querySelectorAll('[title*="Odoo"]');
        for (var j = 0; j < titled.length; j++) {
            var el = titled[j];
            var t = el.getAttribute("title");
            el.setAttribute("title", t.replace(/Odoo\s*/g, BRAND ? BRAND + " " : ""));
        }
    }

    function run() {
        rewrite(document);
        // website 编辑条等可能在加载后由脚本再注入,补一次观察改写。
        try {
            var obs = new MutationObserver(function () {
                rewrite(document);
            });
            obs.observe(document.documentElement, { childList: true, subtree: true });
            // 页面稳定后停止观察,避免长期开销。
            setTimeout(function () {
                obs.disconnect();
            }, 5000);
        } catch (e) {
            // MutationObserver 不可用时忽略,首次改写已覆盖初始 DOM。
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", run, { once: true });
    } else {
        run();
    }
})();
