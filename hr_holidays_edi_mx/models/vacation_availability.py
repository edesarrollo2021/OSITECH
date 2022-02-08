# coding: utf-8
from __future__ import division

import json
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HolidaysHistory(models.AbstractModel):
    _name = "hr.holiday.history"
    _inherit = "report.affiliate.movements"
    _description = "Holidays Availability"

    MAX_LINES = None
    filters_leave = {'period': '', 'filter': 'no_filter', 'enrollment': '', 'employee': '', 'address': ''}
    filter_multi_company = True
    filter_date = None
    order_selected_column = None

    def _get_columns_name(self, options):
        return [
            {},
            {'name': _('Employee')},
            {'name': _('Period')},
            {'name': _('Total Days Assigned')},
            {'name': _('Total Days Used')},
            {'name': _('Total Days Available')},
            {'name': _('Enrollment')},
            {'name': _('Address')}
        ]

    def _get_reports_buttons(self):
        return [
            # {'name': _('Print (TXT)'), 'sequence': 3, 'action': 'print_txt', 'file_export_type': _('TXT')},
            {'name': _('Export (XLSX)'), 'sequence': 1, 'action': 'print_xlsx', 'file_export_type': _('XLSX')}
        ]

    @api.model
    def _init_filter_leave(self, options, previous_options=None):
        if self.filters_leave is None:
            return

        previous_filter = previous_options and previous_options.get('filters_leave')
        options_filter = self.filters_leave or self.filters_leave.get('filter', 'no_filter')

        leave_vals = False
        the_filter = False
        if previous_filter:
            the_filter = previous_filter.get('filter') or options_filter
            if the_filter == 'enrollment_empl':
                leave_vals = previous_filter['enrollment']
            elif the_filter == 'period':
                leave_vals = previous_filter['period']
            elif the_filter == 'employee':
                leave_vals = previous_filter['employee']
            elif the_filter == 'address':
                leave_vals = previous_filter['address']


        if the_filter == 'no_filter':
            options['filters_leave'] = {}
            return

        options['filters_leave'] = {'string': leave_vals}
        options['filters_leave']['filter'] = the_filter

    @api.model
    def _get_options(self, previous_options=None):
        options = super(HolidaysHistory, self)._get_options(previous_options)
        if self.filters_leave:
            self._init_filter_leave(options, previous_options=previous_options)
        return options

    @api.model
    def _get_options_domain(self, options):
        domain = []
        domain += self._get_options_leaves(options)
        return domain

    @api.model
    def _get_options_leaves(self, options):
        domain = []

        if options.get('filters_leave').get('filter') and options['filters_leave']['filter'] == 'enrollment_empl':
            domain.append(('employee_id.registration_number', 'ilike', options['filters_leave']['string']))
        if options.get('filters_leave').get('filter') and options['filters_leave']['filter'] == 'period':
            domain.append(('holiday_status_id.name', 'ilike', options['filters_leave']['string']))
        if options.get('filters_leave').get('filter') and options['filters_leave']['filter'] == 'employee':
            domain.append(('employee_id.complete_name', 'ilike', options['filters_leave']['string']))
        if options.get('filters_leave').get('filter') and options['filters_leave']['filter'] == 'address':
            domain.append(('department_id.name', 'ilike', options['filters_leave']['string']))
        return domain

    @api.model
    def _get_query_lines(self, options, offset=None, limit=None):

        domain = []

        tables, where_clause, where_params = self._query_get(options, domain=domain)
        where_clause = where_clause.replace('hr_leave_allocation', 'allocation')
        query = '''SELECT 
                            allocation.employee_id,
                            allocation.holiday_status_id, 
                            sum(COALESCE(allocation.days_asigned,0)) days_asigned,
                            sum(COALESCE(leaves.days_consumed,0)) days_consumed,
                            sum(COALESCE(allocation.days_asigned, 0) - COALESCE(leaves.days_consumed, 0) ) days_available,
                            allocation.registration_number,
                            allocation.leave_name,
                            allocation.department_name,
                            allocation.employee_name
                    FROM 
                        (SELECT 
                            allocation.employee_id,
                            allocation.holiday_status_id, 
                            SUM(COALESCE(allocation.number_of_days, 0)) days_asigned,
                            employee.registration_number,
                            employee.complete_name as employee_name,
                            leave_type.name as leave_name,
                            department.name as department_name
                        FROM hr_employee employee
                        JOIN hr_leave_allocation allocation ON employee.id=allocation.employee_id
                        JOIN hr_leave_type as leave_type on allocation.holiday_status_id = leave_type.id 
                        JOIN hr_contract contract ON employee.id = contract.employee_id
                        JOIN hr_department department ON department.id = allocation.department_id
                        WHERE  
                            allocation.state = 'validate' 
                            AND allocation.date_due > CURRENT_DATE 
                            AND allocation.is_due = False
                            AND leave_type.time_type='holidays'
                            AND employee.active=TRUE
                            AND contract.state = 'open'
                            AND contract.contracting_regime = '02'
                            AND %s
                        GROUP BY allocation.employee_id, allocation.holiday_status_id, employee.registration_number, 
                        department_name, leave_name, employee_name) allocation

                    LEFT JOIN
                        (SELECT 
                            leave.employee_id,
                            leave.holiday_status_id, 
                            SUM(COALESCE(leave.number_of_days, 0)) days_consumed
                        FROM hr_employee employee
                        JOIN hr_leave leave ON employee.id=leave.employee_id
                        JOIN hr_leave_type as leave_type on leave.holiday_status_id = leave_type.id 
                        JOIN hr_contract contract ON employee.id = contract.employee_id
                        WHERE 
                            leave.state = 'validate' 
                            AND leave_type.time_type='holidays'
                            AND employee.active=TRUE
                            AND contract.state = 'open'
                            AND contract.contracting_regime = '02'
                            AND contract.active = TRUE
                        GROUP BY leave.employee_id, leave.holiday_status_id
                        ) leaves ON allocation.employee_id=leaves.employee_id AND allocation.holiday_status_id=leaves.holiday_status_id
                    GROUP BY allocation.employee_id, allocation.holiday_status_id, allocation.department_name, 
                    allocation.registration_number, allocation.employee_name, allocation.leave_name''' % where_clause

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
            'id': aml['employee_id'],
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
