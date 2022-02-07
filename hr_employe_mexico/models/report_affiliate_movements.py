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


class MexicoEmployeeReports(models.AbstractModel):
    _name = "report.affiliate.movements"
    _description = "Affiliate Movements"

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
            {'name': _('SBC'), 'class': 'number'},
            {'name': _('Worker Type')},
            {'name': _('Salary Type')},
            {'name': _('Working Day Week')},
            {'name': _('Date')},
            {'name': _('Family Medicine Unit')},
            {'name': _('Movement Type')},
            {'name': _('Guide')},
            {'name': _('Work Center')},
            {'name': _('CURP')},
            {'name': _('State')},
        ]

    def _get_columns(self, options):
        return [self._get_columns_name(options)]

    def get_header(self, options):
        columns = self._get_columns(options)
        if 'selected_column' in options and self.order_selected_column:
            selected_column = columns[0][abs(options['selected_column']) - 1]
            if 'sortable' in selected_column.get('class', ''):
                selected_column['class'] = (options['selected_column'] > 0 and 'up ' or 'down ') + selected_column['class']
        return columns

    def _get_templates(self):
        return {
            'main_template': 'hr_employe_mexico.main_template',
            'main_table_header_template': 'hr_employe_mexico.main_table_header',
            'line_template': 'hr_employe_mexico.line_template',
            'search_template': 'hr_employe_mexico.search_template',
        }

    def _get_table(self, options):
        return self.get_header(options), self._get_lines(options)

    def _get_lines(self, options, line_id=None):
        """
            this method builds the lines for rendering.

            Later add an offset for a pagination.
        """
        ctx = self._set_context(options)
        # offset = int(options.get('lines_offset', 0))
        # remaining = int(options.get('lines_remaining', 0))
        # return self._get_lines_for_lot(options, offset, remaining)

        return self.with_context(ctx)._get_lines_for_lot(options)

    def get_report_informations(self, options):
        '''
        return a dictionary of informations that will be needed by the js widget, html of report and searchview, ...
        '''
        options = self._get_options(options)

        searchview_dict = {'options': options, 'context': self.env.context}
        if options.get('employee_id'):
            options['selected_employee'] = [self.env['hr.employee'].browse(int(employee)).name for employee in options['employee_id']]
            options['selected_partner_categories'] = [self.env['res.partner.category'].browse(int(category)).name for category in (options.get('partner_categories') or [])]


        info = {'options': options,
                'context': self.env.context,
                'buttons': self._get_reports_buttons_in_sequence(),
                'main_html': self.get_html(options),
                'searchview_html': self.env['ir.ui.view']._render_template(self._get_templates().get('search_template', 'hr_employe_mexico.search_template'), values=searchview_dict),
                }
        return info

    def _get_report_name(self):
        return _('Employee Report')

    def get_report_filename(self, options):
        """The name that will be used for the file when downloading pdf,xlsx,..."""
        reporname = self._get_report_name()
        if options.get('sicoss', False):
            type = options.get('type_move', 'Reporte')
            reporname = "SICOSS %s" % type
        return reporname.lower().replace(' ', '_')

    @api.model
    def _get_dates_period(self, options, date_from, date_to, mode, period_type=None, strict_range=False):

        def match(dt_from, dt_to):
            return (dt_from, dt_to) == (date_from, date_to)

        string = None
        # If no date_from or not date_to, we are unable to determine a period
        if not period_type or period_type == 'custom':
            date = date_to or date_from
            if match(*date_utils.get_month(date)):
                period_type = 'month'
            elif match(*date_utils.get_quarter(date)):
                period_type = 'quarter'
            elif match(date_utils.get_month(date)[0], fields.Date.today()):
                period_type = 'today'
            else:
                period_type = 'custom'

        if not string:
            if mode == 'single':
                string = _('As of %s') % (format_date(self.env, fields.Date.to_string(date_to)))
            elif period_type == 'year' or (date_from, date_to) == date_utils.get_fiscal_year(date_to):
                string = date_to.strftime('%Y')
            elif period_type == 'month':
                string = format_date(self.env, fields.Date.to_string(date_to), date_format='MMM yyyy')
            elif period_type == 'quarter':
                quarter_names = get_quarter_names('abbreviated', locale=get_lang(self.env).code)
                string = u'%s\N{NO-BREAK SPACE}%s' % (quarter_names[date_utils.get_quarter_number(date_to)], date_to.year)
            else:
                dt_from_str = format_date(self.env, fields.Date.to_string(date_from))
                dt_to_str = format_date(self.env, fields.Date.to_string(date_to))
                string = _('From %s\nto  %s') % (dt_from_str, dt_to_str)

        return {
            'string': string,
            'period_type': period_type,
            'mode': mode,
            'strict_range': strict_range,
            'date_from': date_from and fields.Date.to_string(date_from) or False,
            'date_to': fields.Date.to_string(date_to),
        }

    @api.model
    def _get_dates_previous_period(self, options, period_vals):
        period_type = period_vals['period_type']
        mode = period_vals['mode']
        strict_range = period_vals.get('strict_range', False)
        date_from = fields.Date.from_string(period_vals['date_from'])
        date_to = date_from - datetime.timedelta(days=1)

        if period_type in ('month', 'today', 'custom'):
            return self._get_dates_period(options, *date_utils.get_month(date_to), mode, period_type='month',
                                          strict_range=strict_range)
        if period_type == 'quarter':
            return self._get_dates_period(options, *date_utils.get_quarter(date_to), mode, period_type='quarter',
                                          strict_range=strict_range)
        if period_type == 'year':
            return self._get_dates_period(options, *date_utils.get_fiscal_year(date_to), mode, period_type='year',
                                          strict_range=strict_range)
        return None

    @api.model
    def _init_filter_date(self, options, previous_options=None):
        if self.filter_date is None:
            return

        previous_date = (previous_options or {}).get('date', {})

        # Default values.
        mode = previous_date.get('mode') or self.filter_date.get('mode', 'range')
        options_filter = previous_date.get('filter') or self.filter_date.get('filter') or ('today')
        date_from = fields.Date.to_date(previous_date.get('date_from') or self.filter_date.get('date_from'))
        date_to = fields.Date.to_date(previous_date.get('date_to') or self.filter_date.get('date_to'))
        strict_range = previous_date.get('strict_range', False)

        # Create date option for each company.
        period_type = False
        if 'today' in options_filter:
            date_to = fields.Date.context_today(self)
            date_from = date_utils.get_month(date_to)[0]
        elif 'month' in options_filter:
            date_from, date_to = date_utils.get_month(fields.Date.context_today(self))
            period_type = 'month'
        elif 'quarter' in options_filter:
            date_from, date_to = date_utils.get_quarter(fields.Date.context_today(self))
            period_type = 'quarter'
        elif 'year' in options_filter:
            company_fiscalyear_dates = self.env.company.compute_fiscalyear_dates(fields.Date.context_today(self))
            date_from = company_fiscalyear_dates['date_from']
            date_to = company_fiscalyear_dates['date_to']
        elif not date_from:
            # options_filter == 'custom' && mode == 'single'
            date_from = date_utils.get_month(date_to)[0]

        options['date'] = self._get_dates_period(options, date_from, date_to, mode, period_type=period_type, strict_range=strict_range)
        if 'last' in options_filter:
            options['date'] = self._get_dates_previous_period(options, options['date'])
        options['date']['filter'] = options_filter

    @api.model
    def _get_options(self, previous_options=None):
        # Create default options.
        options = {}

        # Multi-company is there for security purpose and can't be disabled by a filter.
        if self.filter_multi_company:
            if self._context.get('allowed_company_ids'):
                # Retrieve the companies through the multi-companies widget.
                companies = self.env['res.company'].browse(self._context['allowed_company_ids'])
            else:
                # When called from testing files, 'allowed_company_ids' is missing.
                # Then, give access to all user's companies.
                companies = self.env.companies
            if len(companies) > 1:
                options['multi_company'] = [
                    {'id': c.id, 'name': c.name} for c in companies
                ]

        # Call _init_filter_date/_init_filter_comparison because the second one must be called after the first one.
        if self.filter_date:
            self._init_filter_date(options, previous_options=previous_options)
        if self.filter_comparison:
            self._init_filter_comparison(options, previous_options=previous_options)

        filter_list = [attr for attr in dir(self)
                       if (attr.startswith('filter_') or attr.startswith('order_')) and attr not in (
                       'filter_date', 'filter_comparison', 'filter_multi_company') and len(attr) > 7 and not callable(
                getattr(self, attr))]
        for filter_key in filter_list:
            options_key = filter_key[7:]
            init_func = getattr(self, '_init_%s' % filter_key, None)
            if init_func:
                init_func(options, previous_options=previous_options)
            else:
                filter_opt = getattr(self, filter_key, None)
                if filter_opt is not None:
                    if previous_options and options_key in previous_options:
                        options[options_key] = previous_options[options_key]
                    else:
                        options[options_key] = filter_opt
        return options

    @api.model
    def _get_options_domain(self, options):
        domain = []

        if options.get('multi_company', False):
            domain += [('company_id', 'in', self.env.companies.ids)]
        else:
            domain += [('company_id', '=', self.env.company.id)]
        domain += self._get_options_date_domain(options)
        return domain

    @api.model
    def _get_options_date_domain(self, options):
        def create_date_domain(options_date):
            date_field = options_date.get('date_field', 'date')
            domain = [(date_field, '<=', options_date['date_to'])]
            if options_date['mode'] == 'range':
                domain += [(date_field, '>=', options_date['date_from'])]
            return domain

        if not options.get('date'):
            return []
        return create_date_domain(options['date'])

    ####################################################
    # QUERIES
    ####################################################

    def _cr_execute(self, options, query, params=None):
        """
        Similar to self._cr.execute but allowing some custom behavior like shadowing the account_move_line table
        to another one like account_reports_cash_basis does.

        :param options: The report options.
        :param query:   The query to be executed by the report.
        :param params:  The optional params of the _cr.execute method.
        """
        return self._cr.execute(query, params)

    @api.model
    def _query_get(self, options, domain=None):
        domain = self._get_options_domain(options) + (domain or [])
        self.env['hr.employee.affiliate.movements'].check_access_rights('read')

        query = self.env['hr.employee.affiliate.movements']._where_calc(domain)

        # Wrap the query with 'company_id IN (...)' to avoid bypassing company access rights.
        self.env['hr.employee.affiliate.movements']._apply_ir_rules(query)

        return query.get_sql()

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
                hr_employee_affiliate_movements.state,
                employee.name                           AS employee_name,
                employee.last_name                      AS employee_last_name,
                employee.mothers_last_name              AS employee_m_last_name,
                employee.ssnid                          AS ssnid,
                employee.type_worker                    AS type_worker,
                employee.salary_type                    AS salary_type,
                employee.working_day_week               AS working_day_week,
                employee.family_medicine_unit           AS umf,
                employee.birthday                       AS birthday,
                employee.gender                         AS gender,
                company.name                            AS company_name,
                contract.code                           AS contract_code,
                register.employer_registry              AS employer_registry,
                subdelegation.code                      AS subdelegation_code,
                center.code                             AS center_code,
                partner.curp                            AS curp,
                partner.rfc                             AS rfc,
                contract.daily_salary                   AS daily_salary,
                employee.registration_number            AS employee_code,
                hr_employee_affiliate_movements.origin_move AS origin_move
            FROM hr_employee_affiliate_movements
            LEFT JOIN res_company company               ON company.id = hr_employee_affiliate_movements.company_id
            LEFT JOIN hr_employee employee              ON employee.id = hr_employee_affiliate_movements.employee_id
            LEFT JOIN hr_contract contract              ON contract.id = hr_employee_affiliate_movements.contract_id
            LEFT JOIN res_employer_register register    ON register.id = employee.employer_register_id
            LEFT JOIN res_company_subdelegation subdelegation    ON subdelegation.id = register.subdelegation_id
            LEFT JOIN hr_department center              ON center.id = employee.department_id
            LEFT JOIN res_partner partner               ON partner.id = employee.address_home_id
            WHERE hr_employee_affiliate_movements.type = '08' AND %s
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
                {'name': aml['curp'], 'class': 'whitespace_print'},
                {'name': aml['employee_last_name'], 'class': 'whitespace_print'},
                {'name': aml['employee_m_last_name'], 'class': 'whitespace_print'},
                {'name': aml['employee_name'], 'class': 'whitespace_print'},
                {'name': aml['ssnid'], 'class': 'whitespace_print'},
                {'name': aml['rfc'], 'class': 'whitespace_print'},
                {'name': aml['date'].strftime('%d/%m/%Y') if aml['date'] else "", 'class': 'date'},
                {'name': aml['birthday'].strftime('%d/%m/%Y') if aml['birthday'] else "", 'class': 'date'},
                {'name': aml['gender'], 'class': 'whitespace_print'},
                {'name': aml['daily_salary'], 'class': 'number'},
                {'name': aml['sbc'], 'class':'number'},
            ]
        else:
            if self._context.get('print_txt', False):
                columns = [
                    {'name': aml['employer_registry'], 'class': 'whitespace_print'},
                    {'name': aml['ssnid'], 'class': 'whitespace_print'},
                    {'name': aml['employee_last_name'].upper() if aml['employee_last_name'] else '','class': 'whitespace_print'},
                    {'name': aml['employee_m_last_name'].upper() if aml['employee_m_last_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['employee_name'].upper() if aml['employee_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['sbc'], 'class': 'number'},
                    {'name': aml['type_worker'], 'class': 'whitespace_print'},
                    {'name': aml['salary_type'], 'class': 'whitespace_print'},
                    {'name': aml['working_day_week'], 'class': 'whitespace_print'},
                    {'name': aml['date'].strftime('%d%m%Y'), 'class': 'date'},
                    {'name': aml['umf'], 'title': aml['employee_name'], 'class': 'whitespace_print'},
                    {'name': aml['type'], 'class': 'whitespace_print'},
                    {'name': aml['subdelegation_code'], 'class': 'whitespace_print'},
                    {'name': aml['employee_code'], 'class': 'whitespace_print'},
                    {'name': aml['curp'], 'class': 'whitespace_print'},
                ]
            else:
                columns = [
                    {'name': aml['employer_registry'], 'class': 'whitespace_print'},
                    {'name': aml['ssnid'], 'class': 'whitespace_print'},
                    {'name': aml['employee_last_name'].upper() if aml['employee_last_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['employee_m_last_name'].upper() if aml['employee_m_last_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['employee_name'].upper() if aml['employee_name'] else '', 'class': 'whitespace_print'},
                    {'name': aml['sbc'], 'class': 'number'},
                    {'name':  dict(self.env['hr.employee']._fields['type_worker']._description_selection(self.env)).get(aml['type_worker']),
                     'class': 'whitespace_print'},
                    {'name': dict(self.env['hr.employee']._fields['salary_type']._description_selection(self.env)).get(aml['salary_type']),
                     'class': 'whitespace_print'},
                    {'name': aml['working_day_week'], 'class': 'whitespace_print'},
                    {'name': format_date(self.env, aml['date']), 'class': 'date'},
                    {'name': aml['umf'], 'title': aml['employee_name'], 'class': 'whitespace_print'},
                    {'name': dict(self.env['hr.employee.affiliate.movements']._fields['type']._description_selection(self.env)).get(aml['type']),
                     'class': 'whitespace_print'},
                    {'name': aml['subdelegation_code'], 'class': 'whitespace_print'},
                    {'name': aml['center_code'], 'class': 'whitespace_print'},
                    {'name': aml['curp'], 'class': 'whitespace_print'},
                    {'name': dict(self.env['hr.employee.affiliate.movements']._fields['state']._description_selection(self.env)).get(aml['state']),
                     'class': 'whitespace_print'},
                    # {'name': self.format_value(aml['wage'], blank_if_zero=True), 'class': 'number'},
                    # {'name': self.format_value(aml['salary'], blank_if_zero=True), 'class': 'number'},
                    # {'name': dict(self.env['hr.employee.affiliate.movements']._fields['origin_move'].selection).get(aml['origin_move']), 'class': 'whitespace_print'},
                ]
        return {
            'id': aml['id'],
            'class': 'top-vertical-align',
            'columns': columns,
            'level': 2,
        }

    @api.model
    def _get_lines_for_lot(self, options, offset=None, load_more_remaining=None):
        ctx = self._set_context(options)
        lines = []
        aml_lines = []

        # load_more_counter = self.MAX_LINES

        # amls_query, amls_params = self._get_query_lines(options, offset=offset, limit=load_more_counter)
        amls_query, amls_params = self._get_query_lines(options)
        self._cr_execute(options, amls_query, amls_params)

        for aml in self._cr.dictfetchall():
            # Don't show more line than load_more_counter.
            # if load_more_counter == 0:
            #     break

            lines.append(self.with_context(ctx)._get_aml_line(options, aml))

            # if offset > 0:
            #     offset += 1
            #     load_more_remaining -= 1
            #     load_more_counter -= 1

        # if load_more_remaining > 0:
        #     # Load more line.
        #     lines.append(self._get_lines_for_lot(
        #         options,
        #         offset,
        #         load_more_remaining,
        #     ))
        return lines

    def get_html(self, options, line_id=None, additional_context=None):
        ctx = self._set_context(options)
        self = self.with_context(ctx)

        templates = self._get_templates()

        render_values = {
            'report': {
                'name': "self._get_report_name()",
                'summary': "report_manager.summary",
                'company_name': self.env.company.name,
            },
            'options': options,
            'context': ctx,
            'model': self,
        }
        if additional_context:
            render_values.update(additional_context)

        # Create lines/headers.
        if line_id:
            headers = options['headers']
            lines = self._get_lines(options, line_id=line_id)
            template = templates['line_template']
        else:
            headers, lines = self._get_table(options)
            options['headers'] = headers
            template = templates['main_template']
        # if options.get('selected_column'):
        #     lines = self._sort_lines(lines, options)
        render_values['lines'] = {'columns_header': headers, 'lines': lines}

        # Render.
        html = self.env.ref(template)._render(render_values)
        # if self.env.context.get('print_mode', False):
        #     for k, v in self._replace_class().items():
        #         html = html.replace(k, v)
            # append footnote as well
            # html = html.replace(b'<div class="js_account_report_footnotes"></div>')
        return html

    def _get_reports_buttons_in_sequence(self):
        return sorted(self._get_reports_buttons(), key=lambda x: x.get('sequence', 9))

    def _get_reports_buttons(self):
        return [
            {'name': _('Export (XLSX)'), 'sequence': 2, 'action': 'print_xlsx', 'file_export_type': _('XLSX')},
            {'name': _('Print (TXT)'), 'sequence': 3, 'action': 'print_txt', 'file_export_type': _('TXT')},
            # {'name': _('SICOSS (TXT)'), 'sequence': 3, 'action': 'print_sicoss_txt', 'file_export_type': _('TXT')},
            {'name': _('SICOSS Movements (TXT)'), 'sequence': 3, 'action': 'print_sicoss_hight', 'file_export_type': _('TXT')},
            {'name': _('SICOSS Hight(TXT)'), 'sequence': 3, 'action': 'print_csv', 'file_export_type': _('CSV')},
        ]

    def _set_context(self, options):
        ctx = self.env.context.copy()
        if not ctx.get('allowed_company_ids') or not options.get('multi_company'):
            ctx['allowed_company_ids'] = self.env.company.ids
        return ctx

    @api.model
    def format_value(self, amount, currency=False, blank_if_zero=False):
        ''' Format amount to have a monetary display (with a currency symbol).
        E.g: 1000 => 1000.0 $

        :param amount:          A number.
        :param currency:        An optional res.currency record.
        :param blank_if_zero:   An optional flag forcing the string to be empty if amount is zero.
        :return:                The formatted amount as a string.
        '''
        currency_id = currency or self.env.company.currency_id
        if currency_id.is_zero(amount):
            if blank_if_zero:
                return ''
            # don't print -0.0 in reports
            amount = abs(amount)

        if self.env.context.get('no_format'):
            return amount
        return formatLang(self.env, amount, currency_obj=currency_id)

    ##################################
    #   REPORTS
    ##################################
    def get_csv(self, options):
        options['sicoss'] = True
        ctx = self.env.context.copy()
        txt_data = self.with_context(ctx)._get_lines(options)
        lines = ''
        for line in txt_data:
            if not line.get('id'):
                continue
            columns = line.get('columns', [])
            array = [''] * 10
            array[0] = str(columns[0]['name'])[:10] if columns[0]['name'] else '0'.zfill(10)
            array[1] = str(columns[1]['name'])[:20] if columns[1]['name'] else '0'.zfill(20)
            array[2] = str(columns[2]['name'])[:25] if columns[2]['name'] else '0'.zfill(25)
            array[3] = str(columns[3]['name'])[:25] if columns[3]['name'] else '0'.zfill(25)
            array[4] = str(columns[4]['name'])[:25] if columns[4]['name'] else '0'.zfill(25)
            array[5] = str(columns[5]['name'])[:15] if columns[5]['name'] else '0'.zfill(15)
            array[6] = str(columns[6]['name'])[:15] if columns[6]['name'] else '0'.zfill(15)
            array[7] = str(columns[7]['name'])[:8] if columns[7]['name'] else '0'.zfill(8)
            array[8] = str(columns[8]['name'])[:8] if columns[8]['name'] else '0'.zfill(8)
            array[9] = str(columns[9]['name'])[:1] if columns[9]['name'] else '0'.zfill(1)
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

    def get_sicoss(self, options):
        options['sicoss'] = True
        ctx = self.env.context.copy()
        txt_data = self.with_context(ctx)._get_lines(options)
        lines = ''
        for line in txt_data:
            if not line.get('id'):
                continue
            columns = line.get('columns', [])
            array = [''] * 16
            array[0] = str(columns[0]['name'])[:10] if columns[0]['name'] else '0'.zfill(6)
            array[1] = columns[7]['name'] if columns[7]['name'] else '0'.zfill(8)
            array[2] = '0'
            array[3] = 'A'
            array[4] = '010'
            array[5] = '1'
            array[6] = '2'
            array[7] = '3'
            array[8] = '0608'
            array[9] = '0579'
            array[10] = '01'
            array[11] = '0'
            array[12] = str(columns[10]['name'])[:8] if columns[10]['name'] else '0'.zfill(8)
            array[13] = '0.00'
            array[14] = '0.00'
            array[15] = str(columns[11]['name'])[:8] if columns[11]['name'] else '0'.zfill(8)
            lines += ','.join(str(d) for d in array) + '\n'
        return lines

    def print_sicoss_hight(self, options):
        ctx = self.env.context.copy()
        options['type_move'] = ctx.get('type', False)
        ctx.update({'sicoss': True})
        options['sicoss'] = True
        return {
            'type': 'ir_actions_employee_report_download',
            'data': {
                'model': self.env.context.get('model'),
                'options': json.dumps(options),
                'output_format': 'sicoss',
                'context': ctx,
                'report_id': self.env.context.get('id')
                }
            }

    def print_txt(self, options):
        return {
            'type': 'ir_actions_employee_report_download',
            'data': {'model': self.env.context.get('model'),
                     'options': json.dumps(options),
                     'output_format': 'txt',
                     'report_id': self.env.context.get('id'),
                     }
            }

    def print_sicoss_txt(self, options):
        ctx = self._set_context(options)
        ctx.update({'sicoss': True})
        options['sicoss'] = True
        options['type_move'] = ctx.get('type', False)
        return {
            'type': 'ir_actions_employee_report_download',
            'data': {'model': self.env.context.get('model'),
                     'options': json.dumps(options),
                     'output_format': 'txt',
                     'report_id': self.env.context.get('id'),
                     }
            }

    def get_txt(self, options):
        ctx = self._set_context(options)
        ctx.update({'no_format': True, 'print_mode': True, 'raise': True, 'print_txt': True})

        return self.with_context(ctx)._txt_export(options)

    def _txt_export(self, options):
        ctx = self._set_context(options)

        txt_data = self.with_context(ctx)._get_lines(options)
        lines = ''
        if options.get('sicoss', False):
            for line in txt_data:
                if not line.get('id'):
                    continue
                columns = line.get('columns', [])
                data = [';'] * 9
                data[0] = columns[0]['name'].zfill(6) if columns[0]['name'] else '0'.zfill(6)
                data[1] = columns[1]['name'] if columns[1]['name'] else '0'.zfill(8)
                data[2] = columns[2]['name']
                data[3] = columns[3]['name']
                data[4] = columns[4]['name'].zfill(3) if columns[4]['name'] else '0'.zfill(3)
                data[5] = columns[5]['name'].zfill(8) if columns[5]['name'] else '0'.zfill(8)
                data[6] = columns[6]['name'].zfill(8) if columns[6]['name'] else '0'.zfill(8)
                data[7] = columns[7]['name'].zfill(8) if columns[7]['name'] else '0'.zfill(8)
                data[8] = columns[8]['name'].zfill(8) if columns[8]['name'] else '0'.zfill(8)

                lines += ''.join(str(d) for d in data) + '\n'
        else:
            for line in txt_data:
                if not line.get('id'):
                    continue
                columns = line.get('columns', [])
                data = [''] * 19
                data[0] = columns[0]['name'].ljust(11) if columns[0]['name'] else ' '.ljust(11)
                data[1] = columns[1]['name'].ljust(11) if columns[1]['name'] else ' '.ljust(11)
                data[2] = columns[2]['name'].ljust(27).replace('Ñ', '#') if columns[2]['name'] else ' '.ljust(27)
                data[3] = columns[3]['name'].ljust(27).replace('Ñ', '#') if columns[3]['name'] else ' '.ljust(27)
                data[4] = columns[4]['name'].ljust(27).replace('Ñ', '#') if columns[4]['name'] else ' '.ljust(27)
                data[5] = "{0:.2f}".format(columns[5]['name']).replace('.','').zfill(6) if columns[5]['name'] else ' '.zfill(6)
                data[6] = ' '.ljust(6)
                data[7] = columns[6]['name'].ljust(1) if columns[6]['name'] else ' '.ljust(1)
                data[8] = columns[7]['name'].ljust(1) if columns[7]['name'] else ' '.ljust(1)
                data[9] = columns[8]['name'].ljust(1) if columns[8]['name'] else ' '.ljust(1)
                data[10] = columns[9]['name'].ljust(8) if columns[9]['name'] else ' '.ljust(8)
                data[11] = columns[10]['name'] if columns[10]['name'] and len(columns[10]['name']) == 3 else '0'.zfill(3)
                data[12] = ' '.ljust(2)
                data[13] = columns[11]['name'].ljust(2) if columns[11]['name'] else ' '.zfill(2)
                data[14] = columns[12]['name'].ljust(5) if columns[12]['name'] and len(columns[12]['name']) == 5 else '0'.zfill(5)
                data[15] = str(columns[13]['name'])[0:10].ljust(10) if columns[13]['name'] else ' '.ljust(10)
                data[16] = ' '.ljust(1)
                data[17] = columns[14]['name'].ljust(18) if columns[14]['name'] else ' '.ljust(18)
                data[18] = '9'.ljust(1)
                lines += ''.join(str(d) for d in data) + '\n'

                # self.env['hr.employee.affiliate.movements'].sudo().browse(int(line['id'])).write({'state': 'approved'})
        # print( lin)
        return lines

    def print_xlsx(self, options):
        return {
                'type': 'ir_actions_employee_report_download',
                'data': {'model': self.env.context.get('model'),
                         'options': json.dumps(options),
                         'output_format': 'xlsx',
                         'report_id': self.env.context.get('id'),
                         }
                }

    def get_xlsx(self, options, response=None):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })
        sheet = workbook.add_worksheet(self._get_report_name()[:31])

        date_default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2, 'num_format': 'yyyy-mm-dd'})
        date_default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'num_format': 'yyyy-mm-dd'})
        default_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        default_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'})
        title_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'bottom': 2})
        level_0_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 6, 'font_color': '#666666'})
        level_1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 13, 'bottom': 1, 'font_color': '#666666'})
        level_2_col1_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_2_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_2_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666'})
        level_3_col1_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666', 'indent': 2})
        level_3_col1_total_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'font_size': 12, 'font_color': '#666666', 'indent': 1})
        level_3_style = workbook.add_format({'font_name': 'Arial', 'font_size': 12, 'font_color': '#666666'})

        #Set the first column width to 50
        sheet.set_column(0, 0, 50)

        y_offset = 0
        headers, lines = self.with_context(no_format=True, print_mode=True, prefetch_fields=False)._get_table(options)

        # Add headers.
        for header in headers:
            x_offset = 0
            for column in header:
                column_name_formated = column.get('name', '').replace('<br/>', ' ').replace('&nbsp;', ' ')
                colspan = column.get('colspan', 1)
                if colspan == 1:
                    sheet.write(y_offset, x_offset, column_name_formated, title_style)
                else:
                    sheet.merge_range(y_offset, x_offset, y_offset, x_offset + colspan - 1, column_name_formated, title_style)
                x_offset += colspan
            y_offset += 1

        if options.get('hierarchy'):
            lines = self._create_hierarchy(lines, options)
        if options.get('selected_column'):
            lines = self._sort_lines(lines, options)

        # Add lines.
        for y in range(0, len(lines)):
            level = lines[y].get('level')
            if lines[y].get('caret_options'):
                style = level_3_style
                col1_style = level_3_col1_style
            elif level == 0:
                y_offset += 1
                style = level_0_style
                col1_style = style
            elif level == 1:
                style = level_1_style
                col1_style = style
            elif level == 2:
                style = level_2_style
                col1_style = 'total' in lines[y].get('class', '').split(' ') and level_2_col1_total_style or level_2_col1_style
            elif level == 3:
                style = level_3_style
                col1_style = 'total' in lines[y].get('class', '').split(' ') and level_3_col1_total_style or level_3_col1_style
            else:
                style = default_style
                col1_style = default_col1_style

            #write the first column, with a specific style to manage the indentation
            cell_type, cell_value = self._get_cell_type_value(lines[y])
            if cell_type == 'date':
                sheet.write_datetime(y + y_offset, 0, cell_value, date_default_col1_style)
            else:
                sheet.write(y + y_offset, 0, cell_value, col1_style)

            #write all the remaining cells
            for x in range(1, len(lines[y]['columns']) + 1):
                cell_type, cell_value = self._get_cell_type_value(lines[y]['columns'][x - 1])
                if cell_type == 'date':
                    sheet.write_datetime(y + y_offset, x + lines[y].get('colspan', 1) - 1, cell_value, date_default_style)
                else:
                    sheet.write(y + y_offset, x + lines[y].get('colspan', 1) - 1, cell_value, style)

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return generated_file

    def _get_cell_type_value(self, cell):
        if 'date' not in cell.get('class', '') or not cell.get('name'):
            # cell is not a date
            return ('text', cell.get('name', ''))
        if isinstance(cell['name'], (float, datetime.date, datetime.datetime)):
            # the date is xlsx compatible
            return ('date', cell['name'])
        try:
            # the date is parsable to a xlsx compatible date
            lg = self.env['res.lang']._lang_get(self.env.user.lang) or get_lang(self.env)
            return ('date', datetime.datetime.strptime(cell['name'], lg.date_format))
        except:
            # the date is not parsable thus is returned as text
            return ('text', cell['name'])

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
