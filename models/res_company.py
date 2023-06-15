# -*- coding: utf-8 -*-

from odoo import models, fields


class res_company(models.Model):
    _inherit = "res.company"

    always_use_default_workcenter = fields.Boolean(string='Use always the default workcenter')