# -*- coding: utf-8 -*-

import time
from odoo import api, models, _
from odoo.exceptions import UserError


class ReportPayslip(models.AbstractModel):
    _name = 'report.hr_payroll_mexico.report_payslip_lang'
    _description = 'Payslip Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        ids = data.get('context', {}).get('active_ids', docids)
        return {
            'doc_ids': ids,
            'doc_model': self.env['hr.payslip'],
            'data': data,
            'docs': self.env['hr.payslip'].browse(ids),
        }

