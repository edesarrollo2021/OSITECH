# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime, date, time
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'
    _description = 'Generate payslips for all selected employees'


    def _default_estructure(self):
        payslip_run = self.env['hr.payslip.run'].search([('id', 'in', self.env.context.get('active_ids', []))])
        return payslip_run.structure_id.id
    
    employee_ids = fields.Many2many('hr.employee', 'hr_employee_group_rel', 'payslip_id', 'employee_id', 'Employees', required=True, default='')
    structure_id = fields.Many2one('hr.payroll.structure', string='Salary Structure', default=lambda self: self._default_estructure())
    
    select_all_employees = fields.Boolean('Select all employees')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')

    @api.onchange('structure_id')
    def onchange_estructure(self):
        payslip_run=self.env[self.env.context['active_model']].browse(self.env.context['active_id'])
        employee_out = payslip_run.slip_ids.mapped('employee_id')
        if not self.structure_id.ptu_payslip:
            domain = [('structure_type_id','=',self.structure_id.type_id.id),('state','in',['open'])]
            employee_ids = self.env['hr.contract'].search(domain).mapped('employee_id')
        else:
            employee_ids = self.env['hr.ptu.line'].search([('contract_id.structure_type_id','=',self.structure_id.type_id.id),
                                            ('ptu_id.state','in',['approve']),
                                            ('ptu_id.name','=',payslip_run.year_ptu)]).mapped('employee_id')
        employee_ids = employee_ids - employee_out
        return {'domain':{'employee_ids':[('id','in',employee_ids.ids)]}}
    
    @api.onchange('select_all_employees')
    def onchange_select_all_employees(self):
        if self.select_all_employees:
            payslip_run=self.env[self.env.context['active_model']].browse(self.env.context['active_id'])
            employee_out = payslip_run.slip_ids.mapped('employee_id')
            if not self.structure_id.ptu_payslip:
                domain = [('structure_type_id','=',self.structure_id.type_id.id),('state','in',['open'])]
                employee_ids = self.env['hr.contract'].search(domain).mapped('employee_id')
            else:
                employee_ids = self.env['hr.ptu.line'].search([('contract_id.structure_type_id','=',self.structure_id.type_id.id),
                                                ('ptu_id.state','in',['approve']),
                                                ('ptu_id.name','=',payslip_run.year_ptu)]).mapped('employee_id')
            employee_ids = employee_ids - employee_out
            self.employee_ids = [[6, 0, employee_ids.ids]]
        else:
            self.employee_ids = False

    def save(self):
        self.write({'state': 'done'})
        employees = self.with_context(active_test=False).employee_ids
        if not employees:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.employees',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'context': self.env.context
        }


    def compute_sheet(self, options):
        self.ensure_one()
        if not self.env.context.get('active_id'):
            from_date = fields.Date.to_date(self.env.context.get('default_date_start'))
            end_date = fields.Date.to_date(self.env.context.get('default_date_end'))
            payslip_run = self.env['hr.payslip.run'].create({
                'name': from_date.strftime('%B %Y'),
                'date_start': from_date,
                'date_end': end_date,
            })
        else:
            payslip_run = self.env['hr.payslip.run'].browse(self.env.context.get('active_id'))
        employees = self.with_context(active_test=False).employee_ids
        if not employees:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))

        Payslip = self.env['hr.payslip']
        contract_ids = Payslip.search([
            ('payslip_run_id', 'in', payslip_run.ids)
        ]).mapped('contract_id')
        
        
        if not self.structure_id.ptu_payslip:
            contracts = employees._get_contracts(
                payslip_run.date_start, payslip_run.date_end, states=['open', 'close']
            ).filtered(lambda c: c.active)
        else:
            contracts = self.env['hr.ptu.line'].search([('contract_id.structure_type_id','=',self.structure_id.type_id.id),
                                                ('ptu_id.state','in',['approve']),
                                                ('ptu_id.name','=',payslip_run.year_ptu),
                                                ('employee_id','=',employees.ids)
                                                ]).mapped('contract_id')
        contracts -= contract_ids
        if contracts:
            accumulated_payroll_dict = {}
            if contracts:
                if payslip_run.payroll_period_id.end_monthly_period:
                    contracts_ids = tuple(['%s' % c.id for c in contracts])
                    self.env.cr.execute("""
                            SELECT line.total, line.code, slip.contract_id, slip.employee_id
                            FROM hr_payslip_line line
                            JOIN hr_payslip slip ON line.slip_id = slip.id
                            WHERE line.code in ('UI090','UI091','UI092','OP001','D014') AND slip.state='done'
                                AND slip.contract_id IN %s
                                AND slip.year = %s
                                AND slip.payroll_month = %s
                            order by slip.id""",
                                        (contracts_ids, payslip_run.payroll_period_id.year,
                                         str(payslip_run.payroll_period_id.month)))
                    accumulated_payroll_line = self.env.cr.fetchall()
                    for line in accumulated_payroll_line:
                        current_accumulated_payroll_line = accumulated_payroll_dict.setdefault(str(line[2]), {
                            'taxable_month': 0,
                            'subsidy_month': 0,
                            'isr_month': 0,
                            'subsidy_caused_month': 0,
                        })
                        if line[1] == 'UI090':
                            current_accumulated_payroll_line['taxable_month'] += line[0]
                        if line[1] == 'OP001':
                            current_accumulated_payroll_line['subsidy_month'] += line[0]
                        elif line[1] in ['UI091','D014']:
                            current_accumulated_payroll_line['isr_month'] += line[0]
                        if line[1] == 'UI092':
                            current_accumulated_payroll_line['subsidy_caused_month'] += line[0]
            # contracts.with_context(force_work_entry_generation=True)._generate_work_entries(payslip_run.date_start, payslip_run.date_end)
            default_values = Payslip.default_get(Payslip.fields_get())
            payslip_values = []
            for contract in contracts:
                vals = dict(default_values, **{
                    'name': 'Payslip - %s' % (contract.employee_id.name),
                    'employee_id': contract.employee_id.id,
                    'credit_note': payslip_run.credit_note,
                    'payslip_run_id': payslip_run.id,
                    'date_from': payslip_run.date_start,
                    'date_to': payslip_run.date_end,
                    'contract_id': contract.id,
                    'struct_id': self.structure_id.id or contract.structure_type_id.default_struct_id.id,
                    'payroll_period_id': payslip_run.payroll_period_id.id,
                    'payroll_period': payslip_run.payroll_period,
                    'year': payslip_run.payroll_period,
                    'payroll_month': payslip_run.month,
                    'payment_date': payslip_run.payment_date,
                    'type_struct_id': payslip_run.structure_id.type_id.id,
                    'payroll_type': payslip_run.structure_id.payroll_type,
                })
                if payslip_run.payroll_period_id.end_monthly_period and accumulated_payroll_dict.get(str(contract.id)):
                    vals['taxable_month'] = accumulated_payroll_dict[str(contract.id)]['taxable_month']
                    vals['subsidy_month'] = accumulated_payroll_dict[str(contract.id)]['subsidy_month']
                    vals['isr_month'] = accumulated_payroll_dict[str(contract.id)]['isr_month']
                    vals['subsidy_caused_month'] = accumulated_payroll_dict[str(contract.id)]['subsidy_caused_month']
                payslip_values.append(vals)
            payslips = Payslip.with_context(tracking_disable=True).create(payslip_values)
            for payslip in payslips:
                payslip.with_context(payslip_run_id=payslip_run.id)._onchange_employee()
        return self.generate_all(payslip_run, options)

    def generate_all(self, payslip_run, options):
        payslips = self.env['hr.payslip'].search([
            ('payslip_run_id', 'in', payslip_run.ids),
            ('calculated', '=', False),
            ('computed_error', '=', False)
        ], limit=options.get('limit'))
        payslips.with_context(payslip_run_id=payslip_run.id).compute_sheet()
        payslip_run.state = 'verify'
        return {
            'ids': payslips.ids,
            'messages': [],
            'continues': 0 if not payslips else 1,
        }
