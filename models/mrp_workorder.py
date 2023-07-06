# -*- coding: utf-8 -*- 

import datetime

from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    planning_id = fields.Many2one('mrp.production.planning')
    workcenter_id = fields.Many2one(
        'mrp.workcenter', 'Work Center', required=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)], 'progress': [('readonly', True)]},
        group_expand=False, check_company=True)
    calendar_duration_expected = fields.Float(string='Calendar duration expected',compute='_compute_calendar_duration_expected')

    @api.depends('date_planned_start','date_planned_finished')
    def _compute_calendar_duration_expected(self):
        for each in self:
            if each.date_planned_finished and each.date_planned_start:
                calendar_duration_expected = each.date_planned_finished - each.date_planned_start
                each.calendar_duration_expected = calendar_duration_expected.total_seconds()





    """def _preprare_leave(self, date_start):
        res = {'name': self.display_name,
               'calendar_id': self.workcenter_id.resource_calendar_id.id,
               'date_from': date_start,
               'date_to': date_start + relativedelta(minutes=self.duration_expected),
               'resource_id': self.workcenter_id.resource_id.id,
               'time_type': 'other'
               }
        return res

    def _previous_workorder(self, order='date_planned_finished DESC'):
        domain = [('next_work_order_id', 'in', self.ids)]
        return self.search(domain, limit=1, order=order)
"""