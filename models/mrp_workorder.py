# -*- coding: utf-8 -*- 

import datetime

from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    planning_id = fields.Many2one('mrp.production.planning')


    def _preprare_leave(self, date_start):
        res = {'name': self.display_name,
               'calendar_id': self.workcenter_id.resource_calendar_id.id,
               'date_from': date_start,
               'date_to': date_start + relativedelta(minutes=self.duration_expected),
               'resource_id': self.workcenter_id.resource_id.id,
               'time_type': 'other'
               }
        return res

    def _previous_workorder(self,order='date_planned_finished DESC'):
        """ This method return the workorder that is just before the current workorder"""
        domain = [('next_work_order_id', 'in', self.ids)]
        return self.search(domain,limit=1,order=order)


