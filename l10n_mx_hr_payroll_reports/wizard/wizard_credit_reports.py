# -*- coding: utf-8 -*-

import io
import base64
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter
from odoo.tools.safe_eval import safe_eval
from ast import literal_eval
from datetime import date, datetime, timedelta, time


class ReportsCredit(models.TransientModel):
    _name = "report.credit"
    _description = "Credit Report"

    company_id = fields.Many2one('res.company', required=False, string='Company', default=lambda self: self.env.company)
    structure_ids = fields.Many2many('hr.payroll.structure', string='Structure')
    period_ids = fields.Many2many('hr.payroll.period', string='Payroll Period')
    year = fields.Integer(string='Year')
    bimester = fields.Selection([
        ('01', 'January - February'),
        ('02', 'March - April'),
        ('03', 'May - June'),
        ('04', 'July - August'),
        ('05', 'September - October'),
        ('06', 'November - December'),
    ], string='Bimester')
    type = fields.Selection([
        ('fonacot', 'Fonacot'),
        ('infonavit', 'Infonavit'),
    ], string="Report Type", required=True)

    @api.onchange('year', 'bimester')
    def onchange_type_inhability_id(self):
        domain = {}
        if self.type == 'infonavit':
            domain = {'period_ids': []}
            month_bimester = {
                '01': ['1', '2'],
                '02': ['3', '4'],
                '03': ['5', '6'],
                '04': ['7', '8'],
                '05': ['9', '10'],
                '06': ['11', '12'],
            }
            if self.year:
                domain['period_ids'].append(('year', '=', self.year))
            if self.bimester:
                domain['period_ids'].append(('month', 'in', month_bimester[self.bimester]))
        return {'domain': domain}

    ##########################
    # Fonacot
    ##########################
    @api.model
    def _get_query_fonacot_lines(self, domain=None):
        where_clause = domain or "1=1"
        query = '''
                SELECT
                    hr_payslip.id,
                    hr_payslip.contract_id,
                    employee.complete_name                  AS employee_name,
                    employee.registration_number            AS registration_number,
                    employee.fonacot_customer_number        AS n_customer,
                    fonacot.fonacot_credit_number           AS n_fonacot,
                    fonacot.fee                             AS fee,
                    contract.date_end                       AS contract_date_end,
                    struct.name                             AS struct_name,
                    struct.payslip_code                     AS payslip_code,
                    CASE
                        WHEN contract.previous_contract_date IS NOT NULL THEN contract.previous_contract_date
                        ELSE contract.date_start
                    END contract_date,
                    line.amount                             AS total,
                    period.name                             AS period_name,
                    period.date_start                       AS period_date_start,
                    work_days.works                         AS works,
                    work_days.leaves                        AS leaves,
                    dep.name                                AS dep_name,
                    dep.code                                AS dep_code,
                    job.name                                AS job_name,
                    fonacot.date_start                      AS date_start,
                    fonacot.date_end                        AS date_end
                FROM hr_fonacot_credit_line_payslip line
                JOIN hr_payslip                             ON hr_payslip.id = line.slip_id
                JOIN hr_contract contract                   ON contract.id = hr_payslip.contract_id
                JOIN hr_employee employee                   ON employee.id = contract.employee_id
                JOIN hr_fonacot_credit_line fonacot         ON line.fonacot_id = fonacot.id
                JOIN hr_payroll_period period               ON period.id = hr_payslip.payroll_period_id
                JOIN hr_payroll_structure struct            ON hr_payslip.struct_id = struct.id  
                JOIN hr_department dep                      ON employee.department_id = dep.id
                JOIN hr_job job                             ON employee.job_id = job.id
                JOIN (SELECT 
                        days.payslip_id,
                        SUM(CASE
                            WHEN entry.code = 'WORK1101' OR (entry.is_leave IS TRUE AND (entry.type_leave IN ('holidays', 'personal_days'))) 
                            THEN days.number_of_days
                            ELSE 0
                        END) works,
                        SUM(CASE
                            WHEN entry.is_leave IS TRUE AND (entry.type_leave = 'inability') THEN days.number_of_days
                            ELSE 0
                        END) leaves
                    FROM hr_payslip_worked_days days
                    JOIN hr_work_entry_type entry ON days.work_entry_type_id = entry.id
                    GROUP BY days.payslip_id
                ) work_days
                ON work_days.payslip_id = hr_payslip.id
                WHERE period.state in ('open') %s
                ''' % where_clause

        self.env.cr.execute(query)
        results = self.env.cr.dictfetchall()
        return results

    @api.model
    def get_fonacot_lines(self, domain=None):
        results = self._get_query_fonacot_lines(domain)
        if not results:
            raise UserError(_('No data found for the report'))

        data = {}
        periods_names = []
        payslip_codes = set()
        for line in results:
            data.setdefault(line['n_fonacot'], {'periods': {},
                                'contract_date': line['contract_date'].strftime('%d-%m-%Y') if line['contract_date'] else '',
                                'contract_date_end': line['contract_date_end'].strftime('%d-%m-%Y') if line['contract_date_end'] else '',
                                'registration_number': line['registration_number'].upper(),
                                'employee_name': line['employee_name'],
                                'job_name': line['job_name'],
                                'dep_code': line['dep_code'],
                                'dep_name': line['dep_name'],
                                'struct_name': line['struct_name'],
                                'payslip_code': line['payslip_code'],
                                'works': line['works'],
                                'leaves': line['leaves'],
                                'total_works': line['works'] - line['leaves'],
                                'n_fonacot': line['n_fonacot'].upper(),
                                'n_customer': line['n_customer'].upper(),
                                'fee': line['fee'],
                                'date_start': line['date_start'].strftime('%d-%m-%Y') if line['date_start'] else '',
                                'date_end': line['date_end'].strftime('%d-%m-%Y') if line['date_end'] else '',
                                })
            data[line['n_fonacot']]['periods'].setdefault(line['period_name'], [])
            data[line['n_fonacot']]['periods'][line['period_name']].append(line['total'])

            # Group by periods
            period = {'date': line['period_date_start'], 'name': line['period_name'], 'total': 0}
            payslip_codes.add(line['payslip_code'])
            if period not in periods_names:
                periods_names.append(period)
        return [data, periods_names, payslip_codes]

    def print_report_fonacot(self, domain=None):
        file_name = _('FONACOT Report %s') % fields.Datetime.now()
        string_periods = ''
        for period in self.period_ids:
            string_periods += '%s - %s / ' % (period.date_start, period.date_end)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format({'bold': True, 'bg_color': '#100D57', 'font_color': '#FFFFFF', 'border': 1, 'top': 1, 'font_size': 11, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})
        report_format = workbook.add_format({'border': 1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        report_format2 = workbook.add_format({'border':0, 'bold':True, 'font_size':12, 'font_name':'Calibri', 'align':'left'})
        report_format_bold = workbook.add_format({'bold': True, 'border': 1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        currency_format = workbook.add_format({'num_format': num_format, 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})
        empty_format = workbook.add_format({'num_format': '0', 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})

        result = self.get_fonacot_lines(domain)
        data = result[0]
        header = result[1]
        payslip_codes = result[2]
        payslips_type = ''
        for code in payslip_codes:
            payslips_type += '%s. ' % code if code else ''

        first_header = [
            {'sequence': 0.2, 'name': 'No. EMP', 'larg': 15},
            {'sequence': 0.3, 'name': 'NOMBRE', 'larg': 40},
            {'sequence': 0.5, 'name': 'DEPTO', 'larg': 15},
            {'sequence': 0.6, 'name': 'DIRECCIÓN / DEPARTAMENTO', 'larg': 40},
            {'sequence': 0.4, 'name': 'PUESTO', 'larg': 30},
            {'sequence': 0.7, 'name': 'NÓMINA', 'larg': 15},
            {'sequence': 0.0, 'name': 'FECHA ALTA', 'larg': 15},
            {'sequence': 0.1, 'name': 'FECHA BAJA', 'larg': 15},
            {'sequence': 0.8, 'name': 'DÍAS\nTRABAJADOS', 'larg': 15},
            {'sequence': 0.9, 'name': 'INCAPACIDADES', 'larg': 15},
            {'sequence': 1.0, 'name': 'NETO DÍAS\nTRABAJADOS.', 'larg': 15},
            {'sequence': 1.2, 'name': '# EMPLEADO', 'larg': 10},
            {'sequence': 1.1, 'name': '# CRÉDITO', 'larg': 10},
            {'sequence': 1.3, 'name': 'FECHA INICIAL\nDEL CRÉDITO', 'larg': 15},
            {'sequence': 1.4, 'name': 'FECHA FINAL\nDEL CRÉDITO', 'larg': 15},
            {'sequence': 1.5, 'name': 'DESCUENTO\nMENSUAL', 'larg': 15},
        ]

        def _write_sheet_header(sheet):
            total_total = 0
            col = 0
            row = 0

            sheet.merge_range(row, 0, row, 9, 'REPORTE FONACOT', report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 9, 'Tipo de Nómina: ' + payslips_type, report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 9, 'Periodo(s): ' + string_periods, report_format2)
            row += 2

            sheet.set_row(row, 40)

            for head_col in first_header:
                sheet.write(row, col, head_col['name'], header_format)
                sheet.set_column(col, col, head_col['larg'])
                col += 1
            for period in header:
                sheet.write(row, col, period['name'], header_format)
                sheet.set_column(col, col, 40)
                sheet.write(row + 1, col, 'TOTAL', header_format)
                col += 1

            sheet.write(row, col, 'TOTAL', header_format)
            sheet.set_column(col, col, 15)
            row += 2
            for contract in data:
                col = 0
                sheet.write(row, col, data[contract]['registration_number'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['employee_name'], currency_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('job_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('payslip_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract]['contract_date'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['contract_date_end'], report_format)
                col += 1
                sheet.write(row, col, data[contract].get('works', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('leaves', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('total_works', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('n_customer', 0), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('n_fonacot', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('date_start', 0), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('date_end', 0), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('fee', 0), currency_format)
                col += 1

                total_all = 0
                for period in sorted(header, key=lambda k: k['date']):
                    if period['name'] in data[contract]['periods']:
                        total_period = sum(data[contract]['periods'][period['name']])
                    else:
                        total_period = 0
                    period['total'] += total_period
                    sheet.write(row, col, total_period, currency_format)
                    total_all += total_period
                    col += 1
                sheet.write(row, col, total_all, currency_format)
                total_total += total_all
                row += 1

            col = 16
            for period in sorted(header, key=lambda k: k['date']):
                sheet.write(row, col, period['total'], currency_format)
                col += 1
            sheet.write(row, col, total_total, currency_format)

        sheet_header = workbook.add_worksheet("Total")
        _write_sheet_header(sheet_header)

        workbook.close()
        xlsx_data = output.getvalue()
        file_id = self.env['wizard.file.download'].create({
            'file': base64.b64encode(xlsx_data),
            'name': file_name + '.xlsx'
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

    ##########################
    # Infonavit
    ##########################
    @api.model
    def _get_query_infonavit(self, domain):
        where_clause = domain or "1=1"
        query = """
                SELECT 
                    line.total                              AS total,
                    line.code                               AS line_code,
                    line.datas                              AS datas,
                    slip.id                                 AS slip,
                    employee.registration_number            AS employee_code,
                    employee.complete_name                  AS employee_name,
                    contract.code                           AS contract_code,
                    employee.ssnid                          AS ssnid,
                    dep.name                                 AS dep_name,
                    dep.code                                AS dep_code,
                    job.name                                AS job_name,
                    contract.date_end                       AS date_end,
                    period.date_start                       AS period_date_start,
                    period.name                             AS period_name,
                    contract.date_end                       AS contract_date_end,
                    struct.name                             AS struct_name,
                    struct.payslip_code                     AS payslip_code,
                    work_days.works                         AS works,
                    work_days.leaves                        AS leaves,
                    CASE
                        WHEN contract.previous_contract_date IS NOT NULL THEN contract.previous_contract_date
                        ELSE contract.date_start
                    END contract_date
                FROM hr_payslip_line line
                JOIN hr_payslip slip                        ON line.slip_id = slip.id
                JOIN hr_contract contract                   ON slip.contract_id = contract.id
                JOIN hr_employee employee                   ON line.employee_id = employee.id
                JOIN hr_department dep                      ON employee.department_id = dep.id
                JOIN hr_job job                             ON employee.job_id = job.id
                JOIN hr_payroll_period period               ON period.id = slip.payroll_period_id
                JOIN hr_payroll_structure struct            ON slip.struct_id = struct.id   
                JOIN (SELECT 
                        days.payslip_id,
                        SUM(CASE
                            WHEN entry.code = 'WORK1101' OR (entry.is_leave IS TRUE AND (entry.type_leave IN ('holidays', 'personal_days'))) 
                            THEN days.number_of_days
                            ELSE 0
                        END) works,
                        SUM(CASE
                            WHEN entry.is_leave IS TRUE AND (entry.type_leave = 'inability') THEN days.number_of_days
                            ELSE 0
                        END) leaves
                    FROM hr_payslip_worked_days days
                    JOIN hr_work_entry_type entry ON days.work_entry_type_id = entry.id
                    GROUP BY days.payslip_id
                ) work_days
                ON work_days.payslip_id = slip.id
                WHERE 
                    slip.state IN ('done') AND line.code = 'D025' %s 
                """ % where_clause

        self.env.cr.execute(query)
        results = self.env.cr.dictfetchall()
        return results

    @api.model
    def get_infonavit_lines(self, domain=None):
        results = self._get_query_infonavit(domain)
        if not results:
            raise UserError(_('No data found for the report'))

        data = {}
        periods_names = []
        payslip_codes = set()
        for line in results:
            datas = literal_eval(line['datas'])
            if not datas:
                continue
            if datas['type'] == 'percentage':
                type_data = 'Porcentaje'
            if datas['type'] == 'umi':
                type_data = 'UMI'
            if datas['type'] == 'fixed_amount':
                type_data = 'Monto Fijo'

            credit = self.env['hr.infonavit.credit.line'].search([
                ('infonavit_credit_number', '=', datas['infonavit_credit_number']),
            ], limit=1)

            data.setdefault(datas['infonavit_credit_number'], {'periods': {},
                                'ssnid': line['ssnid'],
                                'date_credit': credit.date.strftime('%d-%m-%Y'),
                                'employee_name': line['employee_name'],
                                'employee_code': line['employee_code'].upper(),
                                'struct_name': line['struct_name'],
                                'payslip_code': line['payslip_code'],
                                'dep_name': line['dep_name'],
                                'dep_code': line['dep_code'],
                                'job_name': line['job_name'],
                                'type': type_data,
                                'works': line['works'],
                                'leaves': line['leaves'],
                                'total_works': line['works'] - line['leaves'],
                                'value': datas['value'],
                                'total_bimester': datas['total_bimester'],
                                'daily_infonavit': datas['daily_infonavit'],
                                'days_period': datas['days_period'],
                                'days_absences': datas['days_absences'],
                                'total_day': datas['total_day'],
                                'amount_infonavit': datas['amount_infonavit'],
                                'secure': datas['secure'],
                                'total_infonavit': datas['total_infonavit'],
                                'date': line['period_date_start'],
                                'total_discount': datas['total_discount'],
                                'contract_date': line['contract_date'].strftime('%d-%m-%Y') if line['contract_date'] else '',
                                'contract_date_end': line['contract_date_end'].strftime('%d-%m-%Y') if line['contract_date_end'] else '',
                                })
            payslip_codes.add(line['payslip_code'])
            if data[datas['infonavit_credit_number']]['date'] < line['period_date_start']:
                # Update for last period
                data[datas['infonavit_credit_number']]['value'] = datas['value']
                data[datas['infonavit_credit_number']]['total_bimester'] = datas['total_bimester']
                data[datas['infonavit_credit_number']]['daily_infonavit'] = datas['daily_infonavit']
                data[datas['infonavit_credit_number']]['days_period'] = datas['days_period']
                data[datas['infonavit_credit_number']]['days_absences'] = datas['days_absences']
                data[datas['infonavit_credit_number']]['total_day'] = datas['total_day']
                data[datas['infonavit_credit_number']]['amount_infonavit'] = datas['amount_infonavit']
                data[datas['infonavit_credit_number']]['secure'] = datas['secure']
                data[datas['infonavit_credit_number']]['total_infonavit'] = datas['total_infonavit']
                data[datas['infonavit_credit_number']]['total_discount'] = datas['total_discount']
                data[datas['infonavit_credit_number']]['date'] = line['period_date_start']

            data[datas['infonavit_credit_number']]['periods'].setdefault(line['period_name'], {
                'type': type_data,
                'total': line['total'],
                'value': datas['value'],
                'total_bimester': datas['total_bimester'],
                'daily_infonavit': datas['daily_infonavit'],
                'days_period': datas['days_period'],
                'days_absences': datas['days_absences'],
                'total_day': datas['total_day'],
                'amount_infonavit': datas['amount_infonavit'],
                'secure': datas['secure'],
                'total_infonavit': datas['total_infonavit'],
                'total_discount': datas['total_discount'],
            })

            # Group by periods
            period = {'date': line['period_date_start'], 'name': line['period_name'], 'total': 0}
            if period not in periods_names:
                periods_names.append(period)
        return [data, periods_names, payslip_codes]

    def print_report_infonavit(self, domain=None):
        file_name = _('INFONAVIT Report %s') % fields.Datetime.now()
        string_periods = ''
        for period in self.period_ids:
            string_periods += '%s - %s / ' % (period.date_start, period.date_end)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format({'bold': True, 'bg_color': '#100D57', 'font_color': '#FFFFFF', 'border': 1, 'top': 1, 'font_size': 11, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})
        report_format = workbook.add_format({'border': 1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        report_format2 = workbook.add_format({'border':0, 'bold':True, 'font_size':12, 'font_name':'Calibri', 'align':'left'})
        report_format_bold = workbook.add_format({'bold': True, 'border': 1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        currency_format = workbook.add_format({'num_format': num_format, 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})
        empty_format = workbook.add_format({'num_format': '0', 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})

        result = self.get_infonavit_lines(domain)
        data = result[0]
        header = result[1]
        payslip_codes = result[2]
        payslips_type = ''
        for code in payslip_codes:
            payslips_type += '%s. ' % code if code else ''

        first_header = [
            {'sequence': 0.2, 'name': 'No. EMP', 'larg': 15},
            {'sequence': 0.3, 'name': 'NOMBRE', 'larg': 40},
            {'sequence': 0.7, 'name': 'NSS', 'larg': 15},
            {'sequence': 0.5, 'name': 'DEPTO', 'larg': 15},
            {'sequence': 0.6, 'name': 'DIRECCIÓN / DEPARTAMENTO', 'larg': 40},
            {'sequence': 0.4, 'name': 'PUESTO', 'larg': 30},
            {'sequence': 0.7, 'name': 'NÓMINA', 'larg': 15},
            {'sequence': 0.0, 'name': 'FECHA ALTA', 'larg': 15},
            {'sequence': 0.1, 'name': 'FECHA BAJA', 'larg': 15},
            {'sequence': 0.8, 'name': 'DÍAS\nTRABAJADOS', 'larg': 15},
            {'sequence': 0.9, 'name': 'INCAPACIDADES', 'larg': 15},
            {'sequence': 1.0, 'name': 'NETO DÍAS\nTRABAJADOS.', 'larg': 15},
            {'sequence': 1.1, 'name': '# CRÉDITO', 'larg': 10},
            {'sequence': 1.1, 'name': 'ALTA CRÉDITO', 'larg': 15},
            {'sequence': 1.2, 'name': 'TIPO', 'larg': 10},
            {'sequence': 1.5, 'name': 'TOTAL\nBIMESTRAL', 'larg': 15},
        ]

        def _write_sheet_header(sheet):
            total_total = 0
            col = 0
            row = 0

            sheet.merge_range(row, 0, row, 9, 'REPORTE INFONAVIT', report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 9, 'Tipo de Nómina: ' + payslips_type, report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 9, 'Periodo(s): ' + string_periods, report_format2)
            row += 2

            sheet.set_row(row, 40)

            for head_col in first_header:
                sheet.write(row, col, head_col['name'], header_format)
                sheet.set_column(col, col, head_col['larg'])
                col += 1
            for period in header:
                sheet.write(row, col, period['name'], header_format)
                sheet.set_column(col, col, 40)
                sheet.write(row + 1, col, 'TOTAL', header_format)
                col += 1

            sheet.write(row, col, 'TOTAL', header_format)
            sheet.set_column(col, col, 15)
            row += 2
            for contract in data:
                col = 0
                sheet.write(row, col, data[contract]['employee_code'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['employee_name'], report_format)
                col += 1
                sheet.write(row, col, data[contract].get('ssnid', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('job_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('payslip_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract]['contract_date'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['contract_date_end'], report_format)
                col += 1
                sheet.write(row, col, data[contract].get('works', 0), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('leaves', 0), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('total_works', 0), report_format)
                col += 1
                sheet.write(row, col, contract, report_format)
                col += 1
                sheet.write(row, col, data[contract].get('date_credit', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('type', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('total_bimester', 0), currency_format)
                col += 1

                total_all = 0
                for period in sorted(header, key=lambda k: k['date']):
                    if period['name'] in data[contract]['periods']:
                        total_period = data[contract]['periods'][period['name']]['total']
                    else:
                        total_period = 0
                    period['total'] += total_period
                    sheet.write(row, col, total_period, currency_format)
                    total_all += total_period
                    col += 1
                sheet.write(row, col, total_all, currency_format)
                total_total += total_all
                row += 1

            col = 16
            for period in sorted(header, key=lambda k: k['date']):
                sheet.write(row, col, period['total'], currency_format)
                col += 1
            sheet.write(row, col, total_total, currency_format)

        sheet_header = workbook.add_worksheet("Total")
        _write_sheet_header(sheet_header)

        workbook.close()
        xlsx_data = output.getvalue()
        file_id = self.env['wizard.file.download'].create({
            'file': base64.b64encode(xlsx_data),
            'name': file_name + '.xlsx'
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

    def export_report(self):
        domain = ''
        # Filter Structures
        if len(self.structure_ids) == 1:
            domain += ' AND struct.id = %s' % str(self.structure_ids.id)
        if len(self.structure_ids) > 1:
            domain += ' AND struct.id IN %s' % str(tuple(self.structure_ids.ids))
        # Filter Periods
        if len(self.period_ids) == 1:
            domain += ' AND period.id = %s' % str(self.period_ids.id)
        if len(self.period_ids) > 1:
            domain += ' AND period.id IN %s' % str(tuple(self.period_ids.ids))

        if self.type == 'fonacot':
            return self.print_report_fonacot(domain)
        if self.type == 'infonavit':
            return self.print_report_infonavit(domain)
