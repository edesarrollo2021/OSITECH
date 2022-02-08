# -*- coding: utf-8 -*-

import io
import base64
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell

class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    ########################
    # EXCEL Reports
    ########################

    @api.model
    def _get_query_payslip_isn_line(self, domain=None):
        where_clause = domain or "1=1"
        select = """
                SELECT
                    COALESCE(SUM(line.total), 0) as total,
                    COALESCE(SUM(line.isn_amount), 0) as isn_amount,
                    rule.id as rule_id,
                    rule.code as rule_code,
                    rule.name as rule_name,
                    rule.sequence as sequence,
                    rule.print_to_excel,
                    rule.report_imss,
                    rule.report_isn,
                    rule.consolidate as consolidate,
                    rule.provision as provision,
                    employee.id as employee_id,
                    employee.registration_number as employee_code,
                    employee.name as employee_name,
                    employee.last_name as last_name,
                    employee.mothers_last_name as mothers_last_name,
                    employee.registration_number as employee_code,
                    employee.ssnid as ssnid,
                    dep.code as dep_code,
                    dep.name as dep_name,
                    contract.daily_salary as daily_salary,
                    contract.date_start as contract_date_start,
                    CASE
                        WHEN contract.previous_contract_date IS NOT NULL THEN contract.previous_contract_date
                        ELSE contract.date_start
                    END contract_date
                FROM hr_payslip_line line
                JOIN hr_payslip slip ON line.slip_id = slip.id
                JOIN hr_salary_rule rule ON line.salary_rule_id = rule.id
                JOIN hr_contract contract ON line.contract_id = contract.id
                JOIN hr_employee employee ON line.employee_id = employee.id
                JOIN hr_department dep ON employee.department_id = dep.id
                JOIN hr_payroll_structure struct ON slip.struct_id = struct.id   
                WHERE %s
                    AND line.total > 0 AND slip.state='done'
                    AND rule.report_isn IS TRUE
                    --AND employee.id = 772
                GROUP BY slip.id, rule.id, contract.id, employee.id, dep.id
                ORDER BY slip.id DESC, rule.sequence;
            """
        # # 2.Fetch data from DB
        select = select % (where_clause)
        self.env.cr.execute(select)
        results = self.env.cr.dictfetchall()
        return results

    def _prepare_data_isn(self, domain=None):
        results = self._get_query_payslip_isn_line(domain=domain)
        if not results:
            raise UserError(_("Data Not Found"))
        header_isn = {}
        employees_isn = {}
        isn_codes = ['ISN001', 'ISN002', 'ISN003']
        # Data
        for res in results:
            if res.get('report_isn', False):
                if res['isn_amount'] > 0 or res['rule_code'] in isn_codes:
                    total = res['total'] if res['rule_code'] in isn_codes else res['isn_amount']
                    header_isn.setdefault(res['rule_code'], {'name': res['rule_name'], 'sequence': res['sequence']})
                    employees_isn.setdefault(res['dep_code'], {'employees': [], 'rules': {}})
                    employees_isn[res['dep_code']]['rules'].setdefault(res['rule_code'], []).append(total)
                    if res['consolidate'] and len(employees_isn[res['dep_code']]['rules'][res['rule_code']]) > 1:
                        employees_isn[res['dep_code']]['rules'][res['rule_code']].pop(-1)
                    employees_isn[res['dep_code']]['employees'].append(res['employee_id'])
                    employees_isn[res['dep_code']].setdefault('data', {
                        'dep_name': res['dep_name'],
                    })
        data = {
            'header_isn': header_isn,
            'employees_isn': employees_isn,
        }
        return data

    def print_xlsx_isn(self, structure=None, period=None):
        # Filter Structures
        clause1 = ''
        clause2 = ''
        if len(structure) == 1:
            clause1 = 'slip.struct_id = %s' % str(structure.id)
        if len(structure) > 1:
            clause1 = 'slip.struct_id IN %s' % str(tuple(structure.ids))
        # Filter Periods
        if len(period) == 1:
            clause2 = 'slip.payroll_period_id = %s' % str(period.id)
        if len(period) > 1:
            clause2 = 'slip.payroll_period_id IN %s' % str(tuple(period.ids))
        domain = clause1 if structure else ''
        union = ' AND ' if structure and period else ''
        domain += union
        domain += clause2 if period else ''
        data_isn = self._prepare_data_isn(domain=domain)
        if any(not struct.payslip_code for struct in structure):
            raise ValidationError(_('One of the struct for these payslips has no payslip code.'))
        struct_name = ', '.join(structure.mapped('payslip_code'))
        months = []
        years = []

        for p in period:
            month = dict(self.env['hr.payroll.period']._fields['month']._description_selection(self.env))[p.month]
            months.append(month)
            years.append(str(p.year))

        years = ', '.join(list(set(years)))
        months = ', '.join(list(set(months)))

        domain = ''
        is_one_lote = self.env.context.get('one_lote', False)
        file_name = _('ISN REPORT %s') % fields.Datetime.now()
        if is_one_lote:
            file_name = 'ISN %s %s' % (self.name, fields.Datetime.now())
            domain = 'slip.payslip_run_id = %s' % self.id
        data = self._prepare_data(domain=domain)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory':True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format(
            {'bold':True, 'bg_color':'#100D57', 'font_color':'#FFFFFF',
             'border':1, 'top':1, 'font_size':9, 'align':'center',
             'valign':'vcenter', 'font_name':'Calibri'})
        report_format = workbook.add_format(
            {'border':1, 'bold':True, 'font_size':9, 'font_name':'Calibri',
             'align':'center'})
        formula_format = workbook.add_format(
            {'num_format':num_format, 'bold':True, 'border':1, 'top':1,
             'font_size':8, 'align':'center', 'valign':'vcenter',
             'font_name':'Calibri'})
        currency_format = workbook.add_format(
            {'num_format':num_format, 'bold':True, 'border':1, 'top':1,
             'font_size':9, 'align':'center', 'valign':'vcenter',
             'font_name':'Calibri'})

        header = [
            {'sequence': 0.01, 'name': 'CENTRO DE COSTO', 'larg': 10},
            {'sequence': 0.02, 'name': 'EMPLEADOS', 'larg': 20},
            {'sequence': 0.03, 'name': 'NOMBRE C.COSTO', 'larg': 20},
        ]

        def _write_sheet(sheet, rule_header=None, data=None):
            order_header = dict(sorted(rule_header.items(), key=lambda item: item[1]['sequence']))
            sheet.set_column(0, 0, 15)
            sheet.write(0, 0, 'CIA', report_format)
            sheet.merge_range('B1:C1', self.env.company.name, report_format)
            sheet.write(1, 0, 'PERIODO_ANUAL', report_format)
            sheet.merge_range('B2:C2', years, report_format)
            sheet.write(2, 0, 'TIPO_NOM', report_format)
            sheet.merge_range('B3:C3', struct_name, report_format)
            sheet.write(3, 0, 'TIPO_DIP', report_format)
            sheet.merge_range('B4:C4', '', report_format)
            sheet.write(4, 0, 'MES_ACUM', report_format)
            sheet.merge_range('B5:C5', months, report_format)
            main_col_count = 0
            row_count = 8
            sheet.set_column(3000, 2, 30)
            sheet.set_column(5, 1, 15)
            sheet.set_row(row_count, 60, )
            # Step 1: writing col group headers
            for head_col in header:
                sheet.write(row_count, main_col_count, head_col['name'].replace(' ', '\n'), header_format)
                # sheet.set_column(row_count, main_col_count, head_col['larg'])
                main_col_count += 1
            for rule_head in order_header:
                sheet.set_column(1000, main_col_count, 20)
                sheet.write(row_count, main_col_count, order_header[rule_head]['name'].replace(' ', '\n'), header_format)
                main_col_count += 1

            # Step 2: Write Columns
            total_cc = len(data)
            for ccosto in data:
                main_col_count = 0
                row_count += 1

                total_employees = len(set(data[ccosto]['employees']))

                sheet.write(row_count, main_col_count, ccosto, report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, total_employees, report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, data[ccosto]['data']['dep_name'], report_format)
                main_col_count += 1
                for rule in order_header:
                    sheet.write(row_count, main_col_count, sum(data[ccosto]['rules'].get(rule, [0])), currency_format)
                    # Step 4: Total sum rules
                    start_range = xl_rowcol_to_cell(9, main_col_count)
                    end_range = xl_rowcol_to_cell(total_cc + 8, main_col_count)
                    fila_formula = xl_rowcol_to_cell(total_cc + 10, main_col_count)
                    formula = "=SUM({:s}:{:s})".format(start_range, end_range)
                    sheet.write_formula(fila_formula, formula, formula_format, True)
                    main_col_count += 1

        # Step PRE Last: Send Write File
        if data['employees_isn']:
            sheet_isn = workbook.add_worksheet('ISN')
            _write_sheet(sheet_isn, rule_header=data_isn['header_isn'], data=data_isn['employees_isn'])
        # Step Last: Close File and create on wizard
        workbook.close()
        xlsx_data = output.getvalue()
        file_id = self.env['wizard.file.download'].create({
            'file': base64.b64encode(xlsx_data),
            'name': file_name + '.xlsx'
        })
        return {
            'name': _('Download Report ISN'),
            'view_mode': 'form',
            'res_id': file_id.id,
            'res_model': 'wizard.file.download',
            'view_type': 'form',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

