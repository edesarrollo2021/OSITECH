# -*- coding: utf-8 -*-

from odoo import fields, models, api


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    folder_id = fields.Many2one('documents.folder', string="Workspace", ondelete="restrict", tracking=True,
                                required=False, index=True)


class Documents(models.Model):
    _inherit = 'documents.document'

    @api.model
    def create(self, vals):
        if not vals.get('folder_id') and vals.get('attachment_id'):
            Attachment = self.env['ir.attachment'].browse(vals.get('attachment_id'))
            vals['folder_id'] = Attachment.folder_id.id

        res = super(Documents, self).create(vals)
        if res.res_model == 'hr.employee':
            employee = self.env['hr.employee'].browse(res.res_id)
            res.partner_id = employee.address_home_id if employee.address_home_id else res.partner_id
        return res

