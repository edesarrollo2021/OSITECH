# -*- coding: utf-8 -*-

import io
import base64
import zipfile


from xlrd import open_workbook

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlrd
    try:
        from xlrd import xlsx
    except ImportError:
        xlsx = None
except ImportError:
    xlrd = xlsx = None


class HrEmployeeDocumentImport(models.TransientModel):
    _name = "hr.employee.document.import"
    _description = "Employee Document Import"

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)
    file_ids = fields.Many2many('ir.attachment', string='File excel', required=False)
    file_zip_ids = fields.Many2many('ir.attachment', string='.ZIP', relation='zip_document_employee_attachment', required=False)

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
                try:
                    enrollment = float(sheet.cell_value(row, 0))
                    enrollment = int(enrollment)
                except:
                    enrollment = sheet.cell_value(row, 0)

                employee_id = self.env['hr.employee'].search([('registration_number', '=', enrollment), ('company_id', '=', self.company_id.id)])
                if not employee_id:
                    msg_not_found.append(
                        _('Employee registration %s in the row %s. \n') % (sheet.cell_value(row, 0), str(row + 1)))
                if not sheet.cell_value(row, 1):
                    msg_required.append(_('The name of the file in the row %s. \n') % (str(row + 1)))
                document = str(sheet.cell_value(row, 1))
                filestore = [m for m in zip_namelist if m == document]
                if len(filestore):
                    document_read = zf.read(document)
                    datas = base64.b64encode(document_read)

                    # removing the path and extension
                    name = document.split('.')[0]
                    # TODO: Modify
                    if '/' in name:
                        name = name.split('/')
                        name.reverse()
                        name = name[0]

                    vals = {
                        'name': name,
                        'res_id': employee_id.id,
                        'res_model': employee_id._name,
                        'datas': datas,
                        'store_fname': name,
                        'type': 'binary',
                        'folder_id': employee_id.folder_id.id,
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
        attachments = self.env['ir.attachment'].with_context(no_document=False)  # !Important: no_document
        attachments |= self.env['ir.attachment'].create(list_vals)
        document_vals = []
        for att in attachments:
            employee_id = self.env['hr.employee'].browse([att.res_id])
            vals = {
                'name': att.name,
                'type': 'binary',
                'folder_id': att.folder_id.id,
                'partner_id': employee_id.address_home_id.id,
                'owner_id': self.env.user.id,
                'attachment_id': att.id
            }
            document_vals.append(vals)
        documents = self.env['documents.document']
        documents |= self.env['documents.document'].create(document_vals)
        return {
            'name': _('Documents Employee'),
            'domain': [('id', 'in', attachments.ids)],
            'res_model': 'ir.attachment',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'limit': 80,
        }
