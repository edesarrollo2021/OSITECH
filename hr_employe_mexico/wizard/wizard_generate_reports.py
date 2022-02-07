# -*- coding: utf-8 -*-

import io
import base64
import zipfile

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ContractReports(models.TransientModel):
    _name = "contract.report"
    _description = "Wizard to print contract reports"

    name = fields.Char(string="Name")
    report_ids = fields.Many2many('ir.actions.report', string="Reports")
    contract_ids = fields.Many2many('hr.contract', string="Contracts")
    data = fields.Binary('File', readonly=True)
    state = fields.Selection([
        ('choose', 'choose'),
        ('get', 'get')
    ], default='choose')

    def generate_reports(self):
        this = {
            'type': 'ir.actions.act_window',
            'res_model': 'contract.report',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

        stream = io.BytesIO()
        try:
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as doc_zip:
                for contract in self.contract_ids:
                    for report in self.report_ids:
                        mimetype, out, filename, ext = report.render_any_docs(contract.ids)

                        if len(self.report_ids.ids) == 1 and len(self.contract_ids.ids) == 1:
                            self.write({'state': 'get', 'data': base64.encodebytes(out), 'name': "%s.%s" % (filename, ext)})
                            return this
                        else:
                            doc_zip.writestr("%s - %s.%s" % (contract.code, filename, ext), base64.b64decode(base64.encodebytes(out)), compress_type=zipfile.ZIP_DEFLATED)
        except zipfile.BadZipfile:
            raise UserError(_('BadZipfile exception'))

        content = stream.getvalue()
        out_zip = base64.encodestring(content)

        self.write({'state': 'get', 'data': out_zip, 'name': 'contracts.zip'})
        return this
