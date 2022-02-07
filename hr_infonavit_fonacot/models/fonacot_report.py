# coding: utf-8
from __future__ import division

import json
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class FonacotReport(models.AbstractModel):
    _name = "fonacot.report"
    _inherit = "report.affiliate.movements"
    _description = "Fonacot Report"

    MAX_LINES = None
    filters_credits = {'filter': 'no_filter', 'enrollment': '', 'employee': ''}
    filter_multi_company = True
    filter_date = None
    filters_periods = True
    order_selected_column = None

    def _get_columns_name(self, options):
        return [
            {},
            {'name': _('Date High')},
            {'name': _('Date Down')},
            {'name': _('No. Emp.')},
            {'name': _('Employee')},
            {'name': _('Job')},
            {'name': _('C. Department')},
            {'name': _('Direction / Department')},
            {'name': _('Structure')},
            {'name': _('Worked Days')},
            {'name': _('Absences')},
            {'name': _('Net Days Worked')},
            {'name': _('# Credit')},
            {'name': _('# Employee')},
            {'name': _('Monthly Discount')},
            {'name': _('Biweekly Discount')},
            {'name': _('Period')},
            {'name': _('Date Start Credit')},
            {'name': _('Date End Credit')},
        ]

    def _get_reports_buttons(self):
        return [
            {'name': _('Export (XLSX)'), 'sequence': 1, 'action': 'print_xlsx', 'file_export_type': _('XLSX')}
        ]

    @api.model
    def _init_filter_credits(self, options, previous_options=None):
        if self.filters_credits is None:
            return

        previous_filter = previous_options and previous_options.get('filters_credits')
        options_filter = self.filters_credits or self.filters_credits.get('filter', 'no_filter')

        credit_vals = False
        the_filter = False
        if previous_filter:
            the_filter = previous_filter.get('filter') or options_filter
            if the_filter == 'enrollment_empl':
                credit_vals = previous_filter['enrollment']
            elif the_filter == 'employee':
                credit_vals = previous_filter['employee']

        if the_filter == 'no_filter':
            options['filters_credits'] = {}
            return

        options['filters_credits'] = {'string': credit_vals}
        options['filters_credits']['filter'] = the_filter

    @api.model
    def _get_options(self, previous_options=None):
        options = super(FonacotReport, self)._get_options(previous_options)
        if self.filters_credits:
            self._init_filter_credits(options, previous_options=previous_options)
        if self.filters_periods:
            self._init_filter_periods(options, previous_options=previous_options)
        return options

    @api.model
    def _get_options_domain(self, options):
        domain = []
        domain += self._get_options_fonacot(options)
        domain += self._get_options_periods_domain(options)
        return domain

    @api.model
    def _get_options_fonacot(self, options):
        domain = []

        if options.get('filters_credits').get('filter') and options['filters_credits']['filter'] == 'enrollment_empl':
            domain.append(('contract_id.employee_id.registration_number', 'ilike', options['filters_credits']['string']))
        if options.get('filters_credits').get('filter') and options['filters_credits']['filter'] == 'employee':
            domain.append(('contract_id.employee_id.complete_name', 'ilike', options['filters_credits']['string']))
        return domain

    @api.model
    def _get_query_lines(self, options, offset=None, limit=None):
        domain = []

        tables, where_clause, where_params = self._query_get(options, domain=domain)
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
                    CASE
                        WHEN contract.previous_contract_date IS NOT NULL THEN contract.previous_contract_date
                        ELSE contract.date_start
                    END contract_date,
                    line.amount                             AS total,
                    period.name                             AS period_name,
                    work_days.works                         AS works,
                    work_days.leaves                        AS leaves,
                    dep.name                                 AS cc_name,
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
                JOIN hr_cost_center cc                      ON employee.cost_center_id = cc.id
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
                WHERE period.state in ('open') AND %s
                ''' % where_clause

        if offset:
            query += ' OFFSET %s '
            where_params.append(offset)
        if limit:
            query += ' LIMIT %s '
            where_params.append(limit)

        return query, where_params

    @api.model
    def _query_get(self, options, domain=None):
        domain = self._get_options_domain(options) + (domain or [])
        self.env['hr.payslip'].check_access_rights('read')

        query = self.env['hr.payslip']._where_calc(domain)

        self.env['hr.payslip']._apply_ir_rules(query)

        return query.get_sql()

    @api.model
    def _get_aml_line(self, options, aml):
        columns = [
            {'name': aml['contract_date'].strftime('%d/%m/%Y') if aml['contract_date'] else '', 'class': 'date'},
            {'name': aml['contract_date_end'].strftime('%d/%m/%Y') if aml['contract_date_end'] else '', 'class': 'date'},
            {'name': aml['registration_number'].upper(), 'class': 'whitespace_print'},
            {'name': aml['employee_name'].upper(), 'class': 'whitespace_print'},
            {'name': aml['job_name'].upper(), 'class': 'whitespace_print'},
            {'name': aml['dep_code'].upper(), 'class': 'whitespace_print'},
            {'name': aml['cc_name'].upper(), 'class': 'whitespace_print'},
            {'name': aml['struct_name'].upper(), 'class': 'whitespace_print'},
            {'name': aml['works'], 'class': 'number'},
            {'name': aml['leaves'], 'class': 'number'},
            {'name': aml['works'] - aml['leaves'], 'class': 'number'},
            {'name': aml['n_fonacot'].upper(), 'class': 'whitespace_print'},
            {'name': aml['n_customer'].upper(), 'class': 'whitespace_print'},
            {'name': aml['fee'], 'class': 'number'},
            {'name': aml['total'], 'class': 'number'},
            {'name': aml['period_name'], 'class': 'whitespace_print'},
            {'name': aml['date_start'].strftime('%d/%m/%Y') if aml['date_start'] else '', 'class': 'date'},
            {'name': aml['date_end'].strftime('%d/%m/%Y') if aml['date_end'] else '', 'class': 'date'},
        ]
        return {
            'id': aml['id'],
            'class': 'top-vertical-align',
            'columns': columns,
            'level': 2,
        }

    def print_xlsx(self, options):
        return {
                'type': 'ir_actions_employee_report_download',
                'data': {'model': 'fonacot.report',
                         'options': json.dumps(options),
                         'output_format': 'xlsx',
                         'report_id': self.env.context.get('id'),
                         }
                }

    ####################################################
    # OPTIONS: periods
    ####################################################

    @api.model
    def _get_filter_periods(self):
        return self.env['hr.payroll.period'].search([
            ('company_id', 'in', self.env.user.company_ids.ids or [self.env.company.id]),
            ('state', 'in', ['open'])
        ], order="company_id, name")

    @api.model
    def _init_filter_periods(self, options, previous_options=None):
        if self.filters_periods is None:
            return

        if previous_options and previous_options.get('filters_periods'):
            period_map = dict((opt['id'], opt['selected']) for opt in previous_options['filters_periods'] if 'selected' in opt)
        else:
            last_period = self.env['hr.payroll.period'].search([('state', '=', 'open')], order='year, month asc', limit=1)
            period_map = {last_period.id: True}
        options['filters_periods'] = []

        for j in self._get_filter_periods():
            options['filters_periods'].append({
                'id': j.id,
                'name': j.name,
                'code': j.code,
                'selected': period_map.get(j.id, False),
            })

    @api.model
    def _get_options_periods(self, options):
        return [
            period for period in options.get('filters_periods', []) if period['selected']
        ]

    @api.model
    def _get_options_periods_domain(self, options):
        selected_periods = self._get_options_periods(options)
        return selected_periods and [('payroll_period_id', 'in', [j['id'] for j in selected_periods])] or []

