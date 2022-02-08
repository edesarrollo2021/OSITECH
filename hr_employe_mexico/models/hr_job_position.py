# -*- coding: utf-8 -*-

from datetime import date

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from dateutil.relativedelta import relativedelta


class HrJobPosition(models.Model):
    _name = 'hr.job.position'
    _description = 'Positions in the Jobs'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Number", required=True, copy=False)
    job_id = fields.Many2one("hr.job", string="Job", required=True)
    employee_id = fields.Many2one("hr.employee", string="Employee")
    history_ids = fields.One2many("hr.job.position.history", "position_id", string="History")

    def change_employees(self, employee=False, date_end=False):
        # date_end if employee is removed from position, else False
        date_start = date_end + relativedelta(days=1) if date_end else fields.Date.today()
        date_end = date_end if date_end else fields.Date.today()
        self.history_ids.filtered(lambda x: not x.date_end).write({'date_end': date_end})
        if employee:
            if self.employee_id != employee:
                history = self.env['hr.job.position.history'].create({
                    'employee_id': employee.id,
                    'date_start': date_start,
                    'position_id': self.id,
                })
            self.employee_id = employee.id
        else:
            self.employee_id = False


class HrJobPositionHistory(models.Model):
    _name = 'hr.job.position.history'
    _description = 'Job Position History'

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True)
    date_start = fields.Date(string="Date Start", required=True)
    date_end = fields.Date(string="Date End")
    position_id = fields.Many2one("hr.job.position", string="Position")

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for res in self:
            if res.date_end and res.date_end < res.date_start:
                raise UserError(_('The start date cannot be greater than the end date of the history of the position.'))
