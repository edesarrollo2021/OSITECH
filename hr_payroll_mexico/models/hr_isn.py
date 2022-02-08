# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools import float_round
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError, UserError


class HrIsn(models.Model):
    _name = 'hr.isn'
    _description = 'Payroll Tax'
    _order = 'state_id asc, year desc'

    name = fields.Char(string="Name", store=True, readonly=True, copy=False)
    year = fields.Integer(string='Year', size=4, required=True, copy=False)
    country_id = fields.Many2one('res.country', string='Country', store=True,
                                 default=lambda self: self.env['res.company']._company_default_get().country_id)
    state_id = fields.Many2one('res.country.state', string='State', required=True)
    type = fields.Selection([
        ('fixed', 'Fixed fee'),
        ('range', 'Range'),
    ], required=True, default='fixed', string='Type',
        help="Select type of tax by state.\n" \
             "Select 'Fixed fee' if it is a fixed rate.\n" \
             "Select 'Range' if it is a Range.")
    percent = fields.Float(string='Percentage', digits=dp.get_precision('Excess'))
    isn_line = fields.One2many('hr.isn.range.line', 'isn_id', string="Federal entities")

    def name_get(self):
        result = []
        for isn in self:
            name = 'ISN %s %s ' % (isn.state_id.name.upper(), str(isn.year))
            result.append((isn.id, name))
        return result

    @api.onchange('type')
    def _onchange_type(self):
        if self.type == 'fixed':
            if self.isn_line:
                self.isn_line.unlink()
        if self.type == 'range':
            self.percent = False

    def get_value_isn(self, state_id, amount, year):
        isn_id = self.search([('state_id', '=', state_id), ('year', '=', year)], limit=1)
        amount_tax = 0.0
        percent = 0.0
        for isn in isn_id:
            if isn.type == 'fixed':
                amount_tax = float_round((amount / 100) * isn.percent, precision_digits=3)
                percent = isn.percent
            if isn.type == 'range':
                fixed_fee = isn.isn_line.filtered(lambda d: amount >= d.lim_inf and amount <= d.lim_sup)
                excedente = float_round(amount - fixed_fee.lim_inf, 4)
                total_taxt = float_round((excedente / 100) * fixed_fee.s_excedente, 4)
                amount_tax = float_round(total_taxt + fixed_fee.c_fija, 4)
                percent = fixed_fee.s_excedente
        return {
            'amount': float_round(amount_tax, precision_digits=2, precision_rounding=None, rounding_method='UP'),
            'percent': percent
        }

    @api.model
    def _get_state_name(self, state_id):
        name_state = self.env['res.country.state'].search([('id', '=', state_id)]).name.upper()
        return name_state

    @api.model
    def create(self, vals):
        isn = super(HrIsn, self).create(vals)
        isn.name = 'ISN %s %s' % (isn.state_id.name.upper(), str(isn.year))
        return isn

    def write(self, vals):
        if 'state_id' and 'year' in vals:
            vals['name'] = 'ISN %s %s' % (self._get_state_name(vals['state_id']), vals['year'])
        if 'state_id' in vals and not 'year' in vals:
            vals['name'] = 'ISN %s %s' % (self._get_state_name(vals['state_id']), str(self.year))
        if not 'state_id' in vals and 'year' in vals:
            vals['name'] = 'ISN %s %s' % (self.state_id.name.upper(), str(self.year))
        return super(HrIsn, self).write(vals)


# ~ class HrIsnLine(models.Model):
    # ~ _name = 'hr.isn.range.line'
    # ~ _order = 'lim_inf'

    # ~ isn_id = fields.Many2one('hr.isn', string='ISN')
    # ~ lim_inf = fields.Float(string='Lower limit', digits=dp.get_precision('Excess'))
    # ~ lim_sup = fields.Float(string='Upper limit', digits=dp.get_precision('Excess'))
    # ~ c_fija = fields.Float(string='Fixed fee', digits=dp.get_precision('Excess'))
    # ~ s_excedente = fields.Float(string='Over surplus (%)', digits=dp.get_precision('Excess'),
                               # ~ help="percent to be applied over the lower limit surplus")

    # ~ @api.constrains('lim_sup')
    # ~ def validate_isn_line(self):
        # ~ self.not_be_less()

    # ~ def not_be_less(self):
        # ~ for record in self:
            # ~ if record.lim_sup <= record.lim_inf:
                # ~ raise UserError(_('The upper limit cannot be less than or equal to the lower limit'))
