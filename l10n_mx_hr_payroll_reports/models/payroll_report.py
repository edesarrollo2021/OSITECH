# -*- coding: utf-8 -*-

from odoo.tools.misc import xlsxwriter
from odoo import models, fields, api, _, _lt


class IrActionsPayrollReportDownload(models.AbstractModel):
    # This model is a a hack: it's sole purpose is to override _get_readable_fields
    # of ir.actions.actions to add the 'data' field which, as explained below, contains the
    # necessary parameters for report generation.
    # The reason why we don't extend the ir.actions.actions is because it's not really meant to be
    # extended outside of the base module, the risk being completely destroying the client's db.
    # If you plan on modifying this model, think of reading odoo/enterprise#13820 and/or contact
    # the metastorm team.
    _name = 'ir_actions_hr_payroll_report_mx'
    _description = 'Technical model for Employees report downloads'

    def _get_readable_fields(self):
        # data is not a stored field, but is used to give the parameters to generate the report
        # We keep it this way to ensure compatibility with the way former version called this action.
        return self.env['ir.actions.actions']._get_readable_fields() | {'data'}


class PayrollReport(models.AbstractModel):
    _name = "hr.payroll.report.mx"
    _description = "Payroll Analysis Report"
    _inherit = "account.report"


    # MAX_LINES = 80
    filter_multi_company = True
    filter_unfold_all = None
    filter_hierarchy = True
    filter_structure = True
    filter_date = {'mode': 'range', 'filter': 'this_month'}

    @api.model
    def _get_templates(self):
        templates = super(PayrollReport, self)._get_templates()
        templates['search_template'] = 'l10n_mx_hr_payroll_reports.search_template'
        templates['main_template'] = 'account_reports.main_template_with_filter_input_partner'
        return templates

    @api.model
    def _get_filter_structure(self):
        return self.env['hr.payroll.structure'].with_context(active_test=False).search([], order="id, name")

    @api.model
    def _init_filter_structure(self, options, previous_options=None):
        if self.filter_structure is None:
            return
        if previous_options and previous_options.get('structures'):
            structures_map = dict((opt['id'], opt['selected']) for opt in previous_options['structures'] if opt['selected'])
        else:
            structures_map = {}
        options['structure'] = True
        options['structures'] = []
        for struct in self._get_filter_structure():
            options['structures'].append({
                'id': struct.id,
                'name': struct.name,
                # 'code': struct.code,
                'type': struct.payroll_type,
                'selected': structures_map.get(struct.id, False)
            })

    @api.model
    def _get_options_structures(self, options):
        return [
            struct for struct in options.get('structures', []) if struct['selected']
        ]

    @api.model
    def _get_options_structures_domain(self, options):
        # Make sure to return an empty array when nothing selected to handle archived journals.
        selected_structures = self._get_options_structures(options)
        print('sdsdsdsselected_structuresdd')
        print(selected_structures)
        print('sdsdsdsselected_structuresdd')
        # return selected_structures and [  ('slip_id.structure_id', 'in', [j['id'] for j in selected_structures])] or []
        return selected_structures and [j['id'] for j in selected_structures] or []

    def _get_columns_name(self, options):
        select_struct_ids = self._get_options_structures_domain(options)
        domain = [('print_to_excel', '=', True)]
        if select_struct_ids:
            domain += [('struct_id', 'in', select_struct_ids)]
        columns = [
            {'name': _('No. Empleado')},
            {'name': _('Empleado')},
            {'name': 'CURP'},
            {'name': 'RFC'},
            {'name': 'No. SS'},
            {'name': _('C. Costo')},
            {'name': _('Department')},
            {'name': _('Job Position')},
        ]
        salary_ids = self.env['hr.salary.rule'].search(domain, order="struct_id, sequence")
        for salary in salary_ids:
            columns.append(
                {'name': salary.name, 'class': 'number'}
            )
        print('salaryRule')
        print('salary_rule')
        print(self.env.context)
        print('salary_rule')
        # tables, where_clause, where_params = self.env['hr.payslip.line'].with_context(strict_range=True)._query_get()
        # print(tables, where_clause, where_params)
        print('salaryRule')
        print('salaryRule')


        return columns

    @api.model
    def _get_report_name(self):
        return _('Payroll Concepts')

    @api.model
    def _query_get(self, options, domain=None):
        date_from = self.env.context.get('date_from')
        date_to = self.env.context.get('date_to')
        new_domain = [
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
        ]
        select_struct_ids = self._get_options_structures_domain(options)
        if select_struct_ids:
            new_domain += [('slip_id.struct_id', 'in', select_struct_ids)]

        domain = domain or [] + new_domain
        self.env['hr.payslip.line'].check_access_rights('read')

        query = self.env['hr.payslip.line']._where_calc(domain)

        # Wrap the query with 'company_id IN (...)' to avoid bypassing company access rights.
        # self.env['hr.payslip.line']._apply_ir_rules(query)
        tables, where_clause, where_params = query.get_sql()
        return tables, where_clause, where_params

    @api.model
    def _get_lines(self, options, line_id=None):
        # 1.Build SQL query
        lines = []
        convert_date = self.env['ir.qweb.field.date'].value_to_html

        select = """
            SELECT to_char("hr_payslip_line".date_from, 'MM') as month,
                   to_char("hr_payslip_line".date_from, 'YYYY') as yyyy,
                   COALESCE(SUM("hr_payslip_line".total), 0) as total,
                   rule.id as rule_id,
                   rule.code as rule_code,
                   employee.id as employee_id,
                   employee.complete_name as employee_name, 
                   employee.registration_number as employee_code,
                   dep.name as dep_name, 
                   cc.code as cc_code,
                   job.name job_name
            FROM %s, hr_salary_rule rule, hr_payslip slip, hr_employee employee, hr_department dep, hr_cost_center cc, hr_job job
            WHERE  %s
              AND "hr_payslip_line".slip_id = slip.id
              AND "hr_payslip_line".salary_rule_id = rule.id
              AND "hr_payslip_line".employee_id = employee.id
              AND employee.cost_center_id = cc.id
              AND employee.department_id = dep.id
            GROUP BY month, yyyy, slip.id, employee.id, dep.id, cc.id, job.id, rule.id
            ORDER BY slip.id, yyyy, month
            --LIMIT 10
        """
        domain = []
        tables, where_clause, where_params = self._query_get(options, domain=domain)
        # tables, where_clause, where_params = self.env[
        #     'account.move.line'].with_context(strict_range=True)._query_get()
        # line_model = None
        # if line_id:
        #     split_line_id = line_id.split('_')
        #     line_model = split_line_id[0]
        #     model_id = split_line_id[1]
        #     where_clause += line_model == 'account' and ' AND account_id = %s AND j.id = %s' or ' AND j.id = %s'
        #     where_params += [str(model_id)]
        #     if line_model == 'account':
        #         where_params += [str(split_line_id[
        #                                  2])]  # We append the id of the parent journal in case of an account line
        #
        # # 2.Fetch data from DB
        select = select % (tables, where_clause)
        self.env.cr.execute(select, where_params)
        results = self.env.cr.dictfetchall()
        print('results')
        print('results')
        print(results)
        print('results')
        print('results')
        print('results')
        if not results:
            return lines
        groupby_employees = {}
        for res in results:
            print(res)
            groupby_employees.setdefault(res['employee_id'], {}).setdefault('lines', [])
            groupby_employees[res['employee_id']]['lines'].append(res)
            lines.append({
                'id': res['employee_id'],
                'name': res['employee_name'],
                # 'title_hover':name,
                # 'columns':columns,
                'unfoldable':False,
                # 'caret_options':'account.account',
                # 'class':'o_account_searchable_line o_account_coa_column_contrast',
            })
        print('groupby_employees')
        print('groupby_employees')
        print(groupby_employees)
        print('groupby_employees')
        print('groupby_employees')
        print('results')
        # # 3.Build report lines
        # current_account = None
        # current_journal = line_model == 'account' and results[0][
        #     'journal_id'] or None  # If line_id points toward an account line, we don't want to regenerate the parent journal line
        # for values in results:
        #     if values['journal_id'] != current_journal:
        #         current_journal = values['journal_id']
        #         lines.append(
        #             self._get_journal_line(options, current_journal, results,
        #                                    values))
        #
        #     if self._need_to_unfold('journal_%s' % (current_journal,),
        #                             options) and values[
        #         'account_id'] != current_account:
        #         current_account = values['account_id']
        #         lines.append(self._get_account_line(options, current_journal,
        #                                             current_account, results,
        #                                             values))
        #
        #     # If we need to unfold the line
        #     if self._need_to_unfold('account_%s_%s' % (
        #     values['account_id'], values['journal_id']), options):
        #         vals = {
        #             'id':'month_%s__%s_%s_%s' % (
        #             values['journal_id'], values['account_id'],
        #             values['month'], values['yyyy']),
        #             'name':convert_date(
        #                 '%s-%s-01' % (values['yyyy'], values['month']),
        #                 {'format':'MMM yyyy'}),
        #             'caret_options':True,
        #             'level':4,
        #             'parent_id':"account_%s_%s" % (
        #             values['account_id'], values['journal_id']),
        #             'columns':[{'name':n} for n in
        #                        [self.format_value(values['debit']),
        #                         self.format_value(values['credit']),
        #                         self.format_value(values['balance'])]],
        #         }
        #         lines.append(vals)
        #
        # # Append detail per month section
        # if not line_id:
        #     lines.extend(self._get_line_total_per_month(options, values['company_id'], results))
        return lines
