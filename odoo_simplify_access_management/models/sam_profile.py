# -*- coding: utf-8 -*-
from odoo import _, api, fields, models, tools, SUPERUSER_ID
from odoo.exceptions import ValidationError
from odoo.tools import safe_eval as safe_eval_module
from odoo.tools.safe_eval import safe_eval


VIEW_TYPES = [
    ('list', 'List'),
    ('form', 'Form'),
    ('kanban', 'Kanban'),
    ('calendar', 'Calendar'),
    ('pivot', 'Pivot'),
    ('graph', 'Graph'),
    ('activity', 'Activity'),
    ('gantt', 'Gantt'),
    ('map', 'Map'),
    ('cohort', 'Cohort'),
    ('hierarchy', 'Hierarchy'),
]

MODEL_RULE_KEYS = (
    'hide_create', 'hide_edit', 'hide_delete', 'hide_duplicate',
    'hide_archive', 'hide_export', 'hide_import', 'hide_search', 'readonly',
)


class SamCacheMixin(models.AbstractModel):
    """Shared by all rule-related models: any change clears the ORM cache
    and notifies affected users' browsers to auto-refresh, ensuring rules
    take effect immediately."""
    _name = 'sam.cache.mixin'
    _description = 'SAM Cache Invalidation Mixin'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        records._sam_notify_reload()
        return records

    def write(self, vals):
        # 提前记录受影响用户:从配置移除的用户也需要刷新以恢复界面
        partner_ids = self._sam_affected_partner_ids()
        res = super().write(vals)
        self.env.registry.clear_cache()
        self._sam_notify_reload(extra_partner_ids=partner_ids)
        return res

    def unlink(self):
        partner_ids = self._sam_affected_partner_ids()
        res = super().unlink()
        self.env.registry.clear_cache()
        self._sam_notify_partners(partner_ids)
        return res

    # ------- 浏览器自动刷新通知(bus 推送) -------

    def _sam_profiles(self):
        if self._name == 'sam.profile':
            return self
        if 'profile_id' in self._fields:
            return self.profile_id
        return self.env['sam.profile']

    def _sam_affected_partner_ids(self):
        partner_ids = set()
        for profile in self._sam_profiles().sudo():
            users = profile.user_ids | profile.group_ids.users
            partner_ids.update(users.partner_id.ids)
        return partner_ids

    def _sam_notify_reload(self, extra_partner_ids=None):
        partner_ids = self._sam_affected_partner_ids()
        if extra_partner_ids:
            partner_ids |= set(extra_partner_ids)
        self._sam_notify_partners(partner_ids)

    def _sam_notify_partners(self, partner_ids):
        if not partner_ids or 'bus.bus' not in self.env:
            return
        Bus = self.env['bus.bus'].sudo()
        for partner in self.env['res.partner'].sudo().browse(sorted(partner_ids)):
            Bus._sendone(partner, 'sam_reload', {})


