# -*- coding: utf-8 -*-
from lxml import etree

from odoo import api, models

from .. import text_debrand

# 白标配置界面本身("隐藏 Odoo 品牌"开关等)保留 Odoo 字样,否则管理员
# 看到的是 "隐藏 MyBrand 品牌",意思反了
EXCLUDED_MODELS = frozenset({'sam.profile'})


class BaseDebranding(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def _get_view_postprocessed(self, view, arch, **options):
        """后台视图(表单/列表/看板/搜索,含设置页)中的 "Odoo" 文字换成品牌名。

        结果随 _get_view_cache 缓存(按语言),白标配置变化时由
        sam.profile._sam_sync_debranding 清空 templates 缓存。"""
        arch, models_info = super()._get_view_postprocessed(view, arch, **options)
        if arch and 'Odoo' in arch and self._name not in EXCLUDED_MODELS:
            brand = text_debrand.get_brand(self.env)
            if brand:
                tree = etree.fromstring(arch)
                if text_debrand.debrand_tree(tree, brand):
                    arch = etree.tostring(tree, encoding='unicode')
        return arch, models_info

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """字段标签、帮助提示(问号悬浮说明)与选项标签中的 "Odoo"
        换成品牌名(如用户偏好 "通知处理:在 Odoo 中")。"""
        res = super().fields_get(allfields, attributes)
        if self._name in EXCLUDED_MODELS:
            return res
        brand = None
        for description in res.values():
            for key in ('string', 'help'):
                value = description.get(key)
                if value and text_debrand.has_odoo(value):
                    if brand is None:
                        brand = text_debrand.get_brand(self.env)
                    if brand:
                        description[key] = text_debrand.replace_text(value, brand)
            selection = description.get('selection')
            if isinstance(selection, (list, tuple)) and any(
                    isinstance(item, (list, tuple)) and len(item) == 2
                    and isinstance(item[1], str) and text_debrand.has_odoo(item[1])
                    for item in selection):
                if brand is None:
                    brand = text_debrand.get_brand(self.env)
                if brand:
                    description['selection'] = [
                        [item[0], text_debrand.replace_text(item[1], brand)]
                        if isinstance(item, (list, tuple)) and len(item) == 2
                        and isinstance(item[1], str) else item
                        for item in selection
                    ]
        return res
