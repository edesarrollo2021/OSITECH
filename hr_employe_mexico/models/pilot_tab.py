# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from odoo.addons import decimal_precision as dp

class hrPilotTab(models.Model):
    _name = 'hr.pilot.tab'
    _description = 'Pilot Tab'
    
    name = fields.Char("Name")
    pilot_tab_line = fields.One2many(comodel_name='hr.pilot.tab.line', inverse_name='pilot_tab_id')


class hrPilotTabLine(models.Model):
    _name = 'hr.pilot.tab.line'
    _description = 'Pilot Tab line'

    pilot_tab_id = fields.Many2one('hr.pilot.tab', string='Pilor Tab')
    year = fields.Integer('Antiquity/Years', required=True)
    salary = fields.Float('Salary', required=True)
    seniority_premium = fields.Float('Seniority premium')

