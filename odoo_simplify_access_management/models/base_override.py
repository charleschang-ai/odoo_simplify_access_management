# -*- coding: utf-8 -*-
import ast

from lxml import etree

from odoo import _, api, models, SUPERUSER_ID
from odoo.exceptions import AccessError
from odoo.http import request

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

    def _sam_real_user(self):
        """hr 加载"我的资料"视图(hr.res_users_view_form_profile)时会先
        with_user(SUPERUSER_ID) 提权再进 get_view(为了带上受 groups 保护
        的字段定义),规则若按提权后的 uid=1 计算会全部失效。此时回退到
        HTTP 会话的真实用户。普通 sudo() 提权 uid 不变仍是原用户,
        不会走进这个分支,维持"遇 su 放行"的设计。"""
        if (self.env.uid == SUPERUSER_ID and request and request.session.uid
                and request.session.uid != SUPERUSER_ID):
            return self.with_user(request.session.uid)
        return self

    def _sam_raise(self, message):
        raise AccessError(
            _('%(message)s (Model: %(model)s)\n'
              'This operation is restricted by Access Manage Studio. '
              'Contact your administrator if you have questions.',
              message=message, model=self._name))

    # ------------------------------------------------------------------
    # CRUD / 导出 强制
    # 说明:「记录权限」(域规则) 由 sam.domain.line 同步生成的全局
    # ir.access 限制强制,读/写/建/删全部由 ORM 原生访问控制机制处理。
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
    # 合计摘要(JSON)中的隐藏字段
    # Odoo 20 的 sale.order.extra_total_fields 等 JSON 计算字段把其它字段
    # 的值(如 sale_margin 的毛利)拼成 [{name, lines: [{label, value}]}]
    # 交给前端合计组件显示,不经过视图里的 <field>,字段隐藏规则管不到。
    # _read_format 是 read / web_read / onchange 结果的共同出口,在这里把
    # 数值等于"被隐藏字段当前值"的行去掉;隐藏 xxx_percent 时同时按 xxx
    # 匹配(毛利行显示的是 margin,标签里带 margin_percent)。
    # ------------------------------------------------------------------

    def _read_format(self, fnames, load='_classic_read'):
        result = super()._read_format(fnames, load=load)
        # 先做廉价判断:绝大多数读取不含 JSON 字段,直接返回
        json_fnames = [f for f in fnames
                       if f in self._fields and self._fields[f].type == 'json']
        if not result or not json_fnames or not self._sam_enabled():
            return result
        hidden = set()
        for name, invisible, *_rest in self.env['sam.profile']._get_field_rules(self._name):
            if invisible:
                hidden.add(name)
                hidden.add(name.removesuffix('_percent'))
        hidden = [f for f in hidden if f in self._fields
                  and self._fields[f].type in ('monetary', 'float', 'integer')]
        if not hidden:
            return result
        records = {rec.id: rec for rec in self.sudo()}
        for vals in result:
            record = records.get(vals.get('id'))
            if record is None:
                continue
            hidden_values = [v for v in (record[f] for f in hidden) if v]
            if not hidden_values:
                continue
            for fname in json_fnames:
                vals[fname] = self._sam_filter_summary_lines(vals.get(fname), hidden_values)
        return result

    @staticmethod
    def _sam_filter_summary_lines(groups, hidden_values):
        if not isinstance(groups, list):
            return groups

        def is_hidden(line):
            value = line.get('value') if isinstance(line, dict) else None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False
            return any(abs(value - hv) <= 1e-6 * max(1.0, abs(hv)) for hv in hidden_values)

        filtered = []
        for group in groups:
            if isinstance(group, dict) and isinstance(group.get('lines'), list):
                # 复制而非原地修改:JSON 值可能直接引用 ORM 缓存中的对象
                group = dict(group, lines=[l for l in group['lines'] if not is_hidden(l)])
            filtered.append(group)
        return filtered

    # ------------------------------------------------------------------
    # 视图结构处理(隐藏按钮/页签/字段/筛选/沟通栏,禁用增删改等)
    # ------------------------------------------------------------------

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        self = self._sam_real_user()
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
            self._sam_apply_button_rules(node, view_type, Profile)

            if view_type == 'form':
                chatter = Profile._get_chatter_rules(self._name)
                if chatter and chatter.get('hide_chatter'):
                    self._sam_remove_chatter(node)
                if (self._name == 'res.users'
                        and Profile._get_global_flags().get(
                            'hide_notification_settings')):
                    # 个人资料弹窗顶部"浏览器通知被阻止"横幅
                    # (notification_type 字段本身由字段规则管道隐藏)
                    for el in list(node.iter('widget')):
                        if el.get('name') == 'notification_alert':
                            parent = el.getparent()
                            if parent is not None:
                                parent.remove(el)

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

    def _sam_apply_button_rules(self, node, view_type, Profile):
        button_rules = Profile._get_button_rules(self._name)
        if not button_rules:
            return
        for element_type, name, string in button_rules:
            tag = 'page' if element_type == 'page' else 'button'
            for el in node.iter(tag):
                matched = (name and el.get('name') == name) or (
                    string and (el.get('string') == string or
                                (el.text or '').strip() == string))
                if not matched:
                    continue
                # 不能整块移除:页签/智能按钮内可能声明了视图其他地方的
                # invisible/readonly 表达式所引用的字段(如 sale.order
                # "Other Info" 里的 invoice_status),移除后字段不再随视图
                # 加载,前端求值直接报 Name is not defined。改为强制不可见,
                # 内容保留在 arch 中、字段照常加载。
                el.set('invisible', 'True')
                if tag == 'button' and self._sam_in_list_view(el, view_type):
                    el.set('column_invisible', 'True')

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
