# -*- coding: utf-8 -*-

import calendar
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class VacationPremiumAllowance(models.TransientModel):
    _name = "vacation.premium.allowance"
    _description = "Wizard for vacation premium allowance"

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string="Date from")
    date_to = fields.Date(string="Date to")
    payroll_period_id = fields.Many2one('hr.payroll.period', string='Periodo de nómina')
    payment_holidays_bonus = fields.Selection([('0', 'Pago al aniversario de vacaciones'),
                                               ('1', 'Pagos al disfrute de las vacaciones'),
                                               ('2', 'Pago anticipado al disfrute de las vacaciones'),
                                               ], string='Pago de prima de vacaciones', default='0')
    input_id = fields.Many2one('hr.payslip.input.type', string='Entrada', required=True, default=lambda self: self.env.company.vacation_input_id.id)
    
    def assign(self):
        date_init = self.date_from
        date_end = self.date_to
        contracts = self.env['hr.contract'].search(
            [('employee_id', '!=', False), ('contracting_regime', '=', '02'), ('company_id', 'in', self.company_id.ids),
             ('state', '=', 'open'),('employee_id.payment_holidays_bonus', '=', self.payment_holidays_bonus)])
        results = []

        for contract in contracts:
            contract_stat_date = contract.previous_contract_date or contract.date_start
            month = contract_stat_date.month
            day = contract_stat_date.day
            day2 = contract_stat_date.day

            if month == 2 and day == 29:
                day = calendar.monthrange(int(date_init.year), int(month))[1]
                day2 = calendar.monthrange(int(date_end.year), int(month))[1]
            date_1 = date(date_init.year, month, day)
            date_2 = date(date_end.year, month, day2)
            date_aniversary = False
            if date_1 >= date_init and date_1 <= date_end:
                date_aniversary = date_1
            elif date_2 >= date_init and date_2 <= date_end:
                date_aniversary = date_1 = date_2
            if date_aniversary:
                self.env.cr.execute("""
                                    SELECT
                                        input.id
                                    FROM hr_inputs input
                                    WHERE input.input_id = %s
                                        AND input.employee_id = %s
                                        AND input.year = %s
                                    """, (self.input_id.id, contract.employee_id.id, date_aniversary.year))
                sal = self.env.cr.fetchall()
                if len(sal):
                    continue
                years_antiquity = contract._get_years_antiquity(date_to=date_aniversary)[0]
                age_factor = self.env['hr.table.antiquity.line'].search(
                    [('year', '=', int(years_antiquity)),
                     ('antiquity_line_id', '=', contract.employee_id.antiquity_id.id)])
                amount = contract.daily_salary * age_factor.holidays * (age_factor.vacation_cousin/100)
                vals = {
                        'employee_id': contract.employee_id.id,
                        'input_id': self.input_id.id,
                        'payroll_period_id': self.payroll_period_id.id,
                        'amount': amount,
                        'year': date_aniversary.year,
                        'state': 'confirm',
                    }
                self.env['hr.inputs'].create(vals)
        return
