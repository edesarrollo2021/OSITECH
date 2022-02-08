# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, modules, _
import logging

_logger = logging.getLogger(__name__)


class HrProvisions(models.Model):
    _name = 'hr.provisions'
    _description = 'Provisions'
    _rec_name = "employee_id"

    type = fields.Selection([
        ('bonus', 'Bonus'),
        ('holidays', 'Holidays'),
        ('premium', 'Vacation Premium')
    ], string="Type", default="bonus", required=True)
    contract_id = fields.Many2one("hr.contract", string="Contract", required=True)
    employee_id = fields.Many2one("hr.employee", related="contract_id.employee_id")
    year = fields.Integer(string="Year", required=True)
    amount = fields.Float(string="Amount")
    payslip_run_id = fields.Many2one("hr.payslip.run", string="Payslip Run")
    timbre = fields.Boolean(string="Timbrado?", dafault=False)