class SamProfile(models.Model):
    _name = 'sam.profile'
    _inherit = ['sam.cache.mixin']
    _description = 'SAM Profile'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    user_ids = fields.Many2many(
        'res.users', relation='sam_profile_user_rel',
        column1='profile_id', column2='user_id',
        string='Users', domain=[('share', '=', False)],
    )
    group_ids = fields.Many2many(
        'res.groups', relation='sam_profile_group_rel',
        column1='profile_id', column2='group_id',
        string='User Groups',
        help='Users belonging to these groups also receive this configuration.',
    )
    company_ids = fields.Many2many(
        'res.company', relation='sam_profile_company_rel',
        column1='profile_id', column2='company_id',
        string='Companies',
        help='Leave empty to apply to all companies; only active when the '
             'user\'s current company is in the list.',
    )

    # ------- 全局开关 -------
    readonly_user = fields.Boolean(
        string='Global Read-only',
        help='These users are read-only on all models: create, edit, delete, '
             'duplicate, and archive are denied.',
    )
    disable_developer_mode = fields.Boolean(
        string='Disable Developer Mode',
        help='Prevent these users from using developer mode '
             '(including the ?debug=1 URL method).',
    )
    disable_module_actions = fields.Boolean(
        string='Block Module Install/Upgrade/Uninstall',
    )
    disable_import = fields.Boolean(string='Disable Import (All Models)')
    disable_export = fields.Boolean(string='Disable Export (All Models)')
    restrict_xmlrpc = fields.Boolean(
        string='Disable XML-RPC / External API',
        help='Prevent these users from calling model methods via '
             'XML-RPC / JSON-RPC external API.',
    )
    disable_login = fields.Boolean(
        string='Deny Login',
        help='Prevent these users from logging in (both web and external API '
             'authentication are denied). Active sessions cannot log in again '
             'after expiry or logout.',
    )

    # ------- 沟通栏全局开关(对所有模型生效,无需逐模型添加明细行) -------
    hide_chatter_global = fields.Boolean(string='Hide Chatter (All Models)')
    hide_send_message_global = fields.Boolean(string='Block Send Message (All Models)')
    hide_log_note_global = fields.Boolean(string='Block Log Note (All Models)')
    hide_activities_global = fields.Boolean(string='Block Schedule Activities (All Models)')

    # ------- 白标(Debranding,站点级全局生效,与应用用户无关) -------
    debranding = fields.Boolean(
        string='Hide Odoo Branding (White Label)',
        help='Globally hide: "Powered by Odoo" on login page, browser tab '
             'title, notification email footer branding, odoo.com links in '
             'the user menu, etc.')
    brand_name = fields.Char(
        string='Brand Name',
        help='Name to replace "Odoo" (browser title, PWA app name). '
             'Uses the company name if left empty.')
    url_prefix = fields.Char(
        string='URL Prefix',
        help='Replace the /odoo prefix in URLs, e.g. entering "app" makes '
             'the backend accessible at /app. Leave empty for no change. '
             'Only letters, digits, hyphens, and underscores allowed.')
    favicon = fields.Binary(
        string='Tab Icon (Favicon)', attachment=True,
        help='Replace the browser tab icon, supports ico/png. '
             'Odoo default used if empty.')

    @api.constrains('url_prefix')
    def _check_url_prefix(self):
        from ..debranding import const
        for profile in self:
            prefix = (profile.url_prefix or '').strip().strip('/')
            if prefix and not const.is_valid_prefix(prefix):
                raise ValidationError(
                    _('URL prefix %r is invalid: reserved words '
                      '(web/odoo/mail etc.) not allowed, only letters, '
                      'digits, hyphens, and underscores.') % prefix)

    # ------- Details -------
    hide_menu_ids = fields.Many2many(
        'ir.ui.menu', relation='sam_profile_menu_rel',
        column1='profile_id', column2='menu_id',
        string='Hidden Menus',
        help='Child menus of hidden menus are also hidden.',
    )
    model_line_ids = fields.One2many('sam.model.line', 'profile_id', string='Model Rules')
    field_line_ids = fields.One2many('sam.field.line', 'profile_id', string='Field Rules')
    domain_line_ids = fields.One2many('sam.domain.line', 'profile_id', string='Record Rules')
    button_line_ids = fields.One2many('sam.button.line', 'profile_id', string='Buttons/Tabs')
    filter_line_ids = fields.One2many('sam.filter.line', 'profile_id', string='Filters/Group Bys')
    view_line_ids = fields.One2many('sam.view.line', 'profile_id', string='Hidden Views')
    chatter_line_ids = fields.One2many('sam.chatter.line', 'profile_id', string='Chatter')
    hidden_report_ids = fields.Many2many(
        'ir.actions.report', relation='sam_profile_report_rel',
        column1='profile_id', column2='report_id',
        string='Hidden Reports',
    )
    hidden_action_ids = fields.Many2many(
        'ir.actions.actions', relation='sam_profile_action_rel',
        column1='profile_id', column2='action_id',
        string='Hidden Actions',
        domain=[('binding_model_id', '!=', False)],
    )

    @api.model_create_multi
    def create(self, vals_list):
        profiles = super().create(vals_list)
        if any(v.get('debranding') or v.get('url_prefix') for v in vals_list):
            self._sam_sync_debranding()
        return profiles

    def write(self, vals):
        res = super().write(vals)
        # 应用范围变化时,重建域规则(ir.rule 的定向条件内嵌了用户/组/公司)
        if any(f in vals for f in ('user_ids', 'group_ids', 'company_ids',
                                   'active', 'name')):
            self.domain_line_ids._sam_sync_rules()
        if any(f in vals for f in ('debranding', 'brand_name',
                                   'url_prefix', 'favicon', 'active')):
            self._sam_sync_debranding()
        return res

    def unlink(self):
        rules = self.domain_line_ids.sudo().rule_id
        had_debranding = any(p.debranding for p in self)
        res = super().unlink()
        if rules:
            rules.sudo().unlink()
        if had_debranding:
            self._sam_sync_debranding()
        return res

    # ==================================================================
    # 白标(Debranding)
    # ==================================================================

    DEBRANDING_VIEW_XMLIDS = (
        'odoo_simplify_access_management.debrand_login_powered_by',
        'odoo_simplify_access_management.debrand_mail_layout_footer',
        'odoo_simplify_access_management.debrand_mail_light_footer',
        'odoo_simplify_access_management.debrand_portal_record_sidebar',
    )

    @api.model
    @tools.ormcache()
    def _get_debranding(self):
        """站点级白标配置(与用户无关):取第一条启用白标的有效配置。"""
        from ..debranding import const
        for profile in self.sudo().search([('debranding', '=', True)],
                                          order='sequence, id', limit=1):
            prefix = (profile.url_prefix or '').strip().strip('/')
            if prefix and not const.is_valid_prefix(prefix):
                prefix = ''
            return {
                'enabled': True,
                'brand': (profile.brand_name or '').strip(),
                'prefix': prefix,
                'favicon': bool(profile.favicon),
                'profile_id': profile.id,
            }
        return {'enabled': False, 'brand': '', 'prefix': '',
                'favicon': False, 'profile_id': False}

    @api.model
    def _sam_sync_debranding(self):
        """把白标开关落地:切换继承模板视图、同步 PWA 应用名、重建路由表。"""
        cfg = self._get_debranding()
        enabled = cfg['enabled']
        for xmlid in self.DEBRANDING_VIEW_XMLIDS:
            view = self.env.ref(xmlid, raise_if_not_found=False)
            if view and view.sudo().active != enabled:
                view.sudo().active = enabled
        icp = self.env['ir.config_parameter'].sudo()
        if enabled and cfg['brand']:
            icp.set_param('web.web_app_name', cfg['brand'])
        elif not enabled and icp.get_param('web.web_app_name'):
            icp.set_param('web.web_app_name', False)
        # 前缀可能变化:重建路由表缓存
        self.env.registry.clear_cache('routing')

    # ==================================================================
    # 规则计算(全部 sudo 读取 + ormcache,按 用户+公司 缓存)
    # ==================================================================

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id')
    def _get_profile_ids(self):
        """当前用户 + 当前公司下生效的配置档案 id 元组。"""
        user = self.env.user
        if not user or self.env.uid == SUPERUSER_ID:
            return ()
        group_ids = user.groups_id.ids
        profiles = self.sudo().search([
            '|', ('user_ids', 'in', user.id), ('group_ids', 'in', group_ids or [0]),
        ])
        company = self.env.company
        profiles = profiles.filtered(
            lambda p: not p.company_ids or company in p.company_ids)
        return tuple(profiles.ids)

    def _iter_profiles(self):
        return self.sudo().browse(self._get_profile_ids())

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id')
    def _get_global_flags(self):
        flags = {
            'readonly_user': False,
            'disable_developer_mode': False,
            'disable_module_actions': False,
            'disable_import': False,
            'disable_export': False,
            'restrict_xmlrpc': False,
        }
        for profile in self._iter_profiles():
            for key in flags:
                if profile[key]:
                    flags[key] = True
        return flags

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_model_rules(self, model_name):
        rules = dict.fromkeys(MODEL_RULE_KEYS, False)
        flags = self._get_global_flags()
        if flags['readonly_user']:
            rules['readonly'] = True
        if flags['disable_import']:
            rules['hide_import'] = True
        if flags['disable_export']:
            rules['hide_export'] = True
        for profile in self._iter_profiles():
            for line in profile.model_line_ids:
                if line.model_name != model_name:
                    continue
                for key in MODEL_RULE_KEYS:
                    if line[key]:
                        rules[key] = True
        if rules['readonly']:
            rules.update(hide_create=True, hide_edit=True,
                         hide_delete=True, hide_duplicate=True,
                         hide_archive=True)
        return rules

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_field_rules(self, model_name):
        """返回 ((field_name, invisible, readonly, required,
                  remove_link, no_create), ...)"""
        result = {}
        for profile in self._iter_profiles():
            for line in profile.field_line_ids:
                if line.model_name != model_name or not line.field_name:
                    continue
                prev = result.setdefault(
                    line.field_name, [False, False, False, False, False])
                prev[0] |= line.invisible
                prev[1] |= line.readonly
                prev[2] |= line.required
                prev[3] |= line.remove_link
                prev[4] |= line.no_create
        return tuple((name, *vals) for name, vals in result.items())

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_button_rules(self, model_name):
        """返回 ((element_type, name, string), ...)"""
        result = []
        for profile in self._iter_profiles():
            for line in profile.button_line_ids:
                if line.model_name != model_name:
                    continue
                result.append((line.element_type, line.name or '', line.string or ''))
        return tuple(result)

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_filter_rules(self, model_name):
        """返回 ((name, string), ...) — 作用于 search 视图的 <filter> 节点。"""
        result = []
        for profile in self._iter_profiles():
            for line in profile.filter_line_ids:
                if line.model_name != model_name:
                    continue
                result.append((line.name or '', line.string or ''))
        return tuple(result)

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_hidden_view_types(self, model_name):
        types = set()
        for profile in self._iter_profiles():
            for line in profile.view_line_ids:
                if line.model_name == model_name:
                    types.add(line.view_type)
        return frozenset(types)

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id', 'model_name')
    def _get_chatter_rules(self, model_name):
        rules = {'hide_chatter': False, 'hide_send_message': False,
                 'hide_log_note': False, 'hide_activities': False}
        found = False
        for profile in self._iter_profiles():
            # 全局开关:对所有模型生效
            for key in rules:
                if profile['%s_global' % key]:
                    rules[key] = True
                    found = True
            for line in profile.chatter_line_ids:
                if line.model_name != model_name:
                    continue
                found = True
                for key in rules:
                    if line[key]:
                        rules[key] = True
        return rules if found else {}

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id')
    def _get_all_chatter_rules(self):
        """给前端 session_info 用:{model: {hide_send_message: ..}, ...};
        全局开关放在 '*' 键下,前端未命中具体模型时回退到它。"""
        result = {}
        keys = ('hide_chatter', 'hide_send_message',
                'hide_log_note', 'hide_activities')
        for profile in self._iter_profiles():
            if any(profile['%s_global' % key] for key in keys):
                rules = result.setdefault('*', dict.fromkeys(keys, False))
                for key in keys:
                    if profile['%s_global' % key]:
                        rules[key] = True
            for line in profile.chatter_line_ids:
                rules = result.setdefault(
                    line.model_name, dict.fromkeys(keys, False))
                for key in keys:
                    if line[key]:
                        rules[key] = True
        # 有全局开关时,具体模型行也要叠加全局限制
        if '*' in result:
            for model, rules in result.items():
                if model == '*':
                    continue
                for key in keys:
                    if result['*'][key]:
                        rules[key] = True
        return result

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id')
    def _get_no_search_models(self):
        """禁止搜索的模型名列表(给前端隐藏搜索栏用)。"""
        models_ = set()
        for profile in self._iter_profiles():
            for line in profile.model_line_ids:
                if line.hide_search:
                    models_.add(line.model_name)
        return tuple(sorted(models_))

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id')
    def _get_hidden_menu_ids(self):
        menus = self.env['ir.ui.menu'].sudo()
        for profile in self._iter_profiles():
            menus |= profile.hide_menu_ids
        if not menus:
            return frozenset()
        # 子菜单一并隐藏
        all_menus = menus.with_context(**{'ir.ui.menu.full_list': True}).search(
            [('id', 'child_of', menus.ids)])
        return frozenset(all_menus.ids)

    @api.model
    @tools.ormcache('self.env.uid', 'self.env.company.id')
    def _get_hidden_binding_action_ids(self):
        """隐藏的报表/动作(ir.actions 主键)id 集合。"""
        ids = set()
        for profile in self._iter_profiles():
            ids.update(profile.hidden_report_ids.ids)
            ids.update(profile.hidden_action_ids.ids)
        return frozenset(ids)

    # ==================================================================
    # 工具
    # ==================================================================

    @api.model
    def _eval_domain(self, domain_str):
        """按 ir.rule 的习惯求值 domain 字符串。"""
        eval_context = {
            'user': self.env.user.sudo(),
            'uid': self.env.uid,
            'time': safe_eval_module.time,
            'company_id': self.env.company.id,
            'company_ids': self.env.companies.ids,
        }
        return safe_eval(domain_str, eval_context)


