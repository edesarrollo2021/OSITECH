# -*- coding: utf-8 -*-

import base64
import itertools
import operator
import datetime
import logging
import psycopg2

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, pycompat

try:
    import xlrd
    try:
        from xlrd import xlsx
    except ImportError:
        xlsx = None
except ImportError:
    xlrd = xlsx = None

FIELDS_RECURSION_LIMIT = 3

_logger = logging.getLogger(__name__)


class InputsImport(models.Model):
    _inherit = "hr.employee.import"

    type = fields.Selection(selection_add=[('input', 'Inputs')])

    inputs_colums = {
        0: {'index': 0, 'name': 'employee_id', 'string': 'Empleado(Matrícula)', 'required': True, 'type': 'many2one', 'model': 'hr.employee', 'field_domain': 'registration_number'},
        1: {'index': 1, 'name': 'input_id', 'string': 'Entrada', 'required': True, 'type': 'many2one', 'model': 'hr.payslip.input.type', 'field_domain': 'code'},
        2: {'index': 2, 'name': 'payroll_period_id', 'string': 'Periodo de Nómina', 'required': True, 'type': 'many2one', 'model': 'hr.payroll.period', 'field_domain': 'code'},
        3: {'index': 3, 'name': 'amount', 'string': 'Valor/Importe', 'required': True, 'type': 'float'},
        4: {'index': 4, 'name': 'date', 'string': 'Fecha', 'required': False, 'type': 'date'},
    }

    def get_column(self, index):
        res = super(InputsImport, self).get_column(index)
        if self.type == 'input':
            if index in self.inputs_colums:
                return self.inputs_colums[index]
            else:
                return None
        return res

    def _read_file(self):
        res = super(InputsImport, self)._read_file()
        if self.type == 'input':
            self._read_inputs_xls()
        return res

    def _read_inputs_xls(self):
        """ Read file content, using xlrd lib """
        datafile = base64.b64decode(self.file_ids.datas)
        book = xlrd.open_workbook(file_contents=datafile)
        sheets = book.sheet_names()
        sheet = sheets[0]
        rows_to_import = self._read_xls_book(book, sheet)
        rows_to_import = itertools.islice(rows_to_import, 1, None)
        rows_to_import = itertools.islice(rows_to_import, 1, None)
        msg_error = [_('¡Oops!, wrong file: \n')]
        for rowx, row in enumerate(rows_to_import, 2):
            date = False
            need_date = False
            for index, field in enumerate(row):
                header = self.get_column(index)
                if header:
                    header['field'] = field
                    header['row'] = str(rowx + 1)
                    vals = getattr(self, '_read_field_' + header['type'])(header)
                    if 'error' in vals:
                        msg_error.append(vals['error'])
                    else:
                        if header['name'] == 'date':
                            try:
                                date = fields.Date.to_date(vals['value'].get('date', False))
                            except:
                                msg_error.append(self.msg_date_format % (
                                    header['field'],
                                    header['string'].upper(),
                                    header['row']
                                ))
                        if header['name'] == 'input_id':
                            need_date = self.env['hr.payslip.input.type'].search([('code', '=', field)], limit=1).requires_date

            if need_date and not date:
                msg_error.append(self.msg_required % (
                    'Fecha',
                    str(rowx + 1)
                ))

        if len(msg_error) > 1:
            msg_raise = "".join(msg_error)
            raise ValidationError(_(msg_raise))
        else:
            self.read_file = True

    def import_file(self):
        ctx = dict(self.env.context)
        if self.type == 'employee':
            model = 'hr.employee'
            tag = 'import_employee_stmt'

        if self.type == 'contract':
            model = 'hr.contract'
            tag = 'import_contract_stmt'

        if self.type == 'input':
            model = 'hr.inputs'
            tag = 'import_input_stmt'
        import_wizard = self.env['base_import.import'].create({
            'res_model': model,
            'file': base64.b64decode(self.file_ids.datas),
            'file_name': self.file_ids.name,
            'file_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        ctx['wizard_id'] = import_wizard.id
        self.read_file = False
        return {
            'type': 'ir.actions.client',
            'tag': tag,
            'params': {
                'model': model,
                'context': ctx,
                'filename': self.file_ids.name,
            }
        }


class InputsStmtImportXLS(models.TransientModel):
    _inherit = 'base_import.import'

    def parse_preview(self, options, count=10):
        if options.get('input_stmt_import', False):
            self = self.with_context(input_stmt_import=True)
        return super(InputsStmtImportXLS, self).parse_preview(options, count=count)

    def do(self, fields, columns, options, dryrun=False):
        if options.get('input_stmt_import', False):
            self._cr.execute('SAVEPOINT import_input_stmt')
            res = super(InputsStmtImportXLS, self.with_context(employee_import=True)).do(fields, columns, options, dryrun=dryrun)

            try:
                if dryrun:
                    self._cr.execute('ROLLBACK TO SAVEPOINT import_input_stmt')
                else:
                    self._cr.execute('RELEASE SAVEPOINT import_input_stmt')
                    res['messages'].append({
                        'import_input_stmt': True,
                        })
            except psycopg2.InternalError:
                pass
            return res
        else:
            return super(InputsStmtImportXLS, self).do(fields, columns, options, dryrun=dryrun)
