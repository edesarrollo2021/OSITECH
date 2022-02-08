# -*- coding: utf-8 -*-

import datetime
from datetime import date, timedelta, datetime, time
from pytz import timezone
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from odoo.addons import decimal_precision as dp

import calendar


class Employee(models.Model):
    _inherit = "hr.employee"

    infonavit_ids = fields.One2many('hr.infonavit.credit.line', 'employee_id', "INFONAVIT credit")
    fonacot_ids = fields.One2many('hr.fonacot.credit.line','employee_id', "FONACOT credit")
    fonacot_customer_number = fields.Char("FONACOT customer number", copy=False, required=False, tracking=True)
    
    _sql_constraints = [
        ('fonacot_customer_number_uniq', 'unique(fonacot_customer_number)', 'There is already an employee with this registered FONACOT customer number.'),
    ]
    
    @api.constrains('fonacot_ids')
    def _check_fonacot_customer_number(self):
        for record in self:
            if not record.fonacot_customer_number and record.fonacot_ids:
                raise UserError(_("You must complete the field with the FONACOT customer number."))


class EmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    fonacot_customer_number = fields.Char(readonly=True)


class hrInfonavitCreditHistory(models.Model):
    _name='hr.infonavit.credit.history'
    _order = "date desc"

    infonavit_id = fields.Many2one(comodel_name='hr.infonavit.credit.line', string='INFONAVIT')
    date = fields.Date("Date", required=True)
    move_type = fields.Selection([
        ('high_credit', 'High credit'),
        ('discontinued', 'Discontinued'),
        ('reboot', 'Reboot'),
        ('low_credit', 'Low credit'),
        ],'Move type')

class hrInfonavitCreditLine(models.Model):
    _name = "hr.infonavit.credit.line"
    _rec_name = 'infonavit_credit_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Line of credit number"
    _mail_post_access = 'read'
    _order = "date desc"
    
    employee_id = fields.Many2one('hr.employee', "Employee", required=False, tracking=True)
    infonavit_credit_number = fields.Char("INFONAVIT Credit Number", copy=False, required=True, tracking=True)
    value = fields.Float("Value", copy=False, required=False, tracking=True, digits=dp.get_precision('Infonavit'))
    date = fields.Date("Date (ICV)", required=True, tracking=True)
    date_suspension = fields.Date("Date To", required=False, tracking=True)
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('umi', 'UMI'),
        ('fixed_amount', 'Fixed Amount'),
    ], default="percentage", required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('inactive', 'Inactive'),
    ], default="draft", tracking=True)
    attachment_count = fields.Integer(compute='_compute_attachement_count', string='Attachment')

    _sql_constraints = [
        ('infonavit_credit_number_company_uniq', 'unique(infonavit_credit_number)', 'There is already an employee with this INFONAVIT credit number.'),
    ]

    def _compute_attachement_count(self):
        for i in self:
            attachment_data = self.env['ir.attachment'].sudo().search([('res_id', 'in', i.ids),('res_model', '=', 'hr.infonavit.credit.line')])
            i.attachment_count = len(attachment_data)

    def action_active(self):
        for credit in self:
            infonavit = self.search([('employee_id', '=', self.employee_id.id), ('state', '=', 'active')])
            if not infonavit:
                credit.state = 'active'
            else:
                raise UserError(_("An active INFONAVIT credit already exists for the employee."))

    def action_inactive(self):
        for credit in self:
            credit.state = 'inactive'
        return

    def document_view(self):
        self.ensure_one()
        domain = [
            ('res_id', 'in', self.ids),
            ('res_model', '=', 'hr.infonavit.credit.line')]
        return {
            'name': _('Documents INFONAVIT'),
            'domain': domain,
            'res_model': 'ir.attachment',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'help': _('''<p class="oe_view_nocontent_create">
                               Click to Create for New Documents
                            </p>'''),
            'limit': 80,
            'context': "{'default_res_id': %s,'default_folder_id':%s,'default_res_model':'hr.infonavit.credit.line'}" % (
            self.id, self.employee_id.folder_id.id)
        }

    def calculate_infonavit_credit(self, payslip, sdi, total_available):
        period_id = payslip.payroll_period_id
        contract = payslip.contract_id
        year = period_id.year
        month_bimester = period_id.month
        bimesters = {
            '1': ('1', '2'),
            '2': ('1', '2'),
            '3': ('3', '4'),
            '4': ('3', '4'),
            '5': ('5', '6'),
            '6': ('5', '6'),
            '7': ('7', '8'),
            '8': ('7', '8'),
            '9': ('9', '10'),
            '10': ('9', '10'),
            '11': ('11', '12'),
            '12': ('11', '12'),
        }
        all_periods = self.env['hr.payroll.period'].search([
            ('month', 'in', bimesters[str(month_bimester)]),
            ('year', '=', year),
            ('company_id', '=', period_id.company_id.id),
            ('type', '=', 'ordinary'),
            ('payroll_period', '=', payslip.payroll_period),
            ])
        period_bimester_start = self.env['hr.payroll.period'].search([
            ('month', '=', str(bimesters[str(month_bimester)][0])),
            ('year', '=', year),
            ('company_id', '=', period_id.company_id.id),
            ('start_bumonthly_period', '=', True),
            ('payroll_period', '=', payslip.payroll_period),
            ('type', '=', 'ordinary')
            ], limit=1)
        period_bimester_end = self.env['hr.payroll.period'].search([
            ('month', '=', str(bimesters[str(month_bimester)][1])),
            ('year', '=', year),
            ('company_id', '=', period_id.company_id.id),
            ('end_bumonthly_period', '=', True),
            ('payroll_period', '=', payslip.payroll_period),
            ('type', '=', 'ordinary')
            ], limit=1)
        if not period_bimester_start or not period_bimester_end:
            raise UserError(_('Undefined bimonthly start or end period.'))
        date_start = datetime.combine(payslip.payroll_period_id.date_start, time.min)
        date_end = datetime.combine(payslip.payroll_period_id.date_end, time.max)
        datetime_start = fields.Datetime.to_string(date_start)
        datetime_end = fields.Datetime.to_string(date_end)
        self.env.cr.execute("""
                            SELECT 
                                SUM(entry.duration / calendar.hours_per_day)
                            FROM hr_work_entry entry
                            JOIN hr_work_entry_type type_entry ON type_entry.id = entry.work_entry_type_id
                            JOIN hr_employee employee ON employee.id = entry.employee_id
                            JOIN hr_contract contract ON employee.contract_id = contract.id
                            JOIN resource_calendar calendar ON contract.resource_calendar_id = calendar.id
                            WHERE 
                                contract.id = %s
                                AND type_entry.type_leave = 'inability'
                                AND entry.state in ('validated','draft')
                                AND (entry.out_of_date IS NOT TRUE AND (entry.date_start, entry.date_stop) OVERLAPS (%s, %s))
                            """, (payslip.contract_id.id, datetime_start, datetime_end))

        days_absences = self.env.cr.fetchall()[0][0] or 0
        secure = 15/len(all_periods)
        days_bimester = (period_bimester_end.date_end - period_bimester_start.date_start).days + 1
        pending_amount = 0
        val = ''
        for infonavit in self.env['hr.employee'].search([('id','=',int(payslip.employee_id))]).infonavit_ids:
            if infonavit.state == 'active':
                date_from = payslip.date_from
                date_to = payslip.date_to
                not_calculate = False
                total_discount = 0
                if date_from < infonavit.date < date_to:
                    date_from = infonavit.date
                elif infonavit.date > date_to:
                    not_calculate = True
                if infonavit.date_suspension and date_to > infonavit.date_suspension > date_from:
                    date_to = infonavit.date_suspension
                if contract.date_end and date_to > contract.date_end > date_from:
                    date_to = contract.date_end
                if (infonavit.date_suspension and infonavit.date_suspension < date_from) or (contract.date_end and contract.date_end < date_from):
                    not_calculate = True
                if not not_calculate:
                    days_out = 0
                    if (payslip.date_from - infonavit.date).days < 0:
                        days_out += abs((payslip.date_from - infonavit.date).days)
                    if (date_to -payslip.date_to).days < 0:
                        days_out += abs((date_to -payslip.date_to).days)
                    days_period = ((period_id.date_end - period_id.date_start).days + 1) - days_out - days_absences
                    umi = payslip.company_id.umi
                    
                    if self.type == 'percentage':
                        total_bimester = ((((infonavit.value / 100)) * sdi) * days_bimester)
                        daily_infonavit = (((infonavit.value / 100)) * sdi)
                        amount_infonavit = ((((infonavit.value / 100)) * sdi) * days_period) + secure
                       
                    elif self.type == 'fixed_amount':
                        total_bimester = (infonavit.value * 2)
                        daily_infonavit = total_bimester / days_bimester
                        amount_infonavit = daily_infonavit * days_period + secure
                    elif self.type == 'umi':
                        total_bimester = ((infonavit.value * umi) * 2)
                        daily_infonavit = total_bimester / days_bimester
                        amount_infonavit = daily_infonavit * days_period + secure
                    
                    total_discount = amount_infonavit
                    if amount_infonavit < total_available:
                        total_discount = amount_infonavit
                        total_available -=  amount_infonavit
                    else:
                        total_discount = total_available
                        pending_amount = amount_infonavit - total_available
                        total_available = 0
                    val = {
                        'type': infonavit.type,
                        'value': infonavit.value,
                        'infonavit_credit_number': infonavit.infonavit_credit_number,
                        'total_bimester': total_bimester,
                        'daily_infonavit': daily_infonavit,
                        'days_period': days_period + days_absences,
                        'days_absences': days_absences,
                        'total_day': days_period,
                        'amount_infonavit': float("{0:.2f}".format(amount_infonavit-secure)),
                        'secure': secure,
                        'total_infonavit': float("{0:.2f}".format(amount_infonavit)),
                        'total_discount': float("{0:.2f}".format(total_discount)),
                        }
        return [total_discount, total_available, pending_amount, str(val)]


class hrInfonavitCreditChangeLine(models.Model):
    _name = "hr.infonavit.credit.change.line"
    _order = "date_from asc"
    _rec_name = 'id'
    infonavit_id = fields.Many2one('hr.infonavit.credit.line', "INFONAVIT", required=False)
    type = fields.Selection([
        ('percentage', 'Percentage'),
        ('VSM', 'V.S.M'),
        ('fixed_amount', 'Fixed Amount'),
    ],default="percentage", required=True, track_visibility='onchange')
    value = fields.Float("Value", copy=True, required=False, digits=dp.get_precision('Infonavit'))
    date_from = fields.Date("Date From", required=True)
    date_to = fields.Date("Date To", required=False)
    
    
class hrFonacotCreditLine(models.Model):
    _name = "hr.fonacot.credit.line"
    _rec_name = 'fonacot_credit_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'
    _order = "date_start desc"

    employee_id = fields.Many2one('hr.employee', "Employee", required=False, tracking=True)
    fonacot_credit_number = fields.Char("FONACOT Credit Number", copy=False, required=True, tracking=True)
    fee = fields.Float("Monthly fee", copy=False, required=False, tracking=True)
    date_start = fields.Date("Date Start", required=True, tracking=True)
    date_end = fields.Date("Date End", required=False, tracking=True)
    fonacot_customer_number = fields.Char("FONACOT customer number", related="employee_id.fonacot_customer_number")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ], default="active", tracking=True)
    attachment_count = fields.Integer(compute='_compute_attachement_count', string='Attachment')

    _sql_constraints = [
        ('fonacot_credit_number_uniq', 'unique(fonacot_credit_number)', 'There is already a FONACOT credit registered with this same number.'),
    ]

    def _compute_attachement_count(self):
        for i in self:
            attachment_data = self.env['ir.attachment'].sudo().search([('res_id', 'in', i.ids),('res_model', '=', 'hr.fonacot.credit.line')])
            i.attachment_count = len(attachment_data)

    def action_active(self):
        for credit in self:
            credit.state = 'active'

    def action_inactive(self):
        for credit in self:
            credit.state = 'inactive'
        return

    def document_view(self):
        self.ensure_one()
        domain = [
            ('res_id', 'in', self.ids),
            ('res_model', '=', 'hr.fonacot.credit.line')]
        return {
            'name': _('Documents FONACOT'),
            'domain': domain,
            'res_model': 'ir.attachment',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'help': _('''<p class="oe_view_nocontent_create">
                               Click to Create for New Documents
                            </p>'''),
            'limit': 80,
            'context': "{'default_res_id': %s,'default_folder_id':%s,'default_res_model':'hr.fonacot.credit.line'}" % (
            self.id, self.employee_id.group_id.folder_document_id.id)
        }

    def calculate_fonacot_credit(self, contract, payslip, total_available):
        self.env.cr.execute("""
                                DELETE FROM 
                                    hr_fonacot_credit_line_payslip 
                                WHERE slip_id = %s
                            """, (payslip.id,))
        
        period_id = payslip.payroll_period_id
        year = period_id.year
        month = period_id.month
        all_periods = self.env['hr.payroll.period'].search([('month', '=', month),
                                                            ('year', '=', year),
                                                            ('company_id', '=', period_id.company_id.id),
                                                            ('payroll_period', '=', payslip.payroll_period),
                                                            ('type', '=', 'ordinary')])
        number_periods = len(all_periods)
        period_start = self.env['hr.payroll.period'].search([('month', '=', month),
                                                             ('year', '=', year),
                                                             ('company_id', '=', period_id.company_id.id),
                                                             ('payroll_period', '=', payslip.payroll_period),
                                                             ('start_monthly_period', '=', True),
                                                             ('type', '=', 'ordinary')
                                                             ], limit=1)
        period_end = self.env['hr.payroll.period'].search([('month', '=', month),
                                                           ('year', '=', year),
                                                           ('company_id', '=', period_id.company_id.id),
                                                           ('payroll_period', '=', payslip.payroll_period),
                                                           ('end_monthly_period', '=', True),
                                                           ('type', '=', 'ordinary')
                                                           ], limit=1)
        if not period_start or not period_end:
            raise UserError(_('Undefined start or end period.'))
        date_start = datetime.combine(payslip.payroll_period_id.date_start, time.min)
        date_end = datetime.combine(payslip.payroll_period_id.date_end, time.max)
        datetime_start = fields.Datetime.to_string(date_start)
        datetime_end = fields.Datetime.to_string(date_end)
        self.env.cr.execute("""
                            SELECT 
                                SUM(entry.duration / calendar.hours_per_day)
                            FROM hr_work_entry entry
                            JOIN hr_work_entry_type type_entry ON type_entry.id = entry.work_entry_type_id
                            JOIN hr_employee employee ON employee.id = entry.employee_id
                            JOIN hr_contract contract ON employee.contract_id = contract.id
                            JOIN resource_calendar calendar ON contract.resource_calendar_id = calendar.id
                            WHERE 
                                contract.id = %s
                                AND type_entry.type_leave = 'inability'
                                AND entry.state in ('validated','draft')
                                AND (entry.out_of_date IS NOT TRUE AND (entry.date_start, entry.date_stop) OVERLAPS (%s, %s))
                            """, (payslip.contract_id.id, datetime_start, datetime_end))
        days_absences = self.env.cr.fetchall()[0][0] or 0
        amount_total = 0
        not_calculate =False
        for fonacot in self.env['hr.employee'].search([('id','=',int(payslip.employee_id))]).fonacot_ids:
            if fonacot.state == 'active':
                date_from = payslip.date_from
                date_to = payslip.date_to
                if date_from < fonacot.date_start < date_to:
                    date_from = fonacot.date_start
                elif fonacot.date_start > date_to:
                    not_calculate = True
                if fonacot.date_end and date_to > fonacot.date_end > date_from:
                    date_to = fonacot.date_end
                if contract.date_end and date_to > contract.date_end > date_from:
                    date_to = contract.date_end
                if (fonacot.date_end and fonacot.date_end < date_from) or (contract.date_end and contract.date_end < date_from):
                    not_calculate = True
                if not not_calculate:
                    days = (date_to - date_from).days + 1
                    days_month = (period_end.date_end - period_start.date_start).days + 1
                    days_out = 0
                    if (payslip.date_from - fonacot.date_start).days < 0:
                        days_out += abs((payslip.date_from - fonacot.date_start).days)
                    if (date_to -payslip.date_to).days < 0:
                        days_out += abs((date_to -payslip.date_to).days)
                        if payslip.payroll_period == '04' and date_to.day == 31:
                            days_out -= 1
                    days_period = (period_id.date_end - period_id.date_start).days + 1
                    if payslip.payroll_period == '04':
                        days_period = 15                    
                    amount = fonacot.fee / number_periods
                    credit_amount_total = amount - ((amount / days_period) * days_out) - ((amount / days_period) * days_absences)
                    amount_total += credit_amount_total
                    if total_available < credit_amount_total:
                        credit_amount_total = total_available
                        total_available = 0
                    else:
                        total_available -= credit_amount_total
                    if credit_amount_total > 0:
                        self.env['hr.fonacot.credit.line.payslip'].create({'payslip_run_id':int(payslip.payslip_run_id),'timbre':False,'slip_id':payslip.id,'fonacot_id':fonacot.id,'amount':credit_amount_total})
                not_calculate =False
        return amount_total


class hrFonacotCreditLinePayslip(models.Model):
    _name = "hr.fonacot.credit.line.payslip"
    _description = "Relational Model for payslip and fonacot credit"
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batches')
    slip_id = fields.Many2one('hr.payslip', string='Payslip')
    fonacot_id = fields.Many2one('hr.fonacot.credit.line', string='Fonacot Credit')
    amount = fields.Float("Amount")
    timbre = fields.Boolean('Timbre?', default=False)
