import { patch } from "@web/core/utils/patch";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { session } from "@web/session";

patch(SearchBar.prototype, {
    /**
     * Access Manage Studio:该模型是否允许显示搜索栏。
     * @returns {boolean} true = 允许显示
     */
    samSearchAllowed() {
        const noSearch = (session.sam && session.sam.no_search) || [];
        const resModel = this.env.searchModel && this.env.searchModel.resModel;
        return !resModel || !noSearch.includes(resModel);
    },
});
