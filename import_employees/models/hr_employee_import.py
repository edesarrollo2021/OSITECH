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

_logger = logging.getLogger(__name__)

class HrEmployeeImport(models.Model):
    _name = "hr.employee.import"
    _description = "Import Employees"
    _rec_name = "file_name"

    file_ids = fields.Many2many(string='Select Layout',
        comodel_name='ir.attachment', required=True)
    file_name = fields.Char('Nombre del archivo', related='file_ids.name')
    read_file = fields.Boolean('Read File', default=False)
    type = fields.Selection([
        ('employee', 'Employee'),
        ('contract', 'Contract'),
    ], string='Type', required=False)

    colums = {
        0: {'index': 0, 'name': 'name', 'string': 'Nombre del Empleado', 'required': True, 'type': 'string', 'data': 'employee'}, # Work Inf
        1: {'index': 1, 'name': 'last_name', 'string': 'Apellido Paterno', 'required': True, 'type': 'string', 'data': 'employee'},
        2: {'index': 2, 'name': 'mothers_last_name', 'string': 'Apellido Materno', 'required': False, 'type': 'string', 'data': 'employee'},
        3: {'index': 3, 'name': 'registration_number', 'string': 'No. de Empleado', 'required': None, 'type': 'string', 'data': 'employee'},
        4: {'index': 4, 'name': 'rfc', 'string': 'RFC', 'required': True, 'type': 'string', 'data': 'employee'},
        5: {'index': 5, 'name': 'curp', 'string': 'CURP', 'required': True, 'type': 'string', 'data': 'employee'},
        6: {'index': 6, 'name': 'ssnid', 'string': 'Nº Seguridad Social', 'required': True, 'type': 'string', 'data': 'employee'},
        7: {'index': 7, 'name': 'state_isn_id', 'string': 'Estación(ISN)', 'required': True, 'type': 'many2one', 'model': 'res.country.state.isn', 'field_domain': 'name', 'data': 'employee'},
        8: {'index': 8, 'name': 'department_id', 'string': 'Departamento', 'required': True, 'type': 'many2one', 'model': 'hr.department', 'field_domain': 'name', 'data': 'employee'},
        9: {'index': 9, 'name': 'job_id', 'string': 'Puesto de trabajo', 'required': True, 'type': 'many2one', 'model': 'hr.job', 'field_domain': 'name', 'data': 'employee'},
        10: {'index': 10, 'name': 'position_id', 'string': 'Plaza', 'required': True, 'type': 'many2one', 'model': 'hr.job.position', 'field_domain': 'name', 'data': 'employee'},
        11: {'index': 11, 'name': 'work_email', 'string': 'Correo electrónico laboral', 'required': True, 'type': 'string', 'data': 'employee'},
        12: {'index': 12, 'name': 'work_phone', 'string': 'Teléfono laboral', 'required': False, 'type': 'string', 'data': 'employee'},
        13: {'index': 13, 'name': 'company_id', 'string': 'Compañía', 'required': True, 'type': 'many2one', 'model': 'res.company', 'field_domain': 'name', 'data': 'employee'},
        14: {'index': 14, 'name': 'employer_register_id', 'string': 'Registro Patronal', 'required': True, 'type': 'many2one', 'model': 'res.employer.register', 'field_domain': 'employer_registry', 'data': 'employee'},
        15: {'index': 15, 'name': 'resource_calendar_id', 'string': 'Horas laborales', 'required': True, 'type': 'many2one', 'model': 'resource.calendar', 'field_domain': 'name', 'data': 'employee'},
        16: {'index': 16, 'name': 'antiquity_id', 'string': 'Tabla de Factor', 'required': True, 'type': 'many2one', 'model': 'hr.table.antiquity', 'field_domain': 'name', 'data': 'employee'},
        17: {'index': 17, 'name': 'salary_type', 'string': 'Tipo de salario', 'required': False, 'type': 'selection', 'model': 'hr.employee', 'data': 'employee'},
        18: {'index': 18, 'name': 'working_day_week', 'string': 'Turno semanal', 'required': False, 'type': 'selection', 'data': 'employee'},
        19: {'index': 19, 'name': 'type_working_day', 'string': 'Tipo jornada Laboral', 'required': False, 'type': 'selection', 'data': 'employee'},
        20: {'index': 20, 'name': 'type_worker', 'string': 'Tipo de trabajador', 'required': False, 'type': 'selection', 'data': 'employee'},
        21: {'index': 21, 'name': 'deceased', 'string': '¿Fallecido?', 'required': False, 'type': 'boolean', 'data': 'employee'},
        22: {'index': 22, 'name': 'syndicalist', 'string': '¿Sindicalista?', 'required': False, 'type': 'boolean', 'data': 'employee'},
        23: {'index': 23, 'name': 'pay_extra_hours', 'string': '¿Pagar horas extra?', 'required': False, 'type': 'boolean', 'data': 'employee'},
        24: {'index': 24, 'name': 'isr_adjustment', 'string': '¿Aplicar ISR Anual?', 'required': False, 'type': 'boolean', 'data': 'employee'},
        25: {'index': 25, 'name': 'payment_holidays_bonus', 'string': 'Pago de prima de vacaciones', 'required': False, 'type': 'selection', 'data': 'employee'},
        26: {'index': 26, 'name': 'country_id', 'string': 'Nacionalidad (País)', 'required': False, 'type': 'many2one', 'model': 'res.country', 'field_domain': 'name', 'data': 'employee'},
        27: {'index': 27, 'name': 'passport_id', 'string': 'Nº Pasaporte', 'required': False, 'type': 'string', 'data': 'employee'},
        28: {'index': 28, 'name': 'blood_type', 'string': 'Tipo de Sangre', 'required': False, 'type': 'selection', 'data': 'employee'},
        29: {'index': 29, 'name': 'gender', 'string': 'Género', 'required': True, 'type': 'selection', 'data': 'employee'},
        30: {'index': 30, 'name': 'birthday', 'string': 'Fecha de nacimiento', 'required': False, 'type': 'date', 'data': 'employee'},
        31: {'index': 31, 'name': 'country_of_birth', 'string': 'País de nacimiento', 'required': True, 'type': 'many2one', 'model': 'res.country', 'field_domain': 'name', 'data': 'employee'},
        32: {'index': 32, 'name': 'place_of_birth', 'string': 'Lugar de nacimiento', 'required': True, 'type': 'many2one', 'model': 'res.country.state', 'field_domain': 'name', 'data': 'employee'},
        33: {'index': 33, 'name': 'children', 'string': 'Número de hijos', 'required': False, 'type': 'integer', 'data': 'employee'},
        34: {'index': 34, 'name': 'marital', 'string': 'Estado civil', 'required': True, 'type': 'selection', 'data': 'employee'},
        35: {'index': 35, 'name': 'certificate', 'string': 'Nivel de educación', 'required': False, 'type': 'selection', 'data': 'employee'},
        36: {'index': 36, 'name': 'res_country_id', 'string': 'País de Residencia', 'required': True, 'type': 'many2one', 'model': 'res.country', 'field_domain': 'name', 'data': 'address'},
        37: {'index': 37, 'name': 'state_id', 'string': 'Estado', 'required': True, 'type': 'many2one', 'model': 'res.country.state', 'field_domain': 'name', 'data': 'address'},
        38: {'index': 38, 'name': 'l10n_mx_edi_locality_id', 'string': 'Localidad', 'required': False, 'type': 'many2one', 'model': 'l10n_mx_edi.res.locality', 'field_domain': 'name', 'data': 'address'},
        39: {'index': 39, 'name': 'city', 'string': 'Ciudad', 'required': True, 'type': 'string', 'data': 'address'},
        40: {'index': 40, 'name': 'street_name', 'string': 'Calle', 'required': True, 'type': 'string', 'data': 'address'},
        41: {'index': 41, 'name': 'street_number', 'string': 'Número Exterior-Manzana', 'required': True, 'type': 'string', 'data': 'address'},
        42: {'index': 42, 'name': 'street_number2', 'string': 'Número Interior', 'required': False, 'type': 'string', 'data': 'address'},
        43: {'index': 43, 'name': 'building', 'string': 'Edificio y/o Departamento', 'required': False, 'type': 'string', 'data': 'address'},
        44: {'index': 44, 'name': 'l10n_mx_edi_colony', 'string': 'Colonia', 'required': True, 'type': 'string', 'data': 'address'},
        45: {'index': 45, 'name': 'zip', 'string': 'C.P.', 'required': True, 'type': 'string', 'data': 'address'},
        46: {'index': 46, 'name': 'banco_id', 'string': 'Banco', 'required': True, 'type': 'many2one', 'model': 'res.bank', 'field_domain': 'name'},
        47: {'index': 47, 'name': 'bank_account', 'string': 'No. cuenta bancaria', 'required': True,'type': 'string', 'data': 'address'},
        48: {'index': 48, 'name': 'account_type', 'string': 'Tipo de cuenta', 'required': True, 'type': 'selection', 'model': 'bank.account.employee'},
        # 49: {'index': 49, 'name': 'isr_adjustment', 'string': 'Ajuste de ISR Anual', 'required': False, 'type': 'boolean', 'data': 'employee'},
        49: {'index': 49, 'name': 'personal_savings_bank', 'string':'Caja de ahorros personal', 'required': False, 'type': 'float'},
        50: {'index': 50, 'name': 'resistance_bottom_new', 'string': _('Resistance fund ASSA new income'), 'required': False, 'type': 'float'},
        51: {'index': 51, 'name': 'fixed_resistance_background', 'string': _('Fixed ASSA resistance fund'), 'required': False, 'type': 'float'},
        52: {'index': 52, 'name': 'salary_reduction', 'string': 'Reducción de salario?', 'required': False, 'type': 'boolean', 'data': 'employee'},
        53: {'index': 53, 'name': 'previous_salary', 'string': 'Salario anterior', 'required': False, 'type': 'float'},
        54: {'index': 54, 'name': 'is_manager', 'string': 'Es un director', 'required': False, 'type': 'boolean', 'data': 'employee'},
        55: {'index': 55, 'name': 'pilot_tab_id', 'string': 'Tabulador de Pilotos', 'required': False, 'type': 'many2one', 'model': 'hr.pilot.tab', 'field_domain': 'name'},
        56: {'index': 56, 'name': 'pilot_category', 'string': 'Categoría de Pilotos', 'required': False, 'type': 'selection'},
    }

    msg_required = _('REQUERIDO: Columna %s en la fila %s.\n')
    msg_not_found = _('NO ENCONTRADO: Valor (%s), Columna %s en la fila %s, POSIBLES VALORES %s.\n')
    msg_not_found_m2o = _('NO ENCONTRADO: Valor (%s) Columna %s en la fila %s.\n')
    msg_many = _('MULTIPLES COINCIDENCIAS: Valor (%s) Columna %s en la fila %s.\n')
    msg_date_format = _("FORMATO FECHA: valor (%s) columna %s en la fila %s.\n")
    msg_number_format = _("FORMATO NÚMERO: Valor (%s), Columna %s en la fila %s.\n")
    msg_unique = _('DUPLICADO: (%s) Columna %s en la fila %s.\n')
    msg_contract_unique = _('CONTRATO ABIERTO: Empleado (%s), Columna %s en la fila %s.\n')
    msg_not_match = _('NO COINCIDE: Plaza (%s) no pertenece al Puesto de trabajo (%s), Columna %s en la fila %s.\n')
    msg_not_available = _('NO DISPONIBLE: Plaza (%s), Columna %s en la fila %s.\n')

    def get_column(self, index):
        if self.type == 'employee':
            if index in self.colums:
                return self.colums[index]
            else:
                return None
        if self.type == 'contract':
            if index in self.contract_columns:
                return self.contract_columns[index]
            else:
                return None

    @api.onchange('file_ids')
    def onchange_file_ids(self):
        if self.file_ids:
            self._read_file()

    def clean_file_ids(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _check_file(self, filename):
        return filename and filename.lower().strip().endswith('.xlsx')

    def _read_file(self):
        if len(self.file_ids):
            files = [bool(self._check_file(att.name)) for att in self.file_ids]
            if False in files:
                raise UserError(_('XLSX files only. File not supported.'))
            if files.count(True) > 1:
                raise UserError(_('Only one XLSX file can be selected.'))
            if self.type == 'employee':
                self._read_xls()
        return True

    def float_to_string(self, value):
        if isinstance(value, float):
            return str(value).split('.')[0]
        else:
            return value

    def get_key_from_value(self, d, val):
        keys = [k for k, v in d.items() if v == val]
        if keys:
            return keys[0]
        return None

    def _read_field_selection(self, options):
        model = options.get('model', False) or 'hr.employee'
        vals = dict(self.env[model]._fields.get(options['name'])._description_selection(self.env))
        res = {}
        value = self.get_key_from_value(vals, options['field'])
        if value:
            res['value'] = {options['name']: value}
        else:
            if options['required'] and not options['field']:
                res['error'] = self.msg_required %(
                    options['string'].upper(), options['row']
                )
            if options['field']:
                res['error'] = self.msg_not_found % (
                       options['field'],
                       options['string'].upper(),
                       options['row'],
                       list(vals.values())
                    )
            if not options['required'] and not value:
                res['value'] = {options['name']: ''}
        return res

    def _read_field_string(self, options):
        res = {}
        value = str(options['field'])
        if value:
            res['value'] = {options['name']: value.strip()}
        else:
            if options['required'] and not options['field']:
                res['error'] = self.msg_required %(
                    options['string'].upper(), options['row']
                )
            else:
                res['value'] = {options['name']: ''}
        return res

    def _read_field_many2one(self, options):
        value = str(options['field'])
        domain = [(options['field_domain'], '=', value)]
        res_id = self.env[options['model']].search(domain)
        res = {}
        if res_id:
            if len(res_id) > 1:
                res['error'] = self.msg_many % (
                       value,
                       options['string'].upper(),
                       options['row']
                    )
            else:
                res['value'] = {options['name']: res_id}
        else:
            if options['required'] and not value:
                res['error'] = self.msg_required %(
                    options['string'].upper(), options['row']
                )
            if value:
                res['error'] = self.msg_not_found_m2o % (
                        value,
                        options['string'].upper(),
                        options['row']
                    )
            if not options['required'] and not value:
                res['value'] = {options['name']: False}
        return res

    def _read_field_boolean(self, options):
        res = {}
        if options['field']:
            if options['field'] in [1, '1', 0, '0']:
                res['value'] = {options['name']: u'1' if options['field'] in [1, '1'] else u"0"}
            else:
                res['error'] = self.msg_not_found_m2o % (
                        options['field'],
                        options['string'].upper(),
                        options['row']
                    )
        else:
            if options['required']:
                res['error'] = self.msg_required %(
                    options['string'].upper(), options['row']
                )
            else:
                res['value'] = {options['name']: u"false"}
        return res

    def _read_field_date(self, options):
        res = {}
        if options.get('field'):
            try:
                dt = fields.Date.to_date(options.get('field'))
                birthday = dt.strftime(DEFAULT_SERVER_DATE_FORMAT)
                res['value'] = {options['name']: birthday}
            except:
                res['error'] = self.msg_date_format % (
                        options['field'],
                        options['string'].upper(),
                        options['row']
                    )
        else:
            if options['required']:
                res['error'] = self.msg_required % (
                   options['string'].upper(),
                   options['row']
                )
            else:
                res['value'] = {options['name']: ''}
        return res

    def _read_field_integer(self, options):
        res = {}
        if options.get('field'):
            try:
                value = int(options.get('field'))
                res['value'] = {options['name']: value}
            except:
                res['error'] = self.msg_number_format % (
                    options['field'],
                    options['string'].upper(),
                    options['row']
                )
        else:
            if options['required']:
                res['error'] = self.msg_required % (
                   options['string'].upper(),
                   options['row']
                )
            else:
                res['value'] = {options['name'], ''}
        return res

    def _read_xls(self):
        """ Read file content, using xlrd lib """
        datafile = base64.b64decode(self.file_ids.datas)
        book = xlrd.open_workbook(file_contents=datafile)
        sheets = book.sheet_names()
        sheet = sheets[0]
        rows_to_import = self._read_xls_book(book, sheet)
        rows_to_import = itertools.islice(rows_to_import, 1, None)
        rows_to_import = itertools.islice(rows_to_import, 1, None)
        msg_error = [_('¡Oops!, wrong file: \n')]
        list_rfc = []
        list_curp = []
        list_ssnid = []
        emp_number = []
        list_bank_account = []
        for rowx, row in enumerate(rows_to_import, 0):
            salary_reduction = False
            job_id = False
            position_id = False
            previous_salary = 0
            for index, field in enumerate(row):
                header = self.get_column(index)
                if header:
                    header['field'] = field
                    header['row'] = rowx + 3
                    vals = getattr(self, '_read_field_' + header['type'])(header)

                    if 'error' in vals:
                        msg_error.append(vals['error'])
                    else:
                        if header['name'] == 'rfc':
                            if field not in list_rfc:
                                list_rfc.append(field)
                                employee_rfc = self.env['res.partner'].search_count([('rfc', '=', field)])
                                if employee_rfc:
                                    msg_error.append(self.msg_unique % (
                                            field,
                                            header['string'].upper(),
                                            header['row']
                                        )
                                    )
                            else:
                                msg_error.append(self.msg_unique % (
                                        field,
                                        header['string'].upper(),
                                        header['row']
                                    )
                                )
                        if header['name'] == 'curp':
                            if field not in list_curp:
                                list_curp.append(field)
                                curp = self.env['res.partner'].search_count([('curp', '=', field)])
                                if curp:
                                    msg_error.append(self.msg_unique % (
                                            field,
                                            header['string'].upper(),
                                            header['row']
                                        )
                                    )
                            else:
                                msg_error.append(self.msg_unique % (
                                        field,
                                        header['string'].upper(),
                                        header['row']
                                    )
                                )
                        if header['name'] == 'ssnid':
                            if field not in list_ssnid:
                                list_ssnid.append(field)
                                employee_ssnid = self.env['hr.employee'].search_count([('ssnid', '=', field)])
                                if employee_ssnid:
                                    msg_error.append(self.msg_unique % (
                                            field,
                                            header['string'].upper(),
                                            header['row']
                                        )
                                    )
                            else:
                                msg_error.append(self.msg_unique % (
                                        field,
                                        header['string'].upper(),
                                        header['row']
                                    )
                                )
                        if header['name'] == 'registration_number':
                            if field not in emp_number:
                                employee_number = self.env['hr.employee'].search_count([('registration_number', '=', field)])
                                emp_number.append(field)
                                if employee_number:
                                    msg_error.append(self.msg_unique % (
                                            field,
                                            header['string'].upper(),
                                            header['row']
                                        )
                                    )
                            else:
                                msg_error.append(self.msg_unique % (
                                        field,
                                        header['string'].upper(),
                                        header['row']
                                    )
                                )
                        if header['name'] == 'bank_account':
                            if field not in list_bank_account:
                                list_bank_account.append(field)
                                bank_account = self.env['bank.account.employee'].search_count([('bank_account', '=', field)])
                                if bank_account:
                                    msg_error.append(self.msg_unique % (
                                            field,
                                            header['string'].upper(),
                                            header['row']
                                        )
                                    )
                            else:
                                msg_error.append(self.msg_unique % (
                                        field,
                                        header['string'].upper(),
                                        header['row']
                                    )
                                )
                        if header['name'] == 'job_id':
                            job_id = vals['value'].get('job_id', False)
                        if header['name'] == 'position_id':
                            position_id = vals['value'].get('position_id', False)
                            if position_id.employee_id:
                                msg_error.append(self.msg_not_available % (
                                    field,
                                    header['string'].upper(),
                                    header['row']
                                ))
                        if header['name'] == 'salary_reduction':
                            salary_reduction = vals['value'].get('salary_reduction', False)
                        if header['name'] == 'previous_salary':
                            previous_salary = vals['value'].get('previous_salary', False)
            if salary_reduction == '1' and (not previous_salary or previous_salary < 0):
                msg_error.append(self.msg_required % (
                    'Salario anterior',
                    str(rowx + 3)
                ))
            if job_id and position_id and job_id.id != position_id.job_id.id:
                msg_error.append(self.msg_not_match % (
                    position_id.name,
                    job_id.name,
                    'Sala',
                    str(rowx + 3)
                ))

        if len(msg_error) > 1:
            msg_raise = "".join(msg_error)
            raise ValidationError(_(msg_raise))
        else:
            self.read_file = True


    def _read_xls_book(self, book, sheet_name):
        sheet = book.sheet_by_name(sheet_name)
        # emulate Sheet.get_rows for pre-0.9.4
        for rowx, row in enumerate(map(sheet.row, range(sheet.nrows)), 1):
            values = []
            for colx, cell in enumerate(row, 1):
                if cell.ctype is xlrd.XL_CELL_NUMBER:
                    is_float = cell.value % 1 != 0.0
                    values.append(
                        str(cell.value)
                        if is_float
                        else str(int(cell.value))
                    )
                elif cell.ctype is xlrd.XL_CELL_DATE:
                    is_datetime = cell.value % 1 != 0.0
                    # emulate xldate_as_datetime for pre-0.9.3
                    dt = datetime.datetime(*xlrd.xldate.xldate_as_tuple(cell.value, book.datemode))
                    values.append(
                        dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                        if is_datetime
                        else dt.strftime(DEFAULT_SERVER_DATE_FORMAT)
                    )
                elif cell.ctype is xlrd.XL_CELL_BOOLEAN:
                    values.append(u'True' if cell.value else u'False')
                elif cell.ctype is xlrd.XL_CELL_ERROR:
                    raise ValueError(
                        _("Invalid cell value at row %(row)s, column %(col)s: %(cell_value)s") % {
                            'row': rowx,
                            'col': colx,
                            'cell_value': xlrd.error_text_from_code.get(cell.value, _("unknown error code %s", cell.value))
                        }
                    )
                else:
                    values.append(cell.value)
            if any(x for x in values):
                yield values

    def import_file(self):
        ctx = dict(self.env.context)
        model = 'hr.employee' if self.type == 'employee' else 'hr.contract'
        tag = 'import_employee_stmt' if self.type == 'employee' else 'import_contract_stmt'
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

    def _convert_import_data(self, fields, options):
        """ Extracts the input BaseModel and fields list (with
            ``False``-y placeholders for fields to *not* import) into a
            format Model.import_data can use: a fields list without holes
            and the precisely matching data matrix

            :param list(str|bool): fields
            :returns: (data, fields)
            :rtype: (list(list(str)), list(str))
            :raises ValueError: in case the import data could not be converted
        """
        # Get indices for non-empty fields
        indices = [index for index, field in enumerate(fields) if field]
        if not indices:
            raise ValueError(_("You must configure at least one field to import"))
        # If only one index, itemgetter will return an atom rather
        # than a 1-tuple
        if len(indices) == 1:
            mapper = lambda row: [row[indices[0]]]
        else:
            mapper = operator.itemgetter(*indices)
        # Get only list of actually imported fields
        import_fields = [f for f in fields if f]

        rows_to_import = self._read_xls(options)
        if options.get('headers'):
            rows_to_import = itertools.islice(rows_to_import, 1, None)
        data = [
            list(row) for row in map(mapper, rows_to_import)
            # don't try inserting completely empty rows (e.g. from
            # filtering out o2m fields)
            if any(row)
        ]

        # slicing needs to happen after filtering out empty rows as the
        # data offsets from load are post-filtering
        return data[options.get('skip'):], import_fields


class EmployeeStmtImportXLS(models.TransientModel):
    _inherit = 'base_import.import'

    @api.model
    def _convert_import_data(self, fields, options):
        """ Extracts the input BaseModel and fields list (with
            ``False``-y placeholders for fields to *not* import) into a
            format Model.import_data can use: a fields list without holes
            and the precisely matching data matrix

            :param list(str|bool): fields
            :returns: (data, fields)
            :rtype: (list(list(str)), list(str))
            :raises ValueError: in case the import data could not be converted
        """
        # Get indices for non-empty fields
        indices = [index for index, field in enumerate(fields) if field]
        if not indices:
            raise ValueError(
                _("You must configure at least one field to import"))
        # If only one index, itemgetter will return an atom rather
        # than a 1-tuple
        if len(indices) == 1:
            mapper = lambda row:[row[indices[0]]]
        else:
            mapper = operator.itemgetter(*indices)
        # Get only list of actually imported fields
        import_fields = [f for f in fields if f]

        rows_to_import = self._read_file(options)
        if options.get('headers'):
            if options.get('employee_stmt_import') or options.get('contract_stmt_import') or options.get('input_stmt_import'):
                rows_to_import = itertools.islice(rows_to_import, 2, None)
            else:
                rows_to_import = itertools.islice(rows_to_import, 1, None)
        data = [
            list(row) for row in map(mapper, rows_to_import)
            # don't try inserting completely empty rows (e.g. from
            # filtering out o2m fields)
            if any(row)
        ]

        # slicing needs to happen after filtering out empty rows as the
        # data offsets from load are post-filtering
        return data[options.get('skip'):], import_fields

    def parse_preview(self, options, count=10):
        if options.get('employee_stmt_import', False):
            self = self.with_context(employee_stmt_import=True)
        return super(EmployeeStmtImportXLS, self).parse_preview(options, count=count)

    def do(self, fields, columns, options, dryrun=False):
        if options.get('employee_stmt_import', False):
            self._cr.execute('SAVEPOINT import_employee_stmt')
            res = super(EmployeeStmtImportXLS, self.with_context(employee_import=True)).do(fields, columns, options, dryrun=dryrun)

            try:
                if dryrun:
                    self._cr.execute('ROLLBACK TO SAVEPOINT import_employee_stmt')
                else:
                    self._cr.execute('RELEASE SAVEPOINT import_employee_stmt')
                    res['messages'].append({
                        'import_employee_stmt': True,
                        })
            except psycopg2.InternalError:
                pass
            return res
        else:
            return super(EmployeeStmtImportXLS, self).do(fields, columns, options, dryrun=dryrun)

    def _parse_import_data(self, data, import_fields, options):
        res = super(EmployeeStmtImportXLS, self)._parse_import_data(data, import_fields, options)
        employee_import = self._context.get('employee_import', False)
        if self._context.get('type_import', False) == 'employee':
            if employee_import:
                import_fields.append('partner_employee_ids/employee')
                employee_idx = import_fields.index('partner_employee_ids/employee')
                import_fields.append('partner_employee_ids/type')
                type_idx = import_fields.index('partner_employee_ids/type')
                import_fields.append('partner_employee_ids/name')
                partner_employee_idx = import_fields.index('partner_employee_ids/name')
                import_fields.append('partner_employee_ids/email')
                partner_email_idx = import_fields.index('partner_employee_ids/email')
                # import_fields.append('partner_employee_ids/curp')
                # partner_curp_idx = import_fields.index('partner_employee_ids/curp')
                # import_fields.append('partner_employee_ids/rfc')
                # partner_rfc_idx = import_fields.index('partner_employee_ids/rfc')

                for line in data:
                    partner_name = line[import_fields.index('name')]
                    partner_email = line[import_fields.index('work_email')]
                    # partner_curp = line[import_fields.index('identification_id')]
                    # partner_rfc = line[import_fields.index('rfc')]
                    partner_lastname = line[import_fields.index('last_name')]
                    my_name = '%s %s' % (partner_name, partner_lastname)
                    line.insert(partner_employee_idx, my_name)
                    line.insert(employee_idx, u'true')
                    line.insert(type_idx, 'private')
                    line.insert(partner_email_idx, partner_email)
                    # line.insert(partner_curp_idx, partner_curp)
                    # line.insert(partner_rfc_idx, partner_rfc)
        return res


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    partner_employee_ids = fields.One2many('hr.employee.partner.import', 'employee_id', string='Employee Partner Import')


class EmployeePartner(models.Model):
    _name = "hr.employee.partner.import"
    _inherits = {'res.partner': 'partner_id'}
    _description = "Employee Partners"

    partner_id = fields.Many2one('res.partner', ondelete='cascade', string='Partner Import',)
    employee_id = fields.Many2one('hr.employee', string='Employee Import', ondelete='cascade',)

    def create(self, vals):
        res = super(EmployeePartner, self).create(vals)
        if self._context.get('employee_import', False) and self._context.get('import_file', False):
            res.employee_id.address_home_id = res.partner_id
        return res

