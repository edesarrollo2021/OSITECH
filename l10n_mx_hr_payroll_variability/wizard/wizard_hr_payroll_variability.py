# -*- coding: utf-8 -*-
import io
import base64
import pytz
import calendar
import logging

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from xlsxwriter.utility import xl_rowcol_to_cell

from odoo.addons.l10n_mx_hr_payroll_variability.models.hr_payroll_variability import _get_selection_year, bismester_list
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.date_utils import end_of
from odoo.tools.misc import xlsxwriter

_logger = logging.getLogger(__name__)


class WizardPayslipVariabilityLine(models.TransientModel):
    _name = 'wizard.payslip.variability.line'
    _description = 'Payroll Variability Line'

    wizard_id = fields.Many2one(comodel_name='wizard.payslip.variability', string='Form')
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
        ('3', 'Sin Modificación'),
        ('4', 'Incapacitado')
    ], string="Type Move")


class WizardPayslipVariability(models.TransientModel):
    _name = 'wizard.payslip.variability'
    _description = 'Payroll Variability'

    def _default_values(self):
        year = str(date.today().year)
        bimestre = self.validate_bimestre()
        if bimestre == '1':
            year = str(int(date.today().year) - 1)
        prev_bimester_dic = {
            '1': '6',
            '2': '1',
            '3': '2',
            '4': '3',
            '5': '4',
            '6': '5',
        }
        prev_bimester = prev_bimester_dic[bimestre]
        return (year, prev_bimester)

    def _default_year(self):
        return self._default_values()[0]

    def _default_bimester(self):
        return self._default_values()[1]

    structure_ids = fields.Many2many(
        'hr.payroll.structure', string='Structure', required=True
    )
    year = fields.Selection(_get_selection_year, string='Year', required=True, default=_default_year)
    bimestre = fields.Selection(bismester_list, string='Bimester', required=True, default=_default_bimester)
    date_from = fields.Date(string="From",
        default=lambda self: fields.Date.today())
    date_to = fields.Date(string="To",
        default=lambda self: end_of(fields.Date.today(),'month'))
    computed = fields.Boolean(string="Computed")
    compute_lines = fields.One2many(
        comodel_name='wizard.payslip.variability.line',
        inverse_name='wizard_id', string='Lines')
    date = fields.Date(string="Date Move", readonly=True)

    def validate_bimestre(self):
        bimester_dic = {
            '1': '1',
            '2': '1',
            '3': '2',
            '4': '2',
            '5': '3',
            '6': '3',
            '7': '4',
            '8': '4',
            '9': '5',
            '10': '5',
            '11': '6',
            '12': '6',
        }
        month = str(fields.Date.today().month)
        year = str(fields.Date.today().year)
        bimester = bimester_dic[month]
        if year == self.year and int(self.bimestre) >= int(bimester):
            raise UserError(_("You can only calculate variables, for a previous two-month period."))
        return bimester

    @api.model
    def _get_query_payslip_line(self, domain=None):
        where_clause = domain or "1=1"
        select = """
                SELECT
                    COALESCE(SUM(line.total), 0) as total,
                    rule.id as rule_id,
                    rule.code as rule_code,
                    rule.name as rule_name,
                    rule.sequence as sequence,
                    rule.code ||'--'|| rule.type_perception AS type_perception, 
                    employee.id as employee_id,
                    employee.registration_number as employee_code,
                    employee.name as employee_name,
                    employee.last_name as last_name,
                    employee.mothers_last_name as mothers_last_name,
                    struct.name as struct_name,
                    struct.payslip_code as payslip_code,
                    employee.registration_number as employee_code,
                    employee.ssnid as ssnid,
                    employee.salary_type as salary_type,
                    employee.antiquity_id as antiquity_id,
                    partner.curp as curp,
                    partner.l10n_mx_edi_curp as l10n_mx_edi_curp,
                    partner.rfc as rfc,
                    dep.code as dep_code,
                    dep.name as dep_name,
                    job.name as job_name,
                    contract.id as contract_id,
                    contract.integral_salary as integral_salary,
                    contract.daily_salary as daily_salary,
                    contract.sdi as sdi,
                    contract.sbc as sbc,
                    contract.date_start as contract_date_start,
                    slip.id AS slip_id, 
                    CASE
                        WHEN contract.previous_contract_date IS NOT NULL THEN contract.previous_contract_date
                        ELSE contract.date_start
                    END contract_date
                FROM hr_payslip_line line
                JOIN hr_payslip slip ON line.slip_id = slip.id
                JOIN hr_salary_rule rule ON line.salary_rule_id = rule.id
                JOIN hr_contract contract ON line.contract_id = contract.id
                JOIN hr_employee employee ON line.employee_id = employee.id
                JOIN hr_department dep ON contract.department_id = dep.id
                JOIN hr_job job ON contract.job_id = job.id
                JOIN res_partner partner ON employee.address_home_id = partner.id
                JOIN hr_payroll_structure struct ON slip.struct_id = struct.id   
                WHERE %s
                    AND line.total > 0
                    AND rule.apply_variable_compute
                    AND rule.type = 'perception'
                    AND contract.state = 'open'
                    AND slip.payroll_type = 'O'
                    AND slip.state = 'done'
                    -- AND contract.id = 3050
                GROUP BY slip.id, rule.id, contract.id, employee.id, dep.id, job.id, partner.id, struct.id
                ORDER BY slip.id DESC, rule.sequence;
            """
        # # 2.Fetch data from DB
        select = select % (where_clause)
        self.env.cr.execute(select)
        results = self.env.cr.dictfetchall()
        if not results:
            raise UserError(_("Data Not Found"))
        return results

    def _get_leaves(self, payslips=None):
        query = """
            SELECT 
                employee.id employee_id,
                entry.id entry_id,
                COALESCE(SUM(work.number_of_days),0) number_of_days,
                entry.type_leave,
                entry.name ||'-'|| entry.code as name
            FROM hr_payslip_worked_days work
            JOIN hr_payslip slip ON work.payslip_id = slip.id
            JOIN hr_employee employee ON slip.employee_id = employee.id 
            JOIN hr_work_entry_type entry ON work.work_entry_type_id = entry.id
            WHERE 
                entry.type_leave IN ('leave', 'holidays', 'inability')
                AND work.payslip_id in %s
            GROUP BY entry.id, employee.id
        """
        params = (payslips,)
        self.env.cr.execute(query, params)
        results = self.env.cr.dictfetchall()
        leaves = {}
        header = {}
        for res in results:
            header.setdefault(res['entry_id'], res['name'])
            leaves.setdefault(res['employee_id'], {}).setdefault('rules', {}).setdefault(res['entry_id'], []).append(res['number_of_days'])
            leaves.setdefault(res['employee_id'], {}).setdefault('leaves', {}).setdefault(res['type_leave'], []).append(res['number_of_days'])
        result = {
            'header': header,
            'leaves': leaves
        }
        return result

    def _get_lines(self):
        year = int(self.year)
        bimestre = int(self.bimestre)
        months = [(bimestre * 2), ((bimestre * 2) - 1)]
        months2 = [str((bimestre * 2)), str(((bimestre * 2) - 1))]
        date_start = date(year, months[1], 1)
        last_day = calendar.monthrange(year, months[0])[1]
        date_end = date(year, months[0], last_day) + timedelta(days=1)
        self.date = date_end
        days_bimestre = (date_end - date_start).days
        self.validate_bimestre()
        extra_fields = {
            'year': year,
            'bimestre': bimestre,
            'months2': months2,
            'date_start': date_start,
            'date_end': date_end,
            'days_bimestre': days_bimestre,
        }
        if len(self.structure_ids) == 1:
            clause1 = 'slip.struct_id = %s' % str(self.structure_ids.id)
        if len(self.structure_ids) > 1:
            clause1 = 'slip.struct_id IN %s' % str(tuple(self.structure_ids.ids))
        contract_processed = self.env['hr.payslip.variability'].search([('year', '=', self.year), ('bimestre', '=', self.bimestre)]).mapped('contract_id')._ids
        clause2 = ''
        if contract_processed:
            process = len(contract_processed)
            if process == 1:
                clause2 = " AND slip.contract_id <> %s" % str(contract_processed[0])
            else:
                clause2 = " AND slip.contract_id NOT IN %s" % str(tuple(contract_processed))

        where = clause1 + clause2 + ' AND slip.payroll_month IN %s AND slip.year = %s' % (tuple(months2), year)
        _logger.info('CALL _get_query_payslip_line')
        lines = self._get_query_payslip_line(domain=where)
        _logger.info('END _get_query_payslip_line')
        payslips = {}
        employees = {}
        header = {}
        for line in lines:
            header.setdefault(line['rule_code'], {'name': line['rule_name'], 'sequence': line['sequence']})
            employees.setdefault(line['employee_id'], {'perceptions': {}, 'payslip': {}})
            # employees[line['employee_id']]['rules'].setdefault(line['rule_code'], []).append(line['total'])
            employees[line['employee_id']]['perceptions'].setdefault(line['type_perception'], []).append(line['total'])
            employees[line['employee_id']]['payslip'].setdefault(line['slip_id'], 0)
            payslips.setdefault(line['slip_id'], 0)
            employees.setdefault(line['employee_id'], {}).setdefault('data', {
                'code': line['employee_code'],
                'last_name': line['last_name'],
                'mothers_last_name': line['mothers_last_name'],
                'name': line['employee_name'],
                'ssnid': line['ssnid'],
                'rfc': line['rfc'],
                'curp': line.get('curp', False) or line.get('l10n_mx_edi_curp', ''),
                'salary_type': line['salary_type'],
                'antiquity_id': line['antiquity_id'],
                'struct_name': '%s-%s' % (line['payslip_code'], line['struct_name']),
                'contract_id': line['contract_id'],
                'contract_start_str': fields.Date.from_string(line['contract_date_start']).strftime('%d-%m-%Y'),
                'contract_start': line['contract_date_start'],
                'daily_salary': line['daily_salary'],
                'contract_date': fields.Date.from_string(line['contract_date']).strftime('%d-%m-%Y'),
                'dep_code': line['dep_code'],
                'dep_name': line['dep_name'],
                'job_name': line['job_name'],
                'integral_salary': line['integral_salary'],
                'sdi': line['sdi'],
                'sbc': line['sbc'] or 0,
            })
        payslips = tuple(payslips.keys())
        _logger.info('CALL _get_leaves')
        leaves = self._get_leaves(payslips=payslips)
        _logger.info('END _get_leaves')
        data = {
            'header': header,
            'employees': employees,
            'leaves': leaves,
            'extra_fields': extra_fields,
        }
        return data

    def _get_perception(self, perceptions, days_worked, sbc, employee=None):
        vals = {}
        new_vals = {}
        smvdf = self.env.company.smvdf
        uma = self.env.company.uma
        for percept in perceptions:
            rule_code, key = percept.split('--')
            if key == '029':
                exent_amount = round((uma * 0.40) * days_worked, 2)
                total = sum(perceptions[percept])
                restante = round(total - exent_amount, 2)
                new_vals.setdefault(rule_code, {'exempt': exent_amount, 'tax': restante if restante > 0 else 0.0, 'total': total})
                if restante > 0:
                    vals[rule_code] = restante
            else:
                total = sum(perceptions[percept])
                vals[rule_code] = total
                new_vals.setdefault(rule_code, {'exempt': 0.0, 'tax': total, 'total': total})
        return {
            'perceptions_bimonthly': round(sum(vals.values()), 2),
            'salary_var': round(sum(vals.values()) / days_worked, 2),
            'vals': new_vals
        }

    def _get_new_values(self):
        data = self._get_lines()
        year = data['extra_fields']['year']
        days_bimestre = data['extra_fields']['days_bimestre']
        date_start = data['extra_fields']['date_start']
        date_end = data['extra_fields']['date_end']
        employees = data['employees']
        run = self.env['hr.payslip.run']
        employee_leaves = run._get_leaves_by_dates(employee_ids=employees.keys(), date_from=date_end, date_to=date_end)
        leaves = data['leaves'].get('leaves', {})
        Contract = self.env['hr.contract']
        company = self.env.company
        calculate = self._context.get('calculate', False)
        compute_lines = []
        for employee in employees:
            vals = {}
            has_var = False
            contract_start = employees[employee]['data']['contract_start']
            if contract_start > date_start and contract_start < date_end:
                days_work = (date_end - contract_start).days
            else:
                days_work = days_bimestre
            inability_days = sum(leaves.get(employee, {}).get('leaves', {}).get('inability', [0]))
            holidays = sum(leaves.get(employee, {}).get('leaves', {}).get('holidays', [0]))
            leave_days = sum(leaves.get(employee, {}).get('leaves', {}).get('leave', [0]))
            if leave_days > 7:
                leave_days = 7
            days_worked = days_work - leave_days - inability_days
            contract_id = employees[employee]['data']['contract_id']
            contract = Contract.browse(contract_id)
            salary_type = employees[employee]['data']['salary_type']
            sbc = employees[employee]['data'].get('sbc', 0)
            antiquity_id = employees[employee]['data']['antiquity_id']
            perceptions = employees[employee]['perceptions']
            # GET ANTIQUITY
            res_years_antiquity = contract._get_years_antiquity(date_to=date_end)
            years_antiquity = res_years_antiquity[0]
            days_rest = res_years_antiquity[1]
            if days_rest == 0 and years_antiquity == 0:
                years_antiquity += 1
            if days_rest > 0:
                years_antiquity += 1
            float_antiquity = "{0:.2f}".format(((years_antiquity * 365) + days_rest) / 365)
            antiquity = self.env['hr.table.antiquity.line'].search([
                ('year', '=', years_antiquity),
                ('antiquity_line_id', '=', antiquity_id)
            ])
            factor = round((antiquity.factor + 1), 4)
            variable_salary = 0
            perceptions_bimonthly = 0
            res_perception = self._get_perception(perceptions, days_worked, sbc, employee=employee)
            perceptions_bimonthly = res_perception['perceptions_bimonthly']
            variable_salary = res_perception['salary_var']
            vals = res_perception['vals']
            if variable_salary > 0:
                has_var = True
            integral_salary = contract.integral_salary
            current_sdi = contract.sdi
            new_sdi = integral_salary + variable_salary
            limit_imss = company.uma * company.general_uma
            topado = '-'
            if new_sdi > limit_imss:
                new_sbc = limit_imss
                topado = 'Topado'
            else:
                new_sbc = new_sdi
            type_change_salary = False
            if has_var:
                type_change_salary = '1'
            else:
                type_change_salary = '3'
            type_change_salary = type_change_salary if type_change_salary else '3'
            type_change_salary = '4' if employee in employee_leaves else type_change_salary

            variability = variable_salary
            values = {
                'current_sdi': current_sdi,
                'new_sdi': new_sdi,
                'current_sbc': sbc,
                'new_sbc': new_sbc,
                'topado': topado,
                'leaves': leave_days,
                'inhabilitys': inability_days,
                'days_bimestre': days_bimestre,
                'days_worked': days_worked,
                'perceptions_bimonthly': perceptions_bimonthly,
                'variability': variability,
                'float_antiquity': float(float_antiquity),
                'factor': "{0:.4f}".format(factor),
                'percent_holidays': round(antiquity.vacation_cousin / 100, 4),
                'day_bonus': antiquity.aguinaldo,
                'holidays': holidays,
                'vals': vals,
                'type_change_salary': dict(self.env['wizard.payslip.variability.line']._fields['type_change_salary']._description_selection(self.env))[type_change_salary],
            }
            # if calculate:
            compute_lines.append((0, 0, {
                'employee_id': employee,
                'contract_id': contract.id,
                'current_sdi': current_sdi,
                'new_sdi': new_sdi,
                'sbc': new_sbc,
                'perceptions_bimonthly': perceptions_bimonthly,
                'variable_salary': variability,
                'days_bimestre': days_bimestre,
                'days_worked': days_worked,
                'leaves': leave_days,
                'inhabilitys': inability_days,
                'bimestre': self.bimestre,
                'year': self.year,
                'type_change_salary': type_change_salary,
            }))
            data['employees'][employee].setdefault('vars', values)
        if calculate:
            return compute_lines
        return data

    def salary_cap(self, salary):
        company = self.env.company
        limit_imss = company.uma * company.general_uma
        topado = '-'
        if salary > limit_imss:
            salary = limit_imss
            topado = 'Topado'
        return salary, topado

    def get_before_var(self, employee_id=None):
        prev_bimester_dic = {
            '1':'6',
            '2':'1',
            '3':'2',
            '4':'3',
            '5':'4',
            '6':'5',
        }
        prev_bimestre = prev_bimester_dic[str(self.bimestre)]
        year = int(self.year)
        if prev_bimestre == '6':
            year -= 1
        domain = [
            ('employee_id', '=', employee_id),
            ('bimestre', '=', int(prev_bimestre)),
            ('year', '=', year),
        ]
        vars_previous = self.env['hr.payslip.variability'].search(domain, limit=1, order='id desc')
        return vars_previous

    def calculate(self):
        # Step 1: Get Data
        _logger.info('CALL BUTTON')
        self.compute_lines.unlink()
        data = self.with_context(calculate=True)._get_new_values()
        _logger.info('fin _get_new_values')
        # Step 2: Set Lines
        self.compute_lines = data
        self.computed = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new'
        }

    def export_report(self):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory':True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        num_float4 = '_(#,##0.0000_);_(#,##0.0000;_("0"??_);_(@'
        header_format = workbook.add_format(
            {'bold': True, 'bg_color': '#100D57', 'font_color':'#FFFFFF',
             'border': 1, 'top': 1, 'font_size': 9, 'align':'center',
             'valign': 'vcenter', 'font_name': 'Calibri'})
        report_format = workbook.add_format(
            {'border': 1, 'bold': True, 'font_size': 9, 'font_name': 'Calibri',
             'align': 'center'})
        formula_format = workbook.add_format(
            {'num_format': num_format, 'bold': True, 'border': 1, 'top': 1,
             'font_size': 8, 'align': 'center', 'valign': 'vcenter',
             'font_name': 'Calibri'})
        currency_format = workbook.add_format(
            {'num_format': num_format, 'bold': True, 'border': 1, 'top':1,
             'font_size': 9, 'align': 'center', 'valign': 'vcenter',
             'font_name': 'Calibri'})
        float4_format = workbook.add_format(
            {'num_format': num_float4, 'bold': True, 'border': 1, 'top':1,
             'font_size': 9, 'align': 'center', 'valign': 'vcenter',
             'font_name': 'Calibri'})

        bimester = dict(self._fields['bimestre']._description_selection(self.env))[self.bimestre]
        sheet_name = '%s-%s' % (bimester.upper().replace(' ', ''), self.year)
        file_name = _('VARIABILITY-%s-%s') % (sheet_name, fields.Datetime.now().time())

        header = [
            {'sequence': 0.01, 'name': 'No. EMPLEADO', 'larg': 5},
            {'sequence': 0.02, 'name': 'APELLIDO PATERNO', 'larg': 20},
            {'sequence': 0.02, 'name': 'APELLIDO MATERNO', 'larg': 20},
            {'sequence': 0.02, 'name': 'NOMBRE COMPLETO', 'larg': 30},
            {'sequence': 0.03, 'name': 'NSS', 'larg': 10},
            {'sequence': 0.04, 'name': 'RFC', 'larg': 10},
            {'sequence': 0.05, 'name': 'CURP', 'larg': 10},
            {'sequence': 0.05, 'name': 'TIPO DE NÓMINA', 'larg': 10},
            {'sequence': 0.06, 'name': 'FECHA ALTA', 'larg': 15},
            {'sequence': 0.06, 'name': 'ANTIGÜEDAD', 'larg': 15},
            {'sequence': 0.06, 'name': 'FECHA PLANTA', 'larg': 15},
            {'sequence': 0.07, 'name': 'CCOSTO', 'larg': 5},
            {'sequence': 0.07, 'name': 'NOMBRE DEL CCOSTO', 'larg': 5},
            {'sequence': 0.09, 'name': 'PUESTO DE TRABAJO', 'larg': 30},
            {'sequence': 0.13, 'name': 'BIMESTRE', 'larg': 20},
            {'sequence': 0.14, 'name': 'SALARIO DIARIO', 'larg': 20},
            {'sequence': 0.16, 'name': 'PRIMA VACACIONAL ', 'larg': 20},
            {'sequence': 0.17, 'name': 'DÍAS DE AGUINALDO ', 'larg': 20},
            {'sequence': 0.01, 'name': 'FACTOR DE INTEGRACIÓN', 'larg': 20},
            {'sequence': 0.01, 'name': 'SALARIO FIJO', 'larg': 20},
        ]
        header2 = [
            {'sequence': 0.01, 'name': 'TOTAL DE PERCEPCIONES VARIABLES', 'larg': 20},
            {'sequence': 0.14, 'name': 'DÍAS DEL BIMESTRE', 'larg': 20},
        ]
        header3 = [
            {'sequence': 0.15, 'name': 'DÍAS TRABAJADOS', 'larg': 20},
            {'sequence': 0.01, 'name': 'IMPORTE VARIABLE', 'larg': 20},
            {'sequence': 0.01, 'name': 'SBC', 'larg': 20},
            {'sequence': 0.01, 'name': 'SDI ACTUAL', 'larg': 20},
            {'sequence': 0.01, 'name': 'SDI SIGUIENTE PERIODO', 'larg': 20},
            {'sequence': 0.01, 'name': 'TOPADO', 'larg': 20},
            {'sequence': 0.01, 'name': 'MOVIMIENTO', 'larg': 20},
        ]

        data = self._get_new_values()
        structure = self.structure_ids
        if any(not struct.payslip_code for struct in structure):
            raise ValidationError(_('One of the struct for these payslips has no payslip code.'))
        struct_name = ', '.join(structure.mapped('payslip_code'))

        def _write_sheet(sheet):
            order_header = dict(sorted(data['header'].items(), key=lambda item: item[1]['sequence']))
            main_col_count = 0
            sheet.write(0, 0, 'CIA', report_format)
            sheet.merge_range('B1:C1', self.env.company.name, report_format)
            sheet.write(1, 0, 'PERIODO_ANUAL', report_format)
            sheet.merge_range('B2:C2', self.year, report_format)
            sheet.write(2, 0, 'TIPO_NOM', report_format)
            sheet.merge_range('B3:C3', struct_name, report_format)
            sheet.write(3, 0, 'REPORTE', report_format)
            sheet.merge_range('B4:C4', 'VARIABILIDAD', report_format)
            sheet.write(4, 0, 'MES_ACUM', report_format)
            sheet.merge_range('B5:C5', bimester, report_format)
            row_count = 6
            sheet.set_row(row_count, 60, )
            # Step 1: writing col group headers
            for head_col in header:
                sheet.write(row_count, main_col_count, head_col['name'].replace(' ', '\n'), header_format)
                sheet.set_column(row_count, main_col_count, head_col['larg'])
                main_col_count += 1
            # Step 2: writing col group headers rules
            notaxes_codes = ['P030']
            row_count2 = row_count + 1
            for rule_head in order_header:
                if rule_head in notaxes_codes:

                    sheet.merge_range(row_count, main_col_count, row_count, main_col_count + 2,
                                      order_header[rule_head]['name'],
                                      header_format)
                    sheet.write(row_count2, main_col_count, 'EXENTO', header_format)
                    sheet.write(row_count2, main_col_count + 1, 'GRAVADO', header_format)
                    sheet.write(row_count2, main_col_count + 2, 'TOTAL', header_format)
                    sum_col = 3
                else:
                    sum_col = 1
                    sheet.write(row_count, main_col_count, order_header[rule_head]['name'].replace(' ', '\n'), header_format)
                main_col_count += sum_col
                sheet.set_column(0, main_col_count, 20)
            # Step 3: Header Order
            for h2 in header2:
                sheet.set_column(1000, main_col_count, 20)
                sheet.write(row_count, main_col_count, h2['name'].replace(' ', '\n'), header_format)
                main_col_count += 1
            # Step 4: Header Leaves
            leaves_header = data['leaves'].get('header', {})
            leaves_header = dict(sorted(leaves_header.items(), key=lambda item: item[1]))
            for leave_head in leaves_header:
                sheet.set_column(1000, main_col_count, 20)
                sheet.write(row_count, main_col_count, leaves_header[leave_head].upper().replace(' ', '\n'), header_format)
                main_col_count += 1
            # Step 4: Header Last
            for h3 in header3:
                sheet.set_column(1000, main_col_count, 20)
                sheet.write(row_count, main_col_count, h3['name'].replace(' ', '\n'), header_format)
                main_col_count += 1
            row_count += 1
            # Step 5: Write employee data
            employees = data['employees']
            leaves = data['leaves'].get('leaves', {})
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
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('contract_start_str', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['float_antiquity'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('contract_date', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('dep_code', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('dep_name', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['data'].get('job_name', ''), report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, self.bimestre, report_format)
                main_col_count += 1
                daily_salary = float(employees[employee]['data']['daily_salary'])
                sheet.write(row_count, main_col_count, daily_salary, report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['percent_holidays'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['day_bonus'], report_format)
                main_col_count += 1
                factor = float(employees[employee]['vars']['factor'])
                sheet.write(row_count, main_col_count, factor, float4_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, round(factor * daily_salary, 2), report_format)
                main_col_count += 1

                # Step 6: Write Rules Variability
                for rule in order_header:
                    if rule in notaxes_codes:
                        sum_col2 = 3
                        sheet.write(row_count, main_col_count, employees[employee]['vars']['vals'].get(rule, {}).get('exempt', 0), currency_format)
                        sheet.write(row_count, main_col_count + 1, employees[employee]['vars']['vals'].get(rule, {}).get('tax', 0), currency_format)
                        start_range = xl_rowcol_to_cell(8, main_col_count + 1)
                        end_range = xl_rowcol_to_cell(total_employees + 8, main_col_count + 1)
                        fila_formula = xl_rowcol_to_cell(total_employees + 9, main_col_count + 1)
                        formula = "=SUM({:s}:{:s})".format(start_range, end_range)
                        sheet.write_formula(fila_formula, formula, formula_format, True)

                        sheet.write(row_count, main_col_count + 2, employees[employee]['vars']['vals'].get(rule, {}).get('total', 0), currency_format)
                        start_range = xl_rowcol_to_cell(8, main_col_count + 2)
                        end_range = xl_rowcol_to_cell(total_employees + 8, main_col_count + 2)
                        fila_formula = xl_rowcol_to_cell(total_employees + 9, main_col_count + 2)
                        formula = "=SUM({:s}:{:s})".format(start_range, end_range)
                        sheet.write_formula(fila_formula, formula, formula_format, True)
                    else:
                        sum_col2 = 1
                        sheet.write(row_count, main_col_count, employees[employee]['vars']['vals'].get(rule, {}).get('total', 0), currency_format)
                    # sheet.write(row_count, main_col_count, 0, currency_format)
                    # Step 7: Total sum rules
                    start_range = xl_rowcol_to_cell(8, main_col_count)
                    end_range = xl_rowcol_to_cell(total_employees + 8, main_col_count)
                    fila_formula = xl_rowcol_to_cell(total_employees + 9, main_col_count)
                    formula = "=SUM({:s}:{:s})".format(start_range, end_range)
                    sheet.write_formula(fila_formula, formula, formula_format, True)
                    main_col_count += sum_col2
                # Step 8: Calculate of perceptions
                sheet.write(row_count, main_col_count, employees[employee]['vars']['perceptions_bimonthly'], currency_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['days_bimestre'], report_format)
                main_col_count += 1
                # Step 9: Write Rules Leaves
                for leave in leaves_header:
                    sheet.write(row_count, main_col_count, sum(leaves.get(employee, {}).get('rules', {}).get(leave, [0])), currency_format)
                    main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['days_worked'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['variability'], currency_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['new_sbc'], currency_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['current_sdi'], currency_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['new_sdi'], currency_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['topado'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, employees[employee]['vars']['type_change_salary'], report_format)
                main_col_count += 1
        # Star Call Write Sheet
        if data:
            sheet = workbook.add_worksheet(sheet_name)
            _write_sheet(sheet)
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

    def process(self):
        move = self.env['hr.employee.affiliate.movements']
        var = self.env['hr.payslip.variability']
        date_move = self.date
        for line in self.compute_lines:
            if line.type_change_salary not in ('3', '4'):
                move_id = move.create({
                    'contract_id': line.contract_id.id,
                    'employee_id': line.employee_id.id,
                    'company_id': self.env.company.id,
                    'type': '07',
                    'date': date_move,
                    'wage': line.contract_id.wage,
                    'salary': line.new_sdi,
                    'sbc': line.sbc,
                    'type_change_salary': line.type_change_salary,
                    'contracting_regime': '02',
                    'state': 'draft',
                    'variable': True,
                })
                line.contract_id.write({
                    'sdi': line.new_sdi,
                    'sbc': line.sbc,
                    'variable_salary': line.variable_salary,
                })
                line.contract_id.contract_salary_change(date_move=date_move)

                if move_id:
                    var_id = var.create({
                        'employee_id': line.employee_id.id,
                        'contract_id': line.contract_id.id,
                        'current_sdi': line.current_sdi,
                        'new_sdi': line.new_sdi,
                        'sbc': line.sbc,
                        'perceptions_bimonthly': line.perceptions_bimonthly,
                        'variable_salary': line.variable_salary,
                        'days_bimestre': line.days_bimestre,
                        'days_worked': line.days_worked,
                        'leaves': line.leaves,
                        'inhabilitys': line.inhabilitys,
                        'bimestre': self.bimestre,
                        'year': self.year,
                        'type_change_salary': line.type_change_salary,
                    })
                    var += var_id
        return {
            'name': _('Variability'),
            'domain': [('id', 'in', var.ids)],
            'res_model': 'hr.payslip.variability',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
        }

