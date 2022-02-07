import io
import base64
import itertools
import operator
from datetime import datetime, date, timedelta, time
import logging
import psycopg2
import zipfile
from pytz import timezone, UTC

from collections import namedtuple

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, pycompat, float_compare
from odoo.addons.resource.models.resource import float_to_time, HOURS_PER_DAY

try:
    import xlrd
    try:
        from xlrd import xlsx
    except ImportError:
        xlsx = None
except ImportError:
    xlrd = xlsx = None

DummyAttendance = namedtuple('DummyAttendance', 'hour_from, hour_to, dayofweek, day_period, week_type')

class HrLeaveImportWizard(models.TransientModel):
    _name = "hr.leave.import.wizard"

    file_ids = fields.Many2many(string='Layout', comodel_name='ir.attachment', required=True)
    file_name = fields.Char('File Name', related='file_ids.name')
    create_document = fields.Boolean("Create Documents", default=False)
    file_zip = fields.Binary(string="File Content Document", required=False, filters='*.zip')
    zip_name = fields.Char('Zip name', required=False)

    colums_leaves = {
        0: {'index': 0, 'name': 'holiday_status_id', 'string': 'Tipo de Asuencia', 'required': True, 'type': 'many2one', 'model': 'hr.leave.type', 'field_domain': 'code'},
        1: {'index': 1, 'name': 'employee_id', 'string': 'Empleado(Matrícula)', 'required': True, 'type': 'many2one', 'model': 'hr.employee', 'field_domain': 'registration_number'},
        2: {'index': 2, 'name': 'request_date_from', 'string': 'Fecha de inicio', 'required': True, 'type': 'datetime'},
        3: {'index': 3, 'name': 'request_date_to', 'string': 'Fecha de fin', 'required':True, 'type': 'datetime'},
        # 4: {'index': 4, 'name': 'number_of_days', 'string': 'Nro. de días', 'required':True, 'type': 'float'},
        4: {'index': 4, 'name': 'name', 'string': 'Descripción', 'required': False, 'type': 'string'},
        # 6: {'index': 6, 'name': 'document_ids', 'string': 'File ', 'required': False, 'type': 'string'},
    }

    msg_date_value = _("DATE VALUE: start date (%s) cannot be later than End date (%s), column %s in row %s.\n")
    msg_date_format = _("DATE FORMAT: value (%s) field %s in row %s.\n")
    msg_overlaps = _("OVERLAPS: You can not set 2 time off that overlaps on the same day for the same employee, %s, row %s\n")


    def clean_file_ids(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def get_column(self, index):
        if index in self.colums_leaves:
            return self.colums_leaves[index]
        else:
            return None

    @api.onchange('file_ids')
    def onchange_file_ids(self):
        if self.file_ids:
            self._read_file()

    @api.onchange('file_zip')
    def onchange_file_zip(self):
        if self.zip_name and not self.zip_name.lower().strip().endswith('.zip'):
            raise UserError(_('ZIP files only. File not supported.'))

    def _read_file(self):
        hrImport = self.env['hr.employee.import']
        if len(self.file_ids):
            files = [bool(hrImport._check_file(att.name)) for att in self.file_ids]
            if False in files:
                raise UserError(_('XLSX files only. File not supported.'))
            if files.count(True) > 1:
                raise UserError(_('Only one XLSX file can be selected.'))
            self._read_xls()
        return True


    def data_zipfile(self):
        """ Function doc """
        if self.file_zip:
            datafile = base64.b64decode(self.file_zip)
            input_file = io.BytesIO(datafile)
            if not zipfile.is_zipfile(input_file):
                raise UserError(_('ZIP files only. File not supported.'))
            try:
                # ~ with zipfile.ZipFile(input_file, "r") as z:
                return zipfile.ZipFile(input_file)
            except:
                raise UserError(_('File Content Document is required.'))

    def _check_date(self, employee_id, date_to, date_from):
        domain = [
            ('date_from', '<', date_to),
            ('date_to', '>', date_from),
            ('employee_id', '=', employee_id.id),
            ('state', 'not in', ['cancel', 'refuse']),
        ]
        Leaves = self.env['hr.leave']
        nholidays = Leaves.search_count(domain)
        res = {}
        if nholidays:
            res = {'error': True}
        return res

    def _read_xls(self):
        """ Read file content, using xlrd lib """
        datafile = base64.b64decode(self.file_ids.datas)
        book = xlrd.open_workbook(file_contents=datafile)
        sheets = book.sheet_names()
        sheet = sheets[0]
        hrImport = self.env['hr.employee.import']
        Leave = self.env['hr.leave']
        rows_to_import = hrImport._read_xls_book(book, sheet)
        # rows_to_import = itertools.islice(rows_to_import, 1, None)
        rows_to_import = itertools.islice(rows_to_import, 1, None)
        msg_error = [_('¡Oops!, wrong file: \n')]
        list_leave = []
        zip_namelist = []
        if self.file_zip and self.create_document:
            zf = self.data_zipfile()
            zip_namelist += zf.namelist()
        for rowx, row in enumerate(rows_to_import, 2):
            request_date_from = False
            request_date_to = False
            employee_id = False
            folder_id = False
            holiday_status_id = False
            lines = {}
            for index, field in enumerate(row):
                header = self.get_column(index)
                if header:
                    header['field'] = field
                    header['row'] = rowx + 1
                    vals = getattr(hrImport, '_read_field_' + header['type'])(header)
                    if 'error' in vals:
                        msg_error.append(vals['error'])
                    else:
                        lines[header['name']] = vals['value'].get(header['name'], False)
                        if header['name'] == 'employee_id':
                            employee_id = vals['value'].get('employee_id', False)
                            folder_id = employee_id._get_document_folder()
                            lines[header['name']] = employee_id.id
                        if header['name'] == 'holiday_status_id':
                            holiday_status_id = vals['value'].get('holiday_status_id', False)
                            lines[header['name']] = holiday_status_id.id

                        if header['name'] == 'request_date_from':
                            try:
                                request_date_from = vals['value'].get('request_date_from', False)
                            except:
                                msg_error.append(self.msg_date_format % (
                                    header['field'],
                                    header['string'].upper(),
                                    header['row']
                                ))
                        if header['name'] == 'request_date_to':
                            try:
                                request_date_to = vals['value'].get('request_date_to', False)
                            except:
                                msg_error.append(self.msg_date_format % (
                                    header['field'],
                                    header['string'].upper(),
                                    header['row']
                                ))

                            if request_date_from > request_date_to:
                                msg_error.append(self.msg_date_value % (
                                    request_date_from,
                                    request_date_to,
                                    header['string'].upper(),
                                    header['row']
                                ))
                        if header['name'] == 'document_ids' and vals['value'].get('document_ids') and self.create_document:
                            document = '/%s' % vals['value'].get('document_ids', False)
                            filestore = [m for m in zip_namelist if m.endswith(document)]
                            binary_ducument = zf.read(filestore[0])
                            ducument_data = base64.b64encode(binary_ducument)
                            attachment_dict = {
                                'owner_id': self.env.user.id,
                                'datas': base64.encodebytes(ducument_data),
                                'name': '%s %s' % (employee_id.complete_name, filestore[0]),
                                'folder_id': folder_id.id if folder_id else False,
                                'partner_id':employee_id.address_home_id.id,
                                'res_model': 'hr.leave',
                            }
                            lines[header['name']] = [(0, 0, attachment_dict)]

            # TODO: Check the remaining holiday free time available
            # if holiday_status_id and employee_id and not holiday_status_id.allocation_type == 'no':
            #     fix = self._check_holidays(holiday_status_id, employee_id)
            if employee_id and request_date_from and request_date_to:
                res = self._check_date(employee_id, date_to=request_date_to, date_from=request_date_from)
                if 'error' in res:
                    msg_error.append(self.msg_overlaps % (
                        employee_id.complete_name,
                        rowx+1,
                    ))

                request_date_from = fields.Datetime.from_string(request_date_from)
                request_date_to = fields.Datetime.from_string(request_date_to)
                tz = employee_id.tz or 'UTC'
                if request_date_from and request_date_to and request_date_from > request_date_to:
                    request_date_to = request_date_from
                if not request_date_from:
                    date_from = False
                # elif not holiday.request_unit_half and not holiday.request_unit_hours and not holiday.request_date_to:
                #     holiday.date_to = False
                else:
                    # if holiday.request_unit_half or holiday.request_unit_hours:
                    #     holiday.request_date_to = holiday.request_date_from
                    resource_calendar_id = employee_id.resource_calendar_id or self.env.company.resource_calendar_id
                    domain = [
                        ('calendar_id', '=', resource_calendar_id.id),
                        ('display_type', '=', False)
                    ]
                    attendances = self.env[
                        'resource.calendar.attendance'].read_group(domain, [
                        'ids:array_agg(id)', 'hour_from:min(hour_from)',
                        'hour_to:max(hour_to)', 'week_type', 'dayofweek',
                        'day_period'], ['week_type', 'dayofweek', 'day_period'], lazy=False)

                    # Must be sorted by dayofweek ASC and day_period DESC
                    attendances = sorted([DummyAttendance(group['hour_from'],
                        group['hour_to'], group['dayofweek'], group['day_period'],
                        group['week_type']) for group in attendances], key=lambda att:(att.dayofweek, att.day_period != 'morning')
                    )

                    default_value = DummyAttendance(0, 0, 0, 'morning', False)

                    if resource_calendar_id.two_weeks_calendar:
                        # find week type of start_date
                        start_week_type = int(math.floor((request_date_from.toordinal() - 1) / 7) % 2)
                        attendance_actual_week = [att for att in attendances if att.week_type is False or int(att.week_type) == start_week_type]
                        attendance_actual_next_week = [att for att in attendances if att.week_type is False or int(att.week_type) != start_week_type]
                        # First, add days of actual week coming after date_from
                        attendance_filtred = [att for att in attendance_actual_week if int(att.dayofweek) >= request_date_from.weekday()]
                        # Second, add days of the other type of week
                        attendance_filtred += list(attendance_actual_next_week)
                        # Third, add days of actual week (to consider days that we have remove first because they coming before date_from)
                        attendance_filtred += list(attendance_actual_week)

                        end_week_type = int(math.floor((request_date_to.toordinal() - 1) / 7) % 2)
                        attendance_actual_week = [att for att in attendances if att.week_type is False or int(att.week_type) == end_week_type]
                        attendance_actual_next_week = [att for att in attendances if att.week_type is False or int(att.week_type) != end_week_type]
                        attendance_filtred_reversed = list(reversed([att for att in attendance_actual_week if int(att.dayofweek) <= request_date_to.weekday()]))
                        attendance_filtred_reversed += list(reversed(attendance_actual_next_week))
                        attendance_filtred_reversed += list(reversed(attendance_actual_week))

                        # find first attendance coming after first_day
                        attendance_from = attendance_filtred[0]
                        # find last attendance coming before last_day
                        attendance_to = attendance_filtred_reversed[0]
                    else:
                        # find first attendance coming after first_day
                        attendance_from = next((att for att in attendances if int(att.dayofweek) >= request_date_from.weekday()), attendances[0] if attendances else default_value)
                        # find last attendance coming before last_day
                        attendance_to = next((att for att in reversed(attendances) if int(att.dayofweek) <= request_date_to.weekday()), attendances[-1] if attendances else default_value)

                    compensated_request_date_from = request_date_from
                    compensated_request_date_to = request_date_to

                    hour_from = float_to_time(attendance_from.hour_from)
                    hour_to = float_to_time(attendance_to.hour_to)

                    date_from = timezone(tz).localize(datetime.combine(compensated_request_date_from, hour_from)).astimezone(UTC).replace(tzinfo=None)
                    date_to = timezone(tz).localize(datetime.combine(compensated_request_date_to, hour_to)).astimezone(UTC).replace(tzinfo=None)
                    days = Leave._get_number_of_days(date_from, date_to, employee_id.id)
                    lines['number_of_days'] = days['days']
                    lines['request_date_from'] = date_from
                    lines['request_date_to'] = date_to
                    lines['date_from'] = date_from
                    lines['date_to'] = date_to
            list_leave.append(lines)

        if len(msg_error) > 1:
            msg_raise = "".join(msg_error)
            raise ValidationError(_(msg_raise))
        return list_leave

    def import_file(self):
        res = self._read_xls()
        levaes = []
        for incedents in res:
            # if not incedents.get('incedents'):
            #     del incedents['document_ids']
            leave_id = self.env['hr.leave'].create(incedents).sudo()
            levaes.append(leave_id.id)
            # leave_id.document_ids.write({'res_id': leave_id.id})

        return {
            'name': _('Leaves'),
            'res_model': 'hr.leave',
            'type': 'ir.actions.act_window',
            'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'tree',
            'domain': [('id', 'in', levaes)],
            'context': {},
        }


class HrEmployeeImport(models.Model):
    _inherit = "hr.employee.import"

    def _read_field_datetime(self, options):
        res = {}
        if options.get('field'):
            try:
                dt = fields.Datetime.from_string(options.get('field'))
                date = dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                res['value'] = {options['name']: date}
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

