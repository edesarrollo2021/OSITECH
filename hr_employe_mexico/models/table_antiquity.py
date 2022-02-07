# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp

class hrTableAntiquity(models.Model):
    _name = 'hr.table.antiquity'
    _description = 'Table antiquity'
    
    name = fields.Char("Name")
    table_antiquity_ids = fields.One2many(comodel_name='hr.table.antiquity.line', inverse_name='antiquity_line_id')


class hrTableantiquitysLine(models.Model):
    _name = 'hr.table.antiquity.line'
    _description = 'Table antiquity line'

    def _get_factor_integration(self):
        '''
        This method calculates the integration factor based on the employee's seniority
        '''
        for line in self:
            line.factor = round((((line.holidays*(line.vacation_cousin/100))+365+line.aguinaldo)/365),4)

    antiquity_line_id = fields.Many2one('hr.table.antiquity', string='Table antiquity')
    year = fields.Integer('Antiquity/Years', digits=dp.get_precision('Antiquity'))
    holidays = fields.Integer('Holidays/Days', digits=dp.get_precision('Antiquity'))
    vacation_cousin = fields.Integer('Vacation Cousin (%)', digits=dp.get_precision('Antiquity'))
    aguinaldo = fields.Integer('Aguinaldo/Days', digits=dp.get_precision('Antiquity'))
    factor = fields.Float('Integration factor', digits=dp.get_precision('Antiquity'), compute='_get_factor_integration')

