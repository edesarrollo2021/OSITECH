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


class HrContractImport(models.Model):
    _inherit = "hr.employee.import"

    contract_columns = {
        0: {'index': 0, 'name': 'name', 'string': 'Referencia de contrato', 'required': True, 'type': 'string'},
        1: {'index': 1, 'name': 'employee_id', 'string': 'Empleado(Matrícula)', 'required': True, 'type': 'many2one', 'model': 'hr.employee', 'field_domain': 'registration_number'},
        2: {'index': 2, 'name': 'department_id', 'string': 'Departamento', 'required':True, 'type': 'many2one', 'model': 'hr.department', 'field_domain':'name'},
        3: {'index': 3, 'name': 'job_id', 'string': 'Puesto de trabajo', 'required':True, 'type': 'many2one', 'model': 'hr.job', 'field_domain': 'name'},
        4: {'index': 4, 'name': 'structure_type_id', 'string':'Estructura Salarial', 'required':True, 'type':'many2one', 'model': 'hr.payroll.structure.type', 'field_domain':'name'},
        5: {'index': 5, 'name': 'bank_account_id', 'string': 'Cuenta Bancaria', 'required': True, 'type': 'many2one', 'model': 'bank.account.employee', 'field_domain': 'bank_account'},
        6: {'index': 6, 'name': 'contracting_regime', 'string': 'Régimen de contratación', 'required': True, 'type': 'selection', 'model': 'hr.contract'},
        7: {'index': 7, 'name': 'contract_type', 'string': 'Tipo de Contrato', 'required': True, 'type': 'selection', 'model': 'hr.contract'},
        8: {'index': 8, 'name': 'date_start', 'string': 'Fecha de Alta', 'required': True, 'type': 'date'},
        9: {'index': 9, 'name': 'wage', 'string': 'Salario', 'required': True, 'type':'float'},
        10: {'index': 10, 'name': 'variable_salary', 'string': 'Salario variable', 'required': False, 'type': 'float'},
        11: {'index': 11, 'name': 'date_end', 'string': 'Fecha de finalización', 'required': False, 'type': 'date'},
        12: {'index': 12, 'name': 'previous_contract_date', 'string': 'Fecha contrato anterior', 'required': False, 'type': 'date'},
        13: {'index': 13, 'name': 'payment_period', 'string':'Periodo de pago', 'required':False, 'type':'selection', 'model':'hr.contract'},
        14: {'index': 14, 'name': 'training_end_date', 'string': 'Fecha Final de Capacitación', 'required': False, 'type': 'date'},
        15: {'index': 15, 'name': 'monthly_savings_fund', 'string': 'Fondo de Ahorro Mensual', 'required': False, 'type': 'float'},
        16: {'index': 16, 'name': 'seniority_premium', 'string': 'Salario variable', 'required': False, 'type': 'float'},
    }

    def _read_field_float(self, options):
        res = {}
        value = options['field']
        if value:
            try:
                res['value'] = {options['name']: float(value)}
            except:
                res['error'] = self.msg_number_format % (
                    value,
                    options['string'].upper(),
                    options['row']
                )
        else:
            if options['required']:
                res['error'] = self.msg_required % (
                    options['string'].upper(), options['row']
                )
            else:
                res['value'] = {options['name']: 0.0}
        return res

    def _read_file(self):
        res = super(HrContractImport, self)._read_file()
        if self.type == 'contract':
            self._read_contract_xls()
        return res

    def _read_contract_xls(self):
        """ Read file content, using xlrd lib """
        datafile = base64.b64decode(self.file_ids.datas)
        book = xlrd.open_workbook(file_contents=datafile)
        sheets = book.sheet_names()
        sheet = sheets[0]
        rows_to_import = self._read_xls_book(book, sheet)
        rows_to_import = itertools.islice(rows_to_import, 1, None)
        rows_to_import = itertools.islice(rows_to_import, 1, None)
        msg_error = [_('¡Oops!, wrong file: \n')]
        list_contract = []
        for rowx, row in enumerate(rows_to_import, 2):
            contract_type = False
            date_end = False
            training_end_date = False
            for index, field in enumerate(row):
                header = self.get_column(index)
                if header:
                    header['field'] = field
                    header['row'] = str(rowx + 1)
                    vals = getattr(self, '_read_field_' + header['type'])(header)
                    if 'error' in vals:
                        msg_error.append(vals['error'])
                    else:
                        if header['name'] == 'contract_type':
                            contract_type = vals['value'].get('contract_type', False)
                        if header['name'] == 'date_end':
                            try:
                                date_end = fields.Date.to_date(vals['value'].get('date_end', False))
                            except:
                                msg_error.append(self.msg_date_format % (
                                    header['field'],
                                    header['string'].upper(),
                                    header['row']
                                ))
                        if header['name'] == 'training_end_date':
                            try:
                                training_end_date = fields.Date.to_date(vals['value'].get('training_end_date', False))
                            except:
                                msg_error.append(self.msg_date_format % (
                                    header['field'],
                                    header['string'].upper(),
                                    header['row']
                                ))
                        if header['name'] == 'employee_id':
                            employee_id = vals['value']['employee_id']
                            if employee_id.contract_id and employee_id.contract_id.state == 'open':
                                msg_error.append(self.msg_contract_unique % (
                                    field,
                                    header['string'].upper(),
                                    header['row']
                                ))

            if contract_type == '03' and not date_end:
                msg_error.append(self.msg_required % (
                    'Fecha de finalización',
                    str(rowx + 1)
                ))
            if contract_type == '06' and not training_end_date:
                msg_error.append(self.msg_required % (
                    'Fecha Final de Capacitación',
                    str(rowx + 1)
                ))

        if len(msg_error) > 1:
            msg_raise = "".join(msg_error)
            raise ValidationError(_(msg_raise))
        else:
            self.read_file = True

