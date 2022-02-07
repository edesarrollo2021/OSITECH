# -*- coding: utf-8 -*-

import io
import base64
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell
from datetime import date, datetime, timedelta, time


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    ########################
    # EXCEL Reports
    ########################

    @api.model
    def _query_get(self, domain=None):
        new_domain = [
            '&',('total', '>', 0),
            '|','|',('print_to_excel', '=', True),('report_imss', '=', True),('report_isn', '=', True),
        ]

        domain = domain or [] + new_domain
        self.env['hr.payslip.line'].check_access_rights('read')

        query = self.env['hr.payslip.line']._where_calc(domain)

        # Wrap the query with 'company_id IN (...)' to avoid bypassing company access rights.
        # self.env['hr.payslip.line']._apply_ir_rules(query)
        tables, where_clause, where_params = query.get_sql()
        return tables, where_clause, where_params

    @api.model
    def _get_query_payslip_line(self, domain=None):
        where_clause = domain or "1=1"
        select = """
            SELECT
                COALESCE(SUM(line.total), 0) as total,
                COALESCE(SUM(line.isn_amount), 0) as isn_amount,
                slip.id as slip_id,
                rule.id as rule_id,
                rule.code as rule_code,
                rule.name as rule_name,
                rule.sequence as sequence,
                rule.print_to_excel,
                rule.report_imss,
                rule.report_isn,
                --rule.total_isn,
                rule.consolidate as consolidate,
                rule.provision as provision,
                employee.id as employee_id,
                employee.registration_number as employee_code,
                employee.name as employee_name,
                employee.last_name as last_name,
                employee.mothers_last_name as mothers_last_name,
                struct.name as struct_name,
                employee.registration_number as employee_code,
                employee.ssnid as ssnid,
                partner.curp as curp,
                partner.l10n_mx_edi_curp as l10n_mx_edi_curp,
                partner.rfc as rfc,
                dep.name as dep_name,
                dep.code as dep_code,
                --cc.code as cc_code,
                --cc.name as cc_name,
                job.name job_name,
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
            --JOIN hr_cost_center cc ON employee.cost_center_id = cc.id
            JOIN hr_department dep ON contract.department_id = dep.id
            JOIN hr_job job ON contract.job_id = job.id
            JOIN res_partner partner ON employee.address_home_id = partner.id
            JOIN hr_payroll_structure struct ON slip.struct_id = struct.id   
            WHERE %s
                AND line.total > 0
                AND (rule.print_to_excel IS TRUE OR rule.report_imss IS TRUE OR rule.report_isn IS TRUE OR rule.provision IS TRUE)
                --AND employee.id = 772
            GROUP BY slip.id, rule.id, contract.id, employee.id, dep.id, job.id, partner.id, struct.id
            ORDER BY slip.id, rule.sequence;
        """
        # # 2.Fetch data from DB
        select = select % (where_clause)
        self.env.cr.execute(select)
        results = self.env.cr.dictfetchall()
        return results

    def _prepare_data(self, domain=None):
        results = self._get_query_payslip_line(domain=domain)
        if not results:
            raise UserError(_("Data Not Found"))
        col_header = {}
        groupby_employees = {}
        payslips = {}
        header_imss = {}
        employees_imss = {}
        header_isn = {}
        employees_isn = {}
        header_provision = {}
        employees_provision = {}
        header_isn_cc = {}
        employees_isn_cc = {}
        isn_codes = ['ISN001', 'ISN002', 'ISN003']
        # Data
        for res in results:
            payslips.setdefault(res['slip_id'], res['slip_id'])
            if res.get('print_to_excel', False):
                col_header.setdefault(res['rule_code'], {'name': res['rule_name'], 'sequence': res['sequence']})
                groupby_employees.setdefault(res['employee_id'], {}).setdefault('rules', {}).setdefault(res['rule_code'], [])
                groupby_employees[res['employee_id']]['rules'][res['rule_code']].append(res['total'])
                if res['consolidate'] and len(groupby_employees[res['employee_id']]['rules'][res['rule_code']]) > 1:
                    groupby_employees[res['employee_id']]['rules'][res['rule_code']].pop(-1)
                groupby_employees.setdefault(res['employee_id'], {}).setdefault('data', {
                    'code': res['employee_code'],
                    'last_name': res['last_name'],
                    'mothers_last_name': res['mothers_last_name'],
                    'name': res['employee_name'],
                    'ssnid': res['ssnid'],
                    'rfc': res['rfc'],
                    'curp': res['curp'] or res['l10n_mx_edi_curp'],
                    'struct_name': res['struct_name'],
                    'contract_date_start': fields.Date.from_string(res['contract_date_start']).strftime('%d-%m-%Y'),
                    'contract_date': fields.Date.from_string(res['contract_date']).strftime('%d-%m-%Y'),
                    # 'cc_code': res['cc_code'],
                    # 'cc_name': res['cc_name'],
                    'dep_code': res['dep_code'],
                    'dep_name': res['dep_name'],
                    'job_name': res['job_name'],
                })
            if res.get('report_imss', False):
                header_imss.setdefault(res['rule_code'], {'name': res['rule_name'], 'sequence': res['sequence']})
                employees_imss.setdefault(res['employee_id'], {}).setdefault('rules', {}).setdefault(res['rule_code'], [])
                employees_imss[res['employee_id']]['rules'][res['rule_code']].append(res['total'])
                if res['consolidate'] and len(employees_imss[res['employee_id']]['rules'][res['rule_code']]) > 1:
                    employees_imss[res['employee_id']]['rules'][res['rule_code']].pop(-1)
                employees_imss.setdefault(res['employee_id'], {}).setdefault('data', {
                    'code': res['employee_code'],
                    'last_name': res['last_name'],
                    'mothers_last_name': res['mothers_last_name'],
                    'name': res['employee_name'],
                    'ssnid': res['ssnid'],
                    'rfc': res['rfc'],
                    'curp': res['curp'] or res['l10n_mx_edi_curp'],
                    'struct_name': res['struct_name'],
                    'contract_date_start': fields.Date.from_string(res['contract_date_start']).strftime('%d-%m-%Y'),
                    'contract_date': fields.Date.from_string(res['contract_date']).strftime('%d-%m-%Y'),
                    # 'cc_code': res['cc_code'],
                    # 'cc_name': res['cc_name'],
                    'dep_code': res['dep_code'],
                    'dep_name': res['dep_name'],
                    'job_name': res['job_name'],
                })
            if res['provision']:
                header_provision.setdefault(res['rule_code'], {'name': res['rule_name'], 'sequence': res['sequence']})
                employees_provision.setdefault(res['employee_id'], {}).setdefault(res['rule_code'], [])
                employees_provision[res['employee_id']][res['rule_code']].append(res['total'])
            if res.get('report_isn', False):
                if res['isn_amount'] > 0 or res['rule_code'] in isn_codes:
                    total = res['total'] if res['rule_code'] in isn_codes else res['isn_amount']
                    header_isn.setdefault(res['rule_code'], {'name': res['rule_name'], 'sequence': res['sequence']})
                    employees_isn.setdefault(res['employee_id'], {}).setdefault('rules', {}).setdefault(res['rule_code'], [])
                    employees_isn[res['employee_id']]['rules'][res['rule_code']].append(total)
                    if res['consolidate'] and len(employees_isn[res['employee_id']]['rules'][res['rule_code']]) > 1:
                        employees_isn[res['employee_id']]['rules'][res['rule_code']].pop(-1)
                    employees_isn.setdefault(res['employee_id'], {}).setdefault('data', {
                        'code': res['employee_code'],
                        'last_name': res['last_name'],
                        'mothers_last_name': res['mothers_last_name'],
                        'name': res['employee_name'],
                        'ssnid': res['ssnid'],
                        'rfc': res['rfc'],
                        'curp': res['curp'] or res['l10n_mx_edi_curp'],
                        'struct_name': res['struct_name'],
                        'contract_date_start': fields.Date.from_string(res['contract_date_start']).strftime('%d-%m-%Y'),
                        'contract_date': fields.Date.from_string(res['contract_date']).strftime('%d-%m-%Y'),
                        # 'cc_code': res['cc_code'],
                        # 'cc_name': res['cc_name'],
                        'dep_code': res['dep_code'],
                        'dep_name': res['dep_name'],
                        'job_name': res['job_name'],
                    })
                    #ISN By Center Cost
                    header_isn_cc.setdefault(res['rule_code'], {'name':res['rule_name'], 'sequence':res['sequence']})
                    employees_isn_cc.setdefault(res['dep_code'], {'employees': [], 'rules': {}})
                    employees_isn_cc[res['dep_code']]['rules'].setdefault(res['rule_code'], []).append(total)
                    if res['consolidate'] and len(employees_isn_cc[res['dep_code']]['rules'][res['rule_code']]) > 1:
                        employees_isn_cc[res['dep_code']]['rules'][res['rule_code']].pop(-1)
                    employees_isn_cc[res['dep_code']]['employees'].append(res['employee_id'])
                    employees_isn_cc[res['dep_code']].setdefault('data', {
                        'dep_name':res['dep_name'],
                    })
        data = {
            'payslips': payslips,
            'col_header': col_header,
            'groupby_employees': groupby_employees,
            'header_imss': header_imss,
            'employees_imss': employees_imss,
            'header_provision': header_provision,
            'employees_provision': employees_provision,
            'header_isn': header_isn,
            'employees_isn': employees_isn,
            'header_isn_cc': header_isn_cc,
            'employees_isn_cc': employees_isn_cc,
        }
        return data

    def _get_leaves(self, payslips=None):
        query = """
            SELECT
                slip.employee_id employee_id,
                COALESCE(SUM(work.number_of_days),0) number_of_days,
                CASE
                    WHEN entry.type_leave IS NULL THEN 'daysimss' ELSE entry.type_leave
                END type_leave
            FROM hr_payslip_worked_days work
            JOIN hr_payslip slip ON work.payslip_id = slip.id
            JOIN hr_work_entry_type entry ON work.work_entry_type_id = entry.id
            WHERE 
                (entry.type_leave in ('inability','leave') or entry.code='DIASIMSS')
                AND work.payslip_id in %s
            GROUP BY entry.type_leave, slip.employee_id
        """
        params = (tuple(payslips),)
        self.env.cr.execute(query, params)
        results = self.env.cr.dictfetchall()
        leaves = {}
        for res in results:
            leaves.setdefault(res['employee_id'], {'total': 0}).setdefault(res['type_leave'], res['number_of_days'])
            leaves[res['employee_id']]['total'] += res['number_of_days'] if res['type_leave'] != 'daysimss' else 0
        return leaves

    def _get_leaves_by_dates(self, employee_ids=None, date_from=None, date_to=None):
        query = """
            SELECT employee_id, time_type, sum(number_of_days) as number_of_days 
            FROM hr_leave 
            WHERE date_from <= %s 
                AND date_to >= %s
                AND employee_id in %s
                AND time_type in ('inability','leave')
                AND state = 'validate'
            GROUP BY employee_id, time_type
        """
        params = (date_to, date_from, tuple(employee_ids))
        self.env.cr.execute(query, params)
        results = self.env.cr.dictfetchall()
        data = {}
        for res in results:
            data.setdefault(res['employee_id'], {'total': 0}).setdefault(res['time_type'], res['number_of_days'])
            data[res['employee_id']]['total'] += res['number_of_days']
        return data

    def print_xlsx(self, domain=None, structure=None, period=None):
        # date_start = date_start or fields.Datetime.from_string(self.payroll_period_id.date_start)
        # date_end = date_end or fields.Datetime.from_string(self.payroll_period_id.date_end)
        domain = domain or ''
        is_one_lote = self.env.context.get('one_lote', False)
        file_name = _('Payroll Report %s') % fields.Datetime.now()
        if is_one_lote:
            file_name = 'Nómina-%s %s' % (self.name, fields.Datetime.now())
            domain = "slip.state <> 'cancel' AND slip.payslip_run_id = %s" % self.id
        data = self._prepare_data(domain=domain)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format({'bold':True, 'bg_color':'#100D57', 'font_color':'#FFFFFF', 'border':1, 'top':1, 'font_size':9, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        report_format = workbook.add_format({'border':1, 'bold':True, 'font_size':9, 'font_name':'Calibri', 'align':'center'})
        formula_format = workbook.add_format({'num_format': num_format, 'bold':True, 'border':1, 'top':1, 'font_size':8, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        currency_format = workbook.add_format({'num_format': num_format, 'bold':True, 'border':1, 'top':1, 'font_size':9, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})

        def dateformat(date):
            if date:
                date_format = '%d-%m-%Y'
                if isinstance(date, str):
                    date = datetime.strptime(date, date_format)
                date = date.strftime(date_format)
            return date

        # Data Super Header
        months = []
        years = []
        period = period or self.payroll_period_id
        structure = structure or self.structure_id
        for p in period:
            month = dict(self.env['hr.payroll.period']._fields['month']._description_selection(self.env))[p.month]
            months.append(month)
            years.append(str(p.year))
        years = ', '.join(list(set(years)))
        months = ', '.join(list(set(months)))
        if any(not struct.payslip_code for struct in structure):
            raise ValidationError(_('One of the struct for these payslips has no payslip code.'))
        struct_name = ', '.join(structure.mapped('payslip_code'))
        header = [
            {'sequence': 0.01, 'name': 'No. EMPLEADO', 'larg': 5, 'col':{}},
            {'sequence': 0.02, 'name': 'APELLIDO PATERNO', 'larg': 20, 'col':{}},
            {'sequence': 0.02, 'name': 'APELLIDO MATERNO', 'larg': 20, 'col':{}},
            {'sequence': 0.02, 'name': 'NOMBRE COMPLETO', 'larg': 30, 'col':{}},
            {'sequence': 0.03, 'name': 'NSS', 'larg': 10, 'col':{}},
            {'sequence': 0.04, 'name': 'RFC', 'larg': 10, 'col':{}},
            {'sequence': 0.05, 'name': 'CURP', 'larg': 10, 'col':{}},
            {'sequence': 0.05, 'name': 'TIPO DE NÓMINA', 'larg': 10, 'col':{}},
            {'sequence': 0.06, 'name': 'FECHA ALTA', 'larg': 15, 'col':{}},
            {'sequence': 0.06, 'name': 'FECHA PLANTA', 'larg': 15, 'col':{}},
            {'sequence': 0.07, 'name': 'CCOSTO', 'larg': 5, 'col': {}},
            # {'sequence': 0.07, 'name': 'NOMBRE DEL CCOSTO', 'larg': 5, 'col': {}},
            {'sequence': 0.08, 'name': 'DIRECCIÓN / CCOSTO', 'larg': 30, 'col': {}},
            {'sequence': 0.09, 'name': 'PUESTO DE TRABAJO', 'larg': 30, 'col': {}},
            {'sequence': 0.1, 'name': 'AUSENCIAS', 'larg': 20, 'col': {}},
            {'sequence': 0.11, 'name': 'INCAPACIDADES', 'larg': 20, 'col': {}},
            {'sequence': 0.12, 'name': 'TOTAL AUSENTISMOS', 'larg': 20, 'col': {}},
        ]
        header_imss = [
            {'sequence': 0.1, 'name': 'DÍAS COTIZADOS', 'larg': 20, 'col': {}},
        ]
        header_isn_cc = [
            {'sequence': 0.01, 'name': 'CENTRO DE COSTO', 'larg': 10},
            {'sequence': 0.02, 'name': 'EMPLEADOS', 'larg': 20},
            {'sequence': 0.03, 'name': 'NOMBRE C.COSTO', 'larg': 20},
        ]
        employee_leaves = self._get_leaves(payslips=data['payslips'].keys())

        def _write_sheet_header(sheet, rule_header=None, data=None, employees_provision=None, header_provision=None, report_name=None, report=None):
            order_header = dict(sorted(rule_header.items(), key=lambda item:item[1]['sequence']))
            # order_header = rule_header
            sheet.set_column(0, 0, 15)
            main_col_count = 0
            sheet.write(0, 0, 'CIA', report_format)
            sheet.merge_range('B1:C1', self.env.company.name, report_format)
            sheet.write(1, 0, 'PERIODO_ANUAL', report_format)
            sheet.merge_range('B2:C2', years, report_format)
            sheet.write(2, 0, 'TIPO_NOM', report_format)
            sheet.merge_range('B3:C3', struct_name, report_format)
            sheet.write(3, 0, 'REPORTE', report_format)
            sheet.merge_range('B4:C4', report_name, report_format)
            sheet.write(4, 0, 'MES_ACUM', report_format)
            sheet.merge_range('B5:C5', months, report_format)
            row_count = 6
            row_init = row_count + 1
            # sheet.set_column(3000, 2, 30)
            # sheet.set_column(5, 1, 15)
            sheet.set_row(row_count, 60, )
            # Step 1: writing col group headers
            for head_col in header:
                sheet.write(row_count, main_col_count, head_col['name'].replace(' ', '\n'), header_format)
                sheet.set_column(0, main_col_count, head_col['larg'])
                main_col_count += 1
            if report == 'IMSS':
                for col_imss in header_imss:
                    sheet.write(row_count, main_col_count, col_imss['name'].replace(' ', '\n'), header_format)
                    sheet.set_column(0, main_col_count, col_imss['larg'])
                    main_col_count += 1
            for rule_head in order_header:
                sheet.set_column(1000, main_col_count, 20)
                sheet.write(row_count, main_col_count, order_header[rule_head]['name'].replace(' ', '\n'), header_format)
                main_col_count += 1
            main_col_count += 1
            if header_provision:
                order_header_provision = dict(sorted(header_provision.items(), key=lambda item:item[1]['sequence']))
                for rule_prov in order_header_provision:
                    sheet.set_column(1000, main_col_count, 20)
                    sheet.write(row_count, main_col_count, order_header_provision[rule_prov]['name'].replace(' ', '\n'), header_format)
                    main_col_count += 1

            # Step 2: writing col employee data
            employees = data
            total_employees = len(employees)
            for employee in employees:
                main_col_count = 0
                row_count += 1

                sheet.write(row_count, main_col_count, employees[employee]['data']['code'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data']['last_name'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('mothers_last_name', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('name', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('ssnid', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('rfc', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('curp', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('struct_name', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, dateformat(employees[employee]['data'].get('contract_date_start', '')), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, dateformat(employees[employee]['data'].get('contract_date', '')), report_format)
                main_col_count += 1
                # sheet.write(row_count, main_col_count, employees[employee]['data'].get('cc_code', ''), report_format)
                # main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('dep_code', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('dep_name', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('job_name', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employee_leaves.get(employee, {}).get('leave', 0), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employee_leaves.get(employee, {}).get('inability', 0), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employee_leaves.get(employee, {}).get('total', 0), report_format)
                main_col_count += 1
                if report == 'IMSS':
                    sheet.write(row_count, main_col_count, employee_leaves.get(employee, {}).get('daysimss', 0), report_format)
                    main_col_count += 1

                for rule in order_header:
                    sheet.write(row_count, main_col_count, sum(employees[employee]['rules'].get(rule, [0])), currency_format)
                    # Step 4: Total sum rules
                    start_range = xl_rowcol_to_cell(row_init, main_col_count)
                    end_range = xl_rowcol_to_cell(total_employees + row_init, main_col_count)
                    fila_formula = xl_rowcol_to_cell(total_employees + row_init + 1, main_col_count)
                    formula = "=SUM({:s}:{:s})".format(start_range, end_range)
                    sheet.write_formula(fila_formula, formula, formula_format, True)
                    main_col_count += 1
                main_col_count += 1

                if header_provision:
                    for rule_prov in order_header_provision:
                        sheet.write(row_count, main_col_count, sum(employees_provision.get(employee, {}).get(rule_prov, [0])), currency_format)
                        start_range = xl_rowcol_to_cell(1, main_col_count)
                        end_range = xl_rowcol_to_cell(total_employees + row_init, main_col_count)
                        fila_formula = xl_rowcol_to_cell(total_employees + row_init + 1, main_col_count)
                        formula = "=SUM({:s}:{:s})".format(start_range, end_range)
                        sheet.write_formula(fila_formula, formula, formula_format, True)
                        main_col_count += 1
        # Write Sheet ISN by Center Cost
        def _write_sheet_ccost(sheet, rule_header=None, data=None, report_name=None):
            order_header = dict(sorted(rule_header.items(), key=lambda item: item[1]['sequence']))
            sheet.set_column(0, 0, 15)
            sheet.write(0, 0, 'CIA', report_format)
            sheet.merge_range('B1:C1', self.env.company.name, report_format)
            sheet.write(1, 0, 'PERIODO_ANUAL', report_format)
            sheet.merge_range('B2:C2', years, report_format)
            sheet.write(2, 0, 'TIPO_NOM', report_format)
            sheet.merge_range('B3:C3', struct_name, report_format)
            sheet.write(3, 0, 'REPORTE', report_format)
            sheet.merge_range('B4:C4', report_name, report_format)
            sheet.write(4, 0, 'MES_ACUM', report_format)
            sheet.merge_range('B5:C5', months, report_format)
            main_col_count = 0
            row_count = 8
            sheet.set_column(3000, 2, 30)
            sheet.set_column(5, 1, 15)
            sheet.set_row(row_count, 60, )
            # Step 1: writing col group headers
            for head_col in header_isn_cc:
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
        # if data['employees_isn']:
        #     sheet_isn = workbook.add_worksheet('ISN')
        #     _write_sheet(sheet_isn, rule_header=data_isn['header_isn'], data=data_isn['employees_isn'])

        if data['groupby_employees']:
            sheet_all = workbook.add_worksheet(file_name)
            report_name = 'Reporte Acumulado de Nóminas'
            if is_one_lote:
                report_name = 'Reporte de Nóminas'
            _write_sheet_header(sheet_all, rule_header=data['col_header'], data=data['groupby_employees'], employees_provision=data['employees_provision'], header_provision=data['header_provision'], report_name=report_name, report=None)
        if data['employees_imss']:
            report_name = 'Reporte Acumulado IMSS'
            if is_one_lote:
                report_name = 'Reporte IMSS'
            sheet_imss = workbook.add_worksheet('IMSS')
            _write_sheet_header(sheet_imss, rule_header=data['header_imss'], data=data['employees_imss'], report_name=report_name, report='IMSS')
        if data['employees_isn']:
            report_name = 'Reporte Acumulado ISN por Empleado'
            if is_one_lote:
                report_name = 'Reporte ISN por Empleado'
            sheet_isn = workbook.add_worksheet('ISN Empleados')
            _write_sheet_header(sheet_isn, rule_header=data['header_isn'], data=data['employees_isn'], report_name=report_name, report=None)
        if data['employees_isn_cc']:
            report_name = 'Reporte Acumulado ISN por C.COSTO'
            if is_one_lote:
                report_name = 'Reporte ISN por C. COSTO'
            sheet_isn_cc = workbook.add_worksheet('ISN C.COSTO')
            _write_sheet_ccost(sheet_isn_cc, rule_header=data['header_isn_cc'], data=data['employees_isn_cc'], report_name=report_name)

        # Step Last: Close File and create on wizard
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

    def get_data_taxed(self, domain=None):
        where_clause = domain or "1=1"

        query = """
                    SELECT 
                        COALESCE(SUM(line.total), 0) as total,
                        COALESCE(SUM(line.tax_amount), 0) as tax_amount,
                        rule.code as rule_code,
                        rule.name as rule_name,
                        rule.sequence as sequence,
                        slip.id as slip,
                        employee.id as employee_id,
                        employee.registration_number as employee_code,
                        employee.complete_name as employee_name,
                        contract.code as contract_code,
                        employee.ssnid as ssnid,
                        partner.curp as curp,
                        partner.rfc as rfc,
                        dep.name as dep_name,
                        dep.code as dep_code,
                        job.name as job_name,
                        struct.payslip_code as payslip_code,
                        CASE
                            WHEN contract.previous_contract_date IS NOT NULL THEN contract.previous_contract_date
                            ELSE contract.date_start
                        END contract_date
                    FROM hr_payslip_line line
                    JOIN hr_payslip slip ON line.slip_id = slip.id
                    JOIN hr_contract contract ON slip.contract_id = contract.id
                    JOIN hr_salary_rule rule ON line.salary_rule_id = rule.id
                    JOIN hr_employee employee ON line.employee_id = employee.id
                    JOIN res_partner partner ON employee.address_home_id = partner.id
                    JOIN hr_department dep ON employee.department_id = dep.id
                    JOIN hr_job job ON employee.job_id = job.id
                    JOIN hr_payroll_structure struct ON slip.struct_id = struct.id  
                    WHERE 
                        %s AND rule.taxable IS TRUE 
                        AND slip.state NOT IN ('cancel')
                        AND rule.type = 'perception'
                    GROUP BY line.total, employee.id, employee.complete_name, employee.registration_number, 
                            rule.code, rule.name, slip.id, total, contract.code, employee.ssnid, partner.rfc, 
                            partner.curp, contract_date, dep.code, dep.name, job.name, rule.sequence, struct.payslip_code
                """

        query = query % where_clause
        self.env.cr.execute(query)
        results = self.env.cr.dictfetchall()

        data = {}
        control = []
        header = []
        payslip_codes = set()
        for line in results:
            data.setdefault(line['contract_code'], {'lines_ids': {},
                    'code': line['employee_code'],
                    'payslip_code': line['payslip_code'],
                    'name': line['employee_name'],
                    'ssnid': line['ssnid'],
                    'rfc': line['rfc'],
                    'curp': line['curp'],
                    'contract_date': fields.Date.from_string(line['contract_date']).strftime('%d-%m-%Y'),
                    'dep_code': line['dep_code'],
                    'dep_name': line['dep_name'],
                    'job_name': line['job_name'],
                })
            payslip_codes.add(line['payslip_code'])
            if line['rule_code']:
                data[line['contract_code']]['lines_ids'].setdefault(line['rule_code'], {'taxed': [], 'total': []})
                data[line['contract_code']]['lines_ids'][line['rule_code']]['total'].append(line['total'] - line['tax_amount'])
                data[line['contract_code']]['lines_ids'][line['rule_code']]['taxed'].append(line['tax_amount'])

                rule = {'name': line['rule_name'], 'code': line['rule_code'], 'sequence': line['sequence']}
                if line['rule_code'] not in control:
                    header.append(rule)
                    control.append(line['rule_code'])
        return [data, header, payslip_codes]

    def report_taxed_print(self, domain=''):
        is_one_lote = self.env.context.get('one_lote', False)
        file_name = _('Taxed Report %s') % fields.Datetime.now()
        periods = self.env.context.get('periods', self.env['hr.payroll.period'])
        if is_one_lote:
            file_name = '%s %s' % (self.name, fields.Datetime.now())
            domain = 'slip.payslip_run_id = %s' % self.id
            periods = self.payroll_period_id

        string_periods = ''
        for period in periods:
            string_periods += '%s - %s / ' % (period.date_start, period.date_end)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format({'bold':True, 'bg_color':'#100D57', 'font_color':'#FFFFFF', 'border':1, 'top':1, 'font_size':9, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        report_format = workbook.add_format({'border':0, 'bold':True, 'font_size':9, 'font_name':'Calibri', 'align':'center'})
        report_format2 = workbook.add_format({'border':0, 'bold':True, 'font_size':12, 'font_name':'Calibri', 'align':'left'})
        currency_format = workbook.add_format({'num_format': num_format, 'bold':True, 'border':1, 'top':1, 'font_size':9, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        empty_format = workbook.add_format({'num_format': '0', 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})

        # Write data
        result = self.get_data_taxed(domain)
        data = result[0]
        if not data:
            raise UserError(_('No data found for the report'))
        header = result[1]
        payslip_codes = result[2]
        payslips_type = ''
        for code in payslip_codes:
            payslips_type += '%s. ' % code if code else ''

        first_header = [
            {'sequence': 0.0, 'name': 'No. CONTRATO', 'larg': 15, 'col': {}},
            {'sequence': 0.1, 'name': 'No. EMPLEADO', 'larg': 15, 'col': {}},
            {'sequence': 0.2, 'name': 'NOMBRE', 'larg': 40, 'col': {}},
            {'sequence': 0.3, 'name': 'NSS', 'larg': 15, 'col': {}},
            {'sequence': 0.4, 'name': 'RFC', 'larg': 15, 'col': {}},
            {'sequence': 0.5, 'name': 'CURP', 'larg': 15, 'col': {}},
            {'sequence': 0.6, 'name': 'FECHA\nDE\nANTIGÜEDAD', 'larg': 15, 'col': {}},
            {'sequence': 0.7, 'name': 'C.DEPARTAMENTO', 'larg': 15, 'col': {}},
            {'sequence': 0.8, 'name': 'DIRECCIÓN / DEPARTAMENTO', 'larg': 30, 'col': {}},
            {'sequence': 0.9, 'name': 'PUESTO\nDE\nTRABAJO', 'larg': 30, 'col': {}},
        ]

        def _write_sheet_header(sheet):
            col = 0
            row = 0
            totalize_col = 9

            sheet.merge_range(row, 0, row, 9, 'REPORTE DE GRAVADOS', report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 9, 'Tipo de Nómina: ' + payslips_type, report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 9, 'Periodo(s): ' + string_periods, report_format2)
            row += 2
            sheet.set_row(row, 60)
            for head_col in first_header:
                sheet.write(row, col, head_col['name'], header_format)
                sheet.set_column(col, col, head_col['larg'])
                col += 1
            for head in sorted(header, key=lambda k: k['sequence']):
                sheet.write(row, col, head['name'].replace(' ', '\n'), header_format)
                sheet.set_column(col, col, 15)
                col += 1
                sheet.write(row, col, head['name'].replace(' ', '\n') + "\n(GRAVADO)", header_format)
                sheet.set_column(col, col, 15)
                col -= 1
                sheet.write(row + 1, col, 'EXENTO', header_format)
                col += 1
                sheet.write(row + 1, col, 'GRAVADO', header_format)
                col += 1
                totalize_col += 2
            sheet.write(row, col, 'TOTAL BASE GRAVADA'.replace(' ', '\n'), header_format)
            sheet.set_column(col, col, 15)
            col += 1
            sheet.write(row, col, 'TOTAL EXENTO'.replace(' ', '\n'), header_format)
            sheet.set_column(col, col, 15)
            col += 1
            sheet.write(row, col, 'TOTAL GLOBAL'.replace(' ', '\n'), header_format)
            sheet.set_column(col, col, 15)

            row += 2
            total_no_tax = 0
            total_tax = 0
            total = 0
            for contract in data:
                col = 0
                sheet.write(row, col, contract, report_format)
                col += 1
                sheet.write(row, col, data[contract]['code'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['name'], report_format)
                col += 1
                sheet.write(row, col, data[contract].get('ssnid', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('rfc', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('curp', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('contract_date', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('job_name', ''), report_format)
                col += 1

                # Write lines
                not_tax = 0
                tax = 0
                for rule in sorted(header, key=lambda k: k['sequence']):
                    if rule['code'] not in data[contract]['lines_ids']:
                        sheet.write(row, col, 0.0, currency_format)
                        col += 1
                        sheet.write(row, col, 0.0, currency_format)
                    else:
                        amount = sum(data[contract]['lines_ids'][rule['code']]['total'])
                        amount_tax = sum(data[contract]['lines_ids'][rule['code']]['taxed'])
                        sheet.write(row, col, amount, currency_format)
                        col += 1
                        sheet.write(row, col, amount_tax, currency_format)
                        not_tax += amount
                        tax += amount_tax
                    col += 1

                sheet.write(row, col, tax, currency_format)
                total_tax += tax
                col += 1
                sheet.write(row, col, not_tax, currency_format)
                total_no_tax += not_tax
                col += 1
                sheet.write(row, col, tax + not_tax, currency_format)
                total += tax + not_tax
                row += 1

            col = totalize_col
            sheet.write(row, col, 'TOTAL:', header_format)
            col += 1
            sheet.write(row, col, total_tax, currency_format)
            col += 1
            sheet.write(row, col, total_no_tax, currency_format)
            col += 1
            sheet.write(row, col, total, currency_format)
            row += 1

        sheet_all = workbook.add_worksheet(file_name)
        _write_sheet_header(sheet_all)

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

    def pending_discount_report(self):
        select = """
                    SELECT
                        line.total,
                        line.pending_amount,
                        rule.id as rule_id,
                        rule.code as rule_code,
                        rule.name as rule_name,
                        period.name as period_name,
                        period.code as period_code,
                        employee.id as employee_id,
                        employee.registration_number as employee_code,
                        struct.payslip_code as payslip_code,
                        employee.complete_name as employee_name
                    FROM hr_payslip_line line
                    JOIN hr_payslip slip ON line.slip_id = slip.id
                    JOIN hr_salary_rule rule ON line.salary_rule_id = rule.id
                    JOIN hr_employee employee ON line.employee_id = employee.id
                    JOIN hr_payroll_period period ON slip.payroll_period_id = period.id
                    JOIN hr_payroll_structure struct ON slip.struct_id = struct.id
                    WHERE 
                        slip.state NOT IN ('cancel')
                        AND line.pending_amount > 0
                        AND line.payslip_run_id = %s
                    ORDER BY employee.registration_number, rule.sequence;
                """

        self.env.cr.execute(select, (self.id,))
        data = self.env.cr.dictfetchall()
        if not data:
            raise UserError(_('No data found for the report'))

        string_periods = ''
        for period in self.payroll_period_id:
            string_periods += '%s - %s / ' % (period.date_start, period.date_end)

        payslips_type = ''
        payslip_codes = []
        for code in data:
            if code and code not in payslip_codes:
                payslips_type += '%s. ' % code if code else ''
                payslip_codes.append(code)
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        currency_format = workbook.add_format({'num_format': num_format, 'bold':True, 'border':1, 'top':1, 'font_size':9, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        header_format = workbook.add_format({'bold': True, 'bg_color': '#100D57', 'font_color': '#FFFFFF', 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})
        report_format = workbook.add_format({'border': 1, 'bold': True, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        report_format2 = workbook.add_format({'border':0, 'bold':True, 'font_size':12, 'font_name':'Calibri', 'align':'left'})

        file_name = _('Pending Discount %s %s') % (fields.Datetime.now(), self.name)
        header = [
            {'sequence': 0.1, 'name': 'No. EMPLEADO', 'larg': 15},
            {'sequence': 0.2, 'name': 'NOMBRE', 'larg': 40},
            {'sequence': 0.3, 'name': 'CÓDIGO\nDE\nPERIODO', 'larg': 10},
            {'sequence': 0.4, 'name': 'PERIODO', 'larg': 10},
            {'sequence': 0.5, 'name': 'CÓDIGO\nDE\nREGLA', 'larg': 15},
            {'sequence': 0.6, 'name': 'NOMBRE\nDE\nREGLA', 'larg': 30},
            {'sequence': 0.7, 'name': 'TOTAL', 'larg': 15},
            {'sequence': 0.8, 'name': 'DESCUENTO\nAPLICABLE', 'larg': 15},
            {'sequence': 0.9, 'name': 'PENDIENTE', 'larg': 15},
        ]

        def _write_sheet_header(sheet):
            col = 0
            row = 0

            sheet.merge_range(row, 0, row, 5, 'REPORTE DE DESCUENTOS PENDIENTES', report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 5, 'Tipo de Nómina: ' + payslips_type, report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 5, 'Periodo(s): ' + string_periods, report_format2)
            row += 2

            sheet.set_row(row, 60)
            for head_col in header:
                sheet.set_column(col, col, head_col['larg'])
                sheet.write(row, col, head_col['name'], header_format)
                col += 1

            amount_total = 0
            for line in data:
                col = 0
                row += 1
                sheet.write(row, col, line['employee_code'], report_format)
                col += 1
                sheet.write(row, col, line['employee_name'], report_format)
                col += 1
                sheet.write(row, col, line['period_code'], report_format)
                col += 1
                sheet.write(row, col, line['period_name'], report_format)
                col += 1
                sheet.write(row, col, line['rule_code'], report_format)
                col += 1
                sheet.write(row, col, line['rule_name'], report_format)
                col += 1
                sheet.write(row, col, line['total'] + line['pending_amount'], currency_format)
                col += 1
                sheet.write(row, col, line['total'], currency_format)
                col += 1
                sheet.write(row, col, line['pending_amount'], currency_format)
                amount_total += line['pending_amount']

            col = 7
            row += 1
            sheet.write(row, col, 'TOTAL', header_format)
            col += 1
            sheet.write(row, col, amount_total, currency_format)

        sheet_all = workbook.add_worksheet(file_name)
        _write_sheet_header(sheet_all)

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

    def get_leaves_by_type(self, employees, date_from1, date_to1, period):
        date_start = datetime.combine(date_from1, time.min)
        date_end = datetime.combine(date_to1, time.max)
        datetime_start = fields.Datetime.to_string(date_start)
        datetime_end = fields.Datetime.to_string(date_end)
        if len(period) > 1:
            period_string = f" AND entry.payroll_period_id IN {period._ids} "
        else:
            period_string = f" AND entry.payroll_period_id = {period.id} "

        if not len(employees):
            return [{}, []]
        query = """
                SELECT 
                    leave.id,
                    type_entry.code,
                    type_entry.name,
                    SUM(entry.duration) AS duration,
                    employee.registration_number AS employee_code,
                    employee.complete_name AS employee_name,
                    leave.request_date_from AS date_from,
                    leave.request_date_to AS date_to,
                    leave.folio,
                    entry.out_of_date
                FROM hr_work_entry entry
                JOIN hr_work_entry_type type_entry ON type_entry.id = entry.work_entry_type_id
                JOIN hr_employee employee ON employee.id = entry.employee_id
                JOIN hr_leave leave ON leave.id = entry.leave_id
                WHERE 
                    type_entry.code in ('F04','F03','F01','F06','F10')
                    AND employee.registration_number in %s
                    AND entry.state in ('validated','draft')
                    AND ((entry.out_of_date IS NOT TRUE AND (entry.date_start, entry.date_stop) OVERLAPS (%s, %s))
                    OR (entry.out_of_date IS TRUE """ + period_string + """))
                GROUP BY leave.id, type_entry.code, employee.registration_number, employee.complete_name,
                    entry.out_of_date, type_entry.name, leave.folio
                """
        self.env.cr.execute(query, (tuple(employees), datetime_start, datetime_end))
        results = self.env.cr.dictfetchall()

        data = {}
        header = []
        for line in results:
            date_from = fields.Date.from_string(line['date_from'])
            date_to = fields.Date.from_string(line['date_to'])
            if date_from <= date_from1 and not line['out_of_date']:
                date_from = date_from1
            if date_to1 <= date_to and not line['out_of_date']:
                date_to = date_to1
            data.setdefault(line['code'], [])
            data[line['code']].append({'employee_code': line['employee_code'],
                                       'employee_name': line['employee_name'],
                                       'duration': line['duration'],
                                       'out_of_date': line['out_of_date'],
                                       'folio': line['folio'],
                                       'date_from': date_from.strftime('%d-%m-%Y'),
                                       'date_to': date_to.strftime('%d-%m-%Y')})

            leave = {'name': line['name'], 'code': line['code']}
            if leave not in header:
                header.append(leave)
        return [data, header]

    def get_data_assa_and_aspa(self, domain):
        """
            This method builds all the information for the reports:
             * ASPA
             * ASSA
             * Social objective
             * Saving Fund
        :param domain: string SQL
        :return: list with a dictionary contract data, a list header of 'rules' and a dictionary of leaves for employee
        """
        where_clause = domain or "1=1"

        query = """
                SELECT 
                    COALESCE(SUM(line.total), 0) as total,
                    rule.code as rule_code,
                    rule.name as rule_name,
                    rule.sequence as sequence,
                    slip.id as slip,
                    employee.id as employee_id,
                    employee.registration_number as employee_code,
                    employee.complete_name as employee_name,
                    contract.code as contract_code,
                    contract.daily_salary as daily_salary,
                    employee.ssnid as ssnid,
                    partner.curp as curp,
                    partner.rfc as rfc,
                    dep.code as dep_code,
                    dep.name as dep_name,
                    job.name as job_name,
                    employee.pilot_category as pilot_category,
                    contract.date_end as date_end,
                    period.date_end as report_date,
                    period.name as period_name,
                    period.year as period_year,
                    period.month as period_month,
                    work_days.works as works,
                    work_days.leaves as leaves,
                    work_days.inability as inability,
                    struct.payslip_code as payslip_code,
                    calendar.hours_per_day,
                    CASE
                        WHEN contract.previous_contract_date IS NOT NULL THEN contract.previous_contract_date
                        ELSE contract.date_start
                    END contract_date,
                    CASE
                        WHEN contract.previous_contract_date IS NOT NULL THEN date_part('year',age(period.date_end, contract.previous_contract_date))
                        ELSE date_part('year',age(period.date_end, contract.date_start))
                    END years_antiquity
                FROM hr_payslip_line line
                JOIN hr_payslip slip ON line.slip_id = slip.id
                JOIN hr_contract contract ON slip.contract_id = contract.id
                JOIN hr_salary_rule rule ON line.salary_rule_id = rule.id
                JOIN hr_employee employee ON line.employee_id = employee.id
                JOIN res_partner partner ON employee.address_home_id = partner.id
                JOIN hr_department dep ON employee.department_id = dep.id
                JOIN hr_job job ON employee.job_id = job.id
                JOIN hr_payroll_period period ON period.id = slip.payroll_period_id
                JOIN hr_payroll_structure struct ON slip.struct_id = struct.id   
                JOIN resource_calendar calendar ON contract.resource_calendar_id = calendar.id   
                JOIN (SELECT 
                        days.payslip_id,
                        SUM(CASE
                            WHEN entry.code = 'WORK1101' OR (entry.is_leave IS TRUE AND (entry.type_leave IN ('holidays', 'personal_days'))) 
                            THEN days.number_of_days
                            ELSE 0
                        END) works,
                        SUM(CASE
                            WHEN entry.is_leave IS TRUE AND (entry.code IN ('F04','F06','F10')) THEN days.number_of_days
                            ELSE 0
                        END) leaves,
                        SUM(CASE
                            WHEN entry.is_leave IS TRUE AND (entry.code IN ('F03','F01')) THEN days.number_of_days
                            ELSE 0
                        END) inability
                    FROM hr_payslip_worked_days days
                    JOIN hr_work_entry_type entry ON days.work_entry_type_id = entry.id
                    GROUP BY days.payslip_id
                ) work_days
                ON work_days.payslip_id = slip.id
                WHERE 
                    %s AND slip.state NOT IN ('cancel')
                GROUP BY line.total, employee.id, employee.complete_name, employee.registration_number, 
                        rule.code, rule.name, slip.id, total, contract.code, employee.ssnid, partner.rfc, 
                        partner.curp, contract_date, dep.code, dep.name, job.name, rule.sequence, contract.previous_contract_date, 
                        contract.date_start, period.date_end, contract.daily_salary, contract.date_end, work_days.works, work_days.leaves,
                        work_days.inability, struct.payslip_code, period.name, calendar.hours_per_day, period.month, 
                        period.year, employee.pilot_category
                """
        query = query % where_clause
        self.env.cr.execute(query)
        results = self.env.cr.dictfetchall()
        return results

    def _order_data_report(self, results):
        days_week = {
            '0': 'domingo',
            '1': 'lunes',
            '2': 'martes',
            '3': 'miércoles',
            '4': 'jueves',
            '5': 'viernes',
            '6': 'sábado'
        }
        """
        Examples:
        data : {'CONT-2284':    ---> Contract code
                    {'lines_ids': 
                        {'UI006': [34.8]},
                        {'UI007': [83.5]},      ---> rule amount in the period
                        info of contract...
                    }
                }
        header : [{'name': 'Rule name', 'code': 'UI006', 'sequence': 4, 'total': 0}, ...]  ---> all rules in the period
        """
        data = {}
        header = []
        employees_leaves = {}
        for line in results:
            data.setdefault(line['contract_code'], {'lines_ids': {},
                                                    'periods': [],
                                                    'code': line['employee_code'],
                                                    'name': line['employee_name'],
                                                    'ssnid': line['ssnid'],
                                                    'rfc': line['rfc'],
                                                    'curp': line['curp'],
                                                    'contract_date': fields.Date.from_string(
                                                        line['contract_date']).strftime('%d-%m-%Y'),
                                                    'contract_date2': fields.Date.from_string(
                                                        line['contract_date']).strftime("%d/%m/") + days_week[
                                                                          fields.Date.from_string(
                                                                              line['contract_date']).strftime("%w")],
                                                    'dep_name': line['dep_name'],
                                                    'dep_code': line['dep_code'],
                                                    'job_name': line['job_name'],
                                                    'pilot_category': line['pilot_category'] if line[
                                                        'pilot_category'] else '',
                                                    'years_antiquity': line['years_antiquity'],
                                                    'date_end': fields.Date.from_string(line['date_end']).strftime('%d-%m-%Y') if line['date_end'] else '--',
                                                    'report_date': fields.Date.from_string(
                                                        line['report_date']).strftime('%d-%m-%Y'),
                                                    'report_date2': fields.Date.from_string(line['report_date']),
                                                    'works': 0,
                                                    'leaves': 0,
                                                    'inability': 0,
                                                    'daily_salary': line['daily_salary'],
                                                    'payslip_code': line['payslip_code'],
                                                    'UI002': 0,
                                                    'CS008': 0,
                                                    'UI001': 0,
                                                    })

            if line['period_name'] not in data[line['contract_code']]['periods']:
                data[line['contract_code']]['periods'].append(line['period_name'])
                data[line['contract_code']]['works'] += line['works']
                data[line['contract_code']]['leaves'] += line['leaves']
                data[line['contract_code']]['inability'] += line['inability']

            if line['rule_code']:
                if line['rule_code'] in ['UI001', 'UI002', 'CS008']:
                    if line['rule_code'] == 'UI002' and data[line['contract_code']]['report_date2'] <= line['report_date']:
                        data[line['contract_code']]['UI002'] = line['total']
                        data[line['contract_code']]['report_date2'] = line['report_date']
                    elif line['rule_code'] == 'UI001' and data[line['contract_code']]['report_date2'] <= line['report_date']:
                        data[line['contract_code']]['UI001'] = line['total']
                        data[line['contract_code']]['report_date2'] = line['report_date']
                    elif line['rule_code'] == 'CS008' and data[line['contract_code']]['report_date2'] <= line['report_date']:
                        data[line['contract_code']]['CS008'] = line['total']
                        data[line['contract_code']]['report_date2'] = line['report_date']
                else:
                    data[line['contract_code']]['lines_ids'].setdefault(line['rule_code'], [])
                    data[line['contract_code']]['lines_ids'][line['rule_code']].append(line['total'])

                # order by rules
                rule = {'name': line['rule_name'], 'code': line['rule_code'], 'sequence': line['sequence'], 'total': 0}
                if rule not in header:
                    header.append(rule)

            if line['leaves'] and line['employee_code'] not in employees_leaves:
                employees_leaves[line['employee_code']] = line['hours_per_day']
        return [data, header, employees_leaves]

    def _order_data_sanving_fund(self, results):
        days_week = {
            '0': 'domingo',
            '1': 'lunes',
            '2': 'martes',
            '3': 'miércoles',
            '4': 'jueves',
            '5': 'viernes',
            '6': 'sábado'
        }

        """
        Examples:
        data : {'CONT-2284':    ---> Contract code
                    {'lines_ids': 
                        {'2021 - (2021-10-01 / 2021-10-15) Ordinario':    ---> Period name
                            {'UI006': [34.8]},
                            {'UI007': [83.5]}      ---> rule amount in the period
                        }, 
                        info of contract...
                    }
                }
        periods_rules : {'2021 - (2021-10-01 / 2021-10-15) Ordinario':
                            {'year': 2021,
                            'month': 10,
                            'rules': [{'name': 'Rule name', 'code': 'UI006', 'sequence': 4, 'total': 0}, ...]  ---> all rules in the period
                            }, ...
                        }
        """
        data = {}
        periods_rules = {}
        employees_leaves = {}
        for line in results:
            data.setdefault(line['contract_code'], {'lines_ids': {},
                                                    'code': line['employee_code'],
                                                    'name': line['employee_name'],
                                                    'ssnid': line['ssnid'],
                                                    'rfc': line['rfc'],
                                                    'curp': line['curp'],
                                                    'contract_date': fields.Date.from_string(
                                                        line['contract_date']).strftime('%d-%m-%Y'),
                                                    'contract_date2': fields.Date.from_string(
                                                        line['contract_date']).strftime("%d/%m/") + days_week[
                                                                          fields.Date.from_string(
                                                                              line['contract_date']).strftime("%w")],
                                                    'dep_name': line['dep_name'],
                                                    'dep_code': line['dep_code'],
                                                    'job_name': line['job_name'],
                                                    'pilot_category': line['pilot_category'] if line[
                                                        'pilot_category'] else '',
                                                    'years_antiquity': line['years_antiquity'],
                                                    'date_end': fields.Date.from_string(line['date_end']).strftime('%d-%m-%Y') if line['date_end'] else '--',
                                                    'report_date': fields.Date.from_string(
                                                        line['report_date']).strftime('%d-%m-%Y'),
                                                    'report_date2': fields.Date.from_string(
                                                        line['report_date']).strftime("%d/%m/") + days_week[
                                                                        fields.Date.from_string(
                                                                            line['report_date']).strftime("%w")],
                                                    'works': line['works'],
                                                    'leaves': line['leaves'],
                                                    'inability': line['inability'],
                                                    'daily_salary': line['daily_salary'],
                                                    'payslip_code': line['payslip_code'],
                                                    })
            if line['rule_code']:
                data[line['contract_code']]['lines_ids'].setdefault(line['period_name'], {})
                data[line['contract_code']]['lines_ids'][line['period_name']].setdefault(line['rule_code'], [])
                data[line['contract_code']]['lines_ids'][line['period_name']][line['rule_code']].append(line['total'])

                # Group by periods and by rules
                periods_rules.setdefault(line['period_name'],
                                         {'year': line['period_year'], 'month': line['period_month'], 'rules': []})
                rule = {'name': line['rule_name'], 'code': line['rule_code'], 'sequence': line['sequence'], 'total': 0}
                if rule not in periods_rules[line['period_name']]['rules']:
                    periods_rules[line['period_name']]['rules'].append(rule)

            if line['leaves'] and line['employee_code'] not in employees_leaves:
                employees_leaves[line['employee_code']] = line['hours_per_day']
        return [data, periods_rules, employees_leaves]

    def report_assa_print(self, domain=''):
        is_one_lote = self.env.context.get('one_lote', False)
        if not is_one_lote and len(self) == 1:
            is_one_lote = True
        file_name = _(f'ASSA Report {fields.Datetime.now()}')
        if is_one_lote:
            file_name = f'ASSA Report {self.name} {fields.Datetime.now()}'
            domain = f'slip.payslip_run_id = {self.id}'
        else:
            domain = f'slip.payslip_run_id in {self._ids} '
        domain += 'AND struct.assa_report IS TRUE '
        domain += 'AND rule.union_dues IS TRUE '

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format({'bold':True, 'bg_color':'#100D57', 'font_color':'#FFFFFF', 'border':1, 'top':1, 'font_size':11, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        total_format = workbook.add_format({'bold': True, 'bg_color': '#100D57', 'font_color': '#FFFFFF', 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})
        report_format = workbook.add_format({'border':1, 'font_size':9, 'font_name':'Calibri', 'align':'center'})
        report_format_bold = workbook.add_format({'bold':True, 'border':1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        currency_format = workbook.add_format({'num_format': num_format, 'bold':True, 'border':1, 'top':1, 'font_size':9, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        empty_format = workbook.add_format({'num_format': '0', 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})

        # Write data
        results = self.get_data_assa_and_aspa(domain)
        result = self._order_data_report(results)
        data = result[0]
        if not data:
            raise UserError(_('No data found for the report'))
        header = result[1]
        employees_leaves = result[2]
        first_header = [
            {'sequence': 0.0, 'name': 'Fecha Baja', 'larg': 15, 'col': {}},
            {'sequence': 0.0, 'name': 'No. EMP', 'larg': 15, 'col': {}},
            {'sequence': 0.0, 'name': 'NOMBRE', 'larg': 40, 'col': {}},
            {'sequence': 0.0, 'name': 'SALARIO\nDIARIO', 'larg': 15, 'col': {}},
            {'sequence': 0.1, 'name': 'DEPTO', 'larg': 10, 'col': {}},
            {'sequence': 0.2, 'name': 'PUESTO', 'larg': 40, 'col': {}},
            {'sequence': 0.3, 'name': 'FECHA DE\nINGRESO', 'larg': 15, 'col': {}},
            {'sequence': 0.4, 'name': 'FECHA DE\nREPORTE', 'larg': 40, 'col': {}},
            {'sequence': 0.5, 'name': 'ANTIG.', 'larg': 10, 'col': {}},
            {'sequence': 0.6, 'name': 'NÓMINA', 'larg': 10, 'col': {}},
            {'sequence': 0.7, 'name': 'DÍAS\nTRABAJADOS', 'larg': 15, 'col': {}},
            {'sequence': 0.8, 'name': 'AUSENTISMO', 'larg': 15, 'col': {}},
            {'sequence': 0.9, 'name': 'NETO DÍAS\nTRABAJADOS', 'larg': 15, 'col': {}},
        ]
        abstract_header = {
            "No. Empleados": [],
            "Dias Trabajados": 0,
        }

        periods = self.mapped('payroll_period_id')
        first_date = periods.sorted(lambda x: x.date_start)[0].date_start
        last_date = periods.sorted(lambda x: x.date_end, reverse=True)[0].date_end

        def _write_sheet_header(sheet):
            col = 0
            row = 0
            sheet.set_row(row, 60)

            for head_col in first_header:
                sheet.write(row, col, head_col['name'], header_format)
                sheet.set_column(col, col, head_col['larg'])
                col += 1
            for rule in sorted(header, key=lambda k: k['sequence']):
                sheet.write(row, col, rule['name'].replace(' ', '\n'), header_format)
                sheet.set_column(col, col, 15)
                col += 1

            sheet.write(row, col, 'NÓMINA', header_format)
            sheet.set_column(col, col, 15)
            col += 1

            row += 1
            for contract in data:
                col = 0
                sheet.write(row, col, data[contract]['date_end'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['code'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['name'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['daily_salary'], currency_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('job_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('contract_date', ''), report_format)
                col += 1
                sheet.write(row, col, first_date.strftime('%d/%m/%Y') + ' - ' + last_date.strftime('%d/%m/%Y'), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('years_antiquity', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('payslip_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('works', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('leaves', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('works', 0) - data[contract].get('leaves', 0), report_format)
                col += 1

                # Write lines
                for rule in sorted(header, key=lambda k: k['sequence']):
                    if rule['code'] not in data[contract]['lines_ids']:
                        if rule['code'] == 'UI002':
                            sheet.write(row, col, data[contract].get('UI002', 0), currency_format)
                            rule['total'] += data[contract].get('UI002', 0)
                        elif rule['code'] == 'CS008':
                            sheet.write(row, col, data[contract].get('CS008', 0), currency_format)
                            rule['total'] += data[contract].get('CS008', 0)
                        elif rule['code'] == 'UI001':
                            sheet.write(row, col, data[contract].get('UI001', 0), currency_format)
                            rule['total'] += data[contract].get('UI001', 0)
                        else:
                            sheet.write(row, col, 0.0, currency_format)
                    else:
                        sheet.write(row, col, sum(data[contract]['lines_ids'][rule['code']]), currency_format)
                        rule['total'] += sum(data[contract]['lines_ids'][rule['code']])
                    col += 1

                    abstract_header['No. Empleados'].append(data[contract]['code'])
                    abstract_header['Dias Trabajados'] += data[contract].get('works', 0)

                sheet.write(row, col, data[contract].get('payslip_code', ''), report_format)
                row += 1
            abstract_header['No. Empleados'] = len(abstract_header['No. Empleados'])

        def _write_sheet_abstract(sheet):
            col = 0
            row = 0
            sheet.write(row, col, self.company_id.name, header_format)
            row = 3
            sheet.write(row, col, ','.join(self.mapped('name')), header_format)
            row += 1
            sheet.write(row, col, last_date.strftime('%d-%m-%Y'), header_format)
            row += 1
            for head in abstract_header:
                sheet.write(row, col, head, report_format)
                sheet.write(row, col + 1, abstract_header[head], report_format_bold)
                sheet.set_column(col, col, 30)
                sheet.set_column(col + 1, col + 1, 15)
                row += 1

            # Static construction
            totalize = {
                'Salario Diario': 0,
                'Salario Quincenal': 0,
                'Clausula Sindical': 0,
                'Retiro': 0,
                'Ayuda Sindical': 0,
                'Total Cuotas Sindicales': 0,
                'Evolución Cultural y Deportiva': 0,
                'Cuota Sindical': 0,
                'Seguro Grupo Vida': 0,
                'Caja Ahorro Personal': 0,
                'Sanción Sindical': 0,
                'Fondo de Resistencia ASSA': 0,
                'Apoyo Rotación Aeromar': 0,
                'Prestamos Sindicales': 0,
                'Total Retenciones Sindicales': 0,
            }
            for rule in sorted(header, key=lambda k: k['sequence']):
                if rule['code'] == 'UI002':
                    totalize['Salario Diario'] += rule['total']
                if rule['code'] == 'CS008':
                    totalize['Salario Quincenal'] += rule['total']
                if rule['code'] == 'CS001':
                    totalize['Clausula Sindical'] += rule['total']
                    totalize['Total Cuotas Sindicales'] += rule['total']
                if rule['code'] == 'CS002':
                    totalize['Retiro'] += rule['total']
                    totalize['Total Cuotas Sindicales'] += rule['total']
                if rule['code'] == 'CS003':
                    totalize['Ayuda Sindical'] += rule['total']
                    totalize['Total Cuotas Sindicales'] += rule['total']
                if rule['code'] == 'CS005':
                    totalize['Evolución Cultural y Deportiva'] += rule['total']
                if rule['code'] in ['D036', 'D026']:
                    totalize['Cuota Sindical'] += rule['total']
                    totalize['Total Retenciones Sindicales'] += rule['total']
                if rule['code'] in ['D027', 'D028', 'D029'] or 'SEG. GPO VIDA' in rule['name']:
                    totalize['Seguro Grupo Vida'] += rule['total']
                    totalize['Total Retenciones Sindicales'] += rule['total']
                if rule['code'] == 'D030':
                    totalize['Caja Ahorro Personal'] += rule['total']
                    totalize['Total Retenciones Sindicales'] += rule['total']
                if rule['code'] == 'D031':
                    totalize['Sanción Sindical'] += rule['total']
                    totalize['Total Retenciones Sindicales'] += rule['total']
                if rule['code'] in ['D032', 'D033']:
                    totalize['Fondo de Resistencia ASSA'] += rule['total']
                    totalize['Total Retenciones Sindicales'] += rule['total']
                if rule['code'] == 'D034':
                    totalize['Apoyo Rotación Aeromar'] += rule['total']
                    totalize['Total Retenciones Sindicales'] += rule['total']
                if rule['code'] == 'D035':
                    totalize['Prestamos Sindicales'] += rule['total']
                    totalize['Total Retenciones Sindicales'] += rule['total']
            # Write totalize
            sheet.write(row, col, 'Salario Diario', report_format)
            sheet.write(row, col + 1, totalize['Salario Diario'], currency_format)
            row += 1
            sheet.write(row, col, 'Salario Quincenal', report_format)
            sheet.write(row, col + 1, totalize['Salario Quincenal'], currency_format)
            row += 2
            sheet.write(row, col, 'Clausula Sindical', report_format)
            sheet.write(row, col + 1, totalize['Clausula Sindical'], currency_format)
            row += 1
            sheet.write(row, col, 'Retiro', report_format)
            sheet.write(row, col + 1, totalize['Retiro'], currency_format)
            row += 1
            sheet.write(row, col, 'Ayuda Sindical', report_format)
            sheet.write(row, col + 1, totalize['Ayuda Sindical'], currency_format)
            row += 1
            sheet.write(row, col, 'Total Cuotas Sindicales', report_format_bold)
            sheet.write(row, col + 1, totalize['Total Cuotas Sindicales'], currency_format)
            row += 2
            sheet.write(row, col, 'Evolución Cultural y Deportiva', report_format)
            sheet.write(row, col + 1, totalize['Evolución Cultural y Deportiva'], currency_format)
            row += 2
            sheet.write(row, col, 'Cuota Sindical', report_format)
            sheet.write(row, col + 1, totalize['Cuota Sindical'], currency_format)
            row += 1
            sheet.write(row, col, 'Seguro Grupo Vida', report_format)
            sheet.write(row, col + 1, totalize['Seguro Grupo Vida'], currency_format)
            row += 1
            sheet.write(row, col, 'Caja Ahorro Personal', report_format)
            sheet.write(row, col + 1, totalize['Caja Ahorro Personal'], currency_format)
            row += 1
            sheet.write(row, col, 'Sanción Sindical', report_format)
            sheet.write(row, col + 1, totalize['Sanción Sindical'], currency_format)
            row += 1
            sheet.write(row, col, 'Fondo de Resistencia ASSA', report_format)
            sheet.write(row, col + 1, totalize['Fondo de Resistencia ASSA'], currency_format)
            row += 1
            sheet.write(row, col, 'Apoyo Rotación Aeromar', report_format)
            sheet.write(row, col + 1, totalize['Apoyo Rotación Aeromar'], currency_format)
            row += 1
            sheet.write(row, col, 'Prestamos Sindicales', report_format)
            sheet.write(row, col + 1, totalize['Prestamos Sindicales'], currency_format)
            row += 1
            sheet.write(row, col, 'Total Retenciones Sindicales', report_format_bold)
            sheet.write(row, col + 1, totalize['Total Retenciones Sindicales'], currency_format)
            row += 2
            sheet.write(row, col, 'Total :', report_format_bold)
            sheet.write(row, col + 1, totalize['Total Retenciones Sindicales'] + totalize['Evolución Cultural y Deportiva'] + totalize['Total Cuotas Sindicales'], currency_format)

        info_leaves = self.get_leaves_by_type(employees_leaves.keys(), first_date, last_date, periods)
        leaves = info_leaves[0]
        header_leaves = info_leaves[1]
        def _write_sheet_leaves(sheet):
            row = 0
            for head in sorted(header_leaves, key=lambda k: k['code']):
                col = 0
                sheet.merge_range(row, col, row, col + 5, 'CONCEPTO: ' + head['name'], header_format)
                row += 1
                sheet.write(row, col, 'CLAVE', report_format_bold)
                sheet.set_column(col, col, 15)
                col += 1
                sheet.write(row, col, 'NOMBRE', report_format_bold)
                sheet.set_column(col, col, 40)
                col += 1
                sheet.write(row, col, 'IMPORTE', report_format_bold)
                sheet.set_column(col, col, 15)
                col += 1
                sheet.write(row, col, 'FECHA DESDE', report_format_bold)
                sheet.set_column(col, col, 15)
                col += 1
                sheet.write(row, col, 'FECHA HASTA', report_format_bold)
                sheet.set_column(col, col, 15)
                col += 1
                sheet.write(row, col, 'FOLIO', report_format_bold)
                sheet.set_column(col, col, 20)
                row += 1
                for employee in leaves[head['code']]:
                    col = 0
                    sheet.write(row, col, employee['employee_code'], report_format)
                    col += 1
                    sheet.write(row, col, employee['employee_name'], report_format)
                    col += 1
                    sheet.write(row, col, employee['duration'] / employees_leaves[employee['employee_code']], report_format)
                    col += 1
                    sheet.write(row, col, employee['date_from'], report_format)
                    col += 1
                    sheet.write(row, col, employee['date_to'], report_format)
                    col += 1
                    sheet.write(row, col, employee['folio'], report_format)
                    row += 1
                row += 3

        sheet_header = workbook.add_worksheet("CUOTAS")
        _write_sheet_header(sheet_header)

        sheet_abstract = workbook.add_worksheet("RESUMEN ASSA")
        _write_sheet_abstract(sheet_abstract)

        sheet_leaves = workbook.add_worksheet("AUSENTISMOS")
        _write_sheet_leaves(sheet_leaves)

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

    def report_aspa_print(self, domain=''):
        is_one_lote = self.env.context.get('one_lote', False)
        if not is_one_lote and len(self) == 1:
            is_one_lote = True
        file_name = _(f'ASPA Report {fields.Datetime.now()}')
        if is_one_lote:
            file_name = f'ASPA Report {self.name} {fields.Datetime.now()}'
            domain = f'slip.payslip_run_id = {self.id} '
        else:
            domain = f'slip.payslip_run_id in {self._ids} '
        domain += 'AND struct.aspa_report IS TRUE '
        domain += 'AND rule.union_dues IS TRUE '

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format({'bold':True, 'bg_color':'#100D57', 'font_color':'#FFFFFF', 'border':1, 'top':1, 'font_size':11, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        report_format = workbook.add_format({'border':1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        report_format_bold = workbook.add_format({'bold':True, 'border':1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        currency_format = workbook.add_format({'num_format': num_format, 'bold':True, 'border':1, 'top':1, 'font_size':9, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        empty_format = workbook.add_format({'num_format': '0', 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})

        # Write data
        results = self.get_data_assa_and_aspa(domain)
        result = self._order_data_report(results)
        data = result[0]
        if not data:
            raise UserError(_('No data found for the report'))
        header = result[1]
        employees_leaves = result[2]

        first_header = [
            {'sequence': 0.0, 'name': 'No. EMP', 'larg': 15, 'col': {}},
            {'sequence': 0.0, 'name': 'NOMBRE', 'larg': 40, 'col': {}},
            {'sequence': 0.2, 'name': 'PUESTO', 'larg': 40, 'col': {}},
            {'sequence': 0.3, 'name': 'DEPTO.', 'larg': 10, 'col': {}},
            {'sequence': 0.4, 'name': 'NOMBRE DEL \nDEPARTAMENTO', 'larg': 40, 'col': {}},
            {'sequence': 0.5, 'name': 'FECHA INGRESO', 'larg': 15, 'col': {}},
            {'sequence': 0.5, 'name': ' ', 'larg': 15, 'col': {}},
            {'sequence': 0.6, 'name': 'FECHA REPORTE', 'larg': 40, 'col': {}},
            {'sequence': 0.7, 'name': 'AÑOS ANTIG', 'larg': 15, 'col': {}},
            {'sequence': 0.8, 'name': 'DIAS\nTRABAJADOS', 'larg': 15, 'col': {}},
            {'sequence': 0.9, 'name': 'AUSENTISMO', 'larg': 15, 'col': {}},
            {'sequence': 1.0, 'name': 'NETO DÍAS\nTRABAJADOS', 'larg': 15, 'col': {}},
        ]
        abstract_header = {
            "No. Empleados": [],
            "Dias Trabajados": 0,
        }

        periods = self.mapped('payroll_period_id')
        first_date = periods.sorted(lambda x: x.date_start)[0].date_start
        last_date = periods.sorted(lambda x: x.date_end, reverse=True)[0].date_end

        def _write_sheet_header(sheet):
            col = 0
            row = 0
            sheet.set_row(row, 60)

            for head_col in first_header:
                sheet.write(row, col, head_col['name'], header_format)
                sheet.set_column(col, col, head_col['larg'])
                col += 1
            for rule in sorted(header, key=lambda k: k['sequence']):
                sheet.write(row, col, rule['name'].replace(' ', '\n'), header_format)
                sheet.set_column(col, col, 15)
                col += 1
            sheet.write(row, col, 'Fecha de Baja', header_format)
            sheet.set_column(col, col, 15)

            row += 1
            job_count = 0
            job_count_all = 0
            job_verification = False
            job_rules = {}
            for contract in sorted(data, key=lambda k: data[k]['job_name']):
                job = data[contract].get('job_name', '')
                if job_verification and job_verification != job:
                    row += 1
                    col = 0
                    sheet.write(row, col, job_count, report_format_bold)
                    col += 1
                    sheet.merge_range(row, col, row, col + 2, 'Total ' + job_verification, report_format_bold)
                    col += 11
                    for rule in sorted(header, key=lambda k: k['sequence']):
                        sheet.write(row, col, job_rules[rule['code']], currency_format)
                        job_rules[rule['code']] = 0
                        col += 1
                    row += 3

                    job_count_all += job_count
                    job_count = 0
                job_count += 1
                job_verification = data[contract].get('job_name', '')
                col = 0
                sheet.write(row, col, data[contract]['code'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['name'], report_format)
                col += 1
                sheet.write(row, col, data[contract].get('job_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('contract_date', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('contract_date2', ''), report_format)
                col += 1
                sheet.write(row, col, first_date.strftime('%d/%m/%Y') + ' - ' + last_date.strftime('%d/%m/%Y'), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('years_antiquity', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('works', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('leaves', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('works', 0) - data[contract].get('leaves', 0), report_format)
                col += 1

                # Write lines
                for rule in sorted(header, key=lambda k: k['sequence']):
                    job_rules.setdefault(rule['code'], 0)
                    if rule['code'] not in data[contract]['lines_ids']:
                        if rule['code'] == 'UI002':
                            sheet.write(row, col, data[contract].get('UI002', 0), currency_format)
                            rule['total'] += data[contract].get('UI002', 0)
                            job_rules['UI002'] += data[contract].get('UI002', 0)
                        elif rule['code'] == 'CS008':
                            sheet.write(row, col, data[contract].get('CS008', 0), currency_format)
                            rule['total'] += data[contract].get('CS008', 0)
                            job_rules['CS008'] += data[contract].get('CS008', 0)
                        elif rule['code'] == 'UI001':
                            sheet.write(row, col, data[contract].get('UI001', 0), currency_format)
                            rule['total'] += data[contract].get('UI001', 0)
                            job_rules['UI001'] += data[contract].get('UI001', 0)
                        else:
                            sheet.write(row, col, 0.0, currency_format)
                    else:
                        sheet.write(row, col, sum(data[contract]['lines_ids'][rule['code']]), currency_format)
                        rule['total'] += sum(data[contract]['lines_ids'][rule['code']])
                        job_rules[rule['code']] += sum(data[contract]['lines_ids'][rule['code']])
                    col += 1

                abstract_header['No. Empleados'].append(data[contract]['code'])
                abstract_header['Dias Trabajados'] += data[contract].get('works', 0)

                sheet.write(row, col, data[contract]['date_end'], report_format)
                col += 1
                row += 1
            abstract_header['No. Empleados'] = len(abstract_header['No. Empleados'])

            # total
            row += 1
            col = 0
            sheet.write(row, col, job_count, report_format_bold)
            col += 1
            sheet.merge_range(row, col, row, col + 2, 'Total ' + job_verification, report_format_bold)
            col += 11
            for rule in sorted(header, key=lambda k: k['sequence']):
                sheet.write(row, col, job_rules[rule['code']], currency_format)
                job_rules[rule['code']] = 0
                col += 1
            job_count_all += job_count
            row += 3
            # Total all
            col = 0
            sheet.write(row, col, job_count_all, report_format_bold)
            col += 1
            sheet.merge_range(row, col, row, col + 2, 'Totales', report_format_bold)
            col += 11
            for rule in sorted(header, key=lambda k: k['sequence']):
                sheet.write(row, col, rule['total'], currency_format)
                col += 1

        def _write_sheet_abstract(sheet):
            col = 0
            row = 3
            sheet.write(row, col, ','.join(self.mapped('name')), header_format)
            row += 1
            sheet.write(row, col, last_date.strftime('%d-%m-%Y'), header_format)
            row += 1
            for head in abstract_header:
                sheet.write(row, col, head, report_format)
                sheet.write(row, col + 1, abstract_header[head], report_format_bold)
                sheet.set_column(col, col, 30)
                sheet.set_column(col + 1, col + 1, 15)
                row += 1
            # TODO: modify in consolidate
            for head in sorted(header, key=lambda k: k['sequence']):
                sheet.write(row, col, head['name'], report_format)
                sheet.write(row, col + 1, head['total'], currency_format)
                row += 1

        info_leaves = self.get_leaves_by_type(employees_leaves.keys(), first_date, last_date, periods)
        leaves = info_leaves[0]
        header_leaves = info_leaves[1]

        def _write_sheet_leaves(sheet):
            row = 0
            for head in sorted(header_leaves, key=lambda k: k['code']):
                col = 0
                sheet.merge_range(row, col, row, col + 5, 'CONCEPTO: ' + head['name'], header_format)
                row += 1
                sheet.write(row, col, 'CLAVE', report_format_bold)
                sheet.set_column(col, col, 15)
                col += 1
                sheet.write(row, col, 'NOMBRE', report_format_bold)
                sheet.set_column(col, col, 40)
                col += 1
                sheet.write(row, col, 'IMPORTE', report_format_bold)
                sheet.set_column(col, col, 15)
                col += 1
                sheet.write(row, col, 'FECHA DESDE', report_format_bold)
                sheet.set_column(col, col, 15)
                col += 1
                sheet.write(row, col, 'FECHA HASTA', report_format_bold)
                sheet.set_column(col, col, 15)
                col += 1
                sheet.write(row, col, 'FOLIO', report_format_bold)
                sheet.set_column(col, col, 20)
                row += 1
                for employee in leaves[head['code']]:
                    col = 0
                    sheet.write(row, col, employee['employee_code'], report_format)
                    col += 1
                    sheet.write(row, col, employee['employee_name'], report_format)
                    col += 1
                    sheet.write(row, col, employee['duration'] / employees_leaves[employee['employee_code']], report_format)
                    col += 1
                    sheet.write(row, col, employee['date_from'], report_format)
                    col += 1
                    sheet.write(row, col, employee['date_to'], report_format)
                    col += 1
                    sheet.write(row, col, employee['folio'], report_format)
                    row += 1
                row += 3

        sheet_header = workbook.add_worksheet("CUOTAS")
        _write_sheet_header(sheet_header)

        sheet_abstract = workbook.add_worksheet("RESUMEN ASPA")
        _write_sheet_abstract(sheet_abstract)

        sheet_leaves = workbook.add_worksheet("AUSENTISMOS")
        _write_sheet_leaves(sheet_leaves)

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

    def report_social_objective_print(self, domain=''):
        is_one_lote = self.env.context.get('one_lote', False)
        if not is_one_lote and len(self) == 1:
            is_one_lote = True
        file_name = _('Social Objective Report %s') % fields.Datetime.now()
        if is_one_lote:
            file_name = 'Social Objective %s %s' % (self.name, fields.Datetime.now())
            domain = 'slip.payslip_run_id = %s' % self.id
        else:
            domain = f'slip.payslip_run_id in {self._ids} '
        domain += 'AND struct.social_objective IS TRUE '
        domain += 'AND rule.social_objective IS TRUE '

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format({'bold':True, 'bg_color':'#100D57', 'font_color':'#FFFFFF', 'border':1, 'top':1, 'font_size':11, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        report_format = workbook.add_format({'border':1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        report_format_bold = workbook.add_format({'bold':True, 'border':1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        currency_format = workbook.add_format({'num_format': num_format, 'bold':True, 'border':1, 'top':1, 'font_size':9, 'align':'center', 'valign':'vcenter', 'font_name':'Calibri'})
        empty_format = workbook.add_format({'num_format': '0', 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})

        # Write data
        results = self.get_data_assa_and_aspa(domain)
        result = self._order_data_report(results)
        data = result[0]
        if not data:
            raise UserError(_('No data found for the report'))
        header = result[1]

        first_header = [
            {'sequence': 0.0, 'name': 'No. EMP', 'larg': 15, 'col': {}},
            {'sequence': 0.0, 'name': 'NOMBRE', 'larg': 40, 'col': {}},
            {'sequence': 0.2, 'name': 'PUESTO', 'larg': 40, 'col': {}},
            {'sequence': 0.5, 'name': 'FECHA INGRESO', 'larg': 20, 'col': {}},
            {'sequence': 0.6, 'name': 'FECHA REPORTE', 'larg': 20, 'col': {}},
            {'sequence': 0.7, 'name': 'AÑOS ANTIG', 'larg': 20, 'col': {}},
        ]

        periods = self.mapped('payroll_period_id')
        first_date = periods.sorted(lambda x: x.date_start)[0].date_start
        last_date = periods.sorted(lambda x: x.date_end, reverse=True)[0].date_end

        def _write_sheet_header(sheet):
            col = 0
            row = 0
            sheet.set_row(row, 60)

            for head_col in first_header:
                sheet.write(row, col, head_col['name'], header_format)
                sheet.set_column(col, col, head_col['larg'])
                col += 1
            for rule in sorted(header, key=lambda k: k['sequence']):
                sheet.write(row, col, rule['name'].replace(' ', '\n'), header_format)
                sheet.set_column(col, col, 15)
                col += 1
            sheet.write(row, col, 'Fecha de Baja', header_format)
            sheet.set_column(col, col, 15)

            row += 1
            job_count = 0
            job_count_all = 0
            job_verification = False
            job_rules = {}
            for contract in sorted(data, key=lambda k: data[k]['pilot_category'], reverse=True):
                category_get = data[contract].get('pilot_category', '') or 'otros'
                if job_verification and job_verification != category_get:

                    row += 2
                    col = 0
                    sheet.write(row, col, job_count, report_format_bold)
                    col += 1
                    if job_verification == 'captains':
                        pilot = 'Capitanes'
                    elif job_verification == 'official':
                        pilot = 'Primer Oficial'
                    elif job_verification == 'otros':
                        pilot = 'Otros'
                    sheet.merge_range(row, col, row, col + 2, 'Total ' + pilot, report_format_bold)
                    col += 5
                    for rule in sorted(header, key=lambda k: k['sequence']):
                        sheet.write(row, col, job_rules[rule['code']], currency_format)
                        job_rules[rule['code']] = 0
                        col += 1
                    row += 3

                    job_count_all += job_count
                    job_count = 0
                job_count += 1
                job_verification = data[contract].get('pilot_category', '') or 'otros'
                col = 0
                sheet.write(row, col, data[contract]['code'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['name'], report_format)
                col += 1
                sheet.write(row, col, data[contract].get('job_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('contract_date', ''), report_format)
                col += 1
                sheet.write(row, col, first_date.strftime('%d/%m/%Y') + ' - ' + last_date.strftime('%d/%m/%Y'), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('years_antiquity', ''), report_format)
                col += 1

                # Write lines
                for rule in sorted(header, key=lambda k: k['sequence']):
                    job_rules.setdefault(rule['code'], 0)
                    if rule['code'] not in data[contract]['lines_ids']:
                        if rule['code'] == 'UI002':
                            sheet.write(row, col, data[contract].get('UI002', 0), currency_format)
                            rule['total'] += data[contract].get('UI002', 0)
                            job_rules['UI002'] += data[contract].get('UI002', 0)
                        elif rule['code'] == 'CS008':
                            sheet.write(row, col, data[contract].get('CS008', 0), currency_format)
                            rule['total'] += data[contract].get('CS008', 0)
                            job_rules['CS008'] += data[contract].get('CS008', 0)
                        elif rule['code'] == 'UI001':
                            sheet.write(row, col, data[contract].get('UI001', 0), currency_format)
                            rule['total'] += data[contract].get('UI001', 0)
                            job_rules['UI001'] += data[contract].get('UI001', 0)
                        else:
                            sheet.write(row, col, 0.0, currency_format)
                    else:
                        sheet.write(row, col, sum(data[contract]['lines_ids'][rule['code']]), currency_format)
                        rule['total'] += sum(data[contract]['lines_ids'][rule['code']])
                        job_rules[rule['code']] += sum(data[contract]['lines_ids'][rule['code']])
                    col += 1
                sheet.write(row, col, data[contract]['date_end'], report_format)
                col += 1
                row += 1

            # total
            row += 1
            col = 0
            sheet.write(row, col, job_count, report_format_bold)
            col += 1
            if job_verification == 'captains':
                pilot = 'Capitanes'
            elif job_verification == 'official':
                pilot = 'Primer Oficial'
            elif job_verification == 'otros':
                pilot = 'Otros'
            sheet.merge_range(row, col, row, col + 2, 'Total ' + pilot, report_format_bold)
            col += 5
            for rule in sorted(header, key=lambda k: k['sequence']):
                sheet.write(row, col, job_rules[rule['code']], currency_format)
                job_rules[rule['code']] = 0
                col += 1
            job_count_all += job_count
            row += 3
            # Total all
            col = 0
            sheet.write(row, col, job_count_all, report_format_bold)
            col += 1
            sheet.merge_range(row, col, row, col + 2, 'Total Jefatura de Pilotos', report_format_bold)
            col += 5
            for rule in sorted(header, key=lambda k: k['sequence']):
                sheet.write(row, col, rule['total'], currency_format)
                col += 1
        sheet_header = workbook.add_worksheet("CUOTAS")
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

    def report_saving_fund(self, domain=''):
        is_one_lote = self.env.context.get('one_lote', False)
        file_name = _('Saving Fund Report %s') % fields.Datetime.now()
        periods = self.env.context.get('periods', self.env['hr.payroll.period'])
        if is_one_lote:
            file_name = 'Saving Fund %s %s' % (self.name, fields.Datetime.now())
            domain = ' slip.payslip_run_id = %s' % self.id
            periods = self.payroll_period_id
        domain += ' AND rule.saving_fund IS TRUE '

        string_periods = ''
        for period in periods:
            string_periods += '%s - %s / ' % (period.date_start, period.date_end)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format(
            {'bold': True, 'bg_color': '#100D57', 'font_color': '#FFFFFF', 'border': 1, 'top': 1, 'font_size': 11,
             'align': 'center', 'valign': 'vcenter', 'font_name': 'Calibri'})
        report_format = workbook.add_format({'border': 1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        report_format2 = workbook.add_format({'border':0, 'bold':True, 'font_size':12, 'font_name':'Calibri', 'align':'left'})
        report_format_bold = workbook.add_format(
            {'bold': True, 'border': 1, 'font_size': 9, 'font_name': 'Calibri', 'align': 'center'})
        currency_format = workbook.add_format(
            {'num_format': num_format, 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center',
             'valign': 'vcenter', 'font_name': 'Calibri'})
        empty_format = workbook.add_format(
            {'num_format': '0', 'bold': True, 'border': 1, 'top': 1, 'font_size': 9, 'align': 'center',
             'valign': 'vcenter', 'font_name': 'Calibri'})

        # Write data
        results = self.get_data_assa_and_aspa(domain)
        result = self._order_data_sanving_fund(results)
        data = result[0]
        if not data:
            raise UserError(_('No data found for the report'))
        header = result[1]
        payslip_codes = result[2]
        payslips_type = ''
        for code in payslip_codes:
            payslips_type += '%s. ' % code if code else ''

        first_header = [
            {'sequence': 0.0, 'name': 'No. EMP', 'larg': 15, 'col': {}},
            {'sequence': 0.1, 'name': 'NOMBRE', 'larg': 40, 'col': {}},
            {'sequence': 0.2, 'name': 'DEPTO', 'larg': 10, 'col': {}},
            {'sequence': 0.3, 'name': 'PUESTO', 'larg': 40, 'col': {}},
            {'sequence': 0.4, 'name': 'NÓMINA', 'larg': 10, 'col': {}},
            {'sequence': 0.5, 'name': 'SALARIO\nDIARIO', 'larg': 15, 'col': {}},
            {'sequence': 0.6, 'name': 'FECHA DE\nINGRESO', 'larg': 15, 'col': {}},
            {'sequence': 0.7, 'name': 'FECHA BAJA', 'larg': 15, 'col': {}},
            {'sequence': 0.8, 'name': 'FECHA DE\nREPORTE', 'larg': 15, 'col': {}},
            {'sequence': 0.9, 'name': 'ANTIG.', 'larg': 10, 'col': {}},
            {'sequence': 1.0, 'name': 'DÍAS\nTRABAJADOS', 'larg': 15, 'col': {}},
            {'sequence': 1.1, 'name': 'FALTAS', 'larg': 15, 'col': {}},
            {'sequence': 1.2, 'name': 'INCAPACIDADES', 'larg': 15, 'col': {}},
            {'sequence': 1.3, 'name': 'AUSENTISMO', 'larg': 15, 'col': {}},
            {'sequence': 1.4, 'name': 'NETO DÍAS\nTRABAJADOS', 'larg': 15, 'col': {}},
        ]
        def _write_sheet_header(sheet):
            col = 0
            row = 0

            sheet.merge_range(row, 0, row, 9, 'REPORTE DE FONDO DE AHORRO', report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 9, 'Tipo de Nómina: ' + payslips_type, report_format2)
            row += 1
            sheet.merge_range(row, 0, row, 9, 'Periodo(s): ' + string_periods, report_format2)
            row += 2

            sheet.set_row(row, 60)

            for head_col in first_header:
                sheet.write(row, col, head_col['name'], header_format)
                sheet.set_column(col, col, head_col['larg'])
                col += 1
            for period in header:
                sheet.merge_range(row, col, row, col + len(header[period]['rules']), period, header_format)
                sheet.set_row(row + 1, 40)
                for rule in sorted(header[period]['rules'], key=lambda k: k['sequence']):
                    sheet.write(row + 1, col, rule['name'].replace(' ', '\n'), header_format)
                    sheet.set_column(col, col, 15)
                    col += 1
                sheet.write(row + 1, col, 'TOTAL', header_format)
                sheet.set_column(col, col, 15)
                col += 1
            sheet.write(row, col, 'TOTAL', header_format)
            sheet.set_column(col, col, 15)
            row += 2
            for contract in data:
                col = 0
                sheet.write(row, col, data[contract]['code'], report_format)
                col += 1
                sheet.write(row, col, data[contract]['name'], report_format)
                col += 1
                sheet.write(row, col, data[contract].get('dep_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('job_name', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('payslip_code', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract]['daily_salary'], currency_format)
                col += 1
                sheet.write(row, col, data[contract].get('contract_date', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract]['date_end'], report_format)
                col += 1
                sheet.write(row, col, data[contract].get('report_date', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('years_antiquity', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('works', ''), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('leaves', 0), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('inability', 0), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('leaves', 0) + data[contract].get('inability', 0), report_format)
                col += 1
                sheet.write(row, col, data[contract].get('works', 0) - data[contract].get('leaves', 0) - data[contract].get('inability', 0), report_format)
                col += 1

                # # Write lines
                total_all = 0
                for period in header:
                    total_period = 0
                    for rule in sorted(header[period]['rules'], key=lambda k: k['sequence']):
                        if period not in data[contract]['lines_ids'] or rule['code'] not in data[contract]['lines_ids'][period]:
                            sheet.write(row, col, 0.0, currency_format)
                        else:
                            sheet.write(row, col, sum(data[contract]['lines_ids'][period][rule['code']]), currency_format)
                            total_period += sum(data[contract]['lines_ids'][period][rule['code']])
                            rule['total'] += sum(data[contract]['lines_ids'][period][rule['code']])
                        col += 1
                    sheet.write(row, col, total_period, currency_format)
                    total_all += total_period
                    col += 1
                sheet.write(row, col, total_all, currency_format)
                row += 1

            # Total all
            col = 15
            totals = 0
            for period in header:
                period_total = 0
                for rule in sorted(header[period]['rules'], key=lambda k: k['sequence']):
                    sheet.write(row, col, rule['total'], currency_format)
                    period_total += rule['total']
                    col += 1
                totals += period_total
                sheet.write(row, col, period_total, currency_format)
                col += 1
            sheet.write(row, col, totals, currency_format)

        sheet_header = workbook.add_worksheet("FONDO DE AHORRO")
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

    ##################################
    # TXT Reports
    ##################################

    @api.model
    def get_export_mime_type(self, file_type):
        """ Returns the MIME type associated with a report export file type,
        for attachment generation.
        """
        type_mapping = {
            'xlsx': 'application/vnd.ms-excel',
            'pdf': 'application/pdf',
            'xml': 'application/vnd.sun.xml.writer',
            'xaf': 'application/vnd.sun.xml.writer',
            'txt': 'text/plain',
            'csv': 'text/csv',
            'zip': 'application/zip',
        }
        return type_mapping.get(file_type, False)

    def get_aspa_txt(self):
        empty = '0000000.00'

        domain = 'slip.payslip_run_id = %s' % self.id
        domain += 'AND struct.aspa_report IS TRUE'

        results = self.get_data_assa_and_aspa(domain)
        query_data = self._order_data_report(results)
        data_txt = query_data[0]

        lines = ''
        for contract in data_txt:
            data = [''] * 8
            col = 0
            data[col] = data_txt[contract]['code'].zfill(7) if data_txt[contract]['code'] else '0'.zfill(7)
            col += 1
            data[col] = data_txt[contract]['name'][:20].ljust(20) if data_txt[contract]['name'] else ' '.ljust(20)
            col += 1
            # Rules
            UI109 = 0
            if 'UI109' in data_txt[contract]['lines_ids']:
                UI109 += sum(data_txt[contract]['lines_ids']['UI109'])
            data[col] = "{0:.2f}".format(UI109).zfill(10) if UI109 else empty
            col += 1
            CS001 = 0
            if 'CS001' in data_txt[contract]['lines_ids']:
                CS001 += sum(data_txt[contract]['lines_ids']['CS001'])
            data[col] = "{0:.2f}".format(CS001).zfill(10) if CS001 else empty
            col += 1
            CS002 = 0
            if 'CS002' in data_txt[contract]['lines_ids']:
                CS002 += sum(data_txt[contract]['lines_ids']['CS002'])
            data[col] = "{0:.2f}".format(CS002).zfill(10) if CS001 else empty
            col += 1
            data[col] = empty
            col += 1
            data[col] = empty
            col += 1
            date = datetime.strptime(data_txt[contract]['contract_date'], "%d-%m-%Y")
            data[col] = date.strftime("%d%m%y")
            lines += ''.join(str(d) for d in data) + '\n'

        return lines

    ##################################
    # End TXT Report
    ##################################
