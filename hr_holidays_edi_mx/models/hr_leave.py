# -*- coding: utf-8 -*-

import logging
import base64
import io
import calendar
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, SUPERUSER_ID, tools, _
from odoo.tools import float_compare
from odoo.exceptions import ValidationError, UserError
from odoo.tools.misc import formatLang, format_date

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator
import pdfminer

_logger = logging.getLogger(__name__)

class HolidaysRequest(models.Model):
    _inherit = "hr.leave"

    folio = fields.Char('Folio')
    type_inhability_id = fields.Many2one('hr.leave.inhability', string="Type inhability")
    contract_id = fields.Many2one('hr.contract', string='Contract')
    inhability_classification_id = fields.Many2one('hr.leave.classification',
        states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]},
        string="Classification")
    inhability_category_id = fields.Many2one('hr.leave.category', "Category",
        states = {'cancel':[('readonly', True)], 'refuse':[('readonly', True)],
              'validate1':[('readonly', True)],
              'validate':[('readonly', True)]},
    )
    inhability_subcategory_id = fields.Many2one('hr.leave.subcategory', "Subcategory",
        states={'cancel':[('readonly', True)], 'refuse':[('readonly', True)], 'validate1':[('readonly', True)], 'validate':[('readonly', True)]},
    )
    time_type = fields.Selection(related='holiday_status_id.time_type', store=True)
    # Documents field
    partner_id = fields.Many2one(related='employee_id.address_home_id', store=True)
    document_count = fields.Integer('Document Count', compute='_compute_document_count')
    document_ids = fields.One2many('documents.document', 'leave_id', string='Set Tags')
    reason_reject = fields.Many2one('hr.leave.reason.reject', string="Reason Reject")
    description_reject = fields.Text(string="Description Reject")
    description_cancellation = fields.Text(string="Description Cancellation")
    reject_cancellation = fields.Text(string="Reject Cancellation")

    # Signature
    pdf = fields.Many2one('ir.attachment', string="PDF", copy=False, readonly=False)
    sign_status = fields.Selection([("sent", "Signatures in Progress"),
                                    ("signed", "Fully Signed"),
                                    ("canceled", "Canceled")], related='sign_request_id.state')
    sign_request_id = fields.Many2one('sign.request', string='Sign Request')
    pdf_sign = fields.Many2one('ir.attachment', string="PDF Sign", copy=False, compute='compute_pdf_sign', store=True)

    # Fields for reports
    date_start_contract_char = fields.Char(compute='_get_format_dates', string='Date start (Letters)')
    max_leaves = fields.Integer(compute='_compute_remaining_days', string='Max Leaves')
    remaining_days_qty = fields.Integer(compute='_compute_remaining_days', string='Remaining')
    date_of_return = fields.Date(string='Date of return', compute='_get_date_of_return', store=True)
    date_of_return_char = fields.Char(string='Date of return (format)', compute='_get_date_of_return', store=True)
    year = fields.Integer(string='Año', compute='_ge_year_period', store=True)
    year_to = fields.Integer(string='Año', compute='_ge_year_period', store=True)
    date_approve = fields.Date(string='Date Approve')
    date_approve_chart = fields.Char(string='Date Approve (format)', store=True)
    date_from_char = fields.Char(compute='_get_format_dates', string='From')
    date_to_char = fields.Char(compute='_get_format_dates', string='To')
    description = fields.Char(compute='_get_description', string='Description')
    cancellation = fields.Boolean(string="Cancellation")

    @api.depends('sign_request_id.completed_document')
    def compute_pdf_sign(self):
        for res in self:
            if res.sign_status == 'signed':
                attachment = self.env['ir.attachment'].search([
                    ('res_model', '=', 'sign.request'),
                    ('res_id', '=', res.sign_request_id.id),
                    ('res_field', '=', 'completed_document')
                ], limit=1)
                attachment.write({'name': res.pdf.name})
                res.pdf_sign = attachment
                folder_id = res.employee_id._get_document_folder()
                self.env['documents.document'].create({
                    'name': attachment.name,
                    'folder_id': folder_id.id if folder_id else None,
                    'res_model': res._name,
                    'res_id': res.id,
                    'attachment_id': attachment.id,
                    'leave_id': res.id
                })

    def _get_format_dates(self):
        self.date_of_return_char = '%s' % format_date(self.env, self.date_of_return)
        self.date_from_char = '%s' % format_date(self.env, self.request_date_from)
        self.date_to_char = '%s' % format_date(self.env, self.request_date_to)
        self.date_start_contract_char = '%s' % format_date(self.env, self.contract_id.previous_contract_date if self.contract_id.previous_contract_date else self.contract_id.date_start)

    @api.depends('employee_id', 'holiday_status_id', 'number_of_days_display')
    def _compute_remaining_days(self):
        data_days = {}
        employee_id = self.employee_id.id

        if employee_id:
            data_days = self.holiday_status_id.get_employees_days([employee_id])[employee_id]

        for holiday in self:
            result = data_days.get(holiday.holiday_status_id.id, {})
            holiday.max_leaves = result.get('max_leaves', 0)
            holiday.remaining_days_qty = result.get('remaining_leaves', 0)

    @api.depends('name')
    def _get_description(self):
        for res in self:
            res.description = res.name if res.name else " "

    @api.depends('date_from', 'date_to')
    def _get_date_of_return(self):
        for holiday in self:
            holiday.date_of_return = holiday.request_date_to + relativedelta(days=1)
            list_days = []
            for i in holiday.employee_id.resource_calendar_id.attendance_ids:
                list_days.append(int(i.dayofweek))
            ready = False
            while ready != True:
                if holiday.date_of_return.weekday() not in list_days:
                    holiday.date_of_return = holiday.date_of_return + relativedelta(days=1)
                else:
                    break
        return

    @api.depends('holiday_status_id')
    def _ge_year_period(self):
        for holiday in self:
            if holiday.holiday_status_id.time_type in ['holidays', 'personal']:
                try:
                    holiday.year = int(holiday.holiday_status_id.code.split('-')[-1])
                    holiday.year_to = holiday.year + 1
                except:
                    holiday.year = False
            else:
                holiday.year = holiday.date_from.year
                holiday.year_to = holiday.year

    @api.constrains('holiday_status_id', 'request_date_from', 'request_date_to')
    def _check_holidays_other_years(self):
        for holiday in self:
            """
                this method verifies that there are no consecutive vacations of different years for the same employee
            """
            if holiday.time_type == 'holidays':
                yesterday = holiday.request_date_from + relativedelta(days=-1)
                tomorroy = holiday.request_date_to + relativedelta(days=1)
                res_count = self.search([
                    ('state', 'not in', ['refuse', 'cancel', 'confirm']),
                    ('holiday_status_id.time_type', '=', 'holidays'),
                    ('holiday_status_id.code', '!=', holiday.holiday_status_id.code),
                    ('employee_id', '=', holiday.employee_id.id),
                    '|', ('request_date_to', '=', yesterday), ('request_date_from', '=', tomorroy),
                ])
                if res_count:
                    raise ValidationError(_('There cannot be consecutive vacations of different years'))
            if holiday.time_type == 'personal':
                yesterday = holiday.request_date_from + relativedelta(days=-1)
                tomorroy = holiday.request_date_to + relativedelta(days=1)
                res_count = self.search([
                    ('state', 'not in', ['refuse', 'cancel', 'confirm']),
                    ('holiday_status_id.time_type', '=', 'personal'),
                    ('employee_id', '=', holiday.employee_id.id),
                    '|', ('request_date_to', '=', yesterday), ('request_date_from', '=', tomorroy),
                ])
                if res_count:
                    raise ValidationError(_('You cannot request consecutive personal days'))

    @api.constrains('state', 'number_of_days', 'holiday_status_id')
    def _check_holidays(self):
        mapped_days = self.mapped('holiday_status_id').get_employees_days(self.mapped('employee_id').ids)
        for holiday in self:
            # if self.holiday_status_id.time_type in ['holidays']:
            #     if holiday.number_of_days <= 1:
            #         raise ValidationError(_('They cannot take a vacation of one day or less'))
            if holiday.holiday_type != 'employee' or not holiday.employee_id or holiday.holiday_status_id.allocation_type == 'no':
                continue
            leave_days = mapped_days[holiday.employee_id.id][holiday.holiday_status_id.id]
            if float_compare(leave_days['remaining_leaves'], 0, precision_digits=2) == -1 or float_compare(leave_days['virtual_remaining_leaves'], 0, precision_digits=2) == -1:
                raise ValidationError(
                    _('The number of remaining time off is not sufficient for this time off type %s.\n'
                      'Please also check the time off waiting for validation. No. Employee %s') %(holiday.holiday_status_id.code, holiday.employee_id.registration_number))

    def _compute_document_count(self):
        for record in self:
            docs = self.env['documents.document'].search([('res_model', '=', record._name), ('res_id', 'in', record.ids)])
            record.document_count = len(docs)

    def action_see_documents(self):
        self.ensure_one()
        folder_id = self.employee_id._get_document_folder()
        return {
            'name': _('Documents'),
            'res_model': 'documents.document',
            'type': 'ir.actions.act_window',
            'views': [(False, 'kanban')],
            'view_mode': 'kanban',
            'domain': [('res_model', '=', self._name), ('res_id', 'in', self.ids)],
            'context': {
                "default_folder_id": folder_id.id,
                "searchpanel_default_folder_id": folder_id.id
            },
        }

    def action_validate(self):
        super(HolidaysRequest, self).action_validate()
        for holiday in self:
            holiday.date_approve = fields.Date.context_today(self)
            holiday.date_approve_chart = '%s' % format_date(self.env, holiday.date_approve)
            # Create Report
            if holiday.holiday_status_id.time_type in ['holidays']:
                template = self.env.ref('hr_holidays_edi_mx.action_report_tmpl_holidays_report')
                mimetype, out, filename, ext = template.render_any_docs([holiday.id])

                attachment = holiday.env['ir.attachment'].sudo().create({
                    'name': filename,
                    'type': 'binary',
                    'datas': base64.encodebytes(out),
                    'res_model': holiday._name,
                    'res_id': holiday.id
                })
                folder_id = holiday.employee_id._get_document_folder()
                self.env['documents.document'].create({
                    'name': filename,
                    'folder_id': folder_id.id if folder_id else None,
                    'res_model': holiday._name,
                    'res_id': holiday.id,
                    'attachment_id': attachment.id,
                    'leave_id': holiday.id
                })
                holiday.write({'pdf': attachment.id})
                holiday.send_pdf_to_sign()

            if holiday.holiday_status_id.time_type in ['personal']:
                template = self.env.ref('hr_holidays_edi_mx.action_report_tmpl_personal_days_report')
                mimetype, out, filename, ext = template.render_any_docs([holiday.id])

                attachment = self.env['ir.attachment'].sudo().create({
                    'name': filename,
                    'type': 'binary',
                    'datas': base64.encodebytes(out),
                    'res_model': holiday._name,
                    'res_id': holiday.id
                })
                folder_id = holiday.employee_id._get_document_folder()
                self.env['documents.document'].create({
                    'name': filename,
                    'folder_id': folder_id.id if folder_id else None,
                    'res_model': holiday._name,
                    'res_id': holiday.id,
                    'attachment_id': attachment.id,
                    'leave_id': holiday.id
                })
                holiday.write({'pdf': attachment.id})
                holiday.send_pdf_to_sign()
            holiday.send_mail_notify_approve()
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        if self.holiday_status_id.time_type in ['holidays', 'personal']:
            if self.pdf_sign:
                self.env['documents.document'].search([
                    ('res_id', '=', self.id),
                    ('res_model', '=', self._name),
                    ('attachment_id', '=', self.pdf_sign.id),
                ]).unlink()
        self.send_mail_notify_cancel()
        return True

    def action_reject_cancellation(self):
        self.cancellation = False
        self.send_mail_notify_reject_cancellation()
        return True

    def send_pdf_to_sign(self):
        if (not self.sign_request_id or self.sign_status == 'canceled') and self.pdf:
            # reading the pdf
            parser = PDFParser(io.BytesIO(base64.b64decode(self.pdf.datas)))
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
                        if not 'Firma de Conformidad' in obj.get_text():
                            continue
                        x = obj.bbox[0]
                        y = obj.bbox[3]

                    # if it's a container, recurse
                    elif isinstance(obj, pdfminer.layout.LTFigure):
                        parse_obj(obj._objs)
                return x, y

            page_num = 0
            # loop over all pages in the document
            for page in PDFPage.get_pages(io.BytesIO(base64.b64decode(self.pdf.datas))):
                page_num += 1
                # read the page into a layout object
                interpreter.process_page(page)
                layout = device.get_result()

                x, y = parse_obj(layout._objs)
                x, y = x / page.mediabox[2], (page.mediabox[3] - y) / page.mediabox[3]

                if x and y:
                    break

            page = page_num
            posX = x + 0.025
            posY = y - 0.070  # the height
            width = 0.171
            height = 0.040
            SignSendRequest = self.env['sign.send.request']
            SignTemplate = self.env['sign.template']
            sign_template = SignTemplate.create({
                'name': self.pdf.name,
                'attachment_id': self.pdf.id,
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
            if not self.employee_id.user_id.partner_id.id and not self.employee_id.address_home_id.id:
                return
            sign_send_request = SignSendRequest.create({
                'template_id': sign_template.id,
                'filename': sign_template.name,
                'signer_ids': [(0, False, {
                    'role_id': self.env['sign.item.role'].search([('name', '=', 'Empleado')], limit=1).id,
                    'partner_id': self.employee_id.user_id.partner_id.id if self.employee_id.user_id else self.employee_id.address_home_id.id,
                })],
                'signers_count': 1,
                'signer_id': self.employee_id.address_home_id.id,
                'subject': _("Signature Request - %s") % sign_template.attachment_id.name
            }).sudo()
            request = sign_send_request.create_request()
            self.sign_request_id = request['id']
        return request

    def action_refuse(self):
        self.sign_request_id.unlink()
        res = super(HolidaysRequest, self).action_refuse()
        self.send_mail_notify_refuse()
        if self.pdf:
            self.pdf.unlink()
        return res

    @api.onchange('type_inhability_id')
    def onchange_type_inhability_id(self):
        self.inhability_classification_id = False
        domain = {
            'inhability_classification_id':[
                ('id', 'in', self.type_inhability_id.classification_ids.ids)
            ]
        }
        return {'domain': domain}

    @api.onchange('inhability_classification_id')
    def onchange_inhability_classification_id(self):
        self.inhability_category_id = False
        domain = {'inhability_category_id': [('id', 'in', self.inhability_classification_id.category_ids.ids)]}
        return {'domain': domain}

    @api.onchange('inhability_category_id')
    def onchange_inhability_category_id(self):
        self.inhability_subcategory_id = False
        domain = {'inhability_subcategory_id': [('id', 'in', self.inhability_category_id.subcategory_ids.ids)]}
        return {'domain': domain}

    @api.onchange('employee_id')
    def onchange_employee_id(self):
        self.contract_id = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee_id.id),
            ('contracting_regime', '=', '02'),
            ('state', '=', 'open')
        ], limit=1)

    def send_mail_notify_approve(self):
        '''
           This method sends the holiday approval notifications
        '''
        if self.holiday_status_id.time_type in ['holidays','personal']:
            partner_ids = self.env['res.partner']
            partner_ids |= self.employee_id.mapped('responsible_holidays.address_home_id')
            partner_ids |= self.employee_id.address_home_id
            partner_ids |= self.employee_id.approver_kiosk_id.partner_id
            # partner_ids |= res.employee_id.leave_manager_id.partner_id
            emails = partner_ids.mapped('email')
            ctx = {
                'email_to': ','.join([email for email in emails if email]),
                'email_from': self.employee_id.company_id.email or self.employee_id.address_home_id.email,
                'send_email': True,
            }
            if self.holiday_status_id.time_type in ['holidays']:
                template = self.env.ref('hr_holidays_edi_mx.mail_template_holidays_approve')
            else:
                template = self.env.ref('hr_holidays_edi_mx.mail_template_personal_days_approve')
            template.with_context(ctx).send_mail(self.id, force_send=True, raise_exception=False)

    def send_mail_notify_refuse(self):
        '''
            This method sends notifications of cancellation of vacations
        '''
        if self.holiday_status_id.time_type in ['holidays','personal']:
            partner_ids = self.env['res.partner']
            partner_ids |= self.employee_id.mapped('responsible_holidays.address_home_id')
            partner_ids |= self.employee_id.address_home_id
            partner_ids |= self.employee_id.approver_kiosk_id.partner_id
            # partner_ids |= res.employee_id.leave_manager_id.partner_id
            emails = partner_ids.mapped('email')
            ctx = {
                'email_to': ','.join([email for email in emails if email]),
                'email_from': self.employee_id.company_id.email or self.employee_id.address_home_id.email,
                'send_email': True,
            }
            if self.holiday_status_id.time_type in ['holidays']:
                template = self.env.ref('hr_holidays_edi_mx.mail_template_holidays_refuse')
            else:
                template = self.env.ref('hr_holidays_edi_mx.mail_template_personal_days_refuse')
            template.with_context(ctx).send_mail(self.id, force_send=True, raise_exception=False)

    def send_mail_notify_cancel(self):
        '''
           This method sends the holiday cancellation notifications
        '''
        if self.holiday_status_id.time_type in ['holidays', 'personal']:
            partner_ids = self.env['res.partner']
            partner_ids |= self.employee_id.mapped('responsible_holidays.address_home_id')
            partner_ids |= self.employee_id.address_home_id
            partner_ids |= self.employee_id.approver_kiosk_id.partner_id
            emails = partner_ids.mapped('email')
            ctx = {
                'email_to': ','.join([email for email in emails if email]),
                'email_from': self.employee_id.company_id.email or self.employee_id.address_home_id.email,
                'send_email': True,
            }
            if self.holiday_status_id.time_type in ['holidays']:
                template = self.env.ref('hr_holidays_edi_mx.mail_template_holidays_cancel')
            else:
                template = self.env.ref('hr_holidays_edi_mx.mail_template_personal_days_cancel')
            template.with_context(ctx).send_mail(self.id, force_send=True, raise_exception=False)

    def send_mail_notify_reject_cancellation(self):
        '''
           This method sends the leave reject cancellation notifications
        '''
        if self.holiday_status_id.time_type in ['holidays', 'personal']:
            partner_ids = self.env['res.partner']
            partner_ids |= self.employee_id.mapped('responsible_holidays.address_home_id')
            partner_ids |= self.employee_id.address_home_id
            partner_ids |= self.employee_id.approver_kiosk_id.partner_id
            emails = partner_ids.mapped('email')
            ctx = {
                'email_to': ','.join([email for email in emails if email]),
                'email_from': self.employee_id.company_id.email or self.employee_id.address_home_id.email,
                'send_email': True,
            }
            if self.holiday_status_id.time_type in ['holidays']:
                template = self.env.ref('hr_holidays_edi_mx.mail_template_holidays_reject_cancel')
            else:
                template = self.env.ref('hr_holidays_edi_mx.mail_template_personal_reject_cancel')
            template.with_context(ctx).send_mail(self.id, force_send=True, raise_exception=False)

    @api.model
    def create(self, vals):
        res = super(HolidaysRequest, self).create(vals)
        if res.holiday_status_id.time_type in ['holidays', 'personal']:
            partner_ids = self.env['res.partner']
            partner_ids |= res.employee_id.mapped('responsible_holidays.address_home_id')
            partner_ids |= res.employee_id.address_home_id
            partner_ids |= res.employee_id.approver_kiosk_id.partner_id
            partner_ids |= res.employee_id.leave_manager_id.partner_id
            res._message_subscribe(partner_ids=partner_ids.ids)

            if res.holiday_status_id.time_type in ['holidays','personal']:
                emails = partner_ids.mapped('email')
                ctx = {
                    'email_to': ','.join([email for email in emails if email]),
                    'email_from': res.employee_id.company_id.email or res.employee_id.address_home_id.email,
                    'send_email': True,
                }
                if res.holiday_status_id.time_type in ['holidays']:
                    template = self.env.ref('hr_holidays_edi_mx.mail_template_holidays_create')
                else:
                    template = self.env.ref('hr_holidays_edi_mx.mail_template_personal_days_create')
                template.with_context(ctx).send_mail(res.id, force_send=True, raise_exception=False)
        return res


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    date_due = fields.Date(string="Date Due", readonly=True,
                           states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]})
    is_due = fields.Boolean(string="Due", compute='_get_due_boolean', store=True)

    @api.depends('date_due')
    def _get_due_boolean(self):
        '''
            This method compares and shows if the assignment is overdue
        '''
        for res in self:
            if res.date_due:
                current_date = fields.Date.context_today(res)
                res.is_due = True if current_date > res.date_due else False

    @api.model
    def create(self, values):
        if not values.get('date_due', False):
            type_id = self.env['hr.leave.type'].browse(int(values['holiday_status_id']))
            try:
                date_init = date(int(type_id.code[-4:]), 1, 1)
            except Exception:
                res = super(HrLeaveAllocation, self).create(values)
                return res

            employee = self.env['hr.employee'].browse(int(values['employee_id']))
            contract = self.env['hr.contract'].search([('employee_id', '=', employee.id)], order='date_end', limit=1)
            contract_stat_date = contract.previous_contract_date or contract.date_start
            month = contract_stat_date.month
            day = contract_stat_date.day

            if month == 2 and day == 29:
                day = calendar.monthrange(int(date_init.year), int(month))[1]
            date_1 = date(date_init.year, month, day)
            date_aniversary = False
            if date_1 >= date_init:
                date_aniversary = date_1
            else:
                date_aniversary = date(date_init.year + 1, month, day)

            values['date_due'] = date_aniversary + relativedelta(months=type_id.duration_months)
        res = super(HrLeaveAllocation, self).create(values)
        return res


class Document(models.Model):
    _inherit = 'documents.document'

    leave_id = fields.Many2one('hr.leave', string='Leave')


class HolidaysReasonReject(models.Model):
    _name = 'hr.leave.reason.reject'
    _description = "Holidays Reason Reject"

    name = fields.Char(string="Name")


