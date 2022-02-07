# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.osv import expression


class HrWorkplace(models.Model):
    _name = 'hr.workplace'
    _description = 'Workplaces'

    name = fields.Char("Name", copy=False, required=True)
    code = fields.Char("code", copy=False, required=False, readonly=False, default='/')
    country_id = fields.Many2one('res.country', string='Country', required=True)
    city = fields.Char(string="City")
    state_id = fields.Many2one('res.country.state', string="Fed. State", domain="[('country_id', '=', country_id)]",
                               required=True)
    zip = fields.Char(string="ZIP")
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street 2")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The workplace name must be unique!'),
        ('code_uniq', 'unique(code)', 'The workplace number  must be unique!')
    ]

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
        return self._search(expression.AND([args, domain]), limit=limit, access_rights_uid=name_get_uid)

    @api.model
    def create(self, vals):
        result = super(HrWorkplace, self).create(vals)
        if result.code == '/':
            result.code = self.env['ir.sequence'].next_by_code('hr.workplace')
        result.name = result.name.upper()
        result.code = result.code.upper()
        return result

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = vals.get('name').upper()
        if vals.get('code'):
            vals['code'] = vals.get('code').upper()

        res = super(HrWorkplace, self).write(vals)
        return res
