# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.addons import decimal_precision as dp


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    configuration_table_id = fields.Many2one(related="company_id.configuration_table_id", readonly=False)
    pantry_voucher_factor = fields.Float(related="company_id.pantry_voucher_factor", readonly=False)
    holiday_bonus_factor = fields.Float(related="company_id.holiday_bonus_factor", readonly=False)
    bonus_factor = fields.Float(related="company_id.bonus_factor", readonly=False)
    savings_fund_factor = fields.Float(related="company_id.savings_fund_factor", readonly=False)
    extra_time_factor = fields.Float(related="company_id.extra_time_factor", readonly=False)
    sunday_prime_factor = fields.Float(related="company_id.sunday_prime_factor", readonly=False)
    clearance_factor = fields.Float(related="company_id.clearance_factor", readonly=False)
    factor_ptu = fields.Float(related="company_id.factor_ptu", readonly=False)
    vacation_input_id = fields.Many2one(related="company_id.vacation_input_id", readonly=False)
    
    # == PAC web-services ==
    l10n_mx_edi_pac_payrol = fields.Selection(
        related='company_id.l10n_mx_edi_pac_payrol', readonly=False,
        string='MX PAC*')
    l10n_mx_edi_pac_test_env_payroll = fields.Boolean(
        related='company_id.l10n_mx_edi_pac_test_env_payroll', readonly=False,
        string='MX PAC test environment*')
    l10n_mx_edi_pac_username_payroll = fields.Char(
        related='company_id.l10n_mx_edi_pac_username_payroll', readonly=False,
        string='MX PAC username*')
    l10n_mx_edi_pac_password_payroll = fields.Char(
        related='company_id.l10n_mx_edi_pac_password_payroll', readonly=False,
        string='MX PAC password*')
    l10n_mx_edi_certificate_payroll_ids = fields.Many2many(
        related='company_id.l10n_mx_edi_certificate_payroll_ids', readonly=False,
        string='MX Certificates*')
    

class Company(models.Model):
    _inherit = 'res.company'

    configuration_table_id = fields.Many2one("table.settings", string="Table Settings")
    pantry_voucher_factor = fields.Float(string=_('Pantry Voucher (UMA)'), digits=dp.get_precision('Excess'), default=1)
    holiday_bonus_factor = fields.Float(string=_('Holiday Bonus (UMA)'), digits=dp.get_precision('Excess'), default=15)
    bonus_factor = fields.Float(string=_('Bonus (UMA)'), default=30)
    savings_fund_factor = fields.Float(string=_('Savings Fund (UMA)'), digits=dp.get_precision('Excess'), default=1.3)
    extra_time_factor = fields.Float(string=_('Extra Time (UMA)'), digits=dp.get_precision('Excess'), default=5)
    sunday_prime_factor = fields.Float(string=_('Sunday prime (UMA)'), digits=dp.get_precision('Excess'), default=1)
    clearance_factor = fields.Float(string=_('Clearance (UMA)'), digits=dp.get_precision('Excess'), default=90)
    factor_ptu = fields.Float(string=_('PTU (UMA)'), digits=dp.get_precision('Excess'), default=15)
    vacation_input_id = fields.Many2one("hr.payslip.input.type", string="Vacation Premium Input")
    
    # == PAC web-services ==
    l10n_mx_edi_pac_payrol = fields.Selection(
        selection=[('forsedi', 'Forsedi'),('sefactura', 'Sefactura')],
        string='PAC',
        help='The PAC that will sign/cancel the invoices',
        default='forsedi')
    l10n_mx_edi_pac_test_env_payroll = fields.Boolean(
        string='PAC test environment',
        help='Enable the usage of test credentials',
        default=False)
    l10n_mx_edi_pac_username_payroll = fields.Char(
        string='PAC username',
        help='The username used to request the seal from the PAC')
    l10n_mx_edi_pac_password_payroll = fields.Char(
        string='PAC password',
        help='The password used to request the seal from the PAC')
    l10n_mx_edi_certificate_payroll_ids = fields.Many2many('l10n_mx_edi.certificate', 'certificate_payroll_company_rel', 'company_id', 'certificate_id',
        string='Certificates')
