# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    always_use_default_workcenter = fields.Boolean(string='Use always the default workcenter',
                                                   related='company_id.always_use_default_workcenter',
                                                   readonly=False,
                                                   help='Check this option if you want to force the planning to set the default workcenter '
                                                        'specified in the bom instead of the best one (in terms of performance).')
