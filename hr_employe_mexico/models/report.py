from odoo import fields, models, api


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    contract = fields.Boolean(string="Contract")
