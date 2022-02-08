# -*- coding: utf-8 -*-

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TabChange(models.TransientModel):
    _name = "tab.change"
    _description = "Wizard to change pilots tab amount"

    pilot_tab_id = fields.Many2many('hr.pilot.tab', string='Pilor Tab', required=True)
    percentage = fields.Float(string="Percentage", required=True)
    percentage_antiquity = fields.Float(string="Percentage of Seniority Premium", required=True)

    def generate_increment(self):
        for pilot_tab in self.pilot_tab_id:
            for line_tab in pilot_tab.pilot_tab_line:
                line_tab.salary += line_tab.salary * self.percentage / 100
                line_tab.seniority_premium += line_tab.seniority_premium * self.percentage_antiquity / 100
        self.generate()
        return True

    def generate(self):
        SalaryChange = self.env['contract.salary.change.line']

        employees = self.env['hr.employee'].search([('pilot_tab_id', 'in', self.pilot_tab_id.ids)])
        contracts = self.env['hr.contract'].search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'open')
        ])
        for contract in contracts:
            if contract.num_years(contract.date_start, fields.Date.today()) > 0:
                years_antiquity = contract.num_years(contract.date_start, fields.Date.today())

                pilot_tab = self.env['hr.pilot.tab.line'].search([
                    ('year', '=', years_antiquity),
                    ('pilot_tab_id', '=', contract.employee_id.pilot_tab_id.id)
                ])
                salary = pilot_tab.salary
                seniority_premium = pilot_tab.seniority_premium
                diferents = contract.wage != salary
                contract.wage = salary
                contract.daily_salary = salary / contract.company_id.days_factor if salary else False
                contract.integral_salary = contract._calculate_integral_salary()
                contract.sdi = contract.integral_salary + contract.variable_salary
                contract.seniority_premium = seniority_premium
                limit_imss = contract.company_id.uma * contract.company_id.general_uma
                if contract.sdi > limit_imss:
                    contract.sbc = limit_imss
                else:
                    contract.sbc = contract.sdi

                movements = self.env['hr.employee.affiliate.movements'].search([
                    ('contract_id', '=', contract.id),
                    ('type', '=', '08'),
                ], limit=1)

                if diferents and not movements:
                    self.env['hr.employee.affiliate.movements'].create({
                        'contract_id': contract.id,
                        'employee_id': contract.employee_id.id,
                        'company_id': contract.company_id.id,
                        'type': '08',
                        'date': fields.Date.today(),
                        'wage': contract.wage,
                        'sbc': contract.sbc,
                        'salary': contract.sdi,
                    })
                    self.env['hr.employee.affiliate.movements'].create({
                        'contract_id': contract.id,
                        'employee_id': contract.employee_id.id,
                        'company_id': contract.company_id.id,
                        'type': '07',
                        'date': fields.Date.today(),
                        'wage': contract.wage,
                        'salary': contract.sdi,
                        'sbc': contract.sbc,
                    })

                change_salary = SalaryChange.search([
                    ('contract_id', '=', contract.id),
                    ('wage', '=', contract.wage),
                    ('daily_salary', '=', contract.daily_salary),
                    ('sdi', '=', contract.sdi),
                    ('sbc', '=', contract.sbc),
                    ('integrated_salary', '=', contract.integral_salary),
                    ('seniority_premium', '=', contract.seniority_premium),
                    ('date_end', '=', False),
                ])
                previous_change = SalaryChange.search([('date_end', '=', False), ('contract_id', '=', contract.id)])  # Previous Record
                if not change_salary:
                    previous_change.write({'date_end': fields.Date.today() + relativedelta(days=-1)})
                    SalaryChange.create({
                        'contract_id': contract.id,
                        'wage': contract.wage,
                        'daily_salary': contract.daily_salary,
                        'sdi': contract.sdi,
                        'sbc': contract.sbc,
                        'integrated_salary': contract.integral_salary,
                        'seniority_premium': contract.seniority_premium,
                        'date_start': fields.Date.today(),
                    })

