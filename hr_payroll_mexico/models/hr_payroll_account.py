#-*- coding:utf-8 -*-

from itertools import groupby
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _action_create_account_move_group(self):
        precision = self.env['decimal.precision'].precision_get('Payroll')

        # Add payslip without run
        payslips_to_post = self.filtered(lambda slip: not slip.payslip_run_id)

        # Adding pay slips from a batch and deleting pay slips with a batch that is not ready for validation.
        payslip_runs = (self - payslips_to_post).mapped('payslip_run_id')
        for run in payslip_runs:
            if run._are_payslips_ready():
                payslips_to_post |= run.slip_ids

        # A payslip need to have a done state and not an accounting move.
        payslips_to_post = payslips_to_post.filtered(lambda slip: slip.state == 'done' and not slip.move_id)

        # Check that a journal exists on all the structures
        if any(not payslip.struct_id for payslip in payslips_to_post):
            raise ValidationError(_('One of the contract for these payslips has no structure type.'))
        if any(not structure.journal_id for structure in payslips_to_post.mapped('struct_id')):
            raise ValidationError(_('One of the payroll structures has no account journal defined on it.'))

        # Map all payslips by structure journal and pay slips month.
        # {'journal_id': {'month': [slip_ids]}}
        slip_mapped_data = {slip.struct_id.journal_id.id: {slip.payment_date: self.env['hr.payslip']} for slip in payslips_to_post}
        for slip in payslips_to_post:
            slip_mapped_data[slip.struct_id.journal_id.id][slip.payment_date] |= slip

        moves = []
        for journal_id in slip_mapped_data: # For each journal_id.
            for slip_date in slip_mapped_data[journal_id]: # For each month.
                line_ids = []
                debit_sum = 0.0
                credit_sum = 0.0
                date = slip_date
                move_dict = {
                    'narration': '',
                    'ref': '',
                    'journal_id': journal_id,
                    'date': date,
                }

                for slip in slip_mapped_data[journal_id][slip_date]:
                    move_dict['narration'] = slip.payslip_run_id.name
                    move_dict['ref'] = slip.payslip_run_id.payroll_period_id.name
                    slip_lines = slip._prepare_slip_lines(date, line_ids)
                    line_ids.extend(slip_lines)

                for line_id in line_ids: # Get the debit and credit sum.
                    debit_sum += line_id['debit']
                    credit_sum += line_id['credit']

                # The code below is called if there is an error in the balance between credit and debit sum.
                if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                    slip._prepare_adjust_line(line_ids, 'credit', debit_sum, credit_sum, date)
                elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                    slip._prepare_adjust_line(line_ids, 'debit', debit_sum, credit_sum, date)

                # Add accounting lines in the move
                # GroupBy Analytic Account
                new_vals = {}
                grouping_keys = groupby(line_ids, key=lambda x: (x.get('analytic_account_id'), x.get('rule_code'), x.get('journal_id'), x.get('account_id'), x.get('type')))
                for keys, invoices in grouping_keys:
                    for inv in invoices:
                        new_vals.setdefault(keys, {
                            'name': inv['name'],
                            'partner_id': inv['partner_id'],
                            'account_id': inv['account_id'],
                            'journal_id': inv['journal_id'],
                            'date': inv['date'],
                            'debit': 0.0,
                            'credit': 0.0,
                            'analytic_account_id': inv['analytic_account_id'] if inv['type'] == 'debit' else False,
                        })
                        new_vals[keys]['debit'] += inv['debit'] if inv['type'] == 'debit' else 0
                        new_vals[keys]['credit'] += inv['credit'] if inv['type'] == 'credit' else 0
                move_dict['line_ids'] = [(0, 0, new_vals[line_vals]) for line_vals in new_vals]
                moves.append(move_dict)
                move = self._create_account_move(move_dict)
                for slip in slip_mapped_data[journal_id][slip_date]:
                    slip.write({'move_id': move.id, 'date': date})
                move.action_post()
        return moves

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        if not line.slip_id.contract_id.department_id.analytic_account_id:
            raise UserError(_("You should assign a Analytic Account to department %s.") %line.slip_id.contract_id.department_id.name)
        return {
            'name': line.name,
            'partner_id': line.partner_id.id,
            'account_id': account_id,
            'journal_id': line.slip_id.struct_id.journal_id.id,
            'date': date,
            'debit': debit,
            'credit': credit,
            'type': 'credit' if credit > 0 else 'debit',
            'employee': line.employee_id.id,
            'rule_code': line.salary_rule_id.code,
            'analytic_account_id': line.slip_id.contract_id.department_id.analytic_account_id.id,
        }


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_post_account(self):
        slip_ids = self.mapped('slip_ids').filtered(lambda slip: slip.state != 'cancel')
        slip_ids._action_create_account_move_group()


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

