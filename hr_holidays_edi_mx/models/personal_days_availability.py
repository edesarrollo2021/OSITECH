# coding: utf-8
from __future__ import division

import json
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PersonalDaysHistory(models.AbstractModel):
    _name = "hr.personal.days.history"
    _inherit = "hr.holiday.history"
    _description = "Personal Days Availability"

    def _get_reports_buttons(self):
        return [
            # {'name': _('Print (TXT)'), 'sequence': 3, 'action': 'print_txt', 'file_export_type': _('TXT')},
            {'name': _('Export (XLSX)'), 'sequence': 3, 'action': 'print_xlsx', 'file_export_type': _('XLSX')},
        ]

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
                                AND leave_type.time_type='personal'
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
                                AND leave_type.time_type='personal'
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

    def print_xlsx(self, options):
        return {
                'type': 'ir_actions_employee_report_download',
                'data': {'model': 'hr.personal.days.history',
                         'options': json.dumps(options),
                         'output_format': 'xlsx',
                         'report_id': self.env.context.get('id'),
                         }
                }

    def print_txt(self, options):
        return {
            'type': 'ir_actions_employee_report_download',
            'data': {'model': 'hr.personal.days.history',
                     'options': json.dumps(options),
                     'output_format': 'txt',
                     'report_id': self.env.context.get('id'),
                     }
            }
