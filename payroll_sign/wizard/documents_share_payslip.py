# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

import uuid
import zipfile
import base64
import io

try:
    from BytesIO import BytesIO
except ImportError:
    from io import BytesIO


class DocumentsSharePayslipWizard(models.TransientModel):
    _name = 'documents.share.payslip'
    _description = 'wizard to download ZIP documents'

    name = fields.Char('File name', readonly=False, default=lambda self: "CFDI %s" % fields.Datetime.now())
    payroll_run_ids = fields.Many2one('hr.payslip.run', 'Payroll Run')
    type_search = fields.Selection([
        ('period', 'Period'),
        ('employee', 'Employee'),
    ], string='Search Type', required=True, default='period')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date to')
    contracting_regime = fields.Selection([
        ('02', 'Sueldos y Salarios'),
        ('05', 'Libre'),
        ('07', 'Asimilados'),
    ], string='Contracting Regime')
    include_xml = fields.Boolean(string='Include XML')
    access_token = fields.Char(default=lambda x: str(uuid.uuid4()), groups="documents.group_documents_user")
    attachment_ids = fields.Many2many('ir.attachment', string='Shared attachments')
    data = fields.Binary('File', readonly=True)
    state = fields.Selection([
        ('choose', 'choose'),
        ('get', 'get')
    ], default='choose')

    def search_attachments(self):
        self.ensure_one()
        if self.type_search == 'period':
            domain = [
                ('payslip_run_id', '=', self.payroll_run_ids.id),
            ]
            payslips = self.env['hr.payslip'].search(domain)
        elif self.type_search == 'employee':
            domain = [
                ('employee_id', '=', self.employee_id.id),
                ('date_from', '>=', self.date_from),
                ('date_from', '<=', self.date_to)]
            payslips = self.env['hr.payslip'].search(domain)
        if not payslips:
            raise UserError(_('There are no payrolls with these descriptions.'))
        attachments = self.env['ir.attachment']
        if self.include_xml:
            attachments |= payslips.mapped('cfdi_ids.xml_timbre')

        payslip_id = payslips._ids if len(payslips) > 1 else '(%s)' % payslips.id
        self._cr.execute('''SELECT 
                                CASE
                                    WHEN cfdi.pdf_sign IS NOT NULL THEN cfdi.pdf_sign
                                    ELSE cfdi.pdf
                                END pdf
                            FROM hr_payslip_cfdi AS cfdi
                            JOIN hr_payslip AS payslip          ON cfdi.payslip_id = payslip.id
                            WHERE payslip.id IN %s
                         ''' % (payslip_id,))
        res = self._cr.fetchall()
        results = [r_id[0] for r_id in res if r_id[0]]

        attachments |= self.env['ir.attachment'].browse(results)
        self.make_zip(attachments)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'documents.share.payslip',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    def make_zip(self, attachments):
        stream = io.BytesIO()
        try:
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as doc_zip:
                for attachment in attachments:
                    if attachment.type in ['url', 'empty']:
                        continue
                    filename = attachment.name
                    doc_zip.writestr(filename, base64.b64decode(attachment['datas']), compress_type=zipfile.ZIP_DEFLATED)
        except zipfile.BadZipfile:
            raise UserError(_('BadZipfile exception'))

        content = stream.getvalue()
        out = base64.encodestring(content)
        self.write({'state': 'get', 'data': out, 'name': "%s.zip" % self.name})
