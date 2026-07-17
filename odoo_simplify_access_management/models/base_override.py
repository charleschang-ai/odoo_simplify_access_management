# -*- coding: utf-8 -*-
import ast

from lxml import etree

from odoo import _, api, models
from odoo.exceptions import AccessError

# 我们自己的配置模型不做限制,避免递归/自锁
_SKIP_MODELS = {
    'sam.profile', 'sam.model.line', 'sam.field.line', 'sam.domain.line',
    'sam.button.line', 'sam.filter.line', 'sam.view.line', 'sam.chatter.line',
    'sam.cache.mixin',
}


class Base(models.AbstractModel):
    _inherit = 'base'

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _sam_enabled(self):
        env = self.env
        if env.su or not env.uid:
            return False
        if self._name in _SKIP_MODELS or self._abstract or self._transient:
            return False
        if 'sam.profile' not in env.registry or 'sam.profile' not in env:
            return False
        return True

    def _sam_rules(self):
        return self.env['sam.profile']._get_model_rules(self._name)

    def _sam_raise(self, message):
        raise AccessError(
            _('%(message)s (Model: %(model)s)\n'
              'This operation is restricted by Access Manage Studio. '
              'Contact your administrator if you have questions.',
              message=message, model=self._name))

    # ------------------------------------------------------------------
    # CRUD / 导出 强制
    # 说明:「记录权限」(域规则) 由 sam.domain.line 同步生成的真正
    # ir.rule 强制,读/写/建/删全部由 ORM 原生记录规则机制处理。
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        if self._sam_enabled():
            rules = self._sam_rules()
            if rules['hide_create']:
                self._sam_raise(_('You do not have create permission'))
        return super().create(vals_list)

    def write(self, vals):
        if self and self._sam_enabled():
            rules = self._sam_rules()
            if rules['hide_edit']:
                self._sam_raise(_('You do not have edit permission'))
            if rules['hide_archive'] and 'active' in vals and 'active' in self._fields:
                self._sam_raise(_('You do not have archive/unarchive permission'))
            field_rules = self.env['sam.profile']._get_field_rules(self._name)
            readonly_fields = [name for name, invisible, readonly, *_rest in field_rules
                               if (readonly or invisible) and name in vals]
            if readonly_fields:
                self._sam_raise(_('Field %s is read-only/hidden, modification denied') % ', '.join(readonly_fields))
        return super().write(vals)

    def unlink(self):
        if self and self._sam_enabled():
            rules = self._sam_rules()
            if rules['hide_delete']:
                self._sam_raise(_('You do not have delete permission'))
        return super().unlink()

    def copy(self, default=None):
        if self and self._sam_enabled():
            if self._sam_rules()['hide_duplicate']:
                self._sam_raise(_('You do not have duplicate permission'))
        return super().copy(default=default)

    def export_data(self, fields_to_export):
        if self._sam_enabled():
            if self._sam_rules()['hide_export']:
                self._sam_raise(_('You do not have export permission'))
        return super().export_data(fields_to_export)

    # ------------------------------------------------------------------
    # 视图结构处理(隐藏按钮/页签/字段/筛选/沟通栏,禁用增删改等)
    # ------------------------------------------------------------------

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if not self._sam_enabled():
            return result
        try:
            node = etree.fromstring(result['arch'])
        except Exception:
            return result

        Profile = self.env['sam.profile']
        rules = self._sam_rules()

        if view_type in ('form', 'list', 'kanban'):
            if rules['hide_create']:
                node.set('create', '0')
            if rules['hide_edit']:
                node.set('edit', '0')
            if rules['hide_delete']:
                node.set('delete', '0')
            if rules['hide_duplicate']:
                node.set('duplicate', '0')
            if view_type == 'list':
                if rules['hide_export']:
                    node.set('export_xlsx', '0')
                if rules['hide_import']:
                    node.set('import', '0')
                if rules['hide_edit']:
                    node.attrib.pop('editable', None)

            self._sam_apply_field_rules(node, view_type, Profile)
            self._sam_apply_button_rules(node, Profile)

            if view_type == 'form':
                chatter = Profile._get_chatter_rules(self._name)
                if chatter and chatter.get('hide_chatter'):
                    self._sam_remove_chatter(node)

        elif view_type == 'search':
            if rules['hide_search']:
                # 禁止搜索:清空整个搜索视图(无自动完成、无筛选、无分组)
                for child in list(node):
                    node.remove(child)
            else:
                self._sam_apply_filter_rules(node, Profile)
                self._sam_remove_hidden_search_fields(node, Profile)

        result['arch'] = etree.tostring(node, encoding='unicode')
        return result

    def _sam_node_model(self, el):
        """确定 field 节点所属的模型(内嵌 x2many 子视图按其 comodel 计算)。"""
        chain = []
        parent = el.getparent()
        while parent is not None:
            if parent.tag == 'field' and parent.get('name'):
                chain.append(parent.get('name'))
            parent = parent.getparent()
        model = self._name
        for fname in reversed(chain):
            field = self.env[model]._fields.get(fname)
            comodel = getattr(field, 'comodel_name', None) if field else None
            if not comodel:
                return None
            model = comodel
        return model

    @staticmethod
    def _sam_in_list_view(el, view_type):
        """节点是否渲染为列表列(顶层 list 视图或内嵌 <list> 子视图)。"""
        parent = el.getparent()
        while parent is not None:
            if parent.tag in ('list', 'tree'):
                return True
            if parent.tag == 'field':
                return False
            parent = parent.getparent()
        return view_type == 'list'

    @staticmethod
    def _sam_merge_options(raw, extra):
        """把 extra 合并进 field 节点的 options 属性(dict 字面量字符串)。"""
        if not raw or not raw.strip():
            return repr(extra)
        try:
            options = ast.literal_eval(raw)
            if isinstance(options, dict):
                options.update(extra)
                return repr(options)
        except Exception:
            pass
        # options 含表达式无法求值时,做字符串拼接
        stripped = raw.strip()
        if stripped.endswith('}'):
            head = stripped[:-1].rstrip()
            sep = '' if head.endswith('{') else ', '
            inner = ', '.join('%r: %r' % (k, v) for k, v in extra.items())
            return head + sep + inner + '}'
        return raw

    def _sam_apply_field_rules(self, node, view_type, Profile):
        rules_by_model = {}

        def get_rules(model):
            if model not in rules_by_model:
                rules_by_model[model] = {
                    name: rest
                    for name, *rest in Profile._get_field_rules(model)}
            return rules_by_model[model]

        for el in node.iter('field'):
            model = self._sam_node_model(el)
            if not model:
                continue
            field_rules = get_rules(model)
            fname = el.get('name')
            if fname not in field_rules:
                continue
            invisible, readonly, required, remove_link, no_create = \
                field_rules[fname]
            if invisible:
                el.set('invisible', 'True')
                if self._sam_in_list_view(el, view_type):
                    el.set('column_invisible', 'True')
                el.attrib.pop('required', None)
            if readonly:
                el.set('readonly', 'True')
            if required and not invisible:
                el.set('required', 'True')
            extra = {}
            if remove_link:
                extra['no_open'] = True
            if no_create:
                extra.update(no_create=True, no_create_edit=True,
                             no_quick_create=True)
            if extra:
                el.set('options',
                       self._sam_merge_options(el.get('options'), extra))

    def _sam_apply_button_rules(self, node, Profile):
        button_rules = Profile._get_button_rules(self._name)
        if not button_rules:
            return
        to_remove = []
        for element_type, name, string in button_rules:
            tag = 'page' if element_type == 'page' else 'button'
            for el in node.iter(tag):
                if name and el.get('name') == name:
                    to_remove.append(el)
                elif string and (el.get('string') == string or
                                 (el.text or '').strip() == string):
                    to_remove.append(el)
        for el in to_remove:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

    def _sam_apply_filter_rules(self, node, Profile):
        filter_rules = Profile._get_filter_rules(self._name)
        if not filter_rules:
            return
        to_remove = []
        for el in node.iter('filter'):
            for name, string in filter_rules:
                if name and el.get('name') == name:
                    to_remove.append(el)
                elif string and el.get('string') == string:
                    to_remove.append(el)
        for el in to_remove:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

    def _sam_remove_hidden_search_fields(self, node, Profile):
        """隐藏字段同时从搜索视图移除:字段搜索项与引用它的分组项。"""
        hidden = {name for name, invisible, *_rest
                  in Profile._get_field_rules(self._name) if invisible}
        if not hidden:
            return
        to_remove = [el for el in node.iter('field') if el.get('name') in hidden]
        for el in node.iter('filter'):
            context = el.get('context') or ''
            if 'group_by' in context and any(
                    "'%s'" % f in context or '"%s"' % f in context
                    for f in hidden):
                to_remove.append(el)
        for el in to_remove:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

    def _sam_remove_chatter(self, node):
        to_remove = list(node.iter('chatter'))
        for el in node.iter('div'):
            if 'oe_chatter' in (el.get('class') or ''):
                to_remove.append(el)
        for el in to_remove:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
