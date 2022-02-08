# -*- coding: utf-8 -*-


from odoo import fields, models, api, _


class Employee(models.Model):
    _inherit = "hr.employee"

    responsible_holidays = fields.Many2many(comodel_name="hr.employee", relation="responsible_employee",
                                            column1="employee", column2="responsible", string="Responsible Holidays",
                                            help="Persons who will be notified of this employee's vacation and "
                                                 "personal days.")
    approver_kiosk_id = fields.Many2one('res.users', string="approver (kiosk)")


class EmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    approver_kiosk_id = fields.Many2one('res.users', string="approver (kiosk)")
