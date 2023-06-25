# -*- coding: utf-8 -*- 

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.misc import DEFAULT_SERVER_DATE_FORMAT
from dateutil.relativedelta import relativedelta
from datetime import datetime
from odoo.tools.float_utils import float_is_zero

AUTHORISED_STATES_FOR_REMOVE = ('draft', 'cancel')
DATE_ZERO = datetime.strptime('1970-01-01', DEFAULT_SERVER_DATE_FORMAT)
STATES_TO_VALIDATE = ('in_progress',)


class MrpProductionPlanning(models.Model):
    """ Manufacturing Orders Planning"""
    _name = 'mrp.production.planning'
    _description = 'Manufacturing planning'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc'

    name = fields.Char('Reference', copy=False, readonly=True, default=lambda x: _('New'))
    date_start = fields.Datetime(string="Date from", help="Manufacturing Planning date start", required=True,
                                 states={'draft': [('readonly', False)]}, readonly=True)
    date_done = fields.Datetime(string="Validation Date", help="Manufacturing Planning validation date", required=False,
                                states={'draft': [('readonly', False)], 'in_progress': [('readonly', False)]},
                                readonly=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.user,
                              states={'draft': [('readonly', False)]}, readonly=True)
    state = fields.Selection([('draft', _('Draft')),
                              ('in_progress', _('In progress')),
                              ('done', _('Validated')),
                              ('cancel', _('Canceled'))], default='draft', required=True)
    line_ids = fields.One2many('mrp.production.planning.line', 'planning_id'
                               , states={'draft': [('readonly', False)], 'in_progress': [('readonly', False)]},
                               readonly=True)
    line_ids_count = fields.Integer(compute='_compute_line_ids_count')
    planned_workorder_ids = fields.One2many('mrp.workorder', 'planning_id', 'Work Orders')
    planned_workorder_ids_count = fields.Integer(compute='_compute_planned_workorder_ids_count')

    def _planned_manufacturing_orders(self):
        return self.mapped("planned_workorder_ids").mapped("production_id")

    @api.depends('planned_workorder_ids')
    def _compute_planned_workorder_ids_count(self):
        for each in self:
            each.planned_workorder_ids_count = len(each.planned_workorder_ids)

    @api.depends('line_ids')
    def _compute_line_ids_count(self):
        for each in self:
            each.line_ids_count = len(each.line_ids)

    def _get_requested_qty_by_product(self, product_id, product_uom_id):
        self.ensure_one()
        return sum(self.line_ids.filtered(
            lambda pl: pl.product_id.id == product_id and pl.product_uom_id.id == product_uom_id).mapped("quantity"))

    """@api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for each in self:
            if each.date_to and each.date_from > each.date_to:
                raise ValidationError(_(
                    'Planning %(planning_name)s: start date (%(date_from)s) must be earlier than planning end date (%(date_to)s).',
                    planning_name=each.name, date_from=each.date_from, date_to=each.date_to,
                ))"""

    def action_in_progress(self):
        # self._check_lines_to_schedule()
        for each in self:
            dynamic_prefix_fields = self._build_dynamic_prefix_fields()
            each.name = self.env['ir.sequence'].with_context(dynamic_prefix_fields=dynamic_prefix_fields).next_by_code(
                self._name)
        return self._action_in_progress()

    def action_validate(self):
        self._check_validation()
        self._confirm_planned_manufacturing_orders()
        self._action_validate()

    def _check_validation(self):
        for each in self:
            if each.state not in STATES_TO_VALIDATE:
                raise ValidationError(_("Only In progress Planning(s) can be validated!"))
            if not each.date_done:
                raise ValidationError(_("Validation date is required!"))
            if not self._planned_manufacturing_orders():
                raise ValidationError(_("No planned manufacturing orders has been found!"))
            for order in self._planned_manufacturing_orders():
                # difference between the quantity requested and the quantity planned in orders
                diff = order.product_qty - each._get_requested_qty_by_product(order.product_id.id,
                                                                              order.product_uom_id.id)
                if not float_is_zero(diff, precision_rounding=order.product_uom_id.rounding):
                    raise ValidationError(
                        _("Inconsistency between the Requested Qty and the Planned Qty has been found for product %s") % order.product_id.display_name)

    def _confirm_planned_manufacturing_orders(self):
        self._planned_manufacturing_orders().action_confirm()

    def _action_validate(self):
        self.write({'state': 'done'})

    def _build_dynamic_prefix_fields(self):
        self.ensure_one()
        vals = {}
        for field_name, _ in self._fields.items():
            vals.update({field_name: getattr(self, field_name)})
        return vals

    def _action_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_cancel(self):
        self._remove_related_manufacturings()
        return self._action_cancel()

    def _action_cancel(self):
        self.write({'state': 'cancel'})

    def _remove_related_manufacturings(self):
        self._planned_manufacturing_orders().unlink()

    def _plan_related_manufacturing_requests(self):
        self.mapped("line_ids").mapped("mrp_production_request_id")._action_plan()

    def _check_lines_to_schedule(self):
        for each in self:
            if not each.line_ids:
                raise ValidationError(_("Manufacturing requests to plan are required!"))

    def action_get_production_requests(self):
        for each in self:
            requests = each._get_production_requests_by_period(each.date_from, each.date_to)
            if each.env.context.get('overwrite_exiting_lines', False):
                each.line_ids.unlink()
            each.write({'line_ids': [(0, 0, {'mrp_production_request_id': request.id}) for request in requests]})

    @api.model
    def _get_production_requests_by_period(self, date_from, date_to, reference_date='date_desired',
                                           dates_included=False):
        domain = [('state', '=', 'validated')]
        if dates_included:
            domain.extend([(reference_date, '>=', date_from.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                           (reference_date, '<=', date_to.strftime(DEFAULT_SERVER_DATETIME_FORMAT))])
        else:
            domain.extend([(reference_date, '>', date_from.strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                           (reference_date, '<', date_to.strftime(DEFAULT_SERVER_DATETIME_FORMAT))])
        requests = self.env['mrp.production.request'].search(domain)
        return requests

    def show_line_ids(self):
        self.ensure_one()
        domain = [('planning_id', 'in', self.ids)]
        views = [(self.env.ref('mrp_production_planning.mrp_production_planning_line_tree_view').id, 'tree'),
                 (self.env.ref('mrp_production_planning.mrp_production_planning_line_filter_view').id,'search')]
        if self.state in ('done', 'cancel'):
            views = [
                (self.env.ref('mrp_production_planning.mrp_production_planning_line_tree_view_readonly').id, 'tree'),
                (self.env.ref('mrp_production_planning.mrp_production_planning_line_filter_view').id,'search')]
        return {
            'name': _('Manufacturing requests to plan'),
            'view_mode': 'tree',
            'views': views,
            'res_model': 'mrp.production.planning.line',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {'default_planning_id': self.id},
            'domain': domain,
        }

    def action_create_workorder_planning(self):
        return self._action_create_workorder_planning()

    def _action_create_workorder_planning(self):
        for each in self:
            orders_to_plan = self.env['mrp.production']
            if each.env.context.get('overwrite_exiting_lines', False) and each._planned_manufacturing_orders():
                # unlink the Manufacturing order to auto removing the related workorders
                each._planned_manufacturing_orders().unlink()
            # loop on planning lines by the sequence order (that has been calculated by the scheduler)
            next_wo = {}
            # planning lines can be merged so we have to track the merged lines because they can be used before that they are detected by the loop
            already_used_lines = []
            for planning_line in each.line_ids:
                if planning_line.id in already_used_lines:
                    continue
                sibling_lines = planning_line._get_sibling_lines()
                quantity_to_plan = sum(sibling_lines.mapped("quantity"))
                already_used_lines.extend(sibling_lines.ids)
                order = planning_line.mrp_production_request_id._action_make_production_order(
                    quantity=quantity_to_plan)
                order.write({'planning_id': planning_line.planning_id.id,
                             'date_planned_start': each.date_start,
                             'plan_mrp_production_request_ids': [
                                 (6, 0, sibling_lines.mapped("mrp_production_request_id").ids)]})
                orders_to_plan |= order
                planning_previous_wo = False
                for workorder in order.workorder_ids:
                    workorder.write({'planning_id': each.id})
                    next_wo.update({planning_previous_wo: workorder})
                    planning_previous_wo = workorder
            for workorder, next_workorder in next_wo.items():
                try:
                    workorder.write({'next_work_order_id': next_workorder.id})
                except AttributeError as ae:
                    continue
            for order in orders_to_plan:
                order._plan_workorders()
        self._plan_related_manufacturing_requests()

    """def _plan_workorders(self):
        self.ensure_one()
        date_start = False
        # temporary planning of workcenters used by planning to avoid using already assigned workcenter (assigned in this method)
        workcenters_date_start = {}
        for workorder in self.planned_workorder_ids:
            # first of all,we have to get the previous workorder because in all cases we can not start workorder before that the previous one finished
            previous_wo = workorder._previous_workorder()
            if not workcenters_date_start.get(workorder.workcenter_id.id,False):
                # in this case the date start of the workorder is the greater one between the date start of the planning desired by the planner
                # and planned date finished of the previous workorder
                date_start = max(self.date_start,previous_wo.date_planned_finished or DATE_ZERO)
            else:
                # in the second case,the same workcenter that we will use can be already planned so we have to take the greater date between
                # the leave date finish of the current workcenter and planned date finished of the previous workorder
                # not the or in the second parameter,in the case there is no previous workorder,the workorder with the free workcenter
                # will planned to start immediatly after the free of the workcenter
                date_start = max(workcenters_date_start[workorder.workcenter_id.id],previous_wo.date_planned_finished
                                 or workcenters_date_start[workorder.workcenter_id.id])
            workorder_leave_dict = workorder._preprare_leave(date_start)
            workorder.leave_id = self.env['resource.calendar.leaves'].create(workorder_leave_dict)
            workcenters_date_start.update({workorder.workcenter_id.id:workorder.leave_id.date_to})

    def _plan_manufacturing_orders(self):
        manufacturing_orders = self._planned_manufacturing_orders()
        for mo in manufacturing_orders:
            mo.date_planned_start = min(mo.workorder_ids.mapped("date_planned_start"))
            mo.date_planned_finished = max(mo.workorder_ids.mapped("date_planned_finished"))

   """

    def show_planned_workorder_ids(self):
        self.ensure_one()
        domain = [('planning_id', 'in', self.ids)]
        views = [(self.env.ref('mrp_production_planning.mrp_workorder_gantt_view').id, 'ganttaps'),
                 (self.env.ref('mrp_production_planning.workcenter_line_calendar').id, 'calendar'),
                 (self.env.ref('mrp.mrp_production_workorder_tree_view').id, 'tree'),
                 (self.env.ref('mrp.view_mrp_production_work_order_search').id, 'search'), ]
        if self.state in ('done', 'cancel'):
            views[1] = (self.env.ref('mrp_production_planning.mrp_production_workorder_tree_view_readonly').id, 'tree')
        return {
            'name': _('Planned workorders'),
            'view_mode': 'ganttaps,calendar,tree',
            'views': views,
            'res_model': 'mrp.workorder',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context': {'default_planning_id': self.id, },
            'domain': domain,
        }

    def unlink(self):
        for each in self:
            if each.state not in AUTHORISED_STATES_FOR_REMOVE:
                raise ValidationError(
                    _("Can not remove the Manufacturing planning,you have to check the state or to cancel the planning"))
        return super(MrpProductionPlanning, self).unlink()

    _sql_constraints = [
        ('name_company_uniq', 'unique(name)', 'Planning Reference must be unique !'),
    ]


class MrpProductionPlanningLine(models.Model):
    _name = 'mrp.production.planning.line'
    _description = 'Manufacturing planning line'
    _order = 'sequence'
    _rec_name = 'mrp_production_request_id'

    planning_id = fields.Many2one('mrp.production.planning', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', help="Used to manually re-order the line")
    mrp_production_request_id = fields.Many2one('mrp.production.request', string="Manufacturing request", required=True,
                                                domain=[('state', '=', 'validated')])
    product_id = fields.Many2one('product.product', 'Product', related='mrp_production_request_id.product_id')
    quantity = fields.Float(string="Requested Quantity", digits='Product Unit of Measure', store=True, readonly=False)
    product_uom_id = fields.Many2one('uom.uom', 'Product Unit of Measure',
                                     related='mrp_production_request_id.product_uom_id')
    origin = fields.Char('Source', related='mrp_production_request_id.origin')
    date_request = fields.Datetime('Date', related='mrp_production_request_id.date_request')
    date_desired = fields.Datetime('Desired Date', related='mrp_production_request_id.date_desired')
    quantity_produced = fields.Float(string='Produced Quantity', related='mrp_production_request_id.quantity_produced')
    planning_state = fields.Selection(string='Planning Status', related='planning_id.state')
    state = fields.Selection(string='Status', related='mrp_production_request_id.state')
    average = fields.Float(string="Average",
                           help="The value of this field will be used as priority indicator of the Manufacturing request in the planning")
    merge_request_ids = fields.Many2many('mrp.production.planning.line', 'mrp_production_planning_line_merge_rel',
                                         'parent_id', 'child_id', string='Merge with',
                                         help='The manufacturing requests added here will be merged with the current Request '
                                              'and will be exposed to planner as one single request')

    @api.model_create_multi
    def create(self, vals):
        res = super(MrpProductionPlanningLine, self).create(vals)
        for rec in res:
            if rec.planning_state in ('done', 'cancel'):
                raise ValidationError(_("Can not add line to Validated/Cancelled Planning!"))
        return res

    def unlink(self):
        for rec in self:
            if rec.planning_state in ('done', 'cancel'):
                raise ValidationError(_("Can not remove line from Validated/Cancelled Planning!"))
        return super(MrpProductionPlanningLine, self).unlink()

    @api.onchange('mrp_production_request_id')
    def _onchange_mrp_production_request_id(self):
        if self.mrp_production_request_id:
            self.quantity = self.mrp_production_request_id.quantity

    @api.constrains('mrp_production_request_id')
    def _check_production_requests_uniqueness(self):
        for each in self:
            if len(each.planning_id.line_ids) != len(each.planning_id.line_ids.mapped("mrp_production_request_id")):
                raise ValidationError(_("Some manufacturing requests are inserted several times!"))

    def action_schedule_production_requests(self):
        # we get the average of production request by the universal method of scheduling then use the returned result
        # by the specific scheduling of mrp production planning lines
        if not self.mapped("mrp_production_request_id"):
            raise ValidationError(_("No Manufacturing requests have been selected!"))
        lines_average = self.env['scheduling.rule']._schedule_records(self.mapped("mrp_production_request_id"))
        if not lines_average:
            raise ValidationError(
                _("No Scheduling rules have been detected,please check that there are configured scheduling rules that can be applied!"))
        self._schedule(lines_average)

    @api.model
    def _schedule(self, lines_average):
        lines_to_reorder = self
        for line_id, line_average in lines_average.items():
            planning_line = self.search([('mrp_production_request_id', '=', line_id)])
            planning_line.average = line_average
            lines_to_reorder |= planning_line
        seq = 0
        for line in sorted(lines_to_reorder, key=lambda l: l.average, reverse=True):
            line.sequence = seq
            seq += 1

    def _get_sibling_lines(self):
        """ The sibling lines are either the ones merged with me or the one I am merged with """
        self.ensure_one()
        sibling_lines = self
        for line in self.merge_request_ids:
            sibling_lines |= line._get_sibling_lines()
        sibling_lines |= self.planning_id.line_ids.filtered(lambda l: self.id in l.merge_request_ids.ids)
        return sibling_lines
