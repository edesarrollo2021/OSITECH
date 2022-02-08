# -*- coding: utf-8 -*-

from datetime import date, datetime, timedelta

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class InsuranceMajorMedicalExpenses(models.Model):
    _name = 'insurance.major.medical.expenses'
    _description = 'Insurance Major Medical Expenses'
    _rec_name = "employee_id"

    amount = fields.Float(string="Monthly Amount of the policy", required=True)
    date_start = fields.Date(string="Date Start", required=True)
    date_end = fields.Date(string="Date End", required=True)
    employee_id = fields.Many2one("hr.employee", string="Employee")

    @api.constrains('employee_id', 'date_start', 'date_end')
    def _check_dates_by_employee(self):
        for record in self:
            self.env.cr.execute("""
                            SELECT 
                                1
                            FROM insurance_major_medical_expenses insurance
                            WHERE 
                                insurance.id NOT IN %s
                                AND insurance.employee_id = %s
                                AND (insurance.date_start, insurance.date_end) OVERLAPS (%s, %s)
                        """, (record._ids, record.employee_id.id, record.date_start - timedelta(days=1), record.date_end + timedelta(days=1)))

            overlaps = self.env.cr.rowcount
            if overlaps:
                raise ValidationError(_('An employee cannot have two medical policies on the same dates.'))
