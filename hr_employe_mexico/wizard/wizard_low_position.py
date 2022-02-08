# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LowPosition(models.TransientModel):
    _name = "low.position"
    _description = "Wizard to low position"

    date = fields.Date(string="Date of low", required=True)
    position_id = fields.Many2one("hr.job.position", string="Position", required=True)

    def change_position(self):
        if self.position_id.employee_id:
            self.position_id.change_employees(date_end=self.date)
