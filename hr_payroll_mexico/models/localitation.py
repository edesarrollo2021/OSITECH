# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import ValidationError, UserError


class ResCountryState(models.Model):
    _inherit = 'res.country.state'
    
    state_isn_line = fields.One2many('res.country.state.isn', 'state_id', string="station")
    type_isn = fields.Selection([
        ('fixed', 'Fixed fee'),
        ('range', 'Range'),
    ], required=True, default='fixed', string='Type',
        help="Select type of tax by state.\n" \
             "Select 'Fixed fee' if it is a fixed rate.\n" \
             "Select 'Range' if it is a Range.")
    percent = fields.Float(string='Percentage', digits=dp.get_precision('Excess'))
    isn_line = fields.One2many('hr.isn.range.line', 'state_isn_id', string="Ranges")

class ResCountryStateIsn(models.Model):
    _name = 'res.country.state.isn'

    name = fields.Char(string="Station",copy=False)
    state_id = fields.Many2one('res.country.state', string='State')
    type_isn = fields.Selection([
        ('fixed', 'Fixed fee'),
        ('range', 'Range'),
    ], required=True, default='fixed', string='Type',
        help="Select type of tax by state.\n" \
             "Select 'Fixed fee' if it is a fixed rate.\n" \
             "Select 'Range' if it is a Range.")
    percent = fields.Float(string='Percentage', digits=dp.get_precision('Excess'))
    isn_line = fields.One2many('hr.isn.range.line', 'state_isn_id', string="Ranges")
    gratification = fields.Boolean(string="Expensive cost of living gratification")
    gratification_amount = fields.Float(string="Gratification Amount")

    @api.onchange('type_isn')
    def _onchange_type(self):
        if self.type_isn == 'fixed':
            if self.isn_line:
                self.isn_line.unlink()
        if self.type_isn == 'range':
            self.percent = False


class HrIsnLine(models.Model):
    _name = 'hr.isn.range.line'
    _order = 'lim_inf'
    
    isn_id = fields.Many2one('hr.isn', string='ISN')
    state_isn_id = fields.Many2one('res.country.state.isn', string='State ISN')
    lim_inf = fields.Float(string='Lower limit', digits=dp.get_precision('Excess'))
    lim_sup = fields.Float(string='Upper limit', digits=dp.get_precision('Excess'))
    c_fija = fields.Float(string='Fixed fee', digits=dp.get_precision('Excess'))
    s_excedente = fields.Float(string='Over surplus (%)', digits=dp.get_precision('Excess'),
                               help="percent to be applied over the lower limit surplus")

    @api.constrains('lim_sup')
    def validate_isn_line(self):
        self.not_be_less()

    def not_be_less(self):
        for record in self:
            if record.lim_sup <= record.lim_inf:
                raise UserError(_('The upper limit cannot be less than or equal to the lower limit'))


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    state_isn_id = fields.Many2one('res.country.state.isn', string='Station ISN', required=True)


class EmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    state_isn_id = fields.Many2one('res.country.state.isn', readonly=True)
