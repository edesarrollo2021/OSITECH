# -*- coding: utf-8 -*-

from odoo import fields, models, api, _


class Partner(models.Model):
    _inherit = 'res.partner'

    country_id = fields.Many2one(default=lambda self: self.env['res.country'].search([('code', '=', 'MX')]))
    building = fields.Char(string="Building", help="Building and/or Department")
    street_number = fields.Char(string="Exterior/Block No.")
    street_number2 = fields.Char(string="Interior", help="Interior/Lot No.")
    curp = fields.Char("CURP", copy=False)
    rfc = fields.Char("RFC", copy=False)


class ResUsers(models.Model):
    _inherit = "res.users"

    place_of_birth = fields.Many2one('res.country.state', string='Place of Birth', groups="hr.group_hr_user")