class SamModelLine(models.Model):
    _name = 'sam.model.line'
    _inherit = ['sam.cache.mixin']
    _description = 'SAM Model Rule'

    profile_id = fields.Many2one('sam.profile', string='Profile', required=True,
                                 ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               ondelete='cascade')
    model_name = fields.Char(string='Model Name', related='model_id.model',
                             store=True, readonly=True)
    readonly = fields.Boolean(string='Read-only',
                              help='Equivalent to blocking create, edit, delete, '
                                   'duplicate, and archive simultaneously.')
    hide_create = fields.Boolean(string='Block Create')
    hide_edit = fields.Boolean(string='Block Edit')
    hide_delete = fields.Boolean(string='Block Delete')
    hide_duplicate = fields.Boolean(string='Block Duplicate')
    hide_archive = fields.Boolean(string='Block Archive/Unarchive')
    hide_export = fields.Boolean(string='Block Export')
    hide_import = fields.Boolean(string='Block Import')
    hide_search = fields.Boolean(
        string='Block Search',
        help='Hide the entire search bar on this model\'s views '
             '(search input, filters, group by, favorites).')


class SamFieldLine(models.Model):
    _name = 'sam.field.line'
    _inherit = ['sam.cache.mixin']
    _description = 'SAM Field Rule'

    profile_id = fields.Many2one('sam.profile', string='Profile', required=True,
                                 ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               ondelete='cascade')
    model_name = fields.Char(string='Model Name', related='model_id.model',
                             store=True, readonly=True)
    field_id = fields.Many2one(
        'ir.model.fields', string='Field', required=True, ondelete='cascade',
        domain="[('model_id', '=', model_id)]")
    field_name = fields.Char(string='Field Name', related='field_id.name',
                             store=True, readonly=True)
    invisible = fields.Boolean(string='Hidden')
    readonly = fields.Boolean(string='Read-only')
    required = fields.Boolean(string='Required')
    remove_link = fields.Boolean(
        string='Remove Internal Link',
        help='Remove the internal link arrow next to relational fields, '
             'preventing navigation to the related record\'s full form.')
    no_create = fields.Boolean(
        string='Block Create & Edit Options',
        help='Remove "New..." and "Create and Edit" options from '
             'relational field dropdowns.')


