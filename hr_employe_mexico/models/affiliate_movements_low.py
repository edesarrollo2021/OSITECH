# coding: utf-8
from __future__ import division

import io
import json
import logging
import datetime

from odoo import _, api, fields, models
from odoo.tools import config, date_utils, get_lang, float_compare, translate, pycompat
from odoo.tools.misc import format_date, formatLang, xlsxwriter
from babel.dates import get_quarter_names

_logger = logging.getLogger(__name__)


class EmployeeReportsLow(models.AbstractModel):
    _name = "affiliate.movements.low"
    _inherit = "report.affiliate.movements"
    _description = "Affiliate Movements Low"

    MAX_LINES = None
    filter_multi_company = True
    filter_date = {'mode': 'range', 'filter': 'this_month'}
    filter_comparison = None
    order_selected_column = None

    def _get_columns_name(self, options):
        return [
            {},
            {'name': _('Employee Registry')},
            {'name': _('ssnid')},
            {'name': _('Last Name')},
            {'name': _('Mother Last Name')},
            {'name': _('Name')},
            {'name': _('Date')},
            {'name': _('Movement Type')},
            {'name': _('Guide')},
            {'name': _('Work Center')},
            {'name': _('Reason Liquidation')},
            {'name': _('State')},
        ]

    def _get_reports_buttons(self):
        return [
            {'name': _('Export (XLSX)'), 'sequence': 2, 'action': 'print_xlsx', 'file_export_type': _('XLSX')},
            {'name': _('Print (TXT)'), 'sequence': 3, 'action': 'print_txt', 'file_export_type': _('TXT')},
            {'name': _('SICOSS (TXT)'), 'sequence': 3, 'action': 'print_csv', 'file_export_type': _('CSV')},
        ]

    @api.model
    def _get_query_lines(self, options, offset=None, limit=None):

        domain = []

        tables, where_clause, where_params = self._query_get(options, domain=domain)
        query = """
                SELECT
                    hr_employee_affiliate_movements.id,
                    hr_employee_affiliate_movements.type,
                    hr_employee_affiliate_movements.date,
                    hr_employee_affiliate_movements.employee_id,
                    hr_employee_affiliate_movements.company_id,
                    hr_employee_affiliate_movements.contract_id,
                    hr_employee_affiliate_movements.wage,
                    hr_employee_affiliate_movements.salary,
                    hr_employee_affiliate_movements.sbc,
                    hr_employee_affiliate_movements.origin_move,
                    hr_employee_affiliate_movements.variable,
                    hr_employee_affiliate_movements.reason_liquidation,
                    hr_employee_affiliate_movements.state,
                    employee.name                           AS employee_name,
                    employee.last_name                      AS employee_last_name,
                    employee.mothers_last_name              AS employee_m_last_name,
                    employee.ssnid                          AS ssnid,
                    employee.type_worker                    AS type_worker,
                    employee.salary_type                    AS salary_type,
                    employee.working_day_week               AS working_day_week,
                    employee.family_medicine_unit           AS umf,
                    company.name                            AS company_name,
                    contract.code                           AS contract_code,
                    register.employer_registry              AS employer_registry,
                    subdelegation.code                      AS subdelegation_code,
                    center.code                             AS center_code,
                    partner.curp                            AS curp,
                    employee.registration_number            AS employee_code,
                    hr_employee_affiliate_movements.origin_move AS origin_move
                FROM hr_employee_affiliate_movements
                LEFT JOIN res_company company               ON company.id = hr_employee_affiliate_movements.company_id
                LEFT JOIN hr_employee employee              ON employee.id = hr_employee_affiliate_movements.employee_id
                LEFT JOIN hr_contract contract              ON contract.id = hr_employee_affiliate_movements.contract_id
                LEFT JOIN res_employer_register register    ON register.id = employee.employer_register_id
                LEFT JOIN res_company_subdelegation subdelegation    ON subdelegation.id = register.subdelegation_id
                LEFT JOIN hr_department center             ON center.id = employee.cost_center_id
                LEFT JOIN res_partner partner               ON partner.id = employee.address_home_id
                WHERE hr_employee_affiliate_movements.type = '02' AND %s
            """ % where_clause

        if offset:
            query += ' OFFSET %s '
            where_params.append(offset)
        if limit:
            query += ' LIMIT %s '
            where_params.append(limit)

        return query, where_params

    @api.model
    def _get_aml_line(self, options, aml):
        if options.get('sicoss', False):
            columns = [
                {'name': aml['employee_code'], 'class': 'whitespace_print'},
                {'name': aml['date'].strftime('%d/%m/%Y'), 'class': 'date'},
                {'name': '1', 'class': 'whitespace_print'},
                {'name': 'B', 'class': 'whitespace_print'},
                {'name': '020', 'class':'whitespace_print'},
                {'name': '1', 'class':'whitespace_print'},
                {'name': '2', 'class':'whitespace_print'},
                {'name': '3', 'class':'whitespace_print'},
                {'name': '0608', 'class':'whitespace_print'},
                {'name': '0579', 'class':'whitespace_print'},
                {'name': '01', 'class':'whitespace_print'},
                {'name': '0', 'class':'whitespace_print'},
            ]
        else:
            if self._context.get('print_txt', False):
                columns = [
                    {'name': aml['employer_registry'], 'class': 'whitespace_print'},
                    {'name': aml['ssnid'], 'class': 'whitespace_print'},
                    {'name': aml['employee_last_name'].upper() if aml['employee_last_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['employee_m_last_name'].upper() if aml['employee_m_last_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['employee_name'].upper() if aml['employee_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['date'].strftime('%d%m%Y'), 'class': 'date'},
                    {'name': aml['type'], 'class': 'whitespace_print'},
                    {'name': aml['subdelegation_code'], 'class': 'whitespace_print'},
                    {'name': aml['employee_code'], 'class': 'whitespace_print'},
                    {'name': aml['reason_liquidation'], 'class': 'whitespace_print'},
                ]
            else:
                columns = [
                    {'name': aml['employer_registry'], 'class': 'whitespace_print'},
                    {'name': aml['ssnid'], 'class': 'whitespace_print'},
                    {'name': aml['employee_last_name'].upper() if aml['employee_last_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['employee_m_last_name'].upper() if aml['employee_m_last_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['employee_name'].upper() if aml['employee_name'] else '', 'class': 'whitespace_print'},
                    {'name': format_date(self.env, aml['date']), 'class': 'date'},
                    {'name': dict(self.env['hr.employee.affiliate.movements']._fields['type']._description_selection(self.env)).get(aml['type']),
                     'class': 'whitespace_print'},
                    {'name': aml['subdelegation_code'], 'class': 'whitespace_print'},
                    {'name': aml['center_code'], 'class': 'whitespace_print'},
                    {'name': dict(self.env['hr.employee.affiliate.movements']._fields['reason_liquidation']._description_selection(self.env)).get(aml['reason_liquidation']),
                     'class': 'whitespace_print'},
                    {'name': dict(self.env['hr.employee.affiliate.movements']._fields['state']._description_selection(self.env)).get(aml['state']),
                     'class': 'whitespace_print'},
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
                'data': {'model': 'affiliate.movements.low',
                         'options': json.dumps(options),
                         'output_format': 'xlsx',
                         'report_id': self.env.context.get('id'),
                         }
                }

    def print_txt(self, options):
        return {
            'type': 'ir_actions_employee_report_download',
            'data': {'model': 'affiliate.movements.low',
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
            data = [''] * 14
            data[0] = columns[0]['name'].ljust(11) if columns[0]['name'] else ' '.ljust(11)
            data[1] = columns[1]['name'].ljust(11) if columns[1]['name'] else ' '.ljust(11)
            data[2] = columns[2]['name'].ljust(27).replace('Ñ', '#') if columns[2]['name'] else ' '.ljust(27)
            data[3] = columns[3]['name'].ljust(27).replace('Ñ', '#') if columns[3]['name'] else ' '.ljust(27)
            data[4] = columns[4]['name'].ljust(27).replace('Ñ', '#') if columns[4]['name'] else ' '.ljust(27)
            data[5] = '0'.zfill(15)
            data[6] = columns[5]['name'].ljust(8) if columns[5]['name'] else ' '.ljust(8)
            data[7] = ' '.ljust(5)
            data[8] = columns[6]['name'].ljust(2) if columns[6]['name'] else ' '.ljust(2)
            data[9] = columns[7]['name'].ljust(5) if columns[7]['name'] and len(columns[7]['name']) == 5 else '0'.zfill(5)
            data[10] = str(columns[8]['name'])[:10].ljust(10) if columns[8]['name'] else ' '.ljust(10)
            data[11] = columns[9]['name'].ljust(1) if columns[9]['name'] else ' '.ljust(1)
            data[12] = ' '.ljust(18)
            data[13] = '9'.ljust(1)
            lines += ''.join(str(d) for d in data) + '\n'

            self.env['hr.employee.affiliate.movements'].sudo().browse(int(line['id'])).write({'state': 'approved'})
        return lines


    def get_csv(self, options):
        options['sicoss'] = True
        ctx = self.env.context.copy()
        txt_data = self.with_context(ctx)._get_lines(options)
        lines = ''
        for line in txt_data:
            if not line.get('id'):
                continue
            columns = line.get('columns', [])
            array = [''] * 12
            array[0] = str(columns[0]['name']).zfill(6) if columns[0]['name'] else '0'.zfill(6)
            array[1] = columns[1]['name'] if columns[1]['name'] else '0'.zfill(8)
            array[2] = columns[2]['name']
            array[3] = columns[3]['name']
            array[4] = columns[4]['name']
            array[5] = columns[5]['name']
            array[6] = columns[6]['name']
            array[7] = columns[7]['name']
            array[8] = columns[8]['name']
            array[9] = columns[9]['name']
            array[10] = columns[10]['name']
            array[11] = columns[11]['name']
            lines += ','.join(str(d) for d in array) + '\n'
        return lines

    def print_csv(self, options):
        ctx = self.env.context.copy()
        options['type_move'] = ctx.get('type', False)
        ctx.update({'sicoss': True})
        options['sicoss'] = True
        return {
            'type': 'ir_actions_employee_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'output_format': 'csv',
                'context': ctx,
                'report_id': self.env.context.get('id')
                }
            }


