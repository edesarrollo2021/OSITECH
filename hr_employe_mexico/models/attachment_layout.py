# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AttachmentLayout(models.Model):
    _name = 'attachment.layout'

    name = fields.Char(string='Name', required=True, copy=True,)
    attachment_ids = fields.Many2many('ir.attachment', 'attachment_layout_rel', 'attachment_id', 'layout_id', string="Attachment", required=True, copy=False)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "The name of the layout must be unique!"),
    ]
