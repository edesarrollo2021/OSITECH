# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo.exceptions import ValidationError, AccessError
from odoo import api, fields, models, _


class EmployeeChangeWizard(models.TransientModel):
    _name = "hr.employee.change.wizard"
    _description = "wizard to change the Cost Center title of the employee record"

    employee_id = fields.Many2one('hr.employee', string='Employee')
    date = fields.Date(string="Date", required=True)
    cost_center_id = fields.Many2one('hr.cost.center', string='Cost Center')
    department_id = fields.Many2one('hr.department', string='Department')
    job_id = fields.Many2one('hr.job', string='Job')
    position_id = fields.Many2one('hr.job.position', string='Position')
    field_changes = fields.Selection([
        ('department', 'Department'),
        ('job', 'Job'),
    ], string="Field Change", required=True, default='department')

    def change_fields(self):
        if self.date and self.date > fields.Date.today():
            raise ValidationError(_('The changeover date must be less than or equal to today.'))
        if self.field_changes == 'department':
            self.env['history.changes.employee'].create({
                'employee_id': self.employee_id.id,
                'type': self.field_changes,
                'date': self.date,
                'new_department_id': self.department_id.id,
                'department_id': self.employee_id.department_id.id,
            })
            contracts = self.env['hr.contract'].search([('employee_id', '=', self.employee_id.id), ('state', 'in', ['draft', 'open'])])
            for contract in contracts:
                contract.department_id = self.department_id
            self.employee_id.department_id = self.department_id
        if self.field_changes == 'job' and self.position_id != self.employee_id.position_id:
            self.env['history.changes.employee'].create({
                'employee_id': self.employee_id.id,
                'type': 'position',
                'date': self.date,
                'new_job_id': self.job_id.id,
                'job_id': self.employee_id.job_id.id,
                'new_position_id': self.position_id.id,
                'position_id': self.employee_id.position_id.id,
            })
            contracts = self.env['hr.contract'].search([('employee_id', '=', self.employee_id.id), ('state', 'in', ['draft', 'open'])])
            for contract in contracts:
                contract.job_id = self.job_id
            self.employee_id.job_id = self.job_id
            self.employee_id.position_id.change_employees(date_end=self.date + relativedelta(days=-1))  # no employee
            self.employee_id.position_id = self.position_id
            self.employee_id.position_id.change_employees(self.employee_id, date_end=self.date + relativedelta(days=-1))  # new employee
