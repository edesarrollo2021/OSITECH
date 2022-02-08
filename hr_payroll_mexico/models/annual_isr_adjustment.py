# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class AnnualISRAdjustment(models.Model):
    _name = 'annual.isr.adjustment'
    _description = 'Annual ISR Adjustment'
    _rec_name = "year"
    _order = 'create_date desc'

    company_id = fields.Many2one('res.company', required=True, string='Company', default=lambda self: self.env.company)
    year = fields.Integer(string="Year", required=True)
    line_ids = fields.One2many("annual.isr.adjustment.line", "adjustment_id", string="Lines per Employee")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Verified'),
        ('calculated', 'Calculated'),
        ('approved', 'Passed')
    ], string="State", default='draft')
    project_december = fields.Boolean(string="Project December")
    project_bonuses = fields.Boolean(string="Project Bonuses")
    bonus_project = fields.Boolean(string="Project Bonus")
    table_id = fields.Many2one('table.settings', string="Table ISR")
    structure_type_id = fields.Many2one("hr.payroll.structure.type", string="Payroll Type")
    period_ids = fields.Many2many(
        'hr.payroll.period', string='Payroll Period'
    )
    seniority_premium = fields.Boolean(string="Include seniority premium")

    @api.constrains('state', 'year', 'company_id')
    def _check_duplicated(self):
        for isr in self:
            if isr.state == 'approved':
                others_records = self.env['annual.isr.adjustment'].search([
                    ('state', '=', 'approved'),
                    ('year', '=', isr.year),
                    ('company_id', '=', isr.company_id.id),
                    ('id', '!=', isr.id)
                ], limit=1)
                if others_records:
                    raise ValidationError(_('No two identical records can exist in approved status'))
    
    def calculate_lines(self, options):
        if options.get('recompute'):
            self.write({'state': 'verify'})
            self.env.cr.execute("""
                                    UPDATE 
                                        annual_isr_adjustment_line 
                                    SET calculated = false 
                                    WHERE adjustment_id = %s""", (self.id,))

        _logger.info('calculate %d adjustments...', options.get('limit'))
        contracts = self.env['annual.isr.adjustment.line'].search([
            ('adjustment_id', '=', self.id),
            ('calculated', '=', False),
        ], limit=300)
        
        for i in contracts:
            if len(contracts[0].employee_id.slip_ids) <= 0:
                contracts -= i
            else:
                i.calculated =True
                
        if not contracts:
            self.write({'state': 'calculated'})
            return {
                'ids': [],
                'messages': [],
                'continues': 0,
            }

        self.env.cr.execute("""
                                SELECT
                                    slip.contract_id,
                                    SUM(CASE WHEN line.code = 'TP001' THEN line.total
                                        ELSE 0 END)
                                    AS perception,
                                    SUM(CASE WHEN line.code IN ('D005', 'D002', 'D040') THEN line.total
                                        ELSE 0 END)
                                    AS isr,
                                    SUM(CASE WHEN line.code = 'UI092' AND period.end_monthly_period IS TRUE THEN line.total
                                        ELSE 0 END)
                                    AS subsidy,
                                    SUM(CASE WHEN line.code = 'D003' THEN line.total
                                        ELSE 0 END)
                                    AS subsidy_adjustment,
                                    SUM(CASE WHEN line.code = 'OP002' THEN line.total
                                        ELSE 0 END)
                                    AS reintegration,
                                    SUM(CASE WHEN line.code = 'UI090' THEN line.total
                                        ELSE 0 END) 
                                    AS taxables,
                                    contract.wage
                                FROM hr_payslip_line line
                                JOIN hr_salary_rule rule                    ON line.salary_rule_id = rule.id
                                JOIN hr_payslip slip                        ON line.slip_id = slip.id
                                JOIN hr_payroll_period period               ON period.id = slip.payroll_period_id
                                JOIN hr_contract contract                   ON slip.contract_id = contract.id
                                WHERE
                                    slip.contract_id IN %s
                                    AND slip.state IN ('done')
                                    AND slip.year = %s
                                    AND contract.structure_type_id = %s
                                GROUP BY slip.contract_id, contract.wage
                            """, (contracts.mapped('contract_id')._ids, self.year, self.structure_type_id.id))
        res = self.env.cr.dictfetchall()
        
        results = []
        for line in res:
            contract_id = self.env['hr.contract'].browse(line['contract_id'])

            # TODO: Modify
            salary_all = 0
            isr = 0
            subsidio_causado_all = 0
            isr_retenido_all = 0
            if self.project_december:
                for period in self.period_ids:
                    days_factor_month = self.company_id.days_factor
                    days_factor = days_factor_month / 30
                    payroll_periods_days = {
                        '05': 30,
                        '04': 15,
                        '02': 7,
                        '03': 14,
                        '10': 10,
                        '01': 1,
                        '99': 1,
                                        }
                    days_period = payroll_periods_days[period.payroll_period] * days_factor
                    salary = contract_id.daily_salary * days_period
                    if self.seniority_premium:
                        seniority_premium = (contract_id.seniority_premium / days_factor_month) * days_period
                        if contract_id.seniority_premium > 0:
                            salary += seniority_premium
                    salary_all += salary
                   
                    
                    
                    salary_proyectado = (salary/days_period)*days_factor_month
                    
                    
                    for i in self.table_id.isr_monthly_ids:
                        if salary_proyectado > i.lim_inf and salary_proyectado < i.lim_sup:
                            lim_inf = i.lim_inf
                            porcentaje = round(i.s_excedente/100,4)
                            cuota =  i.c_fija
                    excedente = salary_proyectado - lim_inf
                    impuesto = excedente*porcentaje
                    isr = impuesto+cuota
                    subsidio_causado = 0
                    for i in self.table_id.isr_monthly_subsidy_ids:
                        if salary_proyectado > i.lim_inf and salary_proyectado < i.lim_sup:
                            subsidio_causado = i.s_mensual
                    isr = (isr/days_factor_month)*days_period
                    subsidio_causado = (subsidio_causado/days_factor_month)*days_period
                    diferencia = isr-subsidio_causado
                    isr_retenido = 0
                    if diferencia > 0:
                        isr_retenido = float("{0:.2f}".format( diferencia ))
                    isr_retenido_all += isr_retenido
                    subsidio_causado_all += subsidio_causado
            
            bonuses = 0
            bonuses_gravado = 0
            isr_retener_bonuses = 0
            if self.project_bonuses:
                bonuses_gravado = 0
                days_bonuses = contract_id.time_worked_year(self)
                bonuses = contract_id.daily_salary * days_bonuses
                exencion = self.company_id.bonus_factor * self.company_id.uma
                if bonuses > exencion:
                    bonuses_gravado = bonuses - exencion
                    
                    wage = contract_id.wage
                    percepcion_diaria = "{0:.6f}".format(bonuses_gravado / 365) 
                    percepcion_mensual = float(percepcion_diaria)*30.4
                    sueldo_prestacion = wage+percepcion_mensual
                    amount = 0
                    for i in self.table_id.isr_monthly_ids:
                        if wage > i.lim_inf and wage < i.lim_sup:
                            limit_sueldo = float("{0:.4f}".format(i.lim_inf))
                            tasa_sueldo = round(i.s_excedente/100,4)
                            cuota_mensual = float("{0:.4f}".format(i.c_fija))
                            break
                    for i in self.table_id.isr_monthly_ids:
                        if sueldo_prestacion > i.lim_inf and sueldo_prestacion < i.lim_sup:
                            limit_sueldo_prestacion = float("{0:.4f}".format(i.lim_inf))
                            tasa_sueldo_prestacion = round(i.s_excedente/100,4)
                            cuota_mensual_prestacion = float("{0:.4f}".format(i.c_fija))
                            break
                    excedente_sueldo = float("{0:.4f}".format(wage - limit_sueldo))
                    excedente_sueldo_prestacion = float("{0:.4f}".format(sueldo_prestacion - limit_sueldo_prestacion))
                    impuesto_sueldo = excedente_sueldo*tasa_sueldo
                    impuesto_sueldo_prestacion = excedente_sueldo_prestacion*tasa_sueldo_prestacion
                    isr_mensual = impuesto_sueldo + cuota_mensual
                    isr_mensual_prestacion = impuesto_sueldo_prestacion + cuota_mensual_prestacion
                    diferencia_isr = isr_mensual_prestacion - isr_mensual
                    tasa_proporcion = diferencia_isr/percepcion_mensual
                    isr_retener_bonuses = tasa_proporcion*bonuses_gravado
            annual_perceptions = float("{0:.2f}".format(line['perception'] + salary_all + bonuses))
            annual_taxed = float("{0:.2f}".format(line['taxables'] + salary_all + bonuses_gravado))
            annual_isr = float("{0:.2f}".format(line['isr'] - line['reintegration'] + isr_retenido_all + isr_retener_bonuses))
            annual_subsidy = float("{0:.2f}".format(line['subsidy'] - line['subsidy_adjustment'] + subsidio_causado_all))
            # END TODO
            self.env.cr.execute("""
                                UPDATE 
                                    annual_isr_adjustment_line 
                                SET total_taxed = %s, 
                                    isr_withheld = %s, 
                                    adjustment_paid = %s, 
                                    total_gross = %s, 
                                    calculated = true 
                                WHERE contract_id = %s AND adjustment_id = %s
                                """, (annual_taxed, annual_isr, annual_subsidy, annual_perceptions,
                                 line['contract_id'], self.id))
            results.append(line['contract_id'])

        _logger.info('done %s records', options.get('limit'))

        return {
            'ids': results,
            'messages': [],
            'continues': 1,
        }
    
    def aproved_isr_adjustment(self):
        self.state = 'approved'
        return 
        
    def change_verified(self):
        self.state = 'verify'
        return

    def unlink(self):
        for res in self:
            if res.state == "approved":
                raise UserError(_("You cannot delete approved Annual ISR records."))
        return super(AnnualISRAdjustment, self).unlink()


class AnnualISRAdjustmentLine(models.Model):
    _name = 'annual.isr.adjustment.line'
    _description = 'Annual ISR Adjustment Line'

    employee_id = fields.Many2one("hr.employee", string="Employee", related="contract_id.employee_id")
    contract_id = fields.Many2one("hr.contract", string="Contract", required=True)
    
    
    total_taxed = fields.Float(string="Total Tax")
    isr_withheld = fields.Float(string="ISR Withheld")
    adjustment_paid = fields.Float(string="Subcide Caused")
    total_gross = fields.Float(string="Total Earnings")
    
    
    
    
    adjustment_id = fields.Many2one("annual.isr.adjustment", string="Adjustment")
    calculated = fields.Boolean(string="Calculated?")
    projected_periods = fields.Float(string="December Projected")
    bonus_periods = fields.Float(string="Bonus Projected")
    total_annual_perceptions = fields.Float(string="Total Annual Perceptions")
    total_annual_taxed = fields.Float(string="Total Taxed Annual")
    annual_isr = fields.Float(string="Isr Withheld Annual")
    annual_subsidy = fields.Float(string="Annual Caused Subsidy")
