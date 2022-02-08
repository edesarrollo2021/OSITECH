# -*- coding: utf-8 -*-

import base64
import logging
import io

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator
import pdfminer

from odoo import fields, models, api, _

_logger = logging.getLogger(__name__)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    count_sign_signed = fields.Integer(string='Payroll Receipts Sent', compute='_get_payslips_doc_sign_requested')
    progress_count_sign_signed = fields.Integer(string='% Payroll Receipts Sent', compute='_get_payslips_doc_sign_requested')

    @api.depends('slip_ids.cfdi_ids.sign_request_id')
    def _get_payslips_doc_sign_requested(self):
        if self.payslips_total and type(self.id) == int:
            self._cr.execute('''SELECT payslip.id 
                                FROM hr_payslip AS payslip 
                                JOIN hr_payslip_cfdi AS cfdi        ON payslip.id = cfdi.payslip_id
                                JOIN sign_request AS ssr            ON cfdi.sign_request_id = ssr.id
                                WHERE payslip_run_id = %s AND ssr.state IN ('sent','signed')
                        ''' % (str(self.id)))
            list_sign_request = self._cr.fetchall()
            self.count_sign_signed = len(list_sign_request)
            self.progress_count_sign_signed = (self.count_sign_signed / self.payslips_total) * 100
        else:
            self.count_sign_signed = 0
            self.progress_count_sign_signed = 0

    def send_to_sign(self, options):
        slip_ids = self.env['hr.payslip.cfdi'].search([
            ('payslip_id.invoice_status', '=', 'right_bill'),
            ('payslip_id.payslip_run_id', '=', self.id),
            ('payslip_id.contracting_regime', '!=', '05'),
            ('sign_request_id', '=', False)
        ], limit=options.get('limit')).mapped('payslip_id')
        slip_ids.send_pdf_to_sign()
        return {
            'ids': slip_ids.ids,
            'messages': [],
            'continues': 0 if not slip_ids else 1,
        }


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    request_send = fields.Boolean(string="Request Send", compute="_compute_request_send")

    def _compute_request_send(self):
        for res in self:
            res.request_send = False
            if res.cfdi_ids.mapped('sign_request_id'):
                res.request_send = True

    def send_pdf_to_sign(self):
        PayslipCFDI = self.env['hr.payslip.cfdi']
        sign_request = []
        cont = 1
        for slip in self:
            _logger.info(cont)
            cont += 1
            cfdi_records = PayslipCFDI.search([
                ('payslip_id', '=', slip.id),
                ('invoice_status', '=', 'right_bill'),
            ])
            for cfdi in cfdi_records:
                if (not cfdi.sign_request_id or cfdi.sign_status == 'canceled') and cfdi.pdf and slip.contracting_regime != '05' and cfdi.invoice_status == 'right_bill':
                    # reading the pdf
                    parser = PDFParser(io.BytesIO(base64.b64decode(cfdi.pdf.datas)))
                    document = PDFDocument(parser)
                    rsrcmgr = PDFResourceManager()
                    device = PDFDevice(rsrcmgr)
                    laparams = LAParams()
                    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
                    interpreter = PDFPageInterpreter(rsrcmgr, device)

                    x = y = 0
                    def parse_obj(lt_objs):
                        x = y = 0
                        for obj in lt_objs:
                            # if it's a textbox, print location
                            if isinstance(obj, pdfminer.layout.LTTextBoxHorizontal):
                                if not 'FIRMA DEL TRABAJADOR' in obj.get_text():
                                    continue
                                x = obj.bbox[0]
                                y = obj.bbox[3]

                            # if it's a container, recurse
                            elif isinstance(obj, pdfminer.layout.LTFigure):
                                parse_obj(obj._objs)
                        return x, y

                    page_num = 0
                    # loop over all pages in the document
                    for page in PDFPage.get_pages(io.BytesIO(base64.b64decode(cfdi.pdf.datas))):
                        page_num += 1
                        # read the page into a layout object
                        interpreter.process_page(page)
                        layout = device.get_result()

                        x, y = parse_obj(layout._objs)
                        x, y = x / page.mediabox[2], (page.mediabox[3] - y) / page.mediabox[3]

                        if x and y:
                            break
                    
                    page = page_num
                    posX = x - 0.030
                    posY = y - 0.040  # the height
                    width = 0.171
                    height = 0.040
                    SignSendRequest = self.env['sign.send.request']
                    SignTemplate = self.env['sign.template']
                    sign_template = SignTemplate.create({
                        'name': cfdi.pdf.name,
                        'attachment_id': cfdi.pdf.id,
                        'sign_item_ids': [(0, False, {
                            'name': _('Sign'),
                            'type_id': self.env['sign.item.type'].search([('item_type', '=', 'signature')], limit=1).id,
                            'responsible_id': self.env['sign.item.role'].search([('name', '=', 'Empleado')], limit=1).id,
                            'page': page,
                            'posX': posX,
                            'posY': posY,
                            'width': width,
                            'height': height,
                        })],
                    }).sudo()
                    if not slip.employee_id.user_id.partner_id.id and not slip.employee_id.address_home_id.id:
                        continue
                    sign_send_request = SignSendRequest.create({
                        'template_id': sign_template.id,
                        'filename': sign_template.name,
                        'signer_ids': [(0, False, {
                            'role_id': self.env['sign.item.role'].search([('name', '=', 'Empleado')], limit=1).id,
                            'partner_id': slip.employee_id.user_id.partner_id.id if slip.employee_id.user_id else slip.employee_id.address_home_id.id,
                        })],
                        'signers_count': 1,
                        'signer_id': slip.employee_id.address_home_id.id,
                        'subject': _("Signature Request - %s") % sign_template.attachment_id.name
                    }).sudo()
                    request = sign_send_request.create_request()
                    sign_request.append(request)
                    cfdi.sign_request_id = request['id']
        return sign_request


class HrPayslipCfdi(models.Model):
    _inherit = 'hr.payslip.cfdi'

    sign_status = fields.Selection([("sent", "Signatures in Progress"),
                                    ("signed", "Fully Signed"),
                                    ("canceled", "Canceled")], related='sign_request_id.state')
    sign_request_id = fields.Many2one('sign.request', string='Sign Request')
    pdf_sign = fields.Many2one('ir.attachment', string="PDF Sign", copy=False, compute='compute_pdf_sign', store=True)

    @api.depends('sign_request_id.completed_document')
    def compute_pdf_sign(self):
        for cfdi in self:
            if cfdi.sign_status == 'signed':
                attachment = self.env['ir.attachment'].search([
                    ('res_model', '=', 'sign.request'),
                    ('res_id', '=', cfdi.sign_request_id.id),
                    ('res_field', '=', 'completed_document')
                ], limit=1)
                attachment.write({'name': cfdi.pdf.name})
                cfdi.pdf_sign = attachment

