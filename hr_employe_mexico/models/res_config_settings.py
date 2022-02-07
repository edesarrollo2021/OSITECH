# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.addons import decimal_precision as dp


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    days_factor = fields.Float(related="company_id.days_factor", readonly=False, digits=dp.get_precision('Antiquity'))
    smvdf = fields.Float(related="company_id.smvdf", readonly=False)
    general_uma = fields.Integer(related="company_id.general_uma", readonly=False)
    umi = fields.Float(related="company_id.umi", readonly=False)
    uma = fields.Float(related="company_id.uma", readonly=False)
    personal_days_factor = fields.Integer(related="company_id.personal_days_factor", readonly=False)
    minimum_wage = fields.Float(related="company_id.minimum_wage", readonly=False)
    minimum_wage_border = fields.Float(related="company_id.minimum_wage_border", readonly=False)
    punctuality_attendance_voucher = fields.Float(related="company_id.punctuality_attendance_voucher", readonly=False)
    gasoline_voucher = fields.Float(related="company_id.gasoline_voucher", readonly=False)
    resource_calendar_leave_id = fields.Many2one(
        'resource.calendar', 'Company Working Hours',
        related='company_id.resource_calendar_leave_id', readonly=False, required=False)
    compensation_ro = fields.Float(related="company_id.compensation_ro", readonly=False)
    minimum_triple_compensation = fields.Float(related="company_id.minimum_triple_compensation", readonly=False)
    
    pilots_union_clause = fields.Float(related="company_id.pilots_union_clause", readonly=False)
    aspiring_pilots_union_clause = fields.Float(related="company_id.aspiring_pilots_union_clause", readonly=False)
    pilots_retreat = fields.Float(related="company_id.pilots_retreat", readonly=False)
    
    
    flight_attendant_union_clause = fields.Float(related="company_id.flight_attendant_union_clause", readonly=False)
    aspiring_flight_attendant_union_clause = fields.Float(related="company_id.aspiring_flight_attendant_union_clause", readonly=False)
    flight_attendant_retreat = fields.Float(related="company_id.flight_attendant_retreat", readonly=False)
    union_aid = fields.Float(related="company_id.union_aid", readonly=False)
    cultural_sports_evolution = fields.Float(related="company_id.cultural_sports_evolution", readonly=False)
    union_dues = fields.Float(related="company_id.union_dues", readonly=False)
    personal_savings_bank = fields.Float(related="company_id.personal_savings_bank", readonly=False)
    social_objective = fields.Float(related="company_id.social_objective", readonly=False)
    
    minimum_discount_covid_base = fields.Float(related="company_id.minimum_discount_covid_base", readonly=False)


class Company(models.Model):
    _inherit = 'res.company'

    days_factor = fields.Float('Days Factor', readonly=False, default=30.4, digits=dp.get_precision('Antiquity'))
    smvdf = fields.Float(string="SMVDF")
    general_uma = fields.Integer(string="General (UMA)", default=25)
    umi = fields.Float(string="UMI")
    uma = fields.Float(string="UMA")
    personal_days_factor = fields.Integer(string="Personal Days", help="Number of Personal Days by default")
    folder_document_id = fields.Many2one('documents.folder', string='Folder Documents', required=False,
                                         help="Folder where all documents associated with company will be stored.")
    minimum_wage = fields.Float(string="Minimum wage")
    minimum_wage_border = fields.Float(string="Minimum wage north border free zone")
    
    resource_calendar_leave_id = fields.Many2one('resource.calendar', 'Company Working leave Hours', readonly=False)
    
    punctuality_attendance_voucher = fields.Float('Punctuality and attendance voucher')
    gasoline_voucher = fields.Float('Gasoline voucher')
    compensation_ro = fields.Float('Compensation ro')
    minimum_triple_compensation = fields.Float('Minimum triple compensation')
    
    pilots_union_clause = fields.Float('Pilots union clause')
    aspiring_pilots_union_clause = fields.Float('Aspiring pilots union clause')
    pilots_retreat = fields.Float('Pilots retreat')
    
    flight_attendant_union_clause = fields.Float('Flight attendant union clause')
    aspiring_flight_attendant_union_clause = fields.Float('Aspiring flight attendant union clause')
    flight_attendant_retreat = fields.Float('Flight attendant retreat')
    union_aid = fields.Float('Union aid')
    cultural_sports_evolution = fields.Float('Cultural and sports evolution')
    union_dues = fields.Float('Union dues')
    personal_savings_bank = fields.Float('Personal savings bank')
    social_objective = fields.Float('% Social objective')
    
    minimum_discount_covid_base = fields.Float('Minimum discount covid base')
    
