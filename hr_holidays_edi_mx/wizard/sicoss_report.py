# -*- coding: utf-8 -*-

import calendar
import base64
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SicossReport(models.TransientModel):
    _name = "sicoss.report"
    _description = "Generate Sicoss for inabilities"

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string="Date from")
    date_to = fields.Date(string="Date to")

    @api.model
    def _get_aml_line(self, aml):
        columns = [
            {'name': aml['employee_code'], 'class': 'whitespace_print'},
            {'name': aml['folio'], 'class': 'whitespace_print'},
            {'name': int(float(aml['number_of_days']) + 1), 'class': 'whitespace_print'},
            {'name': aml['date_from'].strftime('%d/%m/%Y') if aml['date_from'] else "", 'class': 'date'},
            {'name': aml['date_to'].strftime('%d/%m/%Y') if aml['date_to'] else "", 'class': 'date'},
            {'name': aml['inhability_code'], 'class': 'whitespace_print'},
            {'name': aml['classification_code'], 'class': 'whitespace_print'},
            {'name': aml['category_code'], 'class': 'whitespace_print'},
            {'name': aml['subcategory_code'], 'class': 'whitespace_print'},
        ]
        return {
            'id': aml['id'],
            'class': 'top-vertical-align',
            'columns': columns,
            'level': 2,
        }

    def _prepare_data(self):
        query = """
                    SELECT
                        hr_leave.id,
                        employee.registration_number            AS employee_code,
                        inhability.code                         AS inhability_code,
                        classification.code                     AS classification_code,
                        category.code                           AS category_code,
                        subcategory.code                        AS subcategory_code,
                        hr_leave.folio,
                        hr_leave.number_of_days,
                        hr_leave.request_date_from              AS date_from,
                        hr_leave.request_date_to                AS date_to
                    FROM hr_leave
                    JOIN hr_leave_type type                     ON type.id = hr_leave.holiday_status_id
                    JOIN hr_leave_inhability inhability         ON inhability.id = hr_leave.type_inhability_id
                    JOIN hr_leave_classification classification ON classification.id = hr_leave.inhability_classification_id
                    JOIN hr_leave_category category             ON category.id = hr_leave.inhability_category_id
                    JOIN hr_leave_subcategory subcategory       ON subcategory.id = hr_leave.inhability_subcategory_id
                    JOIN hr_employee employee                   ON employee.id = hr_leave.employee_id
                    JOIN res_company company                    ON company.id = employee.company_id
                    WHERE hr_leave.state = 'validate'
                        AND type.time_type = 'inability'
                        AND company.id = %s
                        AND (hr_leave.request_date_from, hr_leave.request_date_to) OVERLAPS (%s, %s)
                """

        self.env.cr.execute(query, (self.company_id.id, self.date_from - timedelta(days=1), self.date_to + timedelta(days=1)))
        lines = []
        for aml in self.env.cr.dictfetchall():
            lines.append(self._get_aml_line(aml))
        return lines

    def generate_report_txt(self):
        txt_data = self._prepare_data()
        content = ''
        for line in txt_data:
            if not line.get('id'):
                continue
            columns = line.get('columns', [])
            array = [''] * 9
            array[0] = str(columns[0]['name'])[:10] if columns[0]['name'] else '0'.zfill(10)
            array[1] = str(columns[1]['name'])[:8] if columns[1]['name'] else '0'.zfill(8)
            array[2] = str(columns[2]['name'])[:2] if columns[2]['name'] else '0'.zfill(2)
            array[3] = str(columns[3]['name'])[:10] if columns[3]['name'] else '0'.zfill(10)
            array[4] = str(columns[4]['name'])[:10] if columns[4]['name'] else '0'.zfill(10)
            array[5] = str(columns[5]['name'])[:1] if columns[5]['name'] else '0'.zfill(1)
            array[6] = str(columns[6]['name'])[:1] if columns[6]['name'] else '0'.zfill(1)
            array[7] = str(columns[7]['name'])[:1] if columns[7]['name'] else '0'.zfill(1)
            array[8] = str(columns[8]['name'])[:1] if columns[8]['name'] else '0'.zfill(1)
            content += ','.join(str(d) for d in array) + '\n'

        file_name = 'SICOSS'
        output = base64.encodebytes(bytes(content, 'utf-8'))
        file_id = self.env['wizard.file.download'].create({
            'file': output,
            'name': file_name + '.txt'
        })
        return {
            'name': _('Download Report'),
            'view_mode': 'form',
            'res_id': file_id.id,
            'res_model': 'wizard.file.download',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