class SamDomainLine(models.Model):
    _name = 'sam.domain.line'
    _inherit = ['sam.cache.mixin']
    _description = 'SAM Record Rule'

    profile_id = fields.Many2one('sam.profile', string='Profile', required=True,
                                 ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               ondelete='cascade')
    model_name = fields.Char(string='Model Name', related='model_id.model',
                             store=True, readonly=True)
    domain = fields.Char(
        string='Domain', required=True, default='[]',
        help='e.g. [(\'user_id\', \'=\', user.id)], available variables: '
             'user / uid / company_id / company_ids / time.')
    perm_read = fields.Boolean(string='Apply to Read', default=True)
    perm_write = fields.Boolean(string='Apply to Write')
    perm_create = fields.Boolean(string='Apply to Create')
    perm_unlink = fields.Boolean(string='Apply to Delete')
    rule_id = fields.Many2one('ir.rule', string='Generated Record Rule',
                              readonly=True, copy=False, ondelete='set null')

    @api.constrains('domain', 'model_id')
    def _check_domain(self):
        for line in self:
            try:
                domain = self.env['sam.profile']._eval_domain(line.domain)
                if line.model_name in self.env:
                    self.env[line.model_name].sudo().search_count(domain, limit=1)
            except Exception as exc:
                raise ValidationError(
                    _('Invalid domain expression for model %(model)s: %(error)s',
                      model=line.model_name, error=exc)) from exc

    # ------- ir.rule 同步:数据级强制(读/写/建/删全部走记录规则)-------

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._sam_sync_rules()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get('sam_rule_sync'):
            self._sam_sync_rules()
        return res

    def unlink(self):
        rules = self.sudo().rule_id
        res = super().unlink()
        if rules:
            rules.sudo().unlink()
        return res

    def _sam_rule_vals(self):
        """生成全局 ir.rule 值:域为条件表达式,仅对配置内的用户生效,
        其他用户得到恒真域,不受任何影响。"""
        self.ensure_one()
        profile = self.profile_id
        conds = []
        if profile.user_ids:
            conds.append('user.id in %s' % sorted(profile.user_ids.ids))
        if profile.group_ids:
            conds.append('bool(set(user.groups_id.ids) & set(%s))'
                         % sorted(profile.group_ids.ids))
        cond = '(%s)' % ' or '.join(conds) if conds else 'False'
        if profile.company_ids:
            cond = '%s and company_id in %s' % (
                cond, sorted(profile.company_ids.ids))
        domain_force = "(%s) if (%s) else [(1, '=', 1)]" % (
            self.domain or '[]', cond)
        return {
            'name': 'Access Manage Studio: %s / %s' % (
                profile.name, self.model_name),
            'model_id': self.model_id.id,
            'domain_force': domain_force,
            'perm_read': self.perm_read,
            'perm_write': self.perm_write,
            'perm_create': self.perm_create,
            'perm_unlink': self.perm_unlink,
            'active': profile.active and bool(conds),
            'groups': [(6, 0, [])],
        }

    def _sam_sync_rules(self):
        Rule = self.env['ir.rule'].sudo()
        for line in self:
            vals = line._sam_rule_vals()
            if line.rule_id:
                line.rule_id.sudo().write(vals)
            else:
                line.with_context(sam_rule_sync=True).rule_id = Rule.create(vals)


