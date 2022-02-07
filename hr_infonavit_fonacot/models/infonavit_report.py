# coding: utf-8
from __future__ import division

import json
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class InfonavitReport(models.AbstractModel):
    _name = "infonavit.report"
    _inherit = "report.affiliate.movements"
    _description = "Infonavit Report"

    MAX_LINES = None
    filters_infonavit = {'filter': 'no_filter', 'enrollment': '', 'employee': ''}
    filter_multi_company = True
    filter_date = None
    order_selected_column = None

    def _get_columns_name(self, options):
        return [
            {},
            {'name': _('Enrollment')},
            {'name': _('Employee Name')},
            {'name': _('# Credit')},
            {'name': _('Discount Factor')},
            {'name': _('Discount Rate')},
            {'name': _('Biweekly Discount')}
        ]

    def _get_reports_buttons(self):
        return [
            # {'name': _('Print (TXT)'), 'sequence': 3, 'action': 'print_txt', 'file_export_type': _('TXT')},
            {'name': _('Export (XLSX)'), 'sequence': 1, 'action': 'print_xlsx', 'file_export_type': _('XLSX')}
        ]

    @api.model
    def _init_filter_infonavit(self, options, previous_options=None):
        if self.filters_infonavit is None:
            return

        previous_filter = previous_options and previous_options.get('filters_leave')
        options_filter = self.filters_infonavit or self.filters_infonavit.get('filter', 'no_filter')

        leave_vals = False
        the_filter = False
        if previous_filter:
            the_filter = previous_filter.get('filter') or options_filter
            if the_filter == 'enrollment_empl':
                leave_vals = previous_filter['enrollment']
            elif the_filter == 'employee':
                leave_vals = previous_filter['employee']


        if the_filter == 'no_filter':
            options['filters_leave'] = {}
            return

        options['filters_leave'] = {'string': leave_vals}
        options['filters_leave']['filter'] = the_filter

    @api.model
    def _get_options(self, previous_options=None):
        options = super(InfonavitReport, self)._get_options(previous_options)
        if self.filters_leave:
            self._init_filter_leave(options, previous_options=previous_options)
        return options

    @api.model
    def _get_options_domain(self, options):
        domain = []
        domain += self._get_options_leaves(options)
        return domain

    @api.model
    def _get_options_infonavit(self, options):
        domain = []

        if options.get('filters_leave').get('filter') and options['filters_leave']['filter'] == 'enrollment_empl':
            domain.append(('employee_id.registration_number', 'ilike', options['filters_leave']['string']))
        if options.get('filters_leave').get('filter') and options['filters_leave']['filter'] == 'employee':
            domain.append(('employee_id.complete_name', 'ilike', options['filters_leave']['string']))
        return domain

    @api.model
    def _get_query_lines(self, options, offset=None, limit=None):

        domain = []

        tables, where_clause, where_params = self._query_get(options, domain=domain)
        query = '''
                SELECT
                    hr_employee_affiliate_movements.id,
                    hr_employee_affiliate_movements.type,
                    hr_employee_affiliate_movements.date,
                    hr_employee_affiliate_movements.employee_id,
                    employee.name                           AS employee_name,
                    employee.last_name                      AS employee_last_name,
                    employee.mothers_last_name              AS employee_m_last_name,
                FROM hr_infonavit_credit_line
                LEFT JOIN hr_employee employee              ON employee.id = hr_employee_affiliate_movements.employee_id
                WHERE hr_infonavit_credit_line.state in ['active'] AND %s
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
        self.env['hr.leave.allocation'].check_access_rights('read')

        query = self.env['hr.leave.allocation']._where_calc(domain)

        # Wrap the query with 'company_id IN (...)' to avoid bypassing company access rights.
        self.env['hr.leave.allocation']._apply_ir_rules(query)

        return query.get_sql()

    @api.model
    def _get_aml_line(self, options, aml):
        columns = [
            {'name': aml['employee_name'].upper(), 'class': 'whitespace_print'},
            {'name': aml['leave_name'], 'class': 'whitespace_print'},
            {'name': aml['days_asigned'], 'class': 'number'},
            {'name': aml['days_consumed'], 'class': 'number'},
            {'name': aml['days_available'], 'class': 'number'},
            {'name': aml['registration_number'], 'class': 'whitespace_print'},
            {'name': aml['department_name'], 'class': 'whitespace_print'},
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
                'data': {'model': 'hr.holiday.history',
                         'options': json.dumps(options),
                         'output_format': 'xlsx',
                         'report_id': self.env.context.get('id'),
                         }
                }

    def print_txt(self, options):
        return {
            'type': 'ir_actions_employee_report_download',
            'data': {'model': 'hr.holiday.history',
                     'options': json.dumps(options),
                     'output_format': 'txt',
                     'report_id': self.env.context.get('id'),
                     }
            }

    def _txt_export(self, options):
        ctx = self._set_context(options)

        txt_data = self.with_context(ctx)._get_lines(options)
        lines = ''
        for line in txt_data:
            if not line.get('id'):
                continue
            columns = line.get('columns', [])
            data = [''] * 19
            data[0] = columns[0]['name'].ljust(27).replace('Ñ', '#') if columns[0]['name'] else ' '.ljust(27)
            data[1] = columns[1]['name'].ljust(27).replace('Ñ', '#') if columns[1]['name'] else ' '.ljust(27)
            data[2] = "{0:.2f}".format(columns[2]['name']).replace('.','').zfill(6) if columns[2]['name'] else ' '.zfill(6)
            data[3] = "{0:.2f}".format(columns[3]['name']).replace('.','').zfill(6) if columns[3]['name'] else ' '.zfill(6)
            data[4] = "{0:.2f}".format(columns[4]['name']).replace('.','').zfill(6) if columns[4]['name'] else ' '.zfill(6)
            data[5] = columns[5]['name'].ljust(27).replace('Ñ', '#') if columns[5]['name'] else ' '.ljust(27)
            data[6] = columns[6]['name'].ljust(27).replace('Ñ', '#') if columns[6]['name'] else ' '.ljust(27)

            lines += ''.join(str(d) for d in data) + '\n'

            self.env['hr.employee.affiliate.movements'].sudo().browse(int(line['id'])).write({'state': 'approved'})
        return lines

