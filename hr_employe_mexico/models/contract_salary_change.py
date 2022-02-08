# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import fields, models, api, _
from odoo.osv import expression
from odoo.exceptions import ValidationError


class ContractSalaryChangeLine(models.Model):
    _name = 'contract.salary.change.line'
    _order = 'create_date desc'
    _description = 'Record for the change of salary'

    name = fields.Char(string="Code", default="/")
    date_start = fields.Date(string="Date start", required=True)
    date_end = fields.Date(string="Date end")
    wage = fields.Float(string="Monthly Salary")
    daily_salary = fields.Float(string="Salary")
    sdi = fields.Float(string="SDI")
    sbc = fields.Float(string="SBC")
    integrated_salary = fields.Float(string="Integrated Salary")
    seniority_premium = fields.Float(string="Seniority Premium")
    contract_id = fields.Many2one('hr.contract', string="Contract", required=True)

    @api.constrains('date_start', 'date_end')
    def _constraint_percentage(self):
        for record in self:
            other_res = self.search([
                ('id', '!=', record.id),
                ('contract_id', '=', record.contract_id.id),
                ('date_start', '<=', record.date_end or fields.Date.today() + relativedelta(days=-1)),
            ])
            other_res = other_res.filtered(lambda x: x.date_end == False or x.date_end >= record.date_start)
            if other_res:
                raise ValidationError(_("Two salaries cannot be active within the same date ranges!"))
            if self.search([('id', '!=', record.id), ('contract_id', '=', record.contract_id.id), ('date_end', '=', False)]) and not record.date_end:
                raise ValidationError(_("Two salaries cannot be active within the same date ranges!"))
            if record.date_end and record.date_end < record.date_start:
                raise ValidationError(_("""
                    The end date must be greater than the start date!
                    Review previous salary changes for the contract if the contract has no errors
                """))

    @api.model
    def create(self, vals):
        result = super(ContractSalaryChangeLine, self).create(vals)
        if result.name == '/':
            result.name = self.env['ir.sequence'].next_by_code('contract.salary.change')
        return result
