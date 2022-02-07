# -*- coding: utf-8 -*-

from datetime import datetime, date, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ReportConsolidate(models.TransientModel):
    _name = 'report.consolidate'
    _description = 'Wizard for generate consolidate reports'

    company_ids = fields.Many2many("res.company", string="Companies", default=lambda self: self.env.company, required=True)
    type = fields.Selection([
        ('assa', 'ASSA'),
        ('aspa', 'ASPA'),
        ('social', 'Social Purpose'),
    ], string="Type", default="assa", required=True)
    run_ids = fields.Many2many("hr.payslip.run", string="Payslip Runs", required=True)

    @api.onchange('type')
    def onchange_type(self):
        self.run_ids = False
        domain = {}
        if self.type == 'assa':
            domain = {'run_ids': [('structure_id.assa_report', '=', True),('state','=','close')]}
        if self.type == 'aspa':
            domain = {'run_ids': [('structure_id.aspa_report', '=', True),('state','=','close')]}
        if self.type == 'social':
            domain = {'run_ids': [('structure_id.social_objective', '=', True),('state','=','close')]}
        return {'domain': domain}

    def generate_report(self):
        if len(self.company_ids) > 1:
            domain = f'AND slip.company_id IN {self.company_ids._ids}'
        else:
            domain = f'AND slip.company_id = {self.company_ids.id}'

        if self.type == 'assa':
            return self.run_ids.report_assa_print(domain)
        elif self.type == 'aspa':
            return self.run_ids.report_aspa_print(domain)
        elif self.type == 'social':
            return self.run_ids.report_social_objective_print(domain)
