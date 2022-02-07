# -*- coding: utf-8 -*-

import calendar
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ChangeSalaryTab(models.TransientModel):
    _name = "change.salary.tab"
    _description = "wizard to change the salary for table tab"

    date_from = fields.Date(string="Date from", required=True)
    date_to = fields.Date(string="Date to", required=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)

    def generate(self):
        SalaryChange = self.env['contract.salary.change.line']
        date_init = self.date_from
        date_end = self.date_to

        employees = self.env['hr.employee'].search([('pilot_tab_id', '!=', False)])
        contracts = self.env['hr.contract'].search([
            ('employee_id', 'in', employees.ids),
            ('company_id', 'in', self.company_id.ids),
            ('state', '=', 'open')
        ])

        for contract in contracts:
            month = contract.date_start.month
            day = contract.date_start.day
            day2 = contract.date_start.day

            if month == 2 and day == 29:
                day = calendar.monthrange(int(date_init.year), int(month))[1]
                day2 = calendar.monthrange(int(date_end.year), int(month))[1]
            date_1 = date(date_init.year, month, day)
            date_2 = date(date_end.year, month, day2)
            date_aniversary = False
            if date_1 >= date_init and date_1 <= date_end:
                date_aniversary = date_1
            elif date_2 >= date_init and date_2 <= date_end:
                date_aniversary = date_2

            if date_aniversary and contract.num_years(contract.date_start, date_aniversary) > 0:
                years_antiquity = contract.num_years(contract.date_start, date_aniversary)

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
                        'date': date_aniversary,
                        'wage': contract.wage,
                        'sbc': contract.sbc,
                        'salary': contract.sdi,
                    })

                    self.env['hr.employee.affiliate.movements'].create({
                        'contract_id': contract.id,
                        'employee_id': contract.employee_id.id,
                        'company_id': contract.company_id.id,
                        'type': '07',
                        'date': date_aniversary,
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
                    previous_change.write({'date_end': date_aniversary + relativedelta(days=-1)})
                    SalaryChange.create({
                        'contract_id': contract.id,
                        'wage': contract.wage,
                        'daily_salary': contract.daily_salary,
                        'sdi': contract.sdi,
                        'sbc': contract.sbc,
                        'integrated_salary': contract.integral_salary,
                        'seniority_premium': contract.seniority_premium,
                        'date_start': date_aniversary,
                    })
