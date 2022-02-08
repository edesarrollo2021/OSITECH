# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class HrAlimony(models.Model):
    _name = 'hr.alimony'
    _description = 'Alimony of Employee'

    name = fields.Char(string="Full Name", required=True)
    type = fields.Selection([
        ('gross-isr-imss', 'Gross earnings - ISR - IMSS'),
        ('gross', 'Gross earnings'),
        ('fixed_amount', 'Fixed amount'),
    ], string="Type", required=True)
    amount = fields.Float(string="Amount / Percentage Applicable", required=True)
    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], string="State", default="active", required=True)
    payment_type = fields.Selection([
        ('check', 'Check'),
        ('wire_transfer', 'wire transfer'),
    ], string="Payment type", required=True)
    bank_account = fields.Char(string="Bank Account", required=False)
    bank_id = fields.Many2one("res.bank", string="Bank", required=False)
