from odoo import fields, models, api


class ResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    time_type = fields.Selection(selection_add=[
        ('holidays', 'Holidays'),
        ('inability', 'Inability'),
        ('personal', 'Personal Days'),
    ])

