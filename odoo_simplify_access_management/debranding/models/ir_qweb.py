# -*- coding: utf-8 -*-
from lxml import etree

from odoo import models

from .. import html_debrand, text_debrand

KNOWLEDGE_ONBOARDING_TEMPLATE = 'knowledge.knowledge_article_user_onboarding'


class IrQwebDebranding(models.AbstractModel):
    _inherit = 'ir.qweb'

    def _get_template(self, template):
        """QWeb 模板(登录页、门户、网站、报表、邮件布局、PWA 离线页等)
        静态文字里的 "Odoo" 在编译前换成品牌名。

        只改模板本身的文字,不改渲染时填入的业务数据。编译结果按
        (模板, 文档哈希, 语言) 缓存:这里同步返回修改后的文档字符串,
        品牌名变化时哈希随之变化,不会复用旧品牌的编译结果;白标开关
        变化时 sam.profile 另外清空 templates 缓存。"""
        element, document, ref = super()._get_template(template)
        if document and 'Odoo' in document:
            brand = text_debrand.get_brand(self.env)
            if brand and text_debrand.debrand_tree(element, brand, qweb=True):
                root = element
                while root.getparent() is not None:
                    root = root.getparent()
                document = etree.tostring(root, encoding='unicode')
        return element, document, ref

    def _render(self, template, values=None, **options):
        """知识库(企业版 knowledge)为每个新内部用户生成的 "Welcome xxx"
        欢迎文章,正文由该模板渲染:白标启用时去掉其中的 Odoo 视频、
        示例文件、官方社交账号链接与品牌词。

        本模块不依赖 knowledge,无法覆盖 res.users._generate_tutorial_articles
        (加载先后不确定),因此在模板渲染出口处理。"""
        result = super()._render(template, values, **options)
        if (template == KNOWLEDGE_ONBOARDING_TEMPLATE and result
                and 'sam.profile' in self.env):
            profile_model = self.env['sam.profile'].sudo()
            if profile_model._get_debranding().get('enabled'):
                brand = profile_model._sam_bot_branding()[0]
                result = html_debrand.debrand_knowledge_onboarding(result, brand)
        return result
