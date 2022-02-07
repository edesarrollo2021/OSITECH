# -*- coding: utf-8 -*-

from odoo import fields, models, api


class HistoryChangesEmployee(models.Model):
    _name = 'history.changes.employee'
    _description = 'History of Changes of Employees'
    _order = 'create_date desc'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    contract_id = fields.Many2one('hr.contract', string="Contract")
    type = fields.Selection([
        ('department', 'Department change'),
        ('position', 'Position change'),
        ('cost_center', 'Cost Center Change'),
    ], string="Type")
    date = fields.Date(string="Date")
    department_id = fields.Many2one('hr.department', string="Department")
    new_department_id = fields.Many2one('hr.department', string="New Department")
    job_id = fields.Many2one('hr.job', string="Job")
    new_job_id = fields.Many2one('hr.job', string="New Job")
    position_id = fields.Many2one('hr.job.position', string="Position")
    new_position_id = fields.Many2one('hr.job.position', string="New Position")
    cost_center_id = fields.Many2one('hr.cost.center', string="Cost Center")
    new_cost_center_id = fields.Many2one('hr.cost.center', string="New Cost Center")

    def name_get(self):
        result = []
        for res in self:
            result.append((res.id, "%s - %s (%s)" % (res.employee_id.name, res.type, res.date)))
        return result
