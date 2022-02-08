# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date

from random import uniform,triangular

class ReverseCalculationSalary(models.TransientModel):
    _name = "reverse.calculation.salary"
    _description = "Wizard for reverse calculation of salary"

    contract_id = fields.Many2one("hr.contract", string="Contract")
    net_salary = fields.Float(string="Net Salary")
    contract_benefits = fields.Boolean(string="Include Contract Benefits")
    gross_salary = fields.Float(string="Gross Salary")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], string='State', default='draft')
    
    
    def get_subsidio_empleo(self, gross_salary,table_id,days):
        subsidio = ''
        daily_salary = gross_salary/days
        salary = daily_salary*days
        day_period = self.contract_id.company_id.days_factor
        factor = day_period/days
        salary = salary*factor
        
        subsidio = self.env['table.isr.monthly.subsidy'].search([('table_id','=',table_id.id),('lim_inf','<',salary),('lim_sup','>',salary)])
        if len(subsidio):
            return float("{0:.2f}".format(subsidio.s_mensual/factor)) 
        return 0
    
    def get_isr(self,gross_salary,days,table_id):
        daily_salary = gross_salary/days
        salary = daily_salary*days
        day_period = self.contract_id.company_id.days_factor
        factor = day_period/days
        salary = salary*factor
        lower_limit = 0
        applicable_percentage = 0
        fixed_fee = 0
        for table in table_id.isr_monthly_ids:
            if salary > table.lim_inf and salary < table.lim_sup:
                lower_limit = float("{0:.4f}".format(table.lim_inf))
                applicable_percentage =  float("{0:.4f}".format((table.s_excedente)/100))
                fixed_fee = float("{0:.4f}".format(table.c_fija))
        lower_limit_surplus = salary - lower_limit
        marginal_tax = lower_limit_surplus*applicable_percentage
        isr_113 = marginal_tax + fixed_fee
        return float("{0:.2f}".format(isr_113/factor))
    
    def get_imss_rcv(self,gross_salary, days, table_id, age_factor, risk_factor):
        for contract in self.contract_id:
            daily_salary = gross_salary/days
            sbc = float("{0:.4f}".format(daily_salary * (round(age_factor.factor, 4))))
            limit_imss = contract.company_id.uma*contract.company_id.general_uma
            if sbc > limit_imss:
                sbc = limit_imss
            salary = daily_salary*days
            work_irrigation = (sbc * risk_factor * days)/100
            UMA = float("{0:.4f}".format(contract.company_id.uma))
            benefits_kind_fixed_fee_pattern = float("{0:.4f}".format((UMA*20.400*days)/100))
            benefits_kind_surplus_standard = 0
            if sbc - (UMA * 3) > 0:
                benefits_kind_surplus_standard = float("{0:.4f}".format(sbc - (UMA * 3) * (1.100/100) * days))
            benefits_excess_insured_kind = 0
            if sbc - (UMA * 3) > 0:
                benefits_excess_insured_kind = float("{0:.4f}".format((sbc - (UMA * 3)) * (0.400/100) * days))
            benefits_employer_unique_money = float("{0:.4f}".format(sbc * (0.700/100) * days))
            benefits_insured_single_money = float("{0:.4f}".format(sbc * (0.250/100) * days))
            pensioned_medical_expenses_employer = float("{0:.4f}".format(sbc * (1.050/100) * days))
            pensioned_medical_expenses_insured = float("{0:.4f}".format(sbc * (0.375/100) * days))
            disability_life_employer = float("{0:.4f}".format(sbc * (1.750/100) * days))
            disability_life_insured = float("{0:.4f}".format(sbc * (0.625/100) * days))
            childcare_social_security_expenses_employer = float("{0:.4f}".format(sbc * (1.000/100) * days))
            total_imss_employee = float("{0:.4f}".format(benefits_excess_insured_kind + benefits_insured_single_money + pensioned_medical_expenses_insured + disability_life_insured))
            unemployment_old_age_insured = float("{0:.4f}".format(sbc * (1.125/100) * days)) 
            total_rcv_infonavit = float("{0:.4f}".format(unemployment_old_age_insured))
        return total_imss_employee + total_rcv_infonavit

    def get_td(self,gross_salary, days, table_id, age_factor, risk_factor,assimilated=False):
        imss = 0
        if not assimilated:
            imss = float("{0:.2f}".format(self.get_imss_rcv(gross_salary,  days, table_id, age_factor, risk_factor)))
        isr = self.get_isr(gross_salary,days,table_id)
        return isr+imss

    def get_tp(self, gross_salary,table_id,days,assimilated=False):
        sub_emp = 0
        if not assimilated:
            sub_emp = self.get_subsidio_empleo(gross_salary,table_id,days)
        return sub_emp+gross_salary
    
    def calc_net_salary(self, gross_salary, days, table_id, age_factor, risk_factor,assimilated=False):
        td = self.get_td(gross_salary, days, table_id, age_factor, risk_factor,assimilated=assimilated)
        tp = self.get_tp(gross_salary,table_id,days,assimilated=assimilated)
        return tp-td
    
    def get_rand_number(self,min_value, max_value):
        """
        This function gets a random number from a uniform distribution between
        the two input values [min_value, max_value] inclusively
        Args:
        - min_value (float)
        - max_value (float)
        Return:
        - Random number between this range (float)
        """
        range = max_value - min_value
        choice = triangular(0, 1)
        return min_value + range * choice
    
    def get_value_objetive(self, expected_value, days, table_id, age_factor, risk_factor, assimilated = False):
        gross_salary = 0.0
        net_salary = 0.0
        min_value = 0.0
        max_value = expected_value*2
        while (abs(expected_value - net_salary)) > 0.001:
            gross_salary = float("{0:.4f}".format(self.get_rand_number(min_value, max_value)))
            net_salary = self.calc_net_salary(gross_salary,days,table_id,age_factor,risk_factor,assimilated=assimilated)
            if (expected_value - net_salary) < -0.001:
                max_value = gross_salary
            if (expected_value - net_salary) > 0.001:
                min_value = gross_salary
        return gross_salary
    
    def reverse_calculation_salary(self):
        today = date.today()
        salary = self.net_salary
        contract_id = self.contract_id
        days_salary = contract_id.company_id.days_factor
        table_id = contract_id.company_id.configuration_table_id
        factor = days_salary/ 30
        years_antiquity = contract_id.years_antiquity
        days_rest = contract_id.days_rest
        if days_rest > 0:
            years_antiquity += 1
        age_factor = self.env['hr.table.antiquity.line'].search(
                    [('year', '=', int(years_antiquity)),
                     ('antiquity_line_id', '=', contract_id.employee_id.antiquity_id.id)])
        if contract_id.payment_period == '01':
            days = 1 * factor
        if contract_id.payment_period == '02':
            days = 7 * factor
        if contract_id.payment_period == '03':
            days = 14 * factor
        if contract_id.payment_period == '10':
            days = 10 * factor
        if contract_id.payment_period == '04':
            days = 15 * factor
        if contract_id.payment_period == '05':
            days = 30 * factor
        risk_factor = contract_id.employee_id.employer_register_id.get_risk_factor(today)
        
        if contract_id.contracting_regime == '02':
            wage_salaries = (self.get_value_objetive((salary / days_salary) * days, days, table_id, age_factor, risk_factor) / days) * days_salary
        elif contract_id.contracting_regime in ['08','09','11']:
            wage_salaries = (self.get_value_objetive((salary / days_salary) * days, days, table_id, age_factor, risk_factor, True) / days) * days_salary
        else:
            wage_salaries = salary
        self.gross_salary = wage_salaries
        self.state = 'done'
        domain = [('id', 'in', self.ids)]
        return {
            'name': _('Calculo de Salario Inverso'),
            'domain': domain,
            'context': {'default_net_salary':self.net_salary, 'default_gross_salary':self.gross_salary, 'default_contract_id':self.contract_id.id},
            'res_model': 'reverse.calculation.salary',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'form',
            'target': 'new',
            
        } 
    
