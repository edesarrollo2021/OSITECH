# -*- coding: utf-8 -*-

import calendar
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HolidaysAssignment(models.TransientModel):
    _name = "holidays.assignment"
    _description = "Vacation and Personal Day Allowance"

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string="Date from")
    date_to = fields.Date(string="Date to")
    holidays = fields.Boolean(string="Holidays?")
    personal_days = fields.Boolean(string="Personal Days?")

    def assign(self):
        date_init = self.date_from
        date_end = self.date_to
        contracts = self.env['hr.contract'].search(
            [('employee_id', '!=', False), ('contracting_regime', '=', '02'), ('company_id', 'in', self.company_id.ids),
             ('state', '=', 'open')])
        cont = 1
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

            if date_aniversary and contract.num_years(contract_stat_date, date_aniversary) > 0:
                cont += 1
                holidays_type = self.env['hr.leave.type'].search(
                    [('time_type', '=', 'holidays'), ('code', '=', 'F08-%s' % date_aniversary.year)])
                personal_day_type = self.env['hr.leave.type'].search([
                    ('time_type', '=', 'personal'), ('code', '=', 'F11-%s' % date_aniversary.year)
                ])
                if not personal_day_type and self.personal_days:
                    raise UserError(_('There is no type of absence for a personal day'))
                if not holidays_type and self.holidays:
                    raise UserError(_('There is no type of absence for a holidays'))
                allocations_assignated = sum(self.env['hr.leave.allocation'].search(
                    [('employee_id', '=', contract.employee_id.id), ('holiday_status_id', '=', holidays_type.id),
                     ('state', '!=', 'refuse'), ('is_due', '=', False)]).mapped('number_of_days_display'))
                personal_days_assignated = sum(self.env['hr.leave.allocation'].search(
                    [('employee_id', '=', contract.employee_id.id), ('holiday_status_id', '=', personal_day_type.id),
                     ('state', '!=', 'refuse'), ('is_due', '=', False)]).mapped('number_of_days_display'))

                years_antiquity = contract.num_years(contract_stat_date, date_aniversary)
                days_holidays = self.env['hr.table.antiquity.line'].search([
                    ('year', '=', years_antiquity),
                    ('antiquity_line_id', '=', contract.employee_id.antiquity_id.id)
                ]).holidays

                if self.personal_days and not personal_days_assignated and contract.employee_id.company_id.personal_days_factor and not contract.employee_id.syndicalist:

                    vals = {
                        'name': 'Personal Days %s %s' % (contract.employee_id.complete_name, date_aniversary.year),
                        'holiday_type': 'employee',
                        'number_of_days': contract.employee_id.company_id.personal_days_factor,
                        'employee_id': contract.employee_id.id,
                        # 'contract_id': contract.id,
                        'holiday_status_id': personal_day_type.id,
                        'date_due': date_aniversary + relativedelta(months=personal_day_type.duration_months),
                    }
                    res_id = self.env['hr.leave.allocation'].with_context(date_from=self.date_from).create(vals)
                    results.append(res_id.id)
                    res_id.state = 'validate'
                if self.holidays and days_holidays and not allocations_assignated:
                    vals = {
                        'name': 'Holidays %s %s' % (contract.employee_id.complete_name, date_aniversary.year),
                        'holiday_type': 'employee',
                        'number_of_days': float(days_holidays),
                        'employee_id': contract.employee_id.id,
                        # 'contract_id': contract.id,
                        'holiday_status_id': holidays_type.id,
                        'date_due': date_aniversary + relativedelta(months=holidays_type.duration_months),
                    }
                    res_id = self.env['hr.leave.allocation'].create(vals)
                    results.append(res_id.id)
                    res_id.action_approve()

        return {
            'name': _('Vacation and Personal Day Allowance'),
            'res_model': 'hr.leave.allocation',
            'type': 'ir.actions.act_window',
            'views': [(False, 'list')],
            'view_mode': 'tree',
            'domain': [('id', 'in', results)],
            'context': {},
        }