class EmployeeStmtImportXLS(models.TransientModel):
    _inherit = 'base_import.import'

    def parse_preview(self, options, count=10):
        if options.get('contract_stmt_import', False):
            self = self.with_context(contract_stmt_import=True)
        return super(EmployeeStmtImportXLS, self).parse_preview(options, count=count)

    def do(self, fields, columns, options, dryrun=False):
        if options.get('contract_stmt_import', False):
            self._cr.execute('SAVEPOINT import_contract_stmt')
            res = super(EmployeeStmtImportXLS, self.with_context(employee_import=True)).do(fields, columns, options, dryrun=dryrun)

            try:
                if dryrun:
                    self._cr.execute('ROLLBACK TO SAVEPOINT import_contract_stmt')
                else:
                    self._cr.execute('RELEASE SAVEPOINT import_contract_stmt')
                    res['messages'].append({
                        'import_contract_stmt': True,
                        })
            except psycopg2.InternalError:
                pass
            return res
        else:
            return super(EmployeeStmtImportXLS, self).do(fields, columns, options, dryrun=dryrun)

    @api.model
    def get_fields(self, model, depth=FIELDS_RECURSION_LIMIT):
        """ Recursively get fields for the provided model (through
        fields_get) and filter them according to importability

        The output format is a list of ``Field``, with ``Field``
        defined as:

        .. class:: Field

            .. attribute:: id (str)

                A non-unique identifier for the field, used to compute
                the span of the ``required`` attribute: if multiple
                ``required`` fields have the same id, only one of them
                is necessary.

            .. attribute:: name (str)

                The field's logical (Odoo) name within the scope of
                its parent.

            .. attribute:: string (str)

                The field's human-readable name (``@string``)

            .. attribute:: required (bool)

                Whether the field is marked as required in the
                model. Clients must provide non-empty import values
                for all required fields or the import will error out.

            .. attribute:: fields (list(Field))

                The current field's subfields. The database and
                external identifiers for m2o and m2m fields; a
                filtered and transformed fields_get for o2m fields (to
                a variable depth defined by ``depth``).

                Fields with no sub-fields will have an empty list of
                sub-fields.

        :param str model: name of the model to get fields form
        :param int depth: depth of recursion into o2m fields
        """
        Model = self.env[model]
        importable_fields = [{
            'id': 'id',
            'name': 'id',
            'string': _("External ID"),
            'required': False,
            'fields': [],
            'type': 'id',
        }]
        if not depth:
            return importable_fields

        model_fields = Model.fields_get()
        blacklist = models.MAGIC_COLUMNS + [Model.CONCURRENCY_CHECK_FIELD]
        if not self._context.get('contract_stmt_import', False):
            if model == 'hr.contract':
                blacklist += ['wage', 'hourly_wage', 'daily_salary', 'integral_salary']
        for name, field in model_fields.items():
            if name in blacklist:
                continue
            # an empty string means the field is deprecated, @deprecated must
            # be absent or False to mean not-deprecated
            if field.get('deprecated', False) is not False:
                continue
            if field.get('readonly'):
                states = field.get('states')
                if not states:
                    continue
                # states = {state: [(attr, value), (attr2, value2)], state2:...}
                if not any(attr == 'readonly' and value is False
                           for attr, value in itertools.chain.from_iterable(states.values())):
                    continue
            field_value = {
                'id': name,
                'name': name,
                'string': field['string'],
                # Y U NO ALWAYS HAS REQUIRED
                'required': bool(field.get('required')),
                'fields': [],
                'type': field['type'],
            }

            if field['type'] in ('many2many', 'many2one'):
                field_value['fields'] = [
                    dict(field_value, name='id', string=_("External ID"), type='id'),
                    dict(field_value, name='.id', string=_("Database ID"), type='id'),
                ]
            elif field['type'] == 'one2many':
                field_value['fields'] = self.get_fields(field['relation'], depth=depth - 1)
                if self.user_has_groups('base.group_no_one'):
                    field_value['fields'].append(
                        {'id': '.id', 'name': '.id', 'string': _("Database ID"), 'required': False, 'fields': [],
                         'type': 'id'})

            importable_fields.append(field_value)

        # TODO: cache on model?
        return importable_fields
