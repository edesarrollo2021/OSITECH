# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class AnnualISRAdjustmentEmployee(models.TransientModel):
    _name = 'annual.isr.adjustment.employee'
    _description = 'Wizard for Annual ISR Adjustment by Employee'

    employee_ids = fields.Many2many("hr.employee", relation='isr_adjustment_employees_rel', string="Employees")
    all_employees = fields.Boolean(string="Select all")
    adjustment_id = fields.Many2one("annual.isr.adjustment", string="Adjustment", required=True)

    @api.onchange('adjustment_id')
    def _get_employee_id_domain(self):
        domain = [('state', 'in', ['open']), ('employee_id.isr_adjustment', '=', True)]

        if self.env.context.get('company_id'):
            domain += [('employee_id.company_id', '=', int(self.env.context['company_id']))]
        if self.env.context.get('struct'):
            domain += [('structure_type_id', '=', int(self.env.context['struct']))]
        if self.env.context.get('year'):
            domain += [
                '|', '&',
                ('previous_contract_date', '!=', False),
                ('previous_contract_date', '<=', date(int(self.env.context['year']), 1, 1)),
                '&',
                ('previous_contract_date', '=', False),
                ('date_start', '<=', date(int(self.env.context['year']), 1, 1)),
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', date(int(self.env.context['year']), 12, 1)),
            ]
        employee_ids = self.env['hr.contract'].search(domain).mapped('employee_id')
        if self.env.context.get('default_adjustment_id'):
            Adjustment = self.env['annual.isr.adjustment'].browse(self.env.context['default_adjustment_id'])
            employee_ids -= Adjustment.line_ids.mapped('employee_id')
        return {'domain': {'employee_ids': [('id', 'in', employee_ids.ids)]}}
    
    @api.onchange('all_employees')
    def onchange_all_employees(self):
        domain = [('state', 'in', ['open']), ('employee_id.isr_adjustment', '=', True)]

        if self.env.context.get('company_id'):
            domain += [('employee_id.company_id', '=', int(self.env.context['company_id']))]
        if self.env.context.get('struct'):
            domain += [('structure_type_id', '=', int(self.env.context['struct']))]
        if self.env.context.get('year'):
            domain += [
                '|', '&',
                ('previous_contract_date', '!=', False),
                ('previous_contract_date', '<=', date(int(self.env.context['year']), 1, 1)),
                '&',
                ('previous_contract_date', '=', False),
                ('date_start', '<=', date(int(self.env.context['year']), 1, 1)),
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', date(int(self.env.context['year']), 12, 1)),
            ]
        self.employee_ids = False
        if self.all_employees:
            employee_ids = self.env['hr.contract'].search(domain).mapped('employee_id')
            self.employee_ids = employee_ids - self.adjustment_id.line_ids.mapped('employee_id')

    def save_employees(self):
        if not self.employee_ids:
            return
        date_start = fields.Date.to_string(date(self.adjustment_id.year, 1, 1))
        date_end = fields.Date.to_string(date(self.adjustment_id.year, 12, 1))

        query = """
                    SELECT
                        contract.id,
                        contract.employee_id
                    FROM hr_contract contract
                    WHERE
                        contract.contracting_regime in ('02', '07', '08', '09', '11')
                        AND contract.state = 'open'
                        AND ((contract.previous_contract_date IS NOT NULL
                        AND contract.previous_contract_date < %s)
                        OR (contract.previous_contract_date IS NULL
                        AND contract.date_start <= %s))
                        AND (contract.date_end IS NULL OR contract.date_end >= %s) 
                        AND contract.structure_type_id = %s
                """
        if len(self.employee_ids) > 1:
            query += ' AND contract.employee_id IN %s' % (self.employee_ids._ids,)
        else:
            query += ' AND contract.employee_id = %s' % self.employee_ids.id

        self.env.cr.execute(query, (date_start, date_start, date_end, self.adjustment_id.structure_type_id.id))
        contracts = self.env.cr.fetchall()

        for contract in contracts:
            self.adjustment_id.write({'state': 'verify'})
            self.adjustment_id.line_ids.create({
                'contract_id': contract[0],
                'employee_id': contract[1],
                'adjustment_id': self.adjustment_id.id
            })

