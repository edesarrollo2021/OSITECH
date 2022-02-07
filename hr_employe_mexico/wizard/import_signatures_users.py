# -*- coding: utf-8 -*-

import io
import base64
import zipfile

from xlrd import open_workbook
from dateutil.relativedelta import relativedelta

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


class ImportSignatureUsers(models.TransientModel):
    _name = 'import.signature.users'
    _description = 'Import Signatures for users'

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)
    file_ids = fields.Many2many('ir.attachment', string='File excel', required=False)
    file_zip_ids = fields.Many2many('ir.attachment', string='.ZIP', relation='import_signature_users_attachment', required=False)

    def data_zipfile(self):
        """ Function doc """
        datafile = base64.b64decode(self.file_zip_ids.datas)
        input_file = io.BytesIO(datafile)
        if not zipfile.is_zipfile(input_file):
            raise UserError(_('Only zip files are supported.'))
        try:
            return zipfile.ZipFile(input_file)
        except:
            raise UserError(_('File Content Document is required.'))

    def import_file_document(self):
        if not self.file_zip_ids:
            raise UserError(_("There is no ZIP file"))
        if not self.file_ids:
            raise UserError(_("There is no EXCEL file"))
        if len(self.file_zip_ids) > 1 or len(self.file_ids) > 1:
            raise UserError(_("You are entering more than one file"))
        zf = self.data_zipfile()
        zip_namelist = zf.namelist()
        datafile = base64.b64decode(self.file_ids.datas)
        book = open_workbook(file_contents=datafile)
        sheet = book.sheet_by_index(0)
        msg_not_found = [_('\nNo results were found for: \n')]
        msg_required = [_('\nThe following fields are mandatory: \n')]
        msg_document_not_found = [_('\nThe document name cannot be found in the .zip file: \n')]
        msg_invalidad_format = [_('\nInvalid format: \n')]
        list_vals = []
        for row in range(1, sheet.nrows):
            if sheet.cell_value(row, 0):
                email = sheet.cell_value(row, 0)

                user_id = self.env['res.users'].search([('login', '=', email), ('company_id', '=', self.company_id.id)], limit=1)
                if not user_id:
                    msg_not_found.append(
                        _('Not found User for email %s in the row %s. \n') % (sheet.cell_value(row, 0), str(row + 1)))
                if not sheet.cell_value(row, 2):
                    msg_required.append(_('The name of the file in the row %s. \n') % (str(row + 1)))
                document = str(sheet.cell_value(row, 2))
                filestore = [m for m in zip_namelist if m == document]
                if len(filestore):
                    document_read = zf.read(document)
                    datas = base64.b64encode(document_read)

                    ext = document.split('.')[1]
                    if ext not in ['jpg', 'jpeg', 'png']:
                        msg_invalidad_format.append(_('Invalid format for %s in the row %s. \n (Charge only png, jpg and jpeg)') % (sheet.cell_value(row, 2), str(row + 1)))

                    vals = {
                        'user_id': user_id,
                        'datas': datas,
                    }
                    list_vals.append(vals)
                else:
                    msg_document_not_found.append(_('The document %s in the row %s. \n') % (document, str(row + 1)))
        msgs = []
        if len(msg_required) > 1:
            msgs += msg_required
        if len(msg_not_found) > 1:
            msgs += msg_not_found
        if len(msg_document_not_found) > 1:
            msgs += msg_document_not_found
        if len(msg_invalidad_format) > 1:
            msgs += msg_invalidad_format
        if len(msgs):
            msg_raise = "".join(msgs)
            raise UserError(_(msg_raise))
        users = self.env['res.users']
        for data in list_vals:
            user_id = data['user_id']
            user_id.write({'sign_signature': data['datas']})
            users |= user_id

        return {
            'name': _('Users'),
            'domain': [('id', 'in', users.ids)],
            'res_model': 'res.users',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (self.env.ref('hr_employe_mexico.view_users_customer_form').id, 'form')],
            'limit': 80,
        }
