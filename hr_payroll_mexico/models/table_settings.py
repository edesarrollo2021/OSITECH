# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

from odoo.addons import decimal_precision as dp


class TableSettings(models.Model):
    _name = 'table.settings'
    _order = 'year desc'

    name = fields.Char('Name', required=True)
    year = fields.Integer('Year', required=True)

    ex_pantry_voucher_factor = fields.Float(string=_('Pantry Voucher'))
    ex_holiday_bonus_factor = fields.Float(string=_('Holiday Bonus'))
    ex_bonus_factor = fields.Float(string=_('Bonus'))
    ex_savings_fund_factor = fields.Float(string=_('Savings Fund'))
    ex_extra_time_factor = fields.Float(string=_('Extra Time'))
    ex_sunday_prime_factor = fields.Float(string=_('Sunday prime'))
    ex_clearance_factor = fields.Float(string=_('Clearance'))
    ex_factor_ptu = fields.Float(string=_('PTU'))

    isr_daily_ids = fields.One2many('table.isr.daily', 'table_id', "ISR Daily")
    isr_daily_subsidy_ids = fields.One2many('table.isr.daily.subsidy', 'table_id', "ISR Daily (Subsidy)")

    isr_weekly_ids = fields.One2many('table.isr.weekly', 'table_id', "ISR Weekly")
    isr_Weekly_subsidy_ids = fields.One2many('table.isr.weekly.subsidy', 'table_id', "ISR Weekly (Subsidy)")

    isr_decennial_ids = fields.One2many('table.isr.decennial', 'table_id', "ISR Decennial")
    isr_decennial_subsidy_ids = fields.One2many('table.isr.decennial.subsidy', 'table_id', "ISR Decennial (Subsidy)")

    isr_biweekly_ids = fields.One2many('table.isr.biweekly', 'table_id', "ISR Biweekly")
    isr_biweekly_subsidy_ids = fields.One2many('table.isr.biweekly.subsidy', 'table_id', "ISR Biweekly (Subsidy)")

    isr_monthly_ids = fields.One2many('table.isr.monthly', 'table_id', "ISR Monthly")
    isr_monthly_subsidy_ids = fields.One2many('table.isr.monthly.subsidy', 'table_id', "ISR Monthly (Subsidy)")

    isr_annual_ids = fields.One2many('table.isr.annual', 'table_id', "ISR Annual")


class TableIsrDaily(models.Model):
    _name = 'table.isr.daily'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Daily')
    lim_inf = fields.Float('Lower limit')
    lim_sup = fields.Float('Upper limit')
    c_fija = fields.Float('Fixed fee')
    s_excedente = fields.Float('Over surplus (%)', digits=dp.get_precision('Excess'))
    sequence = fields.Integer('Sequence')


class TableIsrDailySubsidy(models.Model):
    _name = 'table.isr.daily.subsidy'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Daily')
    lim_inf = fields.Float('Lower limit')
    lim_sup = fields.Float('Upper limit')
    s_mensual = fields.Float('Daily allowance')
    sequence = fields.Integer('Sequence')


class TableIsrWeekly(models.Model):
    _name = 'table.isr.weekly'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Weekly')
    lim_inf = fields.Float('Lower limit')
    lim_sup = fields.Float('Upper limit')
    c_fija = fields.Float('Fixed fee')
    s_excedente = fields.Float('Over surplus (%)', digits=dp.get_precision('Excess'))
    sequence = fields.Integer('Sequence')


class TableIsrWeeklySubsidy(models.Model):
    _name = 'table.isr.weekly.subsidy'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Weekly')
    lim_inf = fields.Float('Lower limit')
    lim_sup = fields.Float('Upper limit')
    s_mensual = fields.Float('Weekly allowance')
    sequence = fields.Integer('Sequence')

class TableIsrDecennial(models.Model):
    _name = 'table.isr.decennial'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Decennial')
    lim_inf = fields.Float('Lower limit')
    lim_sup = fields.Float('Upper limit')
    c_fija = fields.Float('Fixed fee')
    s_excedente = fields.Float('Over surplus (%)', digits=dp.get_precision('Excess'))
    sequence = fields.Integer('Sequence')


class TableIsrDecennialSubsidy(models.Model):
    _name = 'table.isr.decennial.subsidy'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Decennial')
    lim_inf = fields.Float('Lower limit')
    lim_sup = fields.Float('Upper limit')
    s_mensual = fields.Float('Decennial allowance')
    sequence = fields.Integer('Sequence')


class TableIsrBiweekly(models.Model):
    _name = 'table.isr.biweekly'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Biweekly')
    lim_inf = fields.Float('Lower limit')
    lim_sup = fields.Float('Upper limit')
    c_fija = fields.Float('Fixed fee')
    s_excedente = fields.Float('Over surplus (%)', digits=dp.get_precision('Excess'))
    sequence = fields.Integer('Sequence')


class TableIsrBiweeklySubsidy(models.Model):
    _name = 'table.isr.biweekly.subsidy'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Biweekly')
    lim_inf = fields.Float('Lower limit')
    lim_sup = fields.Float('Upper limit')
    s_mensual = fields.Float('Biweekly allowance')
    sequence = fields.Integer('Sequence')


class TableIsrMonthly(models.Model):
    _name = 'table.isr.monthly'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Monthly')
    lim_inf = fields.Float('Lower limit')
    lim_sup = fields.Float('Upper limit')
    c_fija = fields.Float('Fixed fee')
    s_excedente = fields.Float('Over surplus (%)', digits=dp.get_precision('Excess'))
    sequence = fields.Integer('Sequence')


class TableIsrMonthlySubsidy(models.Model):
    _name = 'table.isr.monthly.subsidy'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Monthly')
    lim_inf = fields.Float('Lower limit', digits=dp.get_precision('Excess'))
    lim_sup = fields.Float('Upper limit', digits=dp.get_precision('Excess'))
    s_mensual = fields.Float('Monthly allowance', digits=dp.get_precision('Excess'))
    sequence = fields.Integer('Sequence')


class TableIsrAnnual(models.Model):
    _name = 'table.isr.annual'
    _order = 'sequence'

    table_id = fields.Many2one('table.settings', string='ISR Annual')
    lim_inf = fields.Float('Lower limit', digits=dp.get_precision('Excess'))
    lim_sup = fields.Float('Upper limit', digits=dp.get_precision('Excess'))
    c_fija = fields.Float('Fixed fee')
    s_excedente = fields.Float('Over surplus (%)', digits=dp.get_precision('Excess') )
    sequence = fields.Integer('Sequence')
