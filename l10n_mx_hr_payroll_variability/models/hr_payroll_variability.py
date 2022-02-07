# -*- coding: utf-8 -*-

import io
import base64

from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell


def _get_selection_year(self):
    current_year = date.today().year
    list_selection = []
    for item in range(2019, current_year + 1):
        list_selection.append((str(item), str(item)))
    return list_selection

bismester_list = [
    ('1', 'January - February'),
    ('2', 'March - April'),
    ('3', 'May - June'),
    ('4', 'July - August'),
    ('5', 'September - October'),
    ('6', 'November - December'),
]

class HrPayrollVariability(models.Model):
    _name = 'hr.payslip.variability'
    _rec_name = 'employee_id'
    _description = 'Payroll MX Variability'
    _order = 'year, bimestre, id desc'

    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee')
    ssnid = fields.Char(related='employee_id.ssnid', string='NSS')
    contract_id = fields.Many2one(comodel_name='hr.contract', string='Contract')
    current_sdi = fields.Float(string='Current SDI')
    new_sdi = fields.Float(string='New SDI')
    sbc = fields.Float(string='SBC')
    variable_salary = fields.Float(string='Variable Salary')
    perceptions_bimonthly = fields.Float(string='Variable perceptions')
    days_bimestre = fields.Integer(string='Days of the bimester')
    days_worked = fields.Integer(string='Number of days worked')
    leaves = fields.Integer(string='Leaves')
    inhabilitys = fields.Integer(string='Inability')
    # history_id = fields.Many2one(comodel_name='hr.employee.affiliate.movements', string='Affiliates move')
    bimestre = fields.Selection(bismester_list, string='Bimester', required=True)
    year = fields.Selection(_get_selection_year, string='Year', required=True)
    type_change_salary = fields.Selection([
        ('0', 'Fijo'),
        ('1', 'Variable'),
        ('2', 'Mixto'),
        ('3', 'Sin Modificación')
    ], string="Type Move")

