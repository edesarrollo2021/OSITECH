# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.osv import expression


class CostCenter(models.Model):
    _name = 'hr.cost.center'
    _description = 'Cost Center'

    name = fields.Char("Name", required=True, copy=False)
    code = fields.Char("Number", required=False, copy=False, default='/')
    country_id = fields.Many2one('res.country', string='Country', required=True,
                                 default=lambda self: self.env['res.country'].search([('code', '=', 'MX')]))
    state_id = fields.Many2one("res.country.state", readonly=False, domain="[('country_id', '=', country_id)]")
    locality_id = fields.Many2one('l10n_mx_edi.res.locality', string='Locality',
                                              readonly=False, help='Municipality configured for this company')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The cost center name must be unique !'),
        ('code_uniq', 'unique(code)', 'The cost center number  must be unique !')
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
        result = super(CostCenter, self).create(vals)
        if result.code == '/':
            result.code = self.env['ir.sequence'].next_by_code('hr.cost.center')
        result.name = result.name.upper()
        result.code = result.code.upper()
        return result

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = vals.get('name').upper()
        if vals.get('code'):
            vals['code'] = vals.get('code').upper()

        res = super(CostCenter, self).write(vals)
        return res
