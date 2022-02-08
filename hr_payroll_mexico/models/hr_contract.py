# -*- coding: utf-8 -*-

import calendar
from datetime import date, datetime, timedelta, time
from dateutil.relativedelta import relativedelta

from collections import defaultdict
from odoo import api, fields, models, _
from odoo.addons.resource.models.resource import datetime_to_string, string_to_datetime, Intervals
import pytz
import math

from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

class Contract(models.Model):
    _inherit = 'hr.contract'

    def vacation_premium_employee(self):
        actual_year = fields.Date.today().year
        period = self.env['hr.payroll.period'].search([
            ('type', '=', 'ordinary'),
            ('state', 'in', ['open','draft']),
            # ~ ('id', 'in', [18]),
            ('date_start', '=', fields.Date.today()),
        ], limit=1)
        
        if period:
            for res in self.search([('state', '=', 'open'), ('employee_id.payment_holidays_bonus', '=', '0')]):
                if not res.company_id.vacation_input_id:
                    continue
                date_any = res.previous_contract_date if res.previous_contract_date else res.date_start
                month = date_any.month
                day = date_any.day
                if month == 2 and day == 29:
                    day = calendar.monthrange(int(actual_year), int(month))[1]
                date_aniversary = date_any.replace(year=actual_year, day=day)
                if period.date_start <= date_aniversary <=  period.date_end:
                    self.env.cr.execute("""
                                        SELECT
                                            input.id
                                        FROM hr_inputs input
                                        WHERE input.input_id = %s
                                            AND input.employee_id = %s
                                            AND input.year = %s
                                        """, (res.company_id.vacation_input_id.id, res.employee_id.id, date_aniversary.year))
                    sal = self.env.cr.fetchall()
                    if len(sal):
                        continue
                    years_antiquity = res._get_years_antiquity(date_to=date_aniversary)[0]
                    age_factor = self.env['hr.table.antiquity.line'].search(
                        [('year', '=', int(years_antiquity)),
                         ('antiquity_line_id', '=', res.employee_id.antiquity_id.id)])
                    amount = res.daily_salary * age_factor.holidays * (age_factor.vacation_cousin / 100)
                    vals = {
                        'employee_id': res.employee_id.id,
                        'input_id': res.company_id.vacation_input_id.id,
                        'payroll_period_id': period.id,
                        'amount': amount,
                        'year': actual_year,
                    }
                    self.env['hr.inputs'].create(vals)

    def name_get(self):
        context = self.env.context
        result = []
        for contract in self:
            name = contract.name
            if context.get('special_display_name', False):
                name = contract.employee_id.complete_name + ' - ' + contract.name
            result.append((contract.id, name))
        return result

    def _get_contract_work_entries_values(self, date_start, date_stop):
        self.ensure_one()
        contract_vals = super()._get_contract_work_entries_values(date_start, date_stop)
        return contract_vals

    def _get_work_hours(self, date_from, date_to, domain=None, period=False):
        work_data = defaultdict(int)
        work_entries = self.env['hr.work.entry'].read_group(
            self._get_work_hours_domain(date_from, date_to, domain=domain, inside=True),
            ['hours:sum(duration)'],
            ['work_entry_type_id']
        )
        if period:
            work_entries_gap = self.env['hr.work.entry'].read_group(
                                        [('state', 'in', ['validated', 'draft']),('out_of_date','=',True),('payroll_period_id','=',period.id),('employee_id','=',self.employee_id.id)],
                                        ['hours:sum(duration)'],
                                        ['work_entry_type_id']
                                    )
            work_entries += work_entries_gap
        work_data.update({data['work_entry_type_id'][0] if data['work_entry_type_id'] else False: data['hours'] for data in work_entries})
        return work_data

    def _get_more_vals_leave_interval(self, interval, leaves):
        result = super()._get_more_vals_leave_interval(interval, leaves)
        for leave in leaves:
            result.append(('out_of_date', leave[2].out_of_date))
            if leave[2].out_of_date:
                result.append(('payroll_period_id', leave[2].payroll_period_id.id))
        return result

    def calcualte_changes_salary(self, date_from, date_to):
        date_from_str = fields.Datetime.to_string(date_from - timedelta(days=1))
        date_end_str = fields.Datetime.to_string(date_to + timedelta(days=1))
        self.env.cr.execute("""
                                       SELECT 
                                           change.id
                                       FROM contract_salary_change_line change
                                       WHERE 
                                           change.contract_id = %s
                                           AND ((change.date_start, change.date_end) OVERLAPS (%s, %s)
                                           OR (change.date_end IS NULL AND (change.date_start, CURRENT_DATE) OVERLAPS (%s, %s)))
                                   """, (self.id, date_from_str, date_end_str, date_from_str, date_end_str))

        sal = self.env.cr.fetchall()
        ids_sal = [item for t in sal for item in t]
        changes = self.env['contract.salary.change.line'].browse(ids_sal)

        salaries = {}
        for change in changes:
            wages = [change.wage, change.sdi, change.sbc, change.seniority_premium, change.daily_salary,
                     change.integrated_salary]
            start_date = change.date_start if date_from <= change.date_start else date_from
            date_end = change.date_end or date_to
            end_date = date_end if date_to >= date_end else date_to
            for n in range(int((end_date - start_date).days + 1)):
                salaries[start_date + timedelta(days=n)] = wages

        if not changes:
            for n in range(int((date_to - date_from).days + 1)):
                wages = [self.wage, self.sdi, self.sbc, self.seniority_premium, self.daily_salary, self.integral_salary]
                salaries[date_from + timedelta(days=n)] = wages

        return salaries

    def calculate_entry_and_changes(self, date_from, date_to, period, absence=''):
        if absence:
            work_entries_type = self.env['hr.work.entry.type'].search([('code', '=', absence)])
        else:
            work_entries_type = self.env['hr.leave.type'].search([
                ('time_type', 'in', ['leave', 'other', 'inability', 'holidays', 'personal']),
            ]).mapped('work_entry_type_id')

        ###################################
        # Entry in this period
        ###################################
        date_start = datetime.combine(date_from, time.min)
        date_end = datetime.combine(date_to, time.max)
        datetime_start = fields.Datetime.to_string(date_start)
        datetime_end = fields.Datetime.to_string(date_end)

        self.env.cr.execute("""
                                SELECT 
                                    entry.id
                                FROM hr_work_entry entry
                                WHERE 
                                    entry.work_entry_type_id in %s
                                    AND entry.employee_id = %s
                                    AND entry.state in ('validated','draft')
                                    AND (entry.out_of_date = false OR entry.out_of_date IS NULL)  
                                    AND (entry.date_start, entry.date_stop) OVERLAPS (%s, %s)
                            """, (work_entries_type._ids, self.employee_id.id, datetime_start, datetime_end))
        sal = self.env.cr.fetchall()
        ids_sal = [item for t in sal for item in t]
        work_entries = self.env['hr.work.entry'].browse(ids_sal)
        ###################################
        # Entry out of date
        ###################################

        self.env.cr.execute("""
                                SELECT 
                                    entry.id
                                FROM hr_work_entry entry
                                WHERE 
                                    entry.work_entry_type_id in %s
                                    AND entry.employee_id = %s
                                    AND entry.state in ('validated','draft')
                                    AND entry.out_of_date = true 
                                    AND payroll_period_id = %s
                            """, (work_entries_type._ids, self.employee_id.id, period.id))
        sal = self.env.cr.fetchall()
        ids_sal = [item for t in sal for item in t]
        entries_out_of_date = self.env['hr.work.entry'].browse(ids_sal)

        for entry in entries_out_of_date:
            date_from = entry.date_start.date() if entry.date_start.date() <= date_from else date_from
            date_to = entry.date_stop.date() if entry.date_stop.date() >= date_to else date_to

        ###################################
        # Changes of salary in this period

        salaries = self.calcualte_changes_salary(date_from, date_to)
        work_entries |= entries_out_of_date
        return salaries, work_entries

    def calculate_period_salary(self, payslip, days=0):
        wage = 0
        wage_grav = 0
        discount = 0
        seniority_premium = 0
        date_from = payslip.date_from
        date_to = payslip.date_to
        # the contract starts after
        if self.date_start > date_from:
            date_from = self.date_start
        # the contract end before than period
        if self.date_end and self.date_end < date_to:
            date_to = self.date_end
            days -= (payslip.date_to - date_to).days

        days_factor = self.company_id.days_factor
        factor = days_factor / 30
        values, entries_out_of_date = self.calculate_entry_and_changes(date_from, date_to, payslip.payroll_period_id)
        period_days = int((date_to - date_from).days + 1)
        if payslip.payroll_period == '04' and date_to.day == 31:
            period_days -= 1
        for n in range(period_days):
            if date_from + timedelta(days=n) in values:
                wage_entry = values[date_from + timedelta(days=n)][0]
                seniority_entry = values[date_from + timedelta(days=n)][3]

                wage += factor * wage_entry / 30
                seniority_premium += factor * seniority_entry / 30
        # if days are missing
        if date_to.day in [28, 29]:
            qty_mul = 2 if date_to.day == 28 else 1
            wage_entry = values[date_to][0]
            seniority_entry = values[date_to][3]

            wage += (factor * wage_entry / 30) * qty_mul
            seniority_premium += (factor * seniority_entry / 30) * qty_mul
        num_holidays = 0
        num_absences = 0
        for entry in entries_out_of_date:
            wage_entry = 0
            if entry.date_start.date() in values:
                wage_entry = values[entry.date_start.date()][0]
            hours_absences = entry.duration
            absenses = hours_absences / self.resource_calendar_id.hours_per_day
            # count
            num_absences += absenses
            if num_absences > period_days:
                continue

            if entry.work_entry_type_id.type_leave in ['personal_days']:
                wage -= absenses * factor * wage_entry / 30
            elif entry.work_entry_type_id.type_leave == 'holidays':
                num_holidays += absenses
            else:
                discount += absenses * factor * wage_entry / 30
        # holidays
        wage_1 = 0
        if date_to in values:
            wage_1 = values[date_to][0]
        wage -= num_holidays * factor * wage_1 / 30
        wage_grav = wage - discount
        return {"wage": wage, "seniority_premium": seniority_premium, 'wage_grav': wage_grav}

    def calculate_period_imss(self, payslip, uma):
        employee = self.env['hr.employee'].browse([payslip.employee_id])

        ###########################
        # work entries
        date_from = payslip.date_from
        date_to = payslip.date_to

        # the contract starts after
        if self.date_start > date_from:
            date_from = self.date_start
        # the contract end before than period
        if self.date_end and self.date_end < date_to:
            date_to = self.date_end

        date_from_str = fields.Datetime.to_string(date_from - timedelta(days=1))
        date_end_str = fields.Datetime.to_string(date_to + timedelta(days=1))

        self.env.cr.execute("""
                                SELECT 
                                    change.id
                                FROM contract_salary_change_line change
                                WHERE 
                                    change.contract_id = %s
                                    AND ((change.date_start, change.date_end) OVERLAPS (%s, %s)
                                    OR (change.date_end IS NULL AND (change.date_start, CURRENT_DATE) OVERLAPS (%s, %s)))
                            """, (self.id, date_from_str, date_end_str, date_from_str, date_end_str))

        sal = self.env.cr.fetchall()
        ids_sal = [item for t in sal for item in t]
        changes = self.env['contract.salary.change.line'].browse(ids_sal)
        date_start = date(date_from.year, date_from.month, 1)
        date_start = datetime.combine(date_start, time.min)
        date_end = datetime.combine(date_to, time.max)
        datetime_start = fields.Datetime.to_string(date_start)
        datetime_end = fields.Datetime.to_string(date_end)

        ###########################
        # leaves
        work_entries_type = self.env['hr.leave.type'].search([
            ('time_type', 'in', ['inability', 'leave']),
        ]).mapped('work_entry_type_id')
        
        self.env.cr.execute("""
                                SELECT 
                                    entry.id
                                FROM hr_work_entry entry
                                WHERE 
                                    entry.work_entry_type_id in %s
                                    AND entry.employee_id = %s
                                    AND entry.state in ('validated','draft')
                                    AND entry.out_of_date != true 
                                    AND (entry.date_start, entry.date_stop) OVERLAPS (%s, %s)
                            """, (work_entries_type._ids, employee.id, datetime_start, datetime_end))

        sal = self.env.cr.fetchall()
        ids_sal = [item for t in sal for item in t]
        work_entries = self.env['hr.work.entry'].browse(ids_sal)

        # maximum 7 unexcused absences per month
        before_work = 0
        total_work = 0
        rest = 7 * self.resource_calendar_id.hours_per_day
        if sum(work_entries.mapped('duration')) / self.resource_calendar_id.hours_per_day > 7:
            for entry in work_entries:
                if entry.date_stop < datetime.combine(date_from, time.min):
                    before_work += entry.duration
                total_work += entry.duration
            rest -= before_work

        occupational_risk = 0
        fixed_fee = 0
        pattern_surplus = 0
        unique_patron_money = 0
        medical_expenses_pensioned_employer = 0
        disability_life_employer = 0
        daycare_social_security = 0
        insured_surplus = 0
        unique_benefits_insured = 0
        pensioned_medical_expenses_insured = 0
        disability_life_insured = 0
        unemployment_old_age_employer = 0
        unemployment_old_age_employe = 0
        employer_withdrawal = 0
        infonavit = 0
        for change in changes:
            date_s = date_from if date_from >= change.date_start else change.date_start
            date_e = date_to if not change.date_end or date_to <= change.date_end else change.date_end

            start = datetime.combine(date_s, time.min)
            end = datetime.combine(date_e, time.max)

            """
                hours_absences: leaves + inability
                hours_leave: leaves
                hours_disabilities: inability
            """
            hours_absences = 0
            hours_leave = 0
            hours_disabilities = 0
            for entry in work_entries:
                if entry.date_start > end or entry.date_stop < start:
                    continue
                rest -= entry.duration if entry.work_entry_type_id.code == 'F04' else 0
                if rest >= 0 or not entry.work_entry_type_id.code == 'F04':
                    hours_absences += entry.duration
                if rest >= 0 and entry.work_entry_type_id.code == 'F04':
                    hours_leave += entry.duration
                hours_disabilities += entry.duration if entry.work_entry_type_id.type_leave == 'inability' else 0

            absences = hours_absences / self.resource_calendar_id.hours_per_day
            leave = hours_leave / self.resource_calendar_id.hours_per_day
            disabilities = hours_disabilities / self.resource_calendar_id.hours_per_day

            days = (date_e - date_s).days + 1 - absences
            days_leave = (date_e - date_s).days + 1 - leave
            days_disabilities = (date_e - date_s).days + 1 - disabilities
            sbc = change.sbc

            risk_factor = employee.employer_register_id.get_risk_factor(payslip.date_from)
            occupational_risk += ((sbc * risk_factor) * days) / 100
            fixed_fee += ((uma * 20.40) * days_disabilities) / 100

            if sbc - (uma * 3) > 0:
                pattern_surplus += (((sbc - (uma * 3)) * 1.10) * days_disabilities) / 100
                insured_surplus += (((sbc - (uma * 3)) * 0.4) * days_disabilities) / 100

            unique_patron_money += ((sbc * 0.7) * days_disabilities) / 100
            medical_expenses_pensioned_employer += ((sbc * 1.05) * days_disabilities) / 100
            disability_life_employer += ((sbc * 1.75) * days) / 100
            daycare_social_security += ((sbc * 1) * days) / 100
            unique_benefits_insured += ((sbc * 0.25) * days_disabilities) / 100
            pensioned_medical_expenses_insured += ((sbc * 0.375) * days_disabilities) / 100
            disability_life_insured += ((sbc * 0.625) * days) / 100
            unemployment_old_age_employer += ((sbc * 3.150) * days) / 100
            unemployment_old_age_employe += ((sbc * 1.125) * days) / 100
            employer_withdrawal += ((sbc * 2) * days_leave) / 100
            infonavit += ((sbc * 5) * days_leave) / 100
        if not changes:
            hours_absences = 0
            hours_leave = 0
            if not work_entries:
                hours_disabilities = 0
            for entry in work_entries:
                start = datetime.combine(date_from, time.min)
                end = datetime.combine(date_to, time.max)
                if entry.date_start > end or entry.date_stop < start:
                    continue
                rest -= entry.duration if entry.work_entry_type_id.code == 'F04' else 0
                if rest >= 0 or not entry.work_entry_type_id.code == 'F04':
                    hours_absences += entry.duration
                if rest >= 0 and entry.work_entry_type_id.code == 'F04':
                    hours_leave += entry.duration
                hours_disabilities += entry.duration if entry.work_entry_type_id.type_leave == 'inability' else 0

            absences = hours_absences / self.resource_calendar_id.hours_per_day
            leave = hours_leave / self.resource_calendar_id.hours_per_day
            disabilities = hours_disabilities / self.resource_calendar_id.hours_per_day

            days = (date_to - date_from).days + 1 - absences
            days_leave = (date_to - date_from).days + 1 - leave
            days_disabilities = (date_to - date_from).days + 1 - disabilities
            sbc = self.sbc
            risk_factor = employee.employer_register_id.get_risk_factor(payslip.date_from)
            occupational_risk = ((sbc * risk_factor) * days) / 100
            fixed_fee = ((uma * 20.40) * days_disabilities) / 100
            if sbc - (uma * 3) > 0:
                pattern_surplus = (((sbc - (uma * 3)) * 1.10) * days_disabilities) / 100
                insured_surplus = (((sbc - (uma * 3)) * 0.4) * days_disabilities) / 100
            unique_patron_money = ((sbc * 0.7) * days_disabilities) / 100
            medical_expenses_pensioned_employer = ((sbc * 1.05) * days_disabilities) / 100
            disability_life_employer = ((sbc * 1.75) * days) / 100
            daycare_social_security = ((sbc * 1) * days) / 100
            unique_benefits_insured = ((sbc * 0.25) * days_disabilities) / 100
            pensioned_medical_expenses_insured = ((sbc * 0.375) * days_disabilities) / 100
            disability_life_insured = ((sbc * 0.625) * days) / 100
            unemployment_old_age_employer = ((sbc * 3.150) * days) / 100
            unemployment_old_age_employe = ((sbc * 1.125) * days) / 100
            employer_withdrawal = ((sbc * 2) * days_leave) / 100
            infonavit = ((sbc * 5) * days_leave) / 100

        return {"occupational_risk": occupational_risk,
                    "fixed_fee":fixed_fee,
                    "pattern_surplus":pattern_surplus,
                    "unique_patron_money":unique_patron_money,
                    "medical_expenses_pensioned_employer":medical_expenses_pensioned_employer,
                    "disability_life_employer":disability_life_employer,
                    "daycare_social_security":daycare_social_security,
                    "insured_surplus":insured_surplus,
                    "unique_benefits_insured":unique_benefits_insured,
                    "pensioned_medical_expenses_insured":pensioned_medical_expenses_insured,
                    "disability_life_insured":disability_life_insured,
                    "unemployment_old_age_employer":unemployment_old_age_employer,
                    "unemployment_old_age_employe":unemployment_old_age_employe,
                    "employer_withdrawal":employer_withdrawal,
                    "infonavit":infonavit}

    def discount_absences(self, payslip, absence):
        days_factor = self.company_id.days_factor
        factor = days_factor / 30
        discount = 0
        date_from = payslip.date_from
        date_to = payslip.date_to
        values, entries_out_of_date = self.calculate_entry_and_changes(date_from, date_to, payslip.payroll_period_id, absence)
        for entry in entries_out_of_date:
            hours_absences = entry.duration
            absenses = hours_absences / self.resource_calendar_id.hours_per_day
            wage_entry = values[entry.date_start.date()][0]
            discount += absenses * factor * wage_entry / 30
        return discount

    def discount_personal_days(self, payslip):
        days_factor = self.company_id.days_factor
        factor = days_factor / 30
        discount = 0

        date_from = payslip.date_from
        date_to = payslip.date_to

        values, entries_out_of_date = self.calculate_entry_and_changes(date_from, date_to, payslip.payroll_period_id)

        for entry in entries_out_of_date:
            if entry.work_entry_type_id.type_leave != 'personal_days':
                continue
            hours_absences = entry.duration
            absenses = hours_absences / self.resource_calendar_id.hours_per_day
            wage_entry = values[entry.date_start.date()][0]
            discount += absenses * factor * wage_entry / 30

        return discount

    def calculate_time_delay(self, payslip):
        days_factor = self.company_id.days_factor
        factor = days_factor / 30
        discount = 0
        absenses = 0

        date_from = payslip.date_from
        date_to = payslip.date_to

        values, entries_out_of_date = self.calculate_entry_and_changes(date_from, date_to, payslip.payroll_period_id, 'F11')
        for entry in entries_out_of_date:
            hours_absences = entry.duration
            absenses += hours_absences / self.resource_calendar_id.hours_per_day
        total_absenses = int(absenses / 3)

        wage_entry = values[date_to][0]
        discount += total_absenses * factor * wage_entry / 30

        return discount


    def calculate_extras_hours(self, payslip, code, perc=100):
        factor_perc = perc / 100
        date_from = payslip.date_from
        date_to = payslip.date_to

        salaries = self.calcualte_changes_salary(date_from, date_to)

        ###################################
        # Inputs in this period
        date_start = fields.Date.to_string(date_from)
        date_end = fields.Date.to_string(date_to)
        entries_type = self.env['hr.payslip.input.type'].search([('code', '=', code)])

        self.env.cr.execute("""
                                SELECT 
                                    input.amount,
                                    input.date
                                FROM hr_inputs input
                                WHERE 
                                    input.input_id in %s
                                    AND input.employee_id = %s
                                    AND input.state in ('approve')
                                    AND input.date IS NOT NULL
                                    AND (input.date, input.date) OVERLAPS (%s, %s)
                            """, (entries_type._ids, self.employee_id.id, date_start, date_end))
        sal = self.env.cr.fetchall()
        amount = 0
        for input in sal:
            wage = salaries[input[1]][0]
            wage_hours = factor_perc * wage
            amount += input[0] * wage_hours

        return amount

    def calculate_extras_hours_sob(self, payslip, code, perc=100):
        factor_perc = perc / 100
        date_from = payslip.date_from
        date_to = payslip.date_to

        salaries = self.calcualte_changes_salary(date_from, date_to)

        ###################################
        # Inputs in this period
        date_start = fields.Date.to_string(date_from)
        date_end = fields.Date.to_string(date_to)
        entries_type = self.env['hr.payslip.input.type'].search([('code', '=', code)])

        self.env.cr.execute("""
                                SELECT 
                                    input.amount,
                                    input.date
                                FROM hr_inputs input
                                WHERE 
                                    input.input_id in %s
                                    AND input.employee_id = %s
                                    AND input.state in ('confirm', 'approve')
                                    AND input.date IS NOT NULL
                                    AND (input.date, input.date) OVERLAPS (%s, %s)
                            """, (entries_type._ids, self.employee_id.id, date_start, date_end))
        sal = self.env.cr.fetchall()
        amount = 0
        for input in sal:
            wage = salaries[input[1]][0]
            seniority_premium = salaries[input[1]][3] / 2
            wage_hours = factor_perc * (wage + seniority_premium)
            amount += input[0] * wage_hours

        return amount

    def calculate_provisions(self, slip):
        self.ensure_one()
        self.env.cr.execute("""
                                DELETE FROM 
                                    hr_provisions 
                                WHERE payslip_run_id = %s AND contract_id = %s
                            """, (slip.payslip_run_id.id, self.id))
        daily_wage = self.daily_salary
        date_end = slip.payroll_period_id.date_end
        date_start = date(date_end.year, 1, 1)
        years, days = self._get_years_antiquity()
        if days > 0:
            years += 1

        anni_date = self.previous_contract_date or self.date_start
        if date_start < anni_date:
            date_start = anni_date
        if self.date_end and date_end > self.date_end:
            date_end = self.date_end

        try:
            anniversary_date = date(date_end.year, anni_date.month, anni_date.day)
        except:
            anniversary_date = date(date_end.year, anni_date.month, anni_date.day - 1)
        if anniversary_date > date_end:
            try:
                anniversary_date = date(date_end.year - 1, anni_date.month, anni_date.day)
            except:
                anniversary_date = date(date_end.year - 1, anni_date.month, anni_date.day - 1)

        self.env.cr.execute("""
                                SELECT 
                                    line.aguinaldo,
                                    line.holidays,
                                    line.vacation_cousin
                                FROM hr_table_antiquity_line line
                                WHERE 
                                    line.antiquity_line_id in %s
                                    AND line.year = %s
                                LIMIT 1
                            """, (self.employee_id.antiquity_id._ids, years))
        res = self.env.cr.fetchall()[0]
        bonus = res[0]
        holiday = res[1]
        holiday_bonus = res[2]

        DP = (date_end - date_start).days + 1
        DV = (date_end - anniversary_date).days + 1
        DV_post = 0
        year_holiday = anniversary_date.year
        if slip.payroll_period_id.date_start <= anniversary_date <= date_end:
            DV_post = DV
            year_holiday = anniversary_date.year - 1
            try:
                DV = (anniversary_date - date(anniversary_date.year - 1, anniversary_date.month, anniversary_date.day)).days  # one day before the anniversary
            except:
                DV = (anniversary_date - date(anniversary_date.year - 1, anniversary_date.month, anniversary_date.day - 1)).days

        if DP == 366:
            DP -= 1
        if DV == 366:
            DV -= 1

        total_bonus = daily_wage * DP * bonus / 365
        total_holiday = daily_wage * DV * holiday / 365
        total_holiday_bonus = total_holiday * holiday_bonus / 100

        self.env.cr.execute("""
                                SELECT
                                    provisions.type,
                                    SUM(provisions.amount) 
                                FROM hr_provisions provisions
                                WHERE
                                    ((provisions.year = %s AND provisions.type = 'bonus')
                                    OR (provisions.year = %s AND provisions.type <> 'bonus'))
                                    AND provisions.contract_id = %s
                                GROUP BY provisions.type
                            """, (date_end.year, year_holiday, self.id))
        res = self.env.cr.fetchall()
        provisions = dict(res)
        
        bonus = total_bonus - provisions['bonus'] if provisions.get('bonus') else total_bonus
        holiday_amount = total_holiday - provisions['holidays'] if provisions.get('holidays') else total_holiday
        holiday_bonus_amount = total_holiday_bonus - provisions['premium'] if provisions.get('premium') else total_holiday_bonus
        
        self.env['hr.provisions'].create({'type': 'bonus', 'contract_id': self.id, 'year': date_end.year, 'amount': bonus, 'payslip_run_id': slip.payslip_run_id.id,'timbre':False})
        self.env['hr.provisions'].create({'type': 'holidays', 'contract_id': self.id, 'year': year_holiday, 'amount': holiday_amount, 'payslip_run_id': slip.payslip_run_id.id,'timbre':False})
        self.env['hr.provisions'].create({'type': 'premium', 'contract_id': self.id, 'year': year_holiday, 'amount': holiday_bonus_amount, 'payslip_run_id': slip.payslip_run_id.id,'timbre':False})
        if DV_post:
            post_amount = daily_wage * DV_post * holiday / 365
            post_amount_pre = post_amount * holiday_bonus / 100
            holiday_amount += post_amount
            holiday_bonus_amount += post_amount_pre
            self.env['hr.provisions'].create({'type': 'holidays', 'contract_id': self.id, 'year': date_end.year, 'amount': post_amount, 'payslip_run_id': slip.payslip_run_id.id,'timbre':False})
            self.env['hr.provisions'].create({'type': 'premium', 'contract_id': self.id, 'year': date_end.year, 'amount': post_amount_pre, 'payslip_run_id': slip.payslip_run_id.id,'timbre':False})

        return {'bonus': bonus, 'holiday_amount': holiday_amount, 'holiday_bonus_amount': holiday_bonus_amount}
    
    def calculate_provisions_no_adjustment(self, slip):
        years, days = self._get_years_antiquity()
        if days > 0:
            years += 1
        self.env.cr.execute("""
                                SELECT 
                                    line.aguinaldo,
                                    line.holidays,
                                    line.vacation_cousin
                                FROM hr_table_antiquity_line line
                                WHERE 
                                    line.antiquity_line_id in %s
                                    AND line.year = %s
                                LIMIT 1
                            """, (self.employee_id.antiquity_id._ids, years))
        res = self.env.cr.fetchall()[0]
        bonus = res[0]
        holiday = res[1]
        holiday_bonus = res[2]
        days = (slip.date_to - slip.date_from).days + 1
        DP = 15
        DV = 15
        daily_salary = self.daily_salary
        bonus_amount = daily_salary * days * bonus / 365
        holiday_amount = daily_salary * days * holiday / 365
        holiday_bonus_amount = holiday_amount * holiday_bonus / 100
        return {'bonus': bonus_amount, 'holiday_amount': holiday_amount, 'holiday_bonus_amount': holiday_bonus_amount}
    
    def search_antique_table_bonus(self):
        year = self[0].years_antiquity
        if year < 1:
            year = 1
        antique = self.env['hr.table.antiquity.line'].search([('antiquity_line_id','=',self[0].employee_id.antiquity_id.id),('year','=',year)],limit=1)
        return antique.aguinaldo
    
    def time_worked_year(self,payslip,settlement=None):
        date_from = self.previous_contract_date if self.previous_contract_date else self.date_start
        date_to = self.date_end
        if not date_to and settlement:
            return 0
        days = 0
        date1 =datetime.strptime(str(str(payslip.year)+'-01-01'), DEFAULT_SERVER_DATE_FORMAT).date()
        date2 =datetime.strptime(str(str(payslip.year)+'-12-31'), DEFAULT_SERVER_DATE_FORMAT).date()
        if date_from > date1:
            date1 = date_from
        if date_to and date_to < date2:
            date2 = date_to
        days =  (date2 - date1).days+1
        worked_days = self.env['hr.payslip.worked_days']
        days_discount = 0
        days_discount = sum(worked_days.search([('payslip_id.employee_id','=',self.employee_id.id),
                                            ('work_entry_type_id.code','in',['F01','F04']),
                                            ('payslip_id.year','=',str(payslip.year)),
                                            ('payslip_id.state','in',['done']),
                                            ('payslip_id.contract_id.contracting_regime','in',['02']),
                                            ('payslip_id.payroll_type','in',['O'])]).mapped('number_of_days'))
        days = days - days_discount
        if days < 0:
            days = 0
        days_aguinaldo = self.search_antique_table_bonus()
        proportion_days = (days*days_aguinaldo)/365
        return proportion_days
        
    def search_christmas_bonus_payments(self,payslip):
        lines = self.env['hr.payslip.line'].search([('slip_id.employee_id','=',self.employee_id.id),
                                        ('slip_id.contract_id','=',self.id),
                                        ('slip_id.year','=',str(payslip.year)),
                                        ('slip_id.state','=','done'),
                                        ('code','in',['P032'])])
        tax = 0
        total = 0
        for i in lines:
            tax += i.tax_amount
            total += i.total
        return [tax,total]
    
    def holiday_calculation_finiquito(self,payslip):
        date_from = self.date_start
        date_to = self.date_end
        days = 0
        antiquity = self._get_years_antiquity(end=True)
        years_antiquity = antiquity[0]
        days_rest = antiquity[1]
        if days_rest > 0:
            years_antiquity += 1
        antiquity_line = self.env['hr.table.antiquity.line'].search([('antiquity_line_id','=',self.employee_id.antiquity_id.id),('year','=',years_antiquity)],limit=1)
        proportional_days = (antiquity_line.holidays/365) * days_rest
        return [float("{0:.2f}".format(proportional_days)),antiquity_line.vacation_cousin]
    
    def seniority_premium_settlement(self,base):
        date_start = self.previous_contract_date if self.previous_contract_date else self.date_start
        date_end =  self.date_end
        days = float("{0:.2f}".format((((date_end-date_start).days + 1)/365) * 12))
        prima = days * base
        return [prima,days]
    
    def compensation_20_days(self,payslip):
        compensation = 0
        antiquity = self._get_years_antiquity(end=True)
        if payslip.value_type_20 == '1':
            days_compensation_20 = payslip.days_compensation_20
        else:
            days_compensation_20 = 20
        years_antiquity = antiquity[0]
        days_rest = antiquity[1]
        days_total = 0
        if int(years_antiquity) == 0 and payslip.contract_id.contract_type in ['02','03']:
            compensation = (days_rest/2)*float(self.sdi)
            days_total = days_rest/2
        else:
            if payslip.contract_id.contract_type in ['02','03']:
                for i in range(1,int(years_antiquity)+1):
                    if i == 1:
                        compensation += float(self.sdi)*180
                        days_total += 180
                    else:
                        compensation += days_compensation_20*float(self.sdi)
                        days_total += days_compensation_20
                if days_rest > 0:
                    proportion_days = (days_rest * days_compensation_20)/365
                    days_total += proportion_days
                    compensation += proportion_days*float(self.sdi)
            else:
                date_start = self.previous_contract_date if self.previous_contract_date else self.date_start
                date_end =  self.date_end
                days_total = (((date_end-date_start).days + 1)/365) * days_compensation_20
                compensation = days_total * float(self.sdi)
        
        if payslip.value_type_20 == '2':
            compensation = (compensation*payslip.days_compensation_20)/100
        return [compensation,days_total]

    def get_leaves_last_year(self, payslip):
        year = payslip.year
        self.env.cr.execute("""
                    SELECT leave.id
                    FROM hr_leave_allocation leave
                    JOIN hr_leave_type type ON type.id=leave.holiday_status_id
                    WHERE leave.employee_id = %s
                        AND type.time_type in ('holidays')
                        AND leave.state in ('validate')
                        AND type.code = 'F08-%s'
                        AND leave.date_due > CURRENT_DATE
                    LIMIT 1
                """, (payslip.employee_id, year - 1))
        
        sal = self.env.cr.dictfetchall()
        allocation_ids = []
        for i in sal:
            allocation_ids.append(int(i['id']))
        records = self.env['hr.leave.allocation'].browse(allocation_ids)
        days = 0
        for i in records:
            leave_type = i.holiday_status_id.with_context(employee_id=payslip.employee_id)
            data_days = leave_type.get_employees_days([payslip.employee_id])[payslip.employee_id]
            result = data_days.get(i.holiday_status_id.id, {})
            days += result.get('remaining_leaves', 0)
            break
        return days
    
    def get_leaves_last_month(self, payslip):
        date_from = payslip.date_from - relativedelta(months=1)
        date_to = payslip.date_from - relativedelta(days=1)
        period = payslip.payroll_period_id
        ###################################
        # Entry in this period
        ###################################
        date_start = datetime.combine(date_from, time.min)
        date_end = datetime.combine(date_to, time.max)
        datetime_start = fields.Datetime.to_string(date_start)
        datetime_end = fields.Datetime.to_string(date_end)
        self.env.cr.execute("""
                                SELECT 
                                    SUM(entry.duration)
                                FROM hr_work_entry entry
                                JOIN hr_work_entry_type type_entry ON type_entry.id = entry.work_entry_type_id
                                JOIN hr_employee employee ON employee.id = entry.employee_id
                                JOIN hr_contract contract ON employee.contract_id = contract.id
                                JOIN resource_calendar calendar ON contract.resource_calendar_id = calendar.id
                                WHERE 
                                    contract.id = %s
                                    AND type_entry.type_leave IN ('inability', 'leave')
                                    AND entry.state in ('validated', 'draft')
                                    AND ((entry.out_of_date IS NOT TRUE AND (entry.date_start, entry.date_stop) OVERLAPS (%s, %s))
                                        OR (entry.out_of_date IS TRUE AND entry.payroll_period_id = %s))
                            """, (payslip.contract_id.id, datetime_start, datetime_end, period.id))
        sal = self.env.cr.fetchall()
        if sal:
            sal = sal[0][0]
        return True if sal else False

    def get_ptu(self, year):
        self.env.cr.execute("""
                                SELECT
                                    COALESCE(line.total_amount, 0)
                                FROM hr_ptu ptu
                                LEFT JOIN hr_ptu_line line      ON line.ptu_id = ptu.id AND line.contract_id = %s
                                WHERE ptu.name = %s
                                    AND ptu.state = 'approve'
                            """, (self.id, year))
        sal = self.env.cr.fetchall()
        if len(sal):
            return sal[0][0]
        else:
            return 0
            
    def calculate_isr_annual(self, payslip):
        
        adjustment_id = self.env['annual.isr.adjustment.line'].search([('adjustment_id','=',payslip.payslip_run_id.adjustment_id.id),
                                                        ('contract_id','=',payslip.contract_id.id),('adjustment_id.state','=','approved')])
        return adjustment_id
        
    def tope_vale(self, value):
        return math.ceil(value)
