# -*- coding: utf-8 -*- 

import datetime

from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError


class MrpProductionRequest(models.Model):
    _inherit = 'mrp.production.request'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting'),
        ('validated', 'Validated'),
        ('planned', 'Planned'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')],string='State', copy=False, index=True, readonly=True,
        store=True, tracking=True, default='draft',
        help=" * Draft: The MR is not confirmed yet.\n"
             " * Waiting: The MR is confirmed but waiting for approving.\n"
             " * Validated: The MR is confirmed, the production order can be created.\n"
             " * Planned: The MR is planned.\n"
             " * Done: The MR is done, can't be update or deleted anymore.\n"
             " * Cancelled: The MR has been cancelled, can't be confirmed anymore.")

    def _action_plan(self):
        self.write({'state': 'planned'})

    def _action_unplan(self):
        self.write({'state': 'validated'})

    def _prepare_mrp_production(self, quantity=False, product_uom_id=False):
        res = super(MrpProductionRequest,self)._prepare_mrp_production(quantity=quantity, product_uom_id=product_uom_id)
        if self.env.context.get('mrp_production_request_ids',False):
            res.update({'mrp_production_request_ids':self.env.context['mrp_production_request_ids']})
        return res