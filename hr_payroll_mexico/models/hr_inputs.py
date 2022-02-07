# -*- coding: utf-8 -*-

import logging

from datetime import date, datetime, timedelta

from odoo import api, fields, models, tools, modules, _
from odoo.osv import expression
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrInputs(models.Model):
    _name = 'hr.inputs'
    _description = "Input"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'
    _order = 'create_date desc'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  states={'approve': [('readonly', True)], 'cancel': [('readonly', True)], 'rejected': [('readonly', True)]}, tracking=True)
    input_id = fields.Many2one('hr.payslip.input.type', string='Input', required=True,
                               states={'approve': [('readonly', True)], 'cancel': [('readonly', True)], 'rejected': [('readonly', True)]}, tracking=True)
    payroll_period_id = fields.Many2one('hr.payroll.period', string='Payroll Period', tracking=True, required=True)
    amount = fields.Float('Amount', tracking=True,
                          states={'cancel': [('readonly', True)], 'rejected': [('readonly', True)]}, digits=(16, 2))
    state = fields.Selection([
        ('cancel', 'Cancelled'),
        ('confirm', 'To Approve'),
        ('approve', 'Approved'),
        ('rejected', 'Rejected')], string='Status',
        tracking=True, copy=False)
    date = fields.Date(string="Date")
    requires_date = fields.Boolean(related="input_id.requires_date", store=True)
    input_with_share = fields.Many2one('input.with.share', string='Input with Share', required=False, readonly=True)
    year = fields.Integer(string="Year")

    @api.model
    def create(self, vals):
        if not vals.get('state', False):
            vals['state'] = 'approve'
        return super(HrInputs, self).create(vals)

    def action_approve(self):
        self.write({'state': 'approve'})

    def action_disapprove(self):
        self.write({'state': 'confirm'})


class HrPayslipInputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    requires_date = fields.Boolean(string="Requires date?")

    _sql_constraints = [
        ('code_uniq', 'unique (code)',
         "The code must be unique."),
    ]

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('name', operator, name), ('code', operator, name)]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)


class InputWithShare(models.Model):
    _name = 'input.with.share'
    _description = "Inputs With Share"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'employee_id'
    _order = 'create_date desc'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    amount = fields.Float('Amount', required=True, tracking=True, digits=(16, 2))
    paid_amount = fields.Float(compute='_calculate_paid_amount', string='Paid Amount', required=False, copy=False)
    amount_of_fees = fields.Integer(string="Amount of Fees", required=True, tracking=True)
    input_id = fields.Many2one('hr.payslip.input.type', string='Input', required=True, tracking=True)
    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
            ], string='Status', default='active',
        tracking=True, copy=False)
    line_ids = fields.One2many("input.with.share.line", "input_share_id", string="Input Share Lines")
    outstanding_balance = fields.Float(string="Outstanding Balance", compute="_calculate_paid_amount")

    def _calculate_paid_amount(self):
        for res in self:
            res.paid_amount = sum(res.line_ids.mapped('amount'))
            res.outstanding_balance = res.amount - sum(res.line_ids.mapped('amount'))


class InputWithShareLine(models.Model):
    _name = 'input.with.share.line'
    
    input_share_id = fields.Many2one('input.with.share', string='Input with share')
    slip_id = fields.Many2one('hr.payslip', string='Payslip')
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip')
    amount = fields.Float('Amount')
    input_id = fields.Many2one('hr.payslip.input.type', string='Input')
    timbre = fields.Boolean(string="Timbrado?", dafault=False)


class Employee(models.Model):
    _inherit = 'hr.employee'
    
    def payroll_entries_installments_active(self, input_code, payslip):
        input_id = self.env['hr.payslip.input.type'].search([('code','=',input_code)])
        self.env.cr.execute("""
                                DELETE FROM 
                                    input_with_share_line 
                                WHERE slip_id = %s AND input_id = %s
                            """, (payslip.id,input_id.id))
        self.env.cr.execute("""
                                SELECT 
                                    id, id, amount
                                FROM input_with_share share
                                WHERE 
                                    share.input_id = %s
                                    AND state = 'active'
                                    AND employee_id = %s
                                    
                            """, (input_id.id,self.id))
        res = self.env.cr.fetchall()
        for i in res:
            input_share_id = self.env['input.with.share'].browse([i[0]])
            amount_paid = 0
            for line in input_share_id.line_ids:
                if line.slip_id.id != payslip.id:
                    amount_paid += line.amount
            if float(i[2]) - amount_paid > 0:
                return True            
        return False
    
    def payroll_entries_installments(self, payslip,input_code, total_available):
        input_id = self.env['hr.payslip.input.type'].search([('code','=',input_code)])
        self.env.cr.execute("""
                                DELETE FROM 
                                    input_with_share_line 
                                WHERE slip_id = %s AND input_id = %s
                            """, (payslip.id,input_id.id))
        self.env.cr.execute("""
                    SELECT 
                        id, id, amount, amount_of_fees
                    FROM input_with_share share
                    WHERE 
                        share.input_id = %s
                        AND state = 'active'
                        AND employee_id = %s
                        
                """, (input_id.id,self.id))
        res = self.env.cr.fetchall()
        amount_return = 0
        for i in res:
            amount = 0
            input_share_id = self.env['input.with.share'].browse([i[0]])
            amount_paid = 0
            for line in input_share_id.line_ids:
                if line.slip_id.id != payslip.id:
                    amount_paid += line.amount
            
            
            if amount_paid < float(i[2]):
                amount = float(i[2])- amount_paid
                share_amount = float(i[2])/i[3]
                if amount > share_amount:
                    amount = share_amount
                if amount > total_available:
                    amount = total_available
                    total_available = 0
                else:
                    total_available -= amount
                amount_paid += amount
                amount_return += amount
                payslip_run_id = False
                if int(payslip.payslip_run_id) > 0:
                    payslip_run_id = int(payslip.payslip_run_id)
                self.env['input.with.share.line'].create({'slip_id':payslip.id,
                                                          'input_share_id':input_share_id.id,
                                                          'payslip_run_id':payslip_run_id,
                                                          'amount':amount,
                                                          'input_id':input_id.id,
                                                          'timbre':False})        
        return amount_return
    
    def payroll_entries_installments_settlement(self, payslip,input_code, total_available):
        input_id = self.env['hr.payslip.input.type'].search([('code','=',input_code)])
        self.env.cr.execute("""
                                DELETE FROM 
                                    input_with_share_line 
                                WHERE slip_id = %s AND input_id = %s
                            """, (payslip.id,input_id.id))
        self.env.cr.execute("""
                    SELECT 
                        id, id, amount, amount_of_fees
                    FROM input_with_share share
                    WHERE 
                        share.input_id = %s
                        AND state = 'active'
                        AND employee_id = %s
                        
                """, (input_id.id,self.id))
        res = self.env.cr.fetchall()
        amount_return = 0
        for i in res:
            amount = 0
            input_share_id = self.env['input.with.share'].browse([i[0]])
            amount_paid = 0
            for line in input_share_id.line_ids:
                if line.slip_id.id != payslip.id:
                    amount_paid += line.amount
            if amount_paid < float(i[2]):
                amount = float(i[2])- amount_paid
                if amount > total_available:
                    amount = total_available
                    total_available = 0
                else:
                    total_available -= amount
                amount_paid += amount
                amount_return += amount
                payslip_run_id = False
                if int(payslip.payslip_run_id) > 0:
                    payslip_run_id = int(payslip.payslip_run_id)
                self.env['input.with.share.line'].create({'slip_id':payslip.id,
                                                          'input_share_id':input_share_id.id,
                                                          'payslip_run_id':payslip_run_id,
                                                          'amount':amount,
                                                          'input_id':input_id.id,
                                                          'timbre':False})        
        return amount_return