class SamButtonLine(models.Model):
    _name = 'sam.button.line'
    _inherit = ['sam.cache.mixin']
    _description = 'SAM Button Rule'

    profile_id = fields.Many2one('sam.profile', string='Profile', required=True,
                                 ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               ondelete='cascade')
    model_name = fields.Char(string='Model Name', related='model_id.model',
                             store=True, readonly=True)
    element_type = fields.Selection([
        ('button', 'Button / Smart Button'),
        ('page', 'Tab'),
    ], string='Type', required=True, default='button')
    name = fields.Char(string='Technical Name',
                       help='The name attribute of the button (method name or '
                            'action ID) / the name attribute of the tab.')
    string = fields.Char(string='Display Text',
                         help='Match by string label. Use either this or '
                              'technical name.')


class SamFilterLine(models.Model):
    _name = 'sam.filter.line'
    _inherit = ['sam.cache.mixin']
    _description = 'SAM Filter Rule'

    profile_id = fields.Many2one('sam.profile', string='Profile', required=True,
                                 ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               ondelete='cascade')
    model_name = fields.Char(string='Model Name', related='model_id.model',
                             store=True, readonly=True)
    name = fields.Char(string='Technical Name',
                       help='The name attribute of the &lt;filter&gt; node in '
                            'search views. Applies to both filters and group bys.')
    string = fields.Char(string='Display Text')


class SamViewLine(models.Model):
    _name = 'sam.view.line'
    _inherit = ['sam.cache.mixin']
    _description = 'SAM View Rule'

    profile_id = fields.Many2one('sam.profile', string='Profile', required=True,
                                 ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               ondelete='cascade')
    model_name = fields.Char(string='Model Name', related='model_id.model',
                             store=True, readonly=True)
    view_type = fields.Selection(VIEW_TYPES, string='View Type', required=True)


class SamChatterLine(models.Model):
    _name = 'sam.chatter.line'
    _inherit = ['sam.cache.mixin']
    _description = 'SAM Chatter Rule'

    profile_id = fields.Many2one('sam.profile', string='Profile', required=True,
                                 ondelete='cascade', index=True)
    model_id = fields.Many2one('ir.model', string='Model', required=True,
                               ondelete='cascade')
    model_name = fields.Char(string='Model Name', related='model_id.model',
                             store=True, readonly=True)
    hide_chatter = fields.Boolean(string='Hide Entire Chatter')
    hide_send_message = fields.Boolean(string='Block Send Message')
    hide_log_note = fields.Boolean(string='Block Log Note')
    hide_activities = fields.Boolean(string='Block Schedule Activities')
