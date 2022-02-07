# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError, AccessError
from odoo import api, fields, models, _

from dateutil.relativedelta import relativedelta


class ContractChangeWizard(models.TransientModel):
    _name = "hr.contract.change.wizard"
    _description = "wizard to change the department and job title of the contract"

    employee_id = fields.Many2one('hr.employee', string='Employee', related='contract_id.employee_id')
    contract_id = fields.Many2one('hr.contract', string='Contract')
    date = fields.Date(string="Date", default=fields.Date.today())
    salary = fields.Float(string='Salary')
    field_changes = fields.Selection([
        ('salary', 'Salary'),
        ('seniority_premium', 'Seniority Premium'),
    ], string="Field Change", required=True)

    def change_fields(self):
        # if self.field_changes != 'salary':
        #     self.env['history.changes.employee'].create({
        #         'employee_id': self.employee_id.id,
        #         'contract_id': self.contract_id.id,
        #         'type': 'department' if self.field_changes == 'department' else 'job',
        #         'date': self.date,
        #         'new_department_id': self.department_id.id if self.field_changes == 'department' else False,
        #         'department_id': self.contract_id.department_id.id if self.field_changes == 'department' else False,
        #         'new_job_id': self.job_id.id if self.field_changes == 'job' else False,
        #         'job_id': self.contract_id.job_id.id if self.field_changes == 'job' else False,
        #     })
        if self.field_changes == 'salary':
            SalaryChange = self.env['contract.salary.change.line']
            diferents = self.contract_id.wage != self.salary

            self.contract_id.wage = self.salary 
            self.contract_id.daily_salary = self.salary / self.env.company.days_factor if self.salary else False
            self.contract_id.integral_salary = self.contract_id._calculate_integral_salary()
            self.contract_id.sdi = self.contract_id.integral_salary + self.contract_id.variable_salary
            limit_imss = self.contract_id.company_id.uma*self.contract_id.company_id.general_uma
            if self.contract_id.sdi > limit_imss:
                self.contract_id.sbc = limit_imss
            else:
                self.contract_id.sbc = self.contract_id.sdi

            movements = self.env['hr.employee.affiliate.movements'].search([
                ('contract_id', '=', self.contract_id.id),
                ('type', '=', '08'),
            ])
            if not movements:
                self.env['hr.employee.affiliate.movements'].create({
                    'contract_id': self.contract_id.id,
                    'employee_id': self.employee_id.id,
                    'company_id': self.contract_id.company_id.id,
                    'type': '08',
                    'date': self.date,
                    'wage': self.salary,
                    'sbc': self.contract_id.sbc,
                    'salary': self.contract_id.sdi,
                })
            if diferents:
                self.env['hr.employee.affiliate.movements'].create({
                    'contract_id': self.contract_id.id,
                    'employee_id': self.employee_id.id,
                    'company_id': self.contract_id.company_id.id,
                    'type': '07',
                    'date': self.date,
                    'wage': self.salary,
                    'salary': self.contract_id.sdi,
                    'sbc': self.contract_id.sbc,
                })

            change_salary = SalaryChange.search([
                ('contract_id', '=', self.contract_id.id),
                ('wage', '=', self.contract_id.wage),
                ('daily_salary', '=', self.contract_id.daily_salary),
                ('sdi', '=', self.contract_id.sdi),
                ('sbc', '=', self.contract_id.sbc),
                ('integrated_salary', '=', self.contract_id.integral_salary),
                ('seniority_premium', '=', self.contract_id.seniority_premium),
                ('date_end', '=', False),
            ])
            previous_change = SalaryChange.search([('date_end', '=', False), ('contract_id', '=', self.contract_id.id)])  # Previous Record
            if not change_salary:
                if previous_change and previous_change.date_start == self.date:
                    previous_change.write({
                        'wage': self.contract_id.wage,
                        'daily_salary': self.contract_id.daily_salary,
                        'sdi': self.contract_id.sdi,
                        'sbc': self.contract_id.sbc,
                        'integrated_salary': self.contract_id.integral_salary,
                        'seniority_premium': self.contract_id.seniority_premium,
                    })
                else:
                    previous_change.write({'date_end': self.date + relativedelta(days=-1)})
                    SalaryChange.create({
                        'contract_id': self.contract_id.id,
                        'wage': self.contract_id.wage,
                        'daily_salary': self.contract_id.daily_salary,
                        'sdi': self.contract_id.sdi,
                        'sbc': self.contract_id.sbc,
                        'integrated_salary': self.contract_id.integral_salary,
                        'seniority_premium': self.contract_id.seniority_premium,
                        'date_start': self.date,
                    })
        if self.field_changes == 'seniority_premium':
            SalaryChange = self.env['contract.salary.change.line']

            self.contract_id.seniority_premium = self.salary

            change_salary = SalaryChange.search([
                ('contract_id', '=', self.contract_id.id),
                ('wage', '=', self.contract_id.wage),
                ('daily_salary', '=', self.contract_id.daily_salary),
                ('sdi', '=', self.contract_id.sdi),
                ('sbc', '=', self.contract_id.sbc),
                ('integrated_salary', '=', self.contract_id.integral_salary),
                ('seniority_premium', '=', self.salary),
                ('date_end', '=', False),
            ])
            previous_change = SalaryChange.search([('date_end', '=', False), ('contract_id', '=', self.contract_id.id)])  # Previous Record
            if not change_salary:
                if previous_change and previous_change.date_start == self.date:
                    SalaryChange.write({
                        'wage': self.contract_id.wage,
                        'daily_salary': self.contract_id.daily_salary,
                        'sdi': self.contract_id.sdi,
                        'sbc': self.contract_id.sbc,
                        'integrated_salary': self.contract_id.integral_salary,
                        'seniority_premium': self.contract_id.seniority_premium,
                    })
                else:
                    previous_change.write({'date_end': self.date + relativedelta(days=-1)})
                    SalaryChange.create({
                        'contract_id': self.contract_id.id,
                        'wage': self.contract_id.wage,
                        'daily_salary': self.contract_id.daily_salary,
                        'sdi': self.contract_id.sdi,
                        'sbc': self.contract_id.sbc,
                        'integrated_salary': self.contract_id.integral_salary,
                        'seniority_premium': self.contract_id.seniority_premium,
                        'date_start': self.date,
                    })

        return True
