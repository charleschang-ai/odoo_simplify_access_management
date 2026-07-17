# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """存量记录权限行升级后同步生成 ir.rule。"""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['sam.domain.line'].search([])._sam_sync_rules()
