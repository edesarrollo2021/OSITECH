# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime, date, time
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WizardReportFilter(models.TransientModel):
    _name = 'wizard.payroll.report.filter'
    _description = 'Payroll Report Filter'

    company_id = fields.Many2one('res.company', required=False, string='Company', default=lambda self: self.env.company)
    structure_ids = fields.Many2many(
        'hr.payroll.structure', string='Structure',
    )
    period_ids = fields.Many2many(
        'hr.payroll.period', string='Payroll Period'
    )
    type = fields.Selection([
        ('payroll', 'Payroll'),
        ('taxed', 'Taxed Report'),
        ('assa', 'ASSA Report'),
        ('aspa', 'ASPA Report'),
        ('saving', 'Saving Fund Report'),
        ('isn', 'ISN Report'),
    ], string="Report Type", required=True)


    def export_report(self):
        payslipRun = self.env['hr.payslip.run']
        domain = ''
        # Filter Structures
        if len(self.structure_ids) == 1:
            clause1 = 'slip.struct_id = %s' % str(self.structure_ids.id)
        if len(self.structure_ids) > 1:
            clause1 = 'slip.struct_id IN %s' % str(tuple(self.structure_ids.ids))
        # Filter Periods
        if len(self.period_ids) == 1:
            clause2 = 'slip.payroll_period_id = %s' % str(self.period_ids.id)
        if len(self.period_ids) > 1:
            clause2 = 'slip.payroll_period_id IN %s' % str(tuple(self.period_ids.ids))
        domain += clause1 if self.structure_ids else ''
        union = ' AND ' if self.structure_ids and self.period_ids else ''
        domain += union
        domain += clause2 if self.period_ids else ''
        clasue3 = " AND slip.state = 'done'"
        domain += clasue3

        if self.type == 'payroll':
            # dates = self.period_ids.mapped('date_start') + self.period_ids.mapped('date_end')
            # dates.sort(key=lambda date: datetime.strftime(date, '%Y-%m-%d'))
            # date_start = dates[0] if dates else False
            # date_end = dates[-1] if dates else False
            return payslipRun.print_xlsx(domain=domain, structure=self.structure_ids, period=self.period_ids)
        if self.type == 'taxed':
            domain += 'AND slip.company_id = %s' % str(self.company_id.id)
            return payslipRun.with_context(periods=self.period_ids).report_taxed_print(domain=domain)
        if self.type == 'assa':
            domain += 'AND slip.company_id = %s' % str(self.company_id.id)
            return payslipRun.report_assa_print(domain=domain)
        if self.type == 'aspa':
            domain += 'AND slip.company_id = %s' % str(self.company_id.id)
            return payslipRun.report_aspa_print(domain=domain)
        if self.type == 'saving':
            domain += 'AND slip.company_id = %s' % str(self.company_id.id)
            return payslipRun.with_context(periods=self.period_ids).report_saving_fund(domain=domain)

    def export_report_ins(self):
        payslipRun = self.env['hr.payslip.run']
        return payslipRun.print_xlsx_isn(structure=self.structure_ids, period=self.period_ids)

