# -*- coding: utf-8 -*-

import io
import base64
import zipfile

from xlrd import open_workbook
from datetime import datetime, timedelta, date, time as datetime_time

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

try:
    import xlrd
    try:
        from xlrd import xlsx
    except ImportError:
        xlsx = None
except ImportError:
    xlrd = xlsx = None


class GenerateAttendance(models.TransientModel):
    _name = "massive.attendance"
    _description = "Wizard for massive employee attendance creation"

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)
    file_id = fields.Many2many('ir.attachment', string='File excel', required=False)
    # date = fields.Date(string="Date", default=fields.Date.today())

    def generate_attendance(self):
        HRAtendance = self.env['hr.attendance']

        if not self.file_id:
            raise UserError(_("There is no EXCEL file"))
        file = self.file_id[0]
        datafile = base64.b64decode(file.datas)
        book = open_workbook(file_contents=datafile)
        sheet = book.sheet_by_index(0)

        msg_not_found = [_('\nNo results were found for: \n')]
        msg_required = [_('\nThe following fields are mandatory: \n')]
        msg_invalidad_format = [_('\nInvalid format: \n')]

        list_vals = []
        for row in range(1, sheet.nrows):
            if sheet.cell_value(row, 0):
                # ENROLLMENT COLUMN
                employee_id = self.env['hr.employee'].search(
                    [('registration_number', '=', str(sheet.cell_value(row, 0))), ('company_id', '=', self.company_id.id)])
                if not employee_id:
                    msg_not_found.append(
                        _('Employee registration %s in the row %s. \n') % (sheet.cell_value(row, 0), str(row + 1)))

                # DATE FROM COLUMN
                try:
                    is_datetime = sheet.cell_value(row, 1) % 1 != 0.0
                    dt = datetime(*xlrd.xldate.xldate_as_tuple(sheet.cell_value(row, 1), book.datemode))
                    date_from = dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT) if is_datetime else dt.strftime(DEFAULT_SERVER_DATE_FORMAT)
                except:
                    msg_invalidad_format.append(_('%s with the value (%s) in row %s. \n') % (
                    sheet.cell_value(0, 1).upper(), sheet.cell_value(row, 1), str(row + 1)))

                # DATE TO COLUMN
                try:
                    is_datetime = sheet.cell_value(row, 2) % 1 != 0.0
                    dt = datetime(*xlrd.xldate.xldate_as_tuple(sheet.cell_value(row, 2), book.datemode))
                    date_to = dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT) if is_datetime else dt.strftime(DEFAULT_SERVER_DATE_FORMAT)
                except:
                    msg_invalidad_format.append(_('%s with the value (%s) in row %s. \n') % (
                    sheet.cell_value(0, 2).upper(), sheet.cell_value(row, 2), str(row + 1)))

                list_vals.append((employee_id, date_from, date_to))

        msgs = []
        if len(msg_required) > 1:
            msgs += msg_required
        if len(msg_not_found) > 1:
            msgs += msg_not_found
        if len(msg_invalidad_format) > 1:
            msgs += msg_invalidad_format
        if len(msgs):
            msg_raise = "".join(msgs)
            raise UserError(_(msg_raise))
        for value in list_vals:
            HRAtendance |= self.env['hr.attendance'].create({'employee_id': value[0].id, 'check_in': value[1], 'check_out': value[2]})

        return {
            'name': _('Attendances'),
            'domain': [('id', 'in', HRAtendance.ids)],
            'res_model': 'hr.attendance',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form,kanban',
            'limit': 80,
        }
