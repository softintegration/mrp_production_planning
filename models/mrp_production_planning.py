# -*- coding: utf-8 -*- 

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT

AUTHORISED_STATES_FOR_REMOVE = ('draft', 'cancel')


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
                              states={'draft': [('readonly', False)]}, readonly=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users',string='Responsible',default=lambda self: self.env.user)
    state = fields.Selection([('draft', _('Draft')),
                              ('in_progress', _('In progress')),
                              ('done', _('Done')),
                              ('cancel', _('Canceled'))], default='draft', required=True)
    line_ids = fields.One2many('mrp.production.planning.line', 'planning_id'
                               ,states={'draft': [('readonly', False)],'in_progress':[('readonly', False)]}, readonly=True)
    line_ids_count = fields.Integer(compute='_compute_line_ids_count')

    @api.depends('line_ids')
    def _compute_line_ids_count(self):
        for each in self:
            each.line_ids_count = len(each.line_ids)

    """@api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for each in self:
            if each.date_to and each.date_from > each.date_to:
                raise ValidationError(_(
                    'Planning %(planning_name)s: start date (%(date_from)s) must be earlier than planning end date (%(date_to)s).',
                    planning_name=each.name, date_from=each.date_from, date_to=each.date_to,
                ))"""



    def action_validate(self):
        #self._check_lines_to_schedule()
        for each in self:
            dynamic_prefix_fields = self._build_dynamic_prefix_fields()
            each.name = self.env['ir.sequence'].with_context(dynamic_prefix_fields=dynamic_prefix_fields).next_by_code(
                self._name)
        return self._action_validate()

    def _build_dynamic_prefix_fields(self):
        self.ensure_one()
        vals = {}
        for field_name, _ in self._fields.items():
            vals.update({field_name: getattr(self, field_name)})
        return vals

    def _action_validate(self):
        self.write({'state': 'in_progress'})

    def action_cancel(self):
        return self._action_cancel()

    def _action_cancel(self):
        self.write({'state': 'cancel'})

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
        return {
            'name': _('Manufacturing requests to plan'),
            'view_mode': 'tree',
            'views': [(self.env.ref('mrp_production_planning.mrp_production_planning_line_tree_view').id, 'tree'),],
            'res_model': 'mrp.production.planning.line',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'context':{'default_planning_id':self.id},
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

    planning_id = fields.Many2one('mrp.production.planning', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', help="Used to manually re-order the line")
    mrp_production_request_id = fields.Many2one('mrp.production.request', string="Manufacturing request", required=True,
                                                domain=[('state','=','validated')])
    product_id = fields.Many2one('product.product', 'Product', related='mrp_production_request_id.product_id')
    quantity = fields.Float(string="Requested Quantity", digits='Product Unit of Measure',store=True,readonly=False)
    product_uom_id = fields.Many2one('uom.uom', 'Product Unit of Measure',
                                     related='mrp_production_request_id.product_uom_id')
    origin = fields.Char('Source', related='mrp_production_request_id.origin')
    date_request = fields.Datetime('Date', related='mrp_production_request_id.date_request')
    date_desired = fields.Datetime('Desired Date', related='mrp_production_request_id.date_desired')
    quantity_produced = fields.Float(string='Produced Quantity',related='mrp_production_request_id.quantity_produced')
    planning_state = fields.Selection(string='Planning Status',related='planning_id.state')
    state = fields.Selection(string='Status',related='mrp_production_request_id.state')
    average = fields.Float(string="Average",
                           help="The value of this field will be used as priority indicator of the Manufacturing request in the planning")

    @api.model_create_multi
    def create(self, vals):
        res = super(MrpProductionPlanningLine,self).create(vals)
        for rec in res:
            if rec.planning_state in ('done','cancel'):
                raise ValidationError(_("Can not add line to Done/Cancelled Planning!"))
        return res

    def unlink(self):
        for rec in self:
            if rec.planning_state in ('done','cancel'):
                raise ValidationError(_("Can not remove line from Done/Cancelled Planning!"))
        return super(MrpProductionPlanningLine,self).unlink()



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
            raise ValidationError(_("No Scheduling rules have been detected,please check that there are configured scheduling rules that can be applied!"))
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
