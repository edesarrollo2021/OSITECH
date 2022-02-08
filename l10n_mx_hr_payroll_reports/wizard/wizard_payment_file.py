# -*- coding: utf-8 -*-

# from datetime import datetime, date, time

import io
import base64
import logging

from xlsxwriter.utility import xl_rowcol_to_cell

from odoo import api, fields, models, _
from odoo.tools.misc import xlsxwriter
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SPC_STR2 = {
    '(':' ', ')':' ', ',':' ', '°':' ', "'":' ', '!':' ', '#':' ',
    '%':' ', '=':' ', '?':' ', '¿':' ', '¡':' ', '*':' ', '{':' ',
    '}':' ', '[':' ', ']':' ', '>':' ', '<':' ', ';':' ', ':':' ',
    '+':' ', '&':' ', '|':' ', 'Ö':'O', 'Ü':'U', '.':' ', '_':' ',
    'Á':'A', 'É':'E', 'Í':'I', 'Ó':'O', 'Ú':'U', '-':' ', '/':' ', 'Ñ':'N',

}


class WizardPaymentPayroll(models.TransientModel):
    _name = 'wizard.payment.file'
    _description = 'Bank Dispersion'

    @api.model
    def default_get(self, fields):
        result = super(WizardPaymentPayroll, self).default_get(fields)
        if self._context.get('active_id'):
            active_id = int(self._context['active_id'])
            result['payslip_run_id'] = active_id
        return result

    payslip_run_id = fields.Many2one('hr.payslip.run',
        string='Payslip Batches', readonly=True)
    bank_id = fields.Many2one('res.bank', "Bank", required=True)
    bank_code = fields.Char(string="Bank Code",
        related='bank_id.l10n_mx_edi_code', store=True, readonly=True)
    account_type = fields.Selection([
        ('001', 'Account'),
        ('040', 'CLABE'),
        ('003', 'Debit'),
        ('099', 'Check'),
    ], "Account type", required=False)

    def replace_str2(self, name):
        if name:
            name = name.upper()
            for string in name:
                if string in SPC_STR2:
                    name = name.replace(string, SPC_STR2.get(string))
        return name

    def export_report(self):
        if self.bank_code == '014' and self.account_type == '001':
            return self.report_santander_to_santander()
        else:
            raise UserError(_('Bank %s does not have a layout available') % self.bank_id.name)

    @api.model
    def _get_query_payslip_line(self, domain=None):
        where_clause = domain or "1=1"
        select = """
            SELECT
                employee.id as employee_id,
                line.total as total,
                employee.registration_number as employee_code,
                employee.last_name as last_name,
                employee.mothers_last_name as mothers_last_name,
                employee.name as employee_name,
                bank_emp.bank_account as bank_account,
                bank_emp.account_type as account_type,
                bank.bic as bank,
                struct.name as struct
            FROM hr_payslip_line line
            JOIN hr_payslip slip ON line.slip_id = slip.id
            JOIN hr_payroll_structure struct ON slip.struct_id = struct.id
            JOIN hr_salary_rule rule ON line.salary_rule_id = rule.id
            JOIN hr_contract contract ON line.contract_id = contract.id
            JOIN hr_employee employee ON line.employee_id = employee.id
            JOIN bank_account_employee bank_emp ON contract.bank_account_id = bank_emp.id
            JOIN res_bank bank ON bank_emp.bank_id = bank.id
            WHERE %s
                AND line.total > 0 AND rule.code = 'T001'
                AND slip.state = 'done'
        """
        # 2.Fetch data from DB
        select = select % (where_clause)
        self.env.cr.execute(select)
        results = self.env.cr.dictfetchall()
        return results

    def _prepare_data(self, domain=None):
        results = self._get_query_payslip_line(domain=domain)
        if not results:
            raise UserError(_("Data Not Found"))
        groupby_employees = {}

        for res in results:
            employee_name = '%s %s %s' % (res['last_name'], res.get('mothers_last_name', ''), res['employee_name'])
            groupby_employees.setdefault(res['employee_id'], {
                'code': res['employee_code'],
                'last_name': res['last_name'],
                'name': res['employee_name'],
                'mothers_last_name': res['mothers_last_name'],
                'employee_name': employee_name.replace('None ', ''),
                'bank_account': res['bank_account'],
                'bank': res['bank'],
                'struct': res['struct'],
                'total': res['total'],
            })
        return groupby_employees

    #######################################
    # Methods Banks Santander to Santander
    #######################################
    def report_santander_to_santander(self):
        report = 'LOE Supernomina'
        _logger.info("Layout Dispersion: " + report)
        domain = "slip.payslip_run_id = %s AND bank_emp.bank_id = %s AND bank_emp.account_type = '%s'" % (
            str(self.payslip_run_id.id), str(self.bank_id.id), str(self.account_type)
        )
        data = self._prepare_data(domain)
        today = fields.Date.context_today(self).strftime('%m%d%Y')
        account = '65501427093'
        payment_date = self.payslip_run_id.payment_date.strftime('%m%d%Y').zfill(8)
        # if not account or len(account) != 11:
        #     raise UserError('Formato de cuenta de la empresa incorrecto, debe ser de (11) dígitos.')

        content = '100001E%s%s%s%s\n' % (today, account, ' '.ljust(5), payment_date)
        val = 2
        count = 2
        total = 0
        for line in data:
            total += data[line]['total']
            last_name = self.replace_str2(data[line]['last_name'] or ' ')
            mothers_last_name = self.replace_str2(data[line]['mothers_last_name'] or ' ')
            name = self.replace_str2(data[line]['name'] or ' ')
            content += '%s%s%s%s%s%s%s\n' % (
                '%s%s' % (val, str(count).zfill(5)),
                data[line]['code'][0:7].ljust(7),
                last_name[0:30].ljust(30),
                mothers_last_name[0:20].ljust(20),
                name[0:30].ljust(30),
                data[line]['bank_account'][0:16].ljust(16),
                str("{0:.2f}".format(data[line]['total'])).replace('.', '').zfill(18),
            )
            count += 1
        val += 1
        count2 = count - 2
        content += '%s%s%s%s' % (
            val,
            str(count).zfill(5),
            str(count2).zfill(5),
            str("{0:.2f}".format(total)).replace('.', '').zfill(18)
        )
        file_name = 'DISPERISION-%s-%s' % (self.payslip_run_id.name.upper(), fields.Datetime.now())
        output = base64.encodebytes(bytes(content, 'utf-8'))
        file_id = self.env['wizard.file.download'].create({
            'file': output,
            'name': file_name + '.txt'
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

    def _prepare_payment_data(self, domain=None):
        results = self._get_query_payslip_line(domain=domain)
        if not results:
            raise UserError(_("Data Not Found"))
        groupby_employees = {}

        for res in results:
            employee_name = '%s %s %s' % (res['last_name'], res.get('mothers_last_name', ''), res['employee_name'])
            if res['bank'] == self.bank_id.bic:
                bank = 'TRANSFERENCIA - %s' % res['bank']
            elif res['account_type'] == '099':
                bank = 'CHEQUE'
            else:
                bank = 'DEPOSITOS'
            groupby_employees.setdefault(bank, {}).setdefault(res['employee_id'], {
                'code': res['employee_code'],
                'last_name': res['last_name'],
                'name': res['employee_name'],
                'mothers_last_name': res['mothers_last_name'],
                'employee_name': employee_name.replace('None ', ''),
                'bank_account': res['bank_account'],
                'bank': res['bank'],
                'struct':res['struct'],
                'total': res['total'],
            })
        return groupby_employees

    def payment_report(self):
        if self.bank_code != '014':
            raise UserError(_('Bank %s does not have a layout available') % self.bank_id.name)
        domain = "slip.payslip_run_id = %s" % (
            str(self.payslip_run_id.id),
        )
        data = self._prepare_payment_data(domain=domain)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory':True})
        num_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "0"??_);_(@'
        header_format = workbook.add_format(
            {'bold':True, 'bg_color':'#100D57', 'font_color':'#FFFFFF',
             'border':1, 'top':1, 'font_size': 9, 'align':'center',
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
            {'sequence': 0.01, 'name': 'TIPO NÓMINA', 'larg': 10},
            {'sequence': 0.02, 'name': 'ID', 'larg': 5},
            {'sequence': 0.03, 'name': 'CUENTA DE ABONO', 'larg': 20},
            {'sequence': 0.04, 'name': 'BANCO RECEPTOR', 'larg': 20},
            {'sequence': 0.05, 'name': 'BENEFICIARIO', 'larg': 30},
            {'sequence': 0.06, 'name': 'IMPORTE TOTAL', 'larg': 10},
        ]

        def _write_sheet_header(sheet, data=None):
            row_count = 3
            main_col_count = 0
            # sheet.merge_range(row, col + 2, row, 4 + 1, self.env.company.name, report_format)
            sheet.merge_range('C1:D1', self.env.company.name, report_format)
            sheet.merge_range('C2:D2', self.payslip_run_id.name, report_format)
            sheet.set_row(row_count, 60, )
            # Step 1: writing col group headers
            for head_col in header:
                sheet.set_column(1000, main_col_count, 20)
                sheet.write(row_count, main_col_count,head_col['name'].replace(' ', '\n'), header_format)
                main_col_count += 1

            for employee in data:
                main_col_count = 0
                row_count += 1
                sheet.write(row_count, main_col_count, data[employee]['struct'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, data[employee]['code'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, data[employee]['bank_account'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, data[employee]['bank'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, data[employee]['employee_name'], report_format)
                main_col_count += 1
                sheet.write(row_count, main_col_count, data[employee]['total'], currency_format)
                main_col_count += 1
            # Step: Sum Total
            start_range = xl_rowcol_to_cell(4, 5)
            end_range = xl_rowcol_to_cell(len(data) + 4, 5)
            fila_formula = xl_rowcol_to_cell(1, 5)
            formula = "=SUM({:s}:{:s})".format(start_range, end_range)
            sheet.write_formula(fila_formula, formula, formula_format, True)

        if data:
            for res in data:
                sheet = workbook.add_worksheet(res)
                _write_sheet_header(sheet, data=data[res])

        # Step Last: Close File and create on wizard
        workbook.close()
        file_name = 'DISPERISION-%s-%s' % (self.payslip_run_id.name.upper(), fields.Datetime.now())
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

