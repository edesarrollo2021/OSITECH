# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp

from odoo.addons.base_mexico.pyfiscal.generate_company import GenerateRfcCompany


class Company(models.Model):
    _inherit = 'res.company'

    employer_register_ids = fields.One2many('res.employer.register', 'company_id', "Employer Register")
    
    

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "And there is a company with this name!."),
    ]


class EmployerRegister(models.Model):
    _name = 'res.employer.register'
    _rec_name = 'employer_registry'

    def _default_country(self):
        country_id = self.env['res.country'].search([('code', '=', 'MX')], limit=1)
        return country_id

    company_id = fields.Many2one('res.company', "Company")
    employer_registry = fields.Char("Employer Registry", copy=False, required=True)
    electronic_signature = fields.Many2many('ir.attachment', string="Electronic Signature", required=False)
    validity_signature = fields.Date("Validity of Signature", required=False, copy=False)

    delegation_id = fields.Many2one('res.company.delegation', "Delegation", required=True)
    subdelegation_id = fields.Many2one('res.company.subdelegation', "Sub-Delegation", required=True)
    economic_activity = fields.Char("Economic activity", copy=False, required=True)
    state = fields.Selection([
        ('valid', 'Valid'),
        ('timed_out', 'Timed out'),
        ('revoked', 'Revoked'), ], default="valid")
    geographic_area = fields.Selection([
        ('1', 'General Minimum Wages'),
        ('2', 'Northern border'), ], 'Geographic area', required=True)
    risk_factor_ids = fields.One2many('res.group.risk.factor', 'employer_id', string="Annual Risk Factor")
    job_risk = fields.Selection([
        ('1', 'Class I'),
        ('2', 'Class II'),
        ('3', 'Class III'),
        ('4', 'Class IV'),
        ('5', 'Class V'),
        ('99', 'Not apply'),
    ], string='Job risk', required=True)
    country_id = fields.Many2one('res.country', default=_default_country, string="Country")
    city = fields.Char(string="City")
    state_id = fields.Many2one('res.country.state', string="Fed. State")
    zip = fields.Char(string="ZIP")
    locality = fields.Char(string="Locality Name", store=True, readonly=False, compute='_compute_l10n_mx_edi_locality')
    locality_id = fields.Many2one('l10n_mx_edi.res.locality', string="Locality",
        help="Optional attribute used in the XML that serves to define the locality where the domicile is located.")
    colony = fields.Char(string="Colony Name")
    colony_code = fields.Char(string="Colony Code",
        help="Colony code that will be used in the CFDI with the external trade as Emitter colony. It must be a code "
             "from the SAT catalog.")
    country_code = fields.Char(related='country_id.code', readonly=True)
    street_name = fields.Char('Street Name')
    street_number = fields.Char('House Number')
    street_number2 = fields.Char('Door Number')
    street2 = fields.Char(string="Street 2")
    economic_sector_id = fields.Many2one('res.company.economic_sector', "RT fraction", required=False)

    _sql_constraints = [
        ('employer_registryt_uniq', 'UNIQUE (employer_registry)',
         "There is already an employer number registered with the number entered!"),
    ]

    @api.depends('locality_id')
    def _compute_l10n_mx_edi_locality(self):
        for res in self:
            res.locality = res.locality_id.name

    @api.model
    def action_revoked(self):
        for employer in self:
            employer.state = 'revoked'

    @api.model
    def action_timed_out(self):
        for employer in self:
            employer.state = 'timed_out'

    def get_risk_factor(self, date_factor):
        risk_factor = 0
        for group in self:
            if group.risk_factor_ids:
                factor_ids = group.risk_factor_ids.filtered(
                    lambda factor: factor.date_from <= date_factor <= factor.date_to)
                if factor_ids:
                    risk_factor = factor_ids.mapped('risk_factor')[0]
                else:
                    risk_factor = 0
        return risk_factor


class HrGroupRiskFactor(models.Model):
    _name = "res.group.risk.factor"
    _description = "Annual Risk Factor"
    _order = 'date_from desc'

    employer_id = fields.Many2one('res.employer.register', string="group")
    risk_factor = fields.Float(string="Risk Factor", required=True, digits=(16, 4))
    date_from = fields.Date(string="Start Date", required=True)
    date_to = fields.Date(string="End Date", required=True)


class CompanyDelegation(models.Model):
    _name = 'res.company.delegation'

    name = fields.Char('Delegation', required=True)
    code = fields.Char('Code', required=True)
    subdelegation_ids = fields.One2many('res.company.subdelegation', 'delegation_id', 'Sub-Delegation')


class CompanySubDelegation(models.Model):
    _name = 'res.company.subdelegation'

    delegation_id = fields.Many2one('res.company.delegation', "Delegation")
    name = fields.Char('Sub-Delegation', required=True)
    code = fields.Char('Code', required=True)


class CompanyEconomicSector(models.Model):
    _name = 'res.company.economic_sector'

    name = fields.Char('Economic Sector', required=True)
    code = fields.Char('Code', required=True)
