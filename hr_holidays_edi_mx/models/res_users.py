# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class ResUsers(models.Model):
    _inherit = "res.users"

    approve_holidays = fields.Boolean(string="Approve Holidays")
