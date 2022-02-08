# -*- coding: utf-8 -*-

from datetime import date, datetime, timedelta

from odoo import models, fields, api, _
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError, ValidationError


class HrPayrollPeriod(models.Model):
    _name = 'hr.payroll.period'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'
    _order = 'date_start asc'
    _description = 'Payroll Period'

    code = fields.Char(string="Code", index=True, copy=False)
    name = fields.Char(string='Name', required=True, copy=False, readonly=True)
    year = fields.Integer(string='Year', required=True, copy=False, readonly=True,
                          states={'open': [('readonly', False)]})
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('close', 'Close')],
        string='State',
        default='draft',
        readonly=True, tracking=True)
    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], string='Month', readonly=True, states={'open': [('readonly', False)]})
    payroll_period = fields.Selection([
        ('01', 'Daily'),
        ('02', 'Weekly'),
        ('03', 'Fourteen'),
        ('10', 'Decennial'),
        ('04', 'Biweekly'),
        ('05', 'Monthly'),
        ('99', 'Another Peridiocity')
    ], string='Period', default="04", required=True, readonly=True)
    date_start = fields.Date(string='Date Start', required=True, readonly=True)
    date_end = fields.Date(string='Date End', required=True, readonly=True)
    folder_id = fields.Many2one('documents.folder', string='Folder', required=True)

    payslip_run_draft = fields.Integer(compute='_compute_statistics_count', string="Payslip Run (Draft)")
    payslip_run_done = fields.Integer(compute='_compute_statistics_count', string="Payslip Run (Done)")
    payslip_run_cancel = fields.Integer(compute='_compute_statistics_count', string="Payslip Run (Cancel)")

    payslip_draft = fields.Integer(compute='_compute_statistics_count', string="Payslip (Draft)")
    payslip_done = fields.Integer(compute='_compute_statistics_count', string="Payslip (Done)")
    payslip_cancel = fields.Integer(compute='_compute_statistics_count', string="Payslip (Cancel)")

    cfdi_draft = fields.Integer(compute='_compute_statistics_count', string="CFDI (Draft)")
    cfdi_done = fields.Integer(compute='_compute_statistics_count', string="CFDI (Done)")
    cfdi_cancel = fields.Integer(compute='_compute_statistics_count', string="CFDI (Cancel)")
    cfdi_problem = fields.Integer(compute='_compute_statistics_count', string="CFDI (Problem)")

    settlement_draft = fields.Integer(compute='_compute_statistics_count', string="Settlement (Draft)")
    settlement_done = fields.Integer(compute='_compute_statistics_count', string="Settlement (Done)")
    settlement_cancel = fields.Integer(compute='_compute_statistics_count', string="Settlement (Cancel)")

    start_monthly_period = fields.Boolean('Start of Monthly Period', default=False, readonly=True,
                                          states={'open': [('readonly', False)]})
    end_monthly_period = fields.Boolean('End of Monthly Period', default=False, readonly=True,
                                        states={'open': [('readonly', False)]})
    start_bumonthly_period = fields.Boolean('Beginning of the Bimonthly Period', default=False, readonly=True,
                                            states={'open': [('readonly', False)]})
    end_bumonthly_period = fields.Boolean('End of Bimonthly Period', default=False, readonly=True,
                                          states={'open': [('readonly', False)]})
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id,
                                 required=True, readonly=True)
    type = fields.Selection([
        ('ordinary', 'Ordinary'),
        ('settlement', 'Settlement'),
        ('special', 'Special'),
    ], string="Type", default="ordinary", states={'open': [('readonly', True)]})

    # @api.constrains('year', 'month', 'company_id', 'type')
    # def _check_unique_period(self):
    #     for res in self:
    #         if self.search([
    #             ('id', '!=', res.id),
    #             ('type', '=', res.type),
    #             ('year', '=', res.year),
    #             ('month', '=', res.month),
    #             ('company_id', '=', res.company_id.id)], limit=1):
    #             raise UserError(_('Mirameeeeee'))

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('name', operator, name), ('code', operator, name)]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    @api.model
    def _compute_statistics_count(self):
        for period in self:
            period.payslip_run_draft = len(
                self.env['hr.payslip.run'].search([('payroll_period_id', '=', period.id), ('state', '=', 'draft')]))
            period.payslip_run_cancel = len(
                self.env['hr.payslip.run'].search([('payroll_period_id', '=', period.id), ('state', '=', 'cancel')]))
            period.payslip_run_done = len(
                self.env['hr.payslip.run'].search([('payroll_period_id', '=', period.id), ('state', '=', 'close')]))

            period.payslip_draft = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                      ('state', 'in', ['draft']),
                                                                      ('settlement', '=', False)]))
            period.payslip_done = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                     ('state', 'in', ['done']),
                                                                     ('settlement', '=', False)]))
            period.payslip_cancel = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                       ('state', 'in', ['cancel']),
                                                                       ('settlement', '=', False)]))

            period.cfdi_draft = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                   ('state', 'in', ['draft', 'done']),
                                                                   ('contracting_regime', 'not in', ['05']),
                                                                   (
                                                                       'invoice_status', 'in',
                                                                       ['invoice_not_generated'])]))
            period.cfdi_done = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                  ('state', 'in', ['draft', 'done']),
                                                                  ('invoice_status', 'in', ['right_bill'])]))
            period.cfdi_cancel = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                    ('state', 'in', ['draft', 'done']),
                                                                    ('invoice_status', 'in', ['problems_canceled'])]))
            period.cfdi_problem = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                     ('state', 'in', ['draft', 'done']),
                                                                     ('invoice_status', 'in', ['invoice_problems'])]))

            period.settlement_draft = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                         ('settlement', '=', True),
                                                                         ('state', 'in', ['draft'])]))
            period.settlement_done = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                        ('settlement', '=', True),
                                                                        ('state', 'in', ['done']), ]))
            period.settlement_cancel = len(self.env['hr.payslip'].search([('payroll_period_id', '=', period.id),
                                                                          ('settlement', '=', True),
                                                                          ('state', 'in', ['cancel'])]))

    def open_payroll_period(self):
        for period in self:
            period.state = 'open'

    def close_payroll_period(self):
        today = date.today()
        for period in self:
            payslip_run_ids = self.env['hr.payslip.run'].search(
                [('payroll_period_id', '=', period.id)])
            if period.type in ['ordinary','special']:
                for run in payslip_run_ids:
                    if not run.posted_payroll:
                        raise ValidationError(_('You cannot close a period where there are unposted payroll.'))
            if period.type == 'settlement':
                settlement_ids = self.env['hr.payslip'].search(
                    [('payroll_period_id', '=', period.id),
                    ('settlement', '=', True),
                    ('state', 'in', ['draft','verify'])])
                if settlement_ids:
                    raise ValidationError(_('You cannot close periods with settlements in draft or verified status..'))
        return True

    @api.model
    def create(self, vals):
        res = super(HrPayrollPeriod, self).create(vals)
        code = "/"
        if res.type == 'ordinary':
            code = self.env['ir.sequence'].next_by_code('hr.payroll.period.or')
        if res.type == 'settlement':
            code = self.env['ir.sequence'].next_by_code('hr.payroll.period.se')
        if res.type == 'special':
            code = self.env['ir.sequence'].next_by_code('hr.payroll.period.ex')
        res.code = code[:2] + str(res.year) + str(res.month) + str(res.payroll_period) + code[2:]
        return res

    def unlink(self):
        raise UserError(_('Payroll periods cannot be eliminated.'))
        return super(HrPayrollPeriod, self).unlink()

    def write(self, vals):
        bimester = {
            '1': ['1', '2'],
            '2': ['1', '2'],
            '3': ['3', '4'],
            '4': ['3', '4'],
            '5': ['5', '6'],
            '6': ['5', '6'],
            '7': ['7', '8'],
            '8': ['7', '8'],
            '9': ['9', '10'],
            '10': ['9', '10'],
            '11': ['11', '12'],
            '12': ['11', '12'],
        }
        payslip_run_ids = self.env['hr.payslip.run'].search(
            [('payroll_period_id', '=', self.id), ('state', '=', 'close')])
        payslip_ids = self.env['hr.payslip'].search([('payroll_period_id', '=', self.id), ('state', '=', 'done')])
        payslip_bimester_ids = self.env['hr.payslip'].search([
            ('payroll_month', 'in', bimester[self.month]),
            ('company_id', '=', self.company_id.id),
            ('year', '=', self.year),
            ('payroll_period', '=', self.payroll_period),
            ('state', '=', 'done')
        ])
        if payslip_run_ids or payslip_ids or payslip_bimester_ids:
            for field in ['year', 'month', 'start_monthly_period', 'end_monthly_period', 'start_bumonthly_period',
                          'end_bumonthly_period']:
                if field in vals.keys():
                    raise UserError(
                        _('You cannot change the configuration of a period with closed payroll in its two-month period.'))

        year = self.year
        month = self.month

        if vals.get('year'):
            year = vals['year']
        if vals.get('month'):
            month = vals['month']

        if vals.get('start_monthly_period') and vals['start_monthly_period'] == True:
            if self.search([('year', '=', year),
                            ('month', '=', month),
                            ('company_id', '=', self.company_id.id),
                            ('start_monthly_period', '=', True),
                            ('payroll_period', '=', self.payroll_period),
                            ('settlement', '=', False)
                            ]):
                raise UserError(
                    _('There is already a payroll period configured as the beginning of the period for the same month.'))
        if vals.get('end_monthly_period') and vals['end_monthly_period'] == True:
            if self.search([('year', '=', year),
                            ('month', '=', month),
                            ('company_id', '=', self.company_id.id),
                            ('end_monthly_period', '=', True),
                            ('payroll_period', '=', self.payroll_period),
                            ('settlement', '=', False)
                            ]):
                raise UserError(
                    _('There is already a payroll period configured as the end of the period for the same month.'))
        if vals.get('start_bumonthly_period') and vals['start_bumonthly_period'] == True:
            if self.search([('year', '=', year),
                            ('month', '=', month),
                            ('company_id', '=', self.company_id.id),
                            ('start_bumonthly_period', '=', True),
                            ('payroll_period', '=', self.payroll_period),
                            ('settlement', '=', False)
                            ]):
                raise UserError(
                    _('There is already a payroll period configured as the beginning of the bimonthly period for the same month.'))
        if vals.get('end_bumonthly_period') and vals['end_bumonthly_period'] == True:
            if self.search([('year', '=', year),
                            ('month', '=', month),
                            ('company_id', '=', self.company_id.id),
                            ('end_bumonthly_period', '=', True),
                            ('payroll_period', '=', self.payroll_period),
                            ('settlement', '=', False)
                            ]):
                raise UserError(
                    _('There is already a payroll period configured as the end of the bimonthly period for the same month.'))

        return super(HrPayrollPeriod, self).write(vals)
