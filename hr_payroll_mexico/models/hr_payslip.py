# -*- coding: utf-8 -*-

import logging
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, date_utils
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval
from dateutil import relativedelta as rdelta
from lxml import etree as ET

_logger = logging.getLogger(__name__)
import re
import pytz
from pytz import utc, timezone
import base64
import qrcode
from io import StringIO, BytesIO
import zeep

from random import uniform,triangular

from odoo.addons.hr_payroll_mexico.cfdilib_payroll import cfdilib, cfdv32, cfdv33


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'
    _order = 'create_date desc'

    code = fields.Char(string="Code")
    payroll_period_id = fields.Many2one('hr.payroll.period', string='Payroll Period', tracking=True)
    payroll_period = fields.Selection([
        ('01', 'Daily'),
        ('02', 'Weekly'),
        ('03', 'Fourteen'),
        ('10', 'Decennial'),
        ('04', 'Biweekly'),
        ('05', 'Monthly'),
        ('99', 'Another Peridiocity')],
        string='Period', readonly=True, related="payroll_period_id.payroll_period", store=True)
    year = fields.Integer(string='Year', related="payroll_period_id.year", readonly=True, store=True)
    payroll_month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December')], string='Payroll month',
        related="payroll_period_id.month",
        readonly=True, store=True)
    payment_date = fields.Date(string="Payment Date")
    contracting_regime = fields.Selection(related="contract_id.contracting_regime", store=True)
    code_payslip = fields.Char(string='Serie', store=True, readonly=False)
    type_struct_id = fields.Many2one(related="contract_id.structure_type_id", string="Payroll Structure Type")
    payroll_type = fields.Selection([
        ('O', 'Ordinary'),
        ('E', 'Extraordinary'),
    ], string="Type of Payroll", tracking=True, default='O')

    # CFDI
    invoice_status = fields.Selection([
        ('invoice_not_generated', 'Invoice not Generated'),
        ('right_bill', 'Right bill'),
        ('invoice_problems', 'Problems with the invoice'),
        ('problems_canceled', 'Canceled bill'),
    ], string='Invoice Status', default="invoice_not_generated", required=False, readonly=True, tracking=True)
    way_pay = fields.Selection([
        ('99', '99 - To define'),
    ], string='way to pay', default="99", required=True, readonly=True, states={'draft': [('readonly', False)]})
    type_voucher = fields.Selection([
        ('N', 'Payroll'),
    ], string='Type of Voucher', default="N", required=True, readonly=True, states={'draft': [('readonly', False)]})
    payment_method = fields.Selection([
        ('PUE', 'Payment in a single exhibition'),
    ], string='Payment method', default="PUE", required=True, readonly=True, states={'draft': [('readonly', False)]})
    cfdi_use = fields.Selection([
        ('P01', 'To define'),
    ], string='CFDI Use', default="P01", required=True, readonly=True, states={'draft': [('readonly', False)]})

    # Settlement Fields
    settlement = fields.Boolean(string='Settlement', tracking=True)
    reason_liquidation = fields.Selection([
        ('1', _('TERMINATION OF CONTRACT')),
        ('2', _('SEPARACIÓN VOLUNTARIA')),
        ('3', _('ABANDONO DE EMPLEO')),
        ('4', _('DEFUNCIÓN')),
        ('7', _('AUSENTISMOS')),
        ('8', _('RESICIÓN DE CONTRATO')),
        ('9', _('JUBILACIÓN')),
        ('A', _('PENSIÓN')),
        ('5', _('CLAUSURA')),
        ('6', _('OTROS')),
    ],
        string='Reason for liquidation',
        required=False,
        states={'draft': [('readonly', False)]})
    settlemen_date = fields.Date(string='Settlemen date', readonly=True, required=False,
                                 default=lambda self: fields.Date.to_string(date.today().replace(day=1)),
                                 states={'draft': [('readonly', False)]})
    seniority_premium = fields.Boolean(string='Seniority Bonus', default=True)
    
    
    indemnify_employee = fields.Boolean(string='Indemnify the employee')
    
    
    value_type = fields.Selection([
        ('1', _('Days')),
        ('2', _('Percentage')),
    ],
        string='Value Type',
        required=False,
        default='1',
        states={'draft': [('readonly', False)]})
    
    extra_gratification = fields.Boolean(string='Gratificación Extra')
    
    days_indemnify = fields.Integer('Days or percentage Indemnify', required=False, default=90)
    
    
    compensation_20 = fields.Boolean(string='I will pay the compensation of 20 days per year worked?')
    
    value_type_20 = fields.Selection([
        ('1', _('Days')),
        ('2', _('Percentage')),
    ],
        string='Value Type (20)',
        required=False,
        default='1',
        states={'draft': [('readonly', False)]})
    
    days_compensation_20 = fields.Integer(string='Days or percentage Indemnify (20)', default=20)
    
    
    
    
    agreement_employee = fields.Boolean(string='Agreement with the employee')
    amount_agreement = fields.Float('Amount of the agreement', required=False)
    
    
    taxable_month = fields.Float(string='Taxable month')
    subsidy_month = fields.Float(string='Subsidy month')
    isr_month = fields.Float(string='Isr month')
    subsidy_caused_month = fields.Float(string='Subsidy caused_month')
    infonavit_amount_bimester = fields.Float(string='Infonavit amount bimester')
    
    payslip_error = fields.Char(string='Payslip Error', readonly=True, states={'draft': [('readonly', False)]})
    computed_error = fields.Boolean(string='Computes Error')
    calculated = fields.Boolean(string="Calculated?")
    
    
    cfdi_ids = fields.One2many('hr.payslip.cfdi','payslip_id', "CFDIs")
    cfdi_id = fields.Many2one('hr.payslip.cfdi', string='CFDI')
    
    code_error = fields.Char(string='Código de error', readonly=True)
    error = fields.Char(string='Error', readonly=True)
    
    ordinary_period = fields.Boolean(string="Include ordinary period?")
    
    movements_id = fields.Many2one("hr.employee.affiliate.movements", string="Movements low")
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Batch Name', readonly=True,
        copy=False, states={'draft': [('readonly', False)], 'verify': [('readonly', False)], 'done': [('readonly', False)]}, ondelete='cascade',
        domain="[('company_id', '=', company_id)]")
    
    
    @api.constrains('contract_id')
    def validate_contract_id_settlement(self):
        for record in self:
            if record.settlement:
                settlement_ids = self.search([('contract_id','=',record.contract_id.id),('settlement','=',True)])
                if len(settlement_ids) > 1:
                    raise ValidationError(_("There is already a payroll of settlements for the selected contract."))
    
    @api.onchange('employee_id', 'struct_id', 'contract_id', 'date_from', 'date_to', 'payroll_period_id')
    def _onchange_employee(self):
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return
        if self.settlement and not self.payroll_period_id and self.contract_id:
            raise UserError(_("Please select a payroll period.")) 
        if self.settlement and self.contract_id and not self.contract_id.date_end:
            raise UserError(_("You must define the end date of the contract.")) 
        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        self.company_id = employee.company_id
        if not self.contract_id or self.employee_id != self.contract_id.employee_id: # Add a default contract if not already defined
            contracts = employee._get_contracts(date_from, date_to)

            if not contracts or not contracts[0].structure_type_id.default_struct_id:
                self.contract_id = False
                self.struct_id = False
                return
            self.contract_id = contracts[0]
            self.struct_id = contracts[0].structure_type_id.default_struct_id

        lang = employee.sudo().address_home_id.lang or self.env.user.lang
        context = {'lang': lang}
        payslip_name = self.struct_id.payslip_name or _('Salary Slip')
        del context

        self.name = '%s - %s - %s' % (
            payslip_name,
            self.employee_id.complete_name or '',
            format_date(self.env, self.date_from, date_format="MMMM y", lang_code=lang)
        )
        self.payroll_type = self.struct_id.payroll_type
        if date_to > date_utils.end_of(fields.Date.today(), 'month'):
            self.warning_message = _(
                "This payslip can be erroneous! Work entries may not be generated for the period from %(start)s to %(end)s.",
                start=date_utils.add(date_utils.end_of(fields.Date.today(), 'month'), days=1),
                end=date_to,
            )
        else:
            self.warning_message = False
        self.worked_days_line_ids = self._get_new_worked_days_lines()
        self.input_line_ids = self._get_new_input_line_ids()
        if self.settlement:
            self.date_from = self.payroll_period_id.date_start
            self.date_to = self.payroll_period_id.date_end
    
    
    def _get_worked_day_lines_values(self, domain=None):
        payslip_run_id = self.env.context['payslip_run_id']
        self.ensure_one()
        res = []
        hours_per_day = self._get_worked_day_lines_hours_per_day()
        work_hours = self.contract_id._get_work_hours(self.date_from, self.date_to, domain=domain, period=self.payroll_period_id)
        work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
        biggest_work = work_hours_ordered[-1][0] if work_hours_ordered else 0
        add_days_rounding = 0
        for work_entry_type_id, hours in work_hours_ordered:
            work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
            days = round(hours / hours_per_day, 5) if hours_per_day else 0
            if work_entry_type_id == biggest_work:
                days += add_days_rounding
            day_rounded = self._round_days(work_entry_type, days)
            add_days_rounding += (days - day_rounded)
            attendance_line = {
                'sequence': work_entry_type.sequence,
                'work_entry_type_id': work_entry_type_id,
                'number_of_days': day_rounded,
                'number_of_hours': hours,
                'payslip_run_id': payslip_run_id,
            }
            res.append(attendance_line)
        return res
    
    def _get_worked_day_lines(self, domain=None, check_out_of_contract=True):
        """
        :returns: a list of dict containing the worked days values that should be applied for the given payslip
        """
        res = []
        # fill only if the contract as a working schedule linked
        self.ensure_one()
        contract = self.contract_id
        
        payslip_run_id = False
        if self.env.context.get('payslip_run_id'):
            payslip_run_id = self.env.context['payslip_run_id']
        
        if contract.resource_calendar_id:
            res = self.with_context(payslip_run_id=payslip_run_id)._get_worked_day_lines_values(domain=domain)
            leave = 0
            holidays = 0
            personal_days = 0
            inability = 0
            for line in res:
                work_entry_type_id = self.env['hr.work.entry.type'].browse(line['work_entry_type_id'])
                if work_entry_type_id.is_leave:
                    if work_entry_type_id.type_leave == 'leave':
                        leave += line['number_of_days']
                    elif work_entry_type_id.type_leave == 'holidays':
                        holidays += line['number_of_days']
                    elif work_entry_type_id.type_leave == 'personal_days':
                        personal_days += line['number_of_days']
                    elif work_entry_type_id.type_leave == 'inability':
                        inability += line['number_of_days']
            if not check_out_of_contract:
                return res
            entry_type_ids = self.struct_id.unpaid_work_entry_type_ids
            days_factor_month = self.company_id.days_factor
            days_factor = days_factor_month / 30
            payroll_periods_days = {
                '05': 30,
                '04': 15,
                '02': 7,
                '03': 14,
                '10': 10,
                '01': 1,
                '99': 1,
                                }
            days_period = payroll_periods_days[self.payroll_period_id.payroll_period] * days_factor
            attendances_list = contract.resource_calendar_id.attendance_ids.mapped('dayofweek')
            count_days_week = list(set(attendances_list))
            attendances_hours =  sum(attendace.hour_to - attendace.hour_from
                                    for attendace in contract.resource_calendar_id.attendance_ids
                                    )
            days_out = 0
            days_out_imss = 0
            date_from = self.date_from
            date_to = self.date_to
            if self.date_from < contract.date_start:
                date_from = contract.date_start
            if contract.date_end and contract.date_end < self.date_to:
                date_to = contract.date_end
            work100 = (date_to - date_from).days + 1
            work100_imss = (date_to - date_from).days + 1
            if self.date_to.day == 31 and self.payroll_period_id.payroll_period == '04':
                if (contract.date_end and contract.date_end >= self.date_to) or not contract.date_end:
                    days_out -= 1
            elif self.date_to.day == 28 and self.payroll_period_id.payroll_period == '04':
                days_out += 2
            elif self.date_to.day == 29 and self.payroll_period_id.payroll_period == '04':
                days_out += 1
            work100 = (work100 + days_out - holidays - personal_days) * days_factor
            work100_imss = work100_imss - inability - leave
            if contract.date_end and contract.date_end < self.date_from:
                work100 = 0
                work100_imss = 0
            if self.date_to < contract.date_start:
                work100 = 0
                work100_imss = 0
                
            for entry in entry_type_ids:
                if not entry.is_leave:
                    if entry.code == 'PERIODO100':
                        res.append({
                            'sequence': entry.sequence,
                            'work_entry_type_id': entry.id,
                            'number_of_days': days_factor_month,
                            'payslip_run_id': payslip_run_id,
                        })
                    if entry.code == 'FACTORDIA':
                        res.append({
                            'sequence': entry.sequence,
                            'work_entry_type_id': entry.id,
                            'number_of_days': days_period,
                            'number_of_hours': 0,
                            'payslip_run_id': payslip_run_id,
                        })
                    if entry.code == 'DIASIMSS':
                        res.append({
                            'sequence': entry.sequence,
                            'work_entry_type_id': entry.id,
                            'number_of_days': work100_imss,
                            'number_of_hours': 0,
                            'payslip_run_id': payslip_run_id,
                        })
                    if entry.code == 'DIASEMANA':
                        res.append({
                            'sequence': entry.sequence,
                            'work_entry_type_id': entry.id,
                            'number_of_days': len(count_days_week),
                            'number_of_hours': attendances_hours,
                            'payslip_run_id': payslip_run_id,
                        })
                    if entry.code == 'WORK1101':
                        res.append({
                            'sequence': entry.sequence,
                            'work_entry_type_id': entry.id,
                            'number_of_days': work100,
                            'number_of_hours': 0,
                            'payslip_run_id': payslip_run_id,
                        })
        return res
    
    def _get_new_input_line_ids(self):
        
        if self.struct_id.input_line_type_ids:
            payslip_run_id = False
            if self.env.context.get('payslip_run_id'):
                payslip_run_id = self.env.context['payslip_run_id']
            inputs = self.env['hr.inputs'].search([('employee_id','=',self.employee_id.id),
                                                     ('payroll_period_id','=',self.payroll_period_id.id),
                                                     ('state','=','approve'),
                                                     ('input_id','in',self.struct_id.input_line_type_ids.ids)])
            input_line_ids = self.input_line_ids.browse([])
            if inputs:
                for input in inputs:
                    val = {'name':input.input_id.name,
                            'code':input.input_id.code,
                            'amount':input.amount,
                            'input_type_id': input.input_id.id,
                            'payslip_id':self.id,
                            'payslip_run_id': payslip_run_id,
                            }
                    input_line_ids |= input_line_ids.new(val)
            
                return input_line_ids
            else:
                return [(5, False, False)]
    
    def compute_sheet(self):
        payslips = self.filtered(lambda slip: slip.state in ['draft', 'verify'])
        # delete old payslip lines
        payslips.line_ids.unlink()
        for payslip in payslips:
            try:
                vals = {}
                if not payslip.number:
                    number = payslip.number or self.env['ir.sequence'].next_by_code('salary.slip')
                    sequence = self.env['ir.sequence'].search([('code', '=', 'salary.slip')])
                    code_payslip = number.split('/')[0]
                    code = number.split('/')[1]
                    vals = {'number': number, 'code': code, 'code_payslip': code_payslip}
                
                
                if payslip.settlement and payslip.agreement_employee:
                    def get_rand_number(min_value, max_value):
                        """
                        This function gets a random number from a uniform distribution between
                        the two input values [min_value, max_value] inclusively
                        Args:
                        - min_value (float)
                        - max_value (float)
                        Return:
                        - Random number between this range (float)
                        """
                        range = max_value - min_value
                        choice = triangular(0, 1)
                        return min_value + range * choice

                    input_type_id = self.env['hr.payslip.input.type'].search([('code','in',['P037'])])
                    input_gratification_id = self.env['hr.payslip.input'].search([('input_type_id','=',input_type_id.id),('payslip_id','=',payslip.id)])
                    if not input_gratification_id:
                        input_gratification_id = self.env['hr.payslip.input'].create({'input_type_id':input_type_id.id,
                                                                                      'payslip_id':payslip.id,
                                                                                      'amount':0,
                                                                                      })
                    rule_total_id = payslip.struct_id.rule_ids.filtered(lambda r: r.category_id.code == 'NET').id
                    if not rule_total_id:
                        raise UserError(_('An entry must be configured in the salary structure for the concept of total with the code of its category "NET"!'))
                    def get_value_objetive(expected_value):
                        gratification = 0.0
                        total = 0.0
                        min_value = 0.0
                        max_value = expected_value*2
                        count = 0
                        cont = 0
                        aux = 0
                        res = []
                        while (abs(expected_value - total)) > 0.00000000001:
                            count+=1
                            gratification = float("{0:.4f}".format(get_rand_number(min_value, max_value)))
                            input_gratification_id.amount = gratification
                            res = payslip._get_payslip_lines()
                            total = float([line['total'] for line in res if line['salary_rule_id']==rule_total_id][0])
                            if (expected_value - total) < -0.00000000001:
                                max_value = gratification
                            if (expected_value - total) > 0.00000000001:
                                min_value = gratification
                            if gratification == aux:
                                cont += 1
                            aux = gratification
                            if cont == 4:
                                raise UserError(_('The amount of the agreement is less than the payroll result. Check the amount supplied.!'))
                        lines = [(0, 0, line) for line in payslip._get_payslip_lines()]
                        return lines
                    lines = get_value_objetive(payslip.amount_agreement)
                else:
                    lines = [(0, 0, line) for line in payslip._get_payslip_lines()]
                vals['line_ids'] = lines
                vals['state'] = 'verify'
                vals['compute_date'] = fields.Date.today()
                payslip.write(vals)
                self._cr.execute('''UPDATE hr_payslip SET calculated = True, computed_error = False, state = 'verify' WHERE id = %s''' % payslip.id)
            except Exception as e:
                payslip.payslip_error = '%s' % e
                payslip.computed_error = True
                pass
        return True

    def action_payslip_draft(self):
        if self.payslip_run_id.state == 'close' and self.settlement:
            raise UserError(_('You cannot open a payroll if the lot is closed.'))
        if self.invoice_status == 'right_bill' and self.settlement:
            raise UserError(_('You cannot open a payroll with a stamp.'))
        self.write({'state': 'draft','calculated': False})
        return 
    
    def _get_payslip_lines(self):
        self.ensure_one()
        localdict = self.env.context.get('force_payslip_localdict', None)
        payslip_run_id = self.env.context.get('payslip_run_id', None)
        if self.payslip_run_id:
            payslip_run_id = self.payslip_run_id.id
        if localdict is None:
            localdict = self._get_localdict()

        rules_dict = localdict['rules'].dict
        result_rules_dict = localdict['result_rules'].dict

        blacklisted_rule_ids = self.env.context.get('prevent_payslip_computation_line_ids', [])

        result = {}
        total_isn = 0
        for rule in sorted(self.struct_id.rule_ids, key=lambda x: x.sequence):
            if rule.id in blacklisted_rule_ids:
                continue
            localdict.update({
                'result': None,
                'result_qty': 1.0,
                'result_rate': 100,
                'pending_amount':0,
                'isn_amount':0,
                'tax_amount':0,
                'rule_id' : rule,
                'datas' : {},
                'days':0
                })
            if rule._satisfy_condition(localdict):
                amount, qty, rate, pending_amount, isn_amount, tax_amount, datas, days = rule._compute_rule(localdict)
                #check if there is already a rule computed with that code
                previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                #set/overwrite the amount computed for this rule in the localdict
                tot_rule = amount * qty * rate / 100.0
                localdict[rule.code] = tot_rule
                result_rules_dict[rule.code] = {'total': tot_rule, 'amount': amount, 'quantity': qty, 'pending_amount': pending_amount, 'isn_amount': isn_amount, 'tax_amount': tax_amount, 'days':days}
                rules_dict[rule.code] = rule
                # sum the amount for its salary category
                localdict = rule.category_id._sum_salary_rule_category(localdict, tot_rule - previous_amount, isn_amount, tax_amount)
                # Retrieve the line name in the employee's lang
                employee_lang = self.employee_id.sudo().address_home_id.lang
                # This actually has an impact, don   't remove this line
                context = {'lang': employee_lang}
                if rule.code in ['BASIC', 'GROSS', 'NET']:  # Generated by default_get (no xmlid)
                    if rule.code == 'BASIC':
                        rule_name = _('Basic Salary')
                    elif rule.code == "GROSS":
                        rule_name = _('Gross')
                    elif rule.code == 'NET':
                        rule_name = _('Net Salary')
                else:
                    rule_name = rule.with_context(lang=employee_lang).name
                # create/overwrite the rule in the temporary results
                result[rule.code] = {
                    'sequence': rule.sequence,
                    'code': rule.code,
                    'name': rule_name,
                    'note': rule.note,
                    'salary_rule_id': rule.id,
                    'contract_id': localdict['contract'].id,
                    'employee_id': localdict['employee'].id,
                    'amount': amount,
                    'quantity': qty,
                    'rate': rate,
                    'slip_id': self.id,
                    'payslip_run_id': payslip_run_id,
                    'pending_amount': pending_amount,
                    'isn_amount': isn_amount,
                    'tax_amount': tax_amount,
                    'datas': datas,
                    'days': days,
                    'total': float(qty) * amount * rate / 100,
                }
        return result.values()
    
    def action_payslip_cancel(self):
        if self.filtered(lambda slip: slip.state == 'done' and slip.invoice_status == 'right_bill'):
            raise UserError(_("Cannot cancel a payslip that is done."))
        self.write({'state': 'cancel'})
        self.env.cr.execute("""
                                DELETE FROM 
                                    input_with_share_line 
                                WHERE slip_id = %s
                            """, (self.id,))
        self.env.cr.execute("""
                                DELETE FROM 
                                    hr_payroll_pension_deductions 
                                WHERE slip_id = %s
                            """, (self.id,))
        self.env.cr.execute("""
                                DELETE FROM 
                                    hr_fonacot_credit_line_payslip 
                                WHERE slip_id = %s
                            """, (self.id,))
        if not self.settlement:
            self.env.cr.execute("""
                                    DELETE FROM 
                                        hr_provisions 
                                    WHERE payslip_run_id = %s AND contract_id = %s
                                """, (self.payslip_run_id.id, self.contract_id.id))
        return 
    
    
    def unlink(self):
        for payslip in self:
            if any(payslip.state not in ('draft', 'verify') for payslip in self):
                raise UserError(_('You cannot delete a payslip which is not draft or verify!'))
            if any(payslip.invoice_status in ('right_bill') for payslip in self):
                raise UserError(_('You cannot delete already stamped payroll!'))
            self.env.cr.execute("""
                                    DELETE FROM 
                                        input_with_share_line 
                                    WHERE slip_id = %s
                                """, (payslip.id,))
            self.env.cr.execute("""
                                    DELETE FROM 
                                        hr_payroll_pension_deductions 
                                    WHERE slip_id = %s
                                """, (payslip.id,))
            self.env.cr.execute("""
                                    DELETE FROM 
                                        hr_provisions 
                                    WHERE payslip_run_id = %s AND contract_id = %s
                                """, (payslip.payslip_run_id.id, payslip.contract_id.id))
            self.env.cr.execute("""
                                    DELETE FROM 
                                        hr_fonacot_credit_line_payslip 
                                    WHERE slip_id = %s
                                """, (payslip.id,))
        return super(HrPayslip, self).unlink()

    def _get_leaves(self, payslip_id=None):
        query = """
            SELECT 
                employee.id employee_id,
                COALESCE(SUM(work.number_of_days),0) number_of_days,
                CASE
                    WHEN entry.type_leave IS NULL THEN 'work' ELSE entry.type_leave
                END type_leave
            FROM hr_payslip_worked_days work
            JOIN hr_payslip slip ON work.payslip_id = slip.id
            JOIN hr_employee employee ON slip.employee_id = employee.id 
            JOIN hr_work_entry_type entry ON work.work_entry_type_id = entry.id
            WHERE 
                (entry.type_leave IS NOT NULL OR entry.code='WORK1101')
                AND work.payslip_id = %s
            GROUP BY entry.type_leave, employee.id;
        """
        params = (payslip_id,)
        self.env.cr.execute(query, params)
        results = self.env.cr.dictfetchall()
        leaves = {}
        for res in results:
            leaves.setdefault(payslip_id, {}).setdefault(res['type_leave'], res['number_of_days'])
        return leaves
    
    def to_json(self):
        def replace_caracters(car):
            changes = {
                'ñ': 'n',
                'Ñ': 'N',
                'á': 'a',
                'Á': 'A',
                'é': 'e',
                'É': 'E',
                'í': 'i',
                'Í': 'I',
                'ó': 'o',
                'Ó': 'O',
                'ú': 'u',
                'Ú': 'U',
                'ü': 'u',
                'Ü': 'U',
            }
            if changes.get(car.group(0)):
                return changes[car.group(0)]
            else:
                return car.group(0)

        self.env.cr.execute("""
                        SELECT 
                            slip.id                                     AS slip_id,
                            line.id                                     AS line_id, 
                            rule.type                                   AS type, 
                            rule.type_perception                        AS type_perception,                       
                            line.days                                   AS line_days,                       
                            rule.name                                   AS concept,                       
                            line.code                                   AS line_code, 
                            line.quantity                               AS quantity, 
                            line.total                                  AS total, 
                            category.code                               AS category_code,
                            rule.type_deduction                         AS type_deduction,
                            rule.sequence                               AS sequence,
                            line.tax_amount                             AS tax_amount,
                            rule.id                                     AS rule_id,
                            rule.type_overtime                          AS type_overtime,
                            rule.type_disability                        AS type_disability,
                            rule.type_other_payment                     AS type_other_payment
                        FROM hr_payslip_line line
                        JOIN hr_payslip slip ON line.slip_id = slip.id
                        JOIN hr_salary_rule_category category ON line.category_id = category.id
                        JOIN hr_salary_rule rule ON line.salary_rule_id = rule.id
                        WHERE slip.id = %s
                                """,
                    (self.id,))
        line_ids = self.env.cr.dictfetchall()
        perceptions_only = 0
        total_salaries = 0
        other_deduction = 0
        isr_deduction = 0
        discount_amount = 0
        other_payment_only = 0
        disability_amount = 0
        total_taxed = 0
        subsidy_caused = 0
        perceptions_only_indemnify = 0
        total_taxed_indemnify = 0
        perceptions_indemnify = self.env['hr.payslip.line']
        perceptions_list = []
        disability_list = []
        deduction_list = []
        other_list = []
        slip_id = self.id
        leaves_data = self._get_leaves(payslip_id=slip_id)
        subsidy_exists = False
        settlement = self.settlement and (self.indemnify_employee or self.seniority_premium or self.extra_gratification)
        for line in line_ids:
            if line['line_code'] == 'UI092':
                subsidy_caused += line['total']
            if line['category_code'] == 'PERC' and line['type'] == 'perception' and line['type_perception'] not in ['022','023','025','039','044']:
                perceptions_only += line['total']
                total_salaries += line['total']
                if line['total'] > 0:
                    perceptions_dict = {
                                'type': line['type_perception'],
                                'key': line['line_code'],
                                'days': line['line_days'] if line['line_days'] else '',
                                'sequence': line['sequence'],
                                'concept': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, line['concept']),
                                'quantity': line['quantity'],
                                'amount_g': float("{0:.2f}".format(line['tax_amount'])),
                                'amount_e': float("{0:.2f}".format(line['total'] - line['tax_amount'])),
                                'amount_t': float("{0:.2f}".format(line['total'])),
                            }
                    if line['type_perception'] == '019':
                        for input in self.input_line_ids:
                            if input.code == line['line_code']:
                                perceptions_dict['extra_hours'] = [{
                                                                'days': int(round(input.amount/3)),
                                                                'sequence': line['sequence'],
                                                                'type': line['type_overtime'],
                                                                'amount': float("{0:.2f}".format(line['tax_amount'])), 
                                                                'hours': int(input.amount),
                                                            }]
                    perceptions_list.append(perceptions_dict)
            if settlement and line['category_code'] == 'PERC' and line['type'] == 'perception' and line['type_perception'] in ['022','023','025']:
                l = self.env['hr.payslip.line'].browse(line['line_id'])
                perceptions_indemnify += l
                perceptions_only_indemnify += line['total']
                perceptions_only += line['total']
            if settlement and line['line_code'] in ['UI121']:
                total_taxed_indemnify += line['total']
            if line['category_code'] == 'DED' and line['type'] == 'deductions':
                discount_amount += line['total']
                if line['type_deduction'] != '002':
                    other_deduction += line['total']
                elif line['type_deduction'] == '002':
                    isr_deduction += line['total']
                if line['total'] > 0:
                    if line['type_deduction'] != '006':
                        deduction_dict = {
                                    'type': line['type_deduction'],
                                    'key': line['line_code'],
                                    'days': line['line_days'] if line['line_days'] else '',
                                    'sequence': line['sequence'],
                                    'concept': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, line['concept']),
                                    'amount': float("{0:.2f}".format(line['total'])),
                                }
                        deduction_list.append(deduction_dict)
                    else:
                        disability_amount += line['total']
                        disability_concept = line['line_code']
                    
                        if line['type_disability'] == '01':
                            disability = self.env['hr.payslip.worked_days'].search([('code','in',['F02']),('payslip_id','=',self.id)])
                        elif line['type_disability'] == '02':
                            disability = self.env['hr.payslip.worked_days'].search([('code','in',['F01']),('payslip_id','=',self.id)])
                        elif line['type_disability'] == '03':
                            disability = self.env['hr.payslip.worked_days'].search([('code','in',['F03']),('payslip_id','=',self.id)])
                        elif line['type_disability'] == '04':
                            disability = self.env['hr.payslip.worked_days'].search([('code','in',['F09']),('payslip_id','=',self.id)])
                        
                        disability_dict = {
                                    'days': int(disability.number_of_days),
                                    'sequence': line['sequence'],
                                    'type': line['type_disability'],
                                    'amount': float("{0:.2f}".format(line['total'])), 
                                }
                        disability_list.append(disability_dict)
            if line['category_code'] == 'PERC' and line['type'] == 'other_payment':
                other_payment_only += line['total']
                if line['total'] > 0:
                    other_dict = {
                                'type': line['type_other_payment'],
                                'key': line['line_code'],
                                'concept': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, line['concept']),
                                'amount': float("{0:.2f}".format(line['total'])), 
                            }
                    if line['type_other_payment'] == '002':
                        subsidy = self.env['hr.payslip.line'].search([('code','=','UI092'),('slip_id','=',self.id)])
                        subsidy_exists = True
                        other_dict['subsidy'] = float("{0:.2f}".format(subsidy.total))
                        other_dict['subsidy_boolean'] = True
                    other_list.append(other_dict)
                elif line['total'] == 0 and line['type_other_payment'] and self.contract_id.contracting_regime == '02' and line['type_other_payment'] == '002':
                    subsidy = self.env['hr.payslip.line'].search([('code','=','UI092'),('slip_id','=',self.id)])
                    subsidy_exists = True
                    other_dict = {
                                'type': line['type_other_payment'],
                                'key': line['line_code'],
                                'concept': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, line['concept']),
                                'amount': float("{0:.2f}".format(line['total'])), 
                                'subsidy': float("{0:.2f}".format(subsidy.total)), 
                                'subsidy_boolean': True, 
                            }
                    other_list.append(other_dict)
            if line['line_code'] in ['UI090']:
                total_taxed += line['total']
            
        if not subsidy_exists and self.contract_id.contracting_regime == '02':
            other_dict = {
                    'type': '002',
                    'key': 'P105',
                    'concept': 'SUBSIDIO PARA EL EMPLEO',
                    'amount': float("{0:.2f}".format(0.00)),
                    'subsidy': float("{0:.2f}".format(0.00)),
                    'subsidy_boolean': True,
                }
            other_list.append(other_dict)
        if settlement:
            total_taxed += total_taxed_indemnify
            exempt_compensation = perceptions_only_indemnify - total_taxed_indemnify
            acum = 0
            acum_total = 0
            cont = len(perceptions_indemnify.filtered(lambda p: p.total > 0))
            for p in perceptions_indemnify.filtered(lambda p: p.total > 0):
                if p.total > 0:
                    if cont == 1:
                        amount_e = exempt_compensation - acum
                    else:
                        amount_e = int(exempt_compensation * ((p.total*100)/perceptions_only_indemnify)/100)
                    acum += amount_e
                    amount_g = float("{0:.2f}".format(p.total - amount_e))
                    if total_taxed_indemnify == 0:
                        amount_e = float("{0:.2f}".format(p.total))
                        amount_g = float("{0:.2f}".format(0))
                    perceptions_dict= {
                                        'type': p.salary_rule_id.type_perception,
                                        'key': p.salary_rule_id.code,
                                        'concept': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, p.salary_rule_id.name),
                                        'quantity': p.quantity,
                                        'amount_g': float("{0:.2f}".format(amount_g)),
                                        'amount_e': float("{0:.2f}".format(amount_e)),
                                        'amount_t': float("{0:.2f}".format(p.total)),
                                        'days': float("{0:.2f}".format(p.days)) if p.days > 0 else '',
                                        'sequence': p.sequence,
                                    }
                    perceptions_list.append(perceptions_dict)
                cont -= 1
            gravado = float("{0:.2f}".format(total_taxed_indemnify - acum))
        
        perceptions_only = float("{0:.2f}".format(perceptions_only))
        total_salaries = float("{0:.2f}".format(total_salaries))
        other_deduction = float("{0:.2f}".format(other_deduction))
        isr_deduction = float("{0:.2f}".format(isr_deduction))
        discount_amount = float("{0:.2f}".format(discount_amount))
        other_payment_only = float("{0:.2f}".format(other_payment_only))
        subtotal = perceptions_only + other_payment_only
        total = float("{0:.2f}".format(subtotal - discount_amount))
        total_taxed_indemnify = float("{0:.2f}".format(total_taxed_indemnify))
        perceptions_only_indemnify = float("{0:.2f}".format(perceptions_only_indemnify))
        
        if disability_amount > 0:
            deduction_dict = {
                        'type': '006',
                        'key': disability_concept,
                        'concept': 'DESCUENTO POR INCAPACIDAD',
                        'amount': float("{0:.2f}".format(disability_amount)),
                    }
            deduction_list.append(deduction_dict)
        
        
        show_total_taxes_withheld = False
        if isr_deduction > 0:
            show_total_taxes_withheld = True
        
        days = sum(self.env['hr.payslip.worked_days'].search(['|',('work_entry_type_id.code','=','WORK1101'),('work_entry_type_id.type_leave','in',['holidays','personal_days']),('payslip_id','=',self.id)]).mapped('number_of_days'))
        days = "{0:.3f}".format(days)
        if days == '0.000':
            days = "{0:.3f}".format(1)
        date_start_contract = self.contract_id.previous_contract_date if self.contract_id.previous_contract_date else self.contract_id.date_start
        data = {
            'serie': self.code_payslip,
            'number': self.code,
            'date_invoice_tz': '',
            'payment_policy': self.way_pay,
            'certificate_number': '',
            'certificate': '',
            'subtotal': "{0:.2f}".format(subtotal),
            'discount_amount': discount_amount,
            'currency': 'MXN',
            'rate': '1',
            'amount_total': total,
            'document_type': self.type_voucher,
            'pay_method': self.payment_method,
            'pay_method_name': '%s - %s' % (self.payment_method, dict(self._fields['payment_method']._description_selection(self.env)).get(self.payment_method)),
            'emitter_zip': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.company_id.zip),
            'emitter_rfc': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.company_id.vat),
            'emitter_name': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.company_id.name),
            'emitter_fiscal_position_name': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, dict(self.company_id._fields['l10n_mx_edi_fiscal_regime']._description_selection(self.env)).get(self.company_id.l10n_mx_edi_fiscal_regime)),
            'emitter_fiscal_position': self.company_id.l10n_mx_edi_fiscal_regime,
            'receiver_rfc': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.employee_id.address_home_id.rfc.replace('-', '')),
            'receiver_name': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.employee_id.complete_name),
            'receiver_reg_trib': '',
            'receiver_use_cfdi': self.cfdi_use,
            'invoice_lines': [{
                'price_unit': "{0:.2f}".format(subtotal),
                'subtotal_wo_discount': "{0:.2f}".format(subtotal),
                'discount': discount_amount,
            }],
            'taxes': {
                'total_transferred': '0.00',
                'total_withhold': '0.00',
            },
            'payroll': {
                'receiver_use_cfdi_name': '%s - %s' % (self.cfdi_use, dict(self._fields['cfdi_use']._description_selection(self.env)).get(self.cfdi_use)),
                'payment_policy_name': '%s' % dict(self._fields['way_pay']._description_selection(self.env)).get(self.way_pay),
                'type_voucher': self.type_voucher,
                'type': self.payroll_type,
                'payment_date': self.payment_date,
                'date_from': self.date_from if self.date_from > date_start_contract else date_start_contract,
                'date_to': '',
                'number_of_days': days,
                'curp_emitter': '',
                'employer_register': '',
                'vat_emitter': '',
                'uuid_sat': '',
                'seniority_emp': '',
                'curp_emp': '',
                'nss_emp': '',
                'days_work': leaves_data.get(slip_id, {}).get('work', 0.00) + leaves_data.get(slip_id, {}).get('holidays', 0.0) + leaves_data.get(slip_id, {}).get('personal_days', 0.00),
                'holidays': leaves_data.get(slip_id, {}).get('holidays', 0.00),
                'inability': leaves_data.get(slip_id, {}).get('inability', 0.00),
                'leave': leaves_data.get(slip_id, {}).get('leave', 0.00),
                'total_perceptions': perceptions_only,
                'total_deductions': discount_amount,
                'total_other': other_payment_only,
                'emp_risk': '',
                'emp_syndicated': 'No',
                'working_day': self.employee_id.type_working_day,
                'working_day_name': dict(self.employee_id._fields['type_working_day']._description_selection(self.env)).get(self.employee_id.type_working_day) or '',
                'emp_regimen_type': self.contracting_regime,
                'emp_regimen_name': dict(self.contract_id._fields['contracting_regime']._description_selection(self.env)).get(self.contracting_regime).upper(),
                'contract_type': self.contract_id.contract_type,
                'no_emp': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.employee_id.registration_number),
                'emp_name': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.employee_id.complete_name),
                'departament': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.contract_id.department_id.name),
                'emp_job': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.contract_id.job_id.name),
                'emp_job_sat_code': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.contract_id.job_id.sat_code),
                'description_sat': 'Pago de Nomina',
                'unit_key_sat': 'ACT',
                'date_start_contract': date_start_contract,
                'payment_periodicity': '',
                'emp_bank': '',
                'emp_bank_name': self.contract_id.bank_account_id.bank_id.bic or '',
                'emp_account': '',
                'emp_base_salary': '',
                'emp_diary_salary': '',
                'emp_state': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.employee_id.address_id.state_id.code),
                'emp_state_name': re.sub(r"[ñÑáÁéÉíÍóÓúÚüÜ]", replace_caracters, self.employee_id.address_id.state_id.name),
                'total_salaries': float("{0:.2f}".format(total_salaries)),
                'total_compensation': float("{0:.2f}".format(perceptions_only_indemnify)),
                'total_retirement': 0,
                'total_taxed': float("{0:.2f}".format(total_taxed)),
                'total_exempt': float("{0:.2f}".format((total_salaries+perceptions_only_indemnify) - total_taxed)),
                'perceptions': list(perceptions_list),
                'total_other_deductions': other_deduction,
                'show_total_taxes_withheld': show_total_taxes_withheld,
                'total_taxes_withheld': isr_deduction,
                'deductions': list(deduction_list),
                'other_payments': list(other_list),
                'inabilities': disability_list,
                'subsidy_caused': subsidy_caused,
                'compensation_paid': perceptions_only_indemnify,
                'compensation_years': self.contract_id[0].years_antiquity,
                'compensation_last_salary': self.contract_id.wage,
                'compensation': True if perceptions_only_indemnify > 0 else False,
                'currency': self.env.company.currency_id,
                'qr_timbre': '',
                'stamp_sat': '',
                'stamp_cfd': '',
                'original_string': '',
                'date_stamped': '',
                'cfdi_issue_date': '',
                'certificate_number': '',
                'certificate_number_emisor': '',
            },
        }
        if settlement:
            if perceptions_only_indemnify > self.contract_id.wage:
                compensation_cumulative = self.contract_id.wage
            else:
                compensation_cumulative = perceptions_only_indemnify
            
            if perceptions_only_indemnify - self.contract_id.wage > 0:
                data['payroll']['compensation_no_cumulative'] = float("{0:.2f}".format(perceptions_only_indemnify - self.contract_id.wage))
            else:
                data['payroll']['compensation_no_cumulative'] = 0
                
            data['payroll']['compensation_cumulative'] = float("{0:.2f}".format(compensation_cumulative))
        
        if self.contract_id.bank_account_id.bank_account:
            data['payroll']['emp_account'] = self.contract_id.bank_account_id.bank_account
            if len(self.contract_id.bank_account_id.bank_account) != 18:
                data['payroll']['emp_bank'] = self.contract_id.bank_account_id.bank_id.l10n_mx_edi_code
        if self.employee_id.deceased:
            data['receiver_rfc'] = 'XAXX010101000'
        if self.company_id.l10n_mx_edi_pac_test_env_payroll and self.company_id.l10n_mx_edi_pac_payrol == 'forsedi':
            data['receiver_rfc'] = 'TUCA5703119R5'
        if self.company_id.l10n_mx_edi_pac_test_env_payroll and self.company_id.l10n_mx_edi_pac_payrol == 'sefactura':
            data['emitter_rfc'] = 'EWE1709045U0'
        
        if self.payroll_type == 'E':
            if self.settlement:
                data['payroll']['date_to'] = self.date_to
                data['payroll']['type'] = 'O'
            else:
                data['payroll']['date_to'] = self.date_from if self.date_from > date_start_contract else date_start_contract
        else:
            data['payroll']['date_to'] = self.date_to
        if self.contract_id.contract_type in ['01','02','03','04','05','06','07','08']:
            data['payroll']['employer_register']= self.employee_id.employer_register_id.employer_registry
            if self.contract_id.contracting_regime == '02':
                data['payroll']['nss_emp'] = self.employee_id.ssnid.replace('-', '')
                data['payroll']['emp_risk'] = self.employee_id.employer_register_id.job_risk
                data['payroll']['date_start'] = date_start_contract
                data['payroll']['daily_salary'] = "{0:.2f}".format(self.contract_id.daily_salary)
                data['payroll']['emp_diary_salary'] = "{0:.2f}".format(self.contract_id.sdi)
                if self.employee_id.syndicalist:
                    data['payroll']['emp_syndicated'] = 'Sí'
                date_1 = date_start_contract
                date_2 = self.date_to if self.struct_id.payroll_type == 'O' else date_1
                
                week = (int(abs(date_1 - date_2).days))/7
                antiquity_date = rdelta.relativedelta(date_2,date_1)
                antiquity = 'P'+str(int(week))+'W'
                data['payroll']['seniority_emp'] = antiquity
        if not self.employee_id.address_home_id.curp:
            if self.employee_id.gender == 'male':
                data['payroll']['curp_emp'] = 'XEXX010101HNEXXXA4'
            else:
                data['payroll']['curp_emp'] = 'XEXX010101MNEXXXA8'
        else:
            data['payroll']['curp_emp'] = self.employee_id.address_home_id.curp
        if self.payroll_type == 'O':
            data['payroll']['payment_periodicity'] = self.payroll_period
        else:
            if self.settlement:
                data['payroll']['payment_periodicity'] = self.payroll_period
            else:
                data['payroll']['payment_periodicity'] = '99'
        return data    
    
    
    def get_folder(self):
        name_folder = str(self.payslip_run_id.id)+'-'+str(self.struct_id.name)        
        folder_id = self.env['documents.folder'].search([('parent_folder_id','=',self.payroll_period_id.folder_id.id),('name','=',name_folder)])
        if not folder_id:
            folder_id = self.env['documents.folder'].create({
                                                            'name':name_folder,
                                                            'parent_folder_id':self.payroll_period_id.folder_id.id,
                                                            'company_id':self.company_id.id,
                                                            })
        return folder_id.id
                                    
    def test_pdf(self):
        values = self.to_json()
        return self.env.ref('hr_payroll_mexico.action_report_payslips').sudo().report_action(self, data=values)

    def action_cfdi_nomina_generate(self):
        for slip in self:
            try:
                if not slip.payslip_run_id and slip.settlement:
                    raise UserError(_('In order to stamp the settlement, it must be associated with a batch of'))
                if slip.payslip_run_id.state != 'close' and slip.settlement:
                    raise UserError(_('The payroll lot must be closed'))
                if slip.invoice_status != 'right_bill':
                    tz = pytz.timezone(self.env.user.partner_id.tz)
                    values = slip.to_json()
                    certificate = slip.company_id.l10n_mx_edi_certificate_payroll_ids.sudo().get_valid_certificate()
                    content = certificate.content
                    key = certificate.key
                    password_key = certificate.password
                    if not certificate:
                        raise UserError(_('No valid certificate found'))
                    if slip.company_id.l10n_mx_edi_pac_test_env_payroll and slip.company_id.l10n_mx_edi_pac_payrol == 'forsedi':
                        url = 'http://dev33.facturacfdi.mx/WSTimbradoCFDIService?wsdl'
                        username = 'pruebasWS'
                        password = 'pruebasWS'
                    elif slip.company_id.l10n_mx_edi_pac_test_env_payroll and slip.company_id.l10n_mx_edi_pac_payrol == 'sefactura':
                        url = 'http://pruebas.sefactura.com.mx:3014/sefacturapac/TimbradoService?wsdl'
                        username = 'Aeromar'
                        password = 'Aeromar'
                    elif slip.company_id.l10n_mx_edi_pac_payrol == 'forsedi':
                        url = 'https://v33.facturacfdi.mx/WSTimbradoCFDIService?wsdl'
                        username = slip.company_id.l10n_mx_edi_pac_username
                        password = slip.company_id.l10n_mx_edi_pac_password
                    elif slip.company_id.l10n_mx_edi_pac_payrol == 'sefactura':
                        url = 'https://www.sefactura.com.mx/sefacturapac/TimbradoService?wsdl'
                        username = slip.company_id.l10n_mx_edi_pac_username
                        password = slip.company_id.l10n_mx_edi_pac_password

                    payroll = cfdv33.get_payroll(values, certificado=content, llave_privada=key,
                                                                        password=password_key, tz=tz, url=url, user=username, password_pac = password,  
                                                                        debug_mode=True, pac=slip.company_id.l10n_mx_edi_pac_payrol)
                    if not payroll.error_timbrado:
                        NSMAP = {
                             'xsi':'http://www.w3.org/2001/XMLSchema-instance',
                             'cfdi':'http://www.sat.gob.mx/cfd/3', 
                             'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
                             }
                        file=payroll.document_path.read()
                        document = ET.fromstring(file)
                        Complemento = document.find('cfdi:Complemento', NSMAP)
                        TimbreFiscalDigital = Complemento.find('tfd:TimbreFiscalDigital', NSMAP)
                        folder_id = slip.get_folder()
                        xml = base64.b64encode(file)
                        ir_attachment=self.env['ir.attachment']
                        document_obj=self.env['documents.document']
                        value={u'name': str(slip.employee_id.complete_name)+'_'+str(slip.date_from)+'_'+str(slip.date_to), 
                                            u'url': False,
                                            u'company_id': slip.company_id.id, 
                                            u'folder_id': folder_id, 
                                            u'name': str(slip.employee_id.complete_name)+'_'+str(slip.date_from)+'_'+str(slip.date_to)+'.xml', 
                                            u'type': u'binary', 
                                            u'public': False, 
                                            u'datas':xml , 
                                            u'description': False}
                        xml_timbre = ir_attachment.create(value)
                        document_obj.create({
                                    'attachment_id':xml_timbre.id,
                                    'name':str(slip.employee_id.complete_name)+'_'+str(slip.date_from)+'_'+str(slip.date_to),
                                    'type': u'binary', 
                                        })
                        url_qr ='https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?&id=%s&re=%s&rr=%s&tt=%s&fe=%s' % (TimbreFiscalDigital.attrib['UUID'],values['emitter_rfc'],values['receiver_rfc'],values['amount_total'],TimbreFiscalDigital.attrib['SelloCFD'][-8:])
                        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=20, border=4)
                        qr.add_data(url_qr)
                        qr.make(fit=True)
                        img = qr.make_image()
                        buffer = BytesIO()
                        img.save(buffer, format="PNG")
                        date_stamped = datetime.strptime(TimbreFiscalDigital.attrib['FechaTimbrado'], '%Y-%m-%dT%H:%M:%S')
                        date_stamped = date_stamped.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)
                        cfdi_issue_date = datetime.strptime(payroll.date_timbre, '%Y-%m-%dT%H:%M:%S')
                        cfdi_issue_date = cfdi_issue_date.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)
                        img_str = base64.b64encode(buffer.getvalue())
                        values['payroll']['uuid_sat'] = TimbreFiscalDigital.attrib['UUID']
                        values['payroll']['qr_timbre'] = img_str
                        values['payroll']['stamp_sat'] = TimbreFiscalDigital.attrib['SelloSAT']
                        values['payroll']['stamp_cfd'] = TimbreFiscalDigital.attrib['SelloCFD']
                        values['payroll']['original_string'] = payroll.cadena_original
                        values['payroll']['date_stamped'] = fields.Datetime.from_string(date_stamped)
                        values['payroll']['cfdi_issue_date'] = fields.Datetime.from_string(cfdi_issue_date)
                        values['payroll']['certificate_number_emisor'] = document.attrib['NoCertificado']
                        values['payroll']['certificate_number'] = TimbreFiscalDigital.attrib['NoCertificadoSAT']
                        # Create PDF CFDI
                        pdf_content, content_type = self.env.ref('hr_payroll_mexico.action_report_payslips').sudo()._render_qweb_pdf(slip.ids[0], data=values)
                        pdf_name = safe_eval(slip.struct_id.report_id.print_report_name, {'object': slip}) or _("Payslip")
                        # Sudo to allow payroll managers to create document.document without access to the
                        # application
                        attachment = self.env['ir.attachment'].sudo().create({
                            'name': pdf_name,
                            'type': 'binary',
                            'datas': base64.encodebytes(pdf_content),
                            'res_model': slip._name,
                            'res_id': slip.id
                        })

                        vals = {
                             'invoice_date':TimbreFiscalDigital.attrib['FechaTimbrado'],
                             'certificate_number':TimbreFiscalDigital.attrib['NoCertificadoSAT'],
                             'certificate_number_emisor':document.attrib['NoCertificado'],
                             'stamp_cfd':TimbreFiscalDigital.attrib['SelloCFD'],
                             'stamp_sat':TimbreFiscalDigital.attrib['SelloSAT'],
                             'original_string':payroll.cadena_original,
                             'cfdi_issue_date':payroll.date_timbre,
                             'uuid_sat':TimbreFiscalDigital.attrib['UUID'],
                             'xml_timbre':xml_timbre.id,
                             'qr_timbre':img_str,
                             'pdf': attachment.id,
                             'amount_total': values['amount_total'],
                             'invoice_status':'right_bill',
                             'payslip_id':slip.id
                            }
                        cfdi_id = self.env['hr.payslip.cfdi'].create(vals)
                        self._cr.execute('''UPDATE hr_payslip_worked_days SET timbre = True WHERE payslip_id = %s''' % (slip.id,))
                        self._cr.execute('''UPDATE hr_payslip_input SET timbre = True WHERE payslip_id = %s''' % (slip.id,))
                        self._cr.execute('''UPDATE hr_payslip_line SET timbre = True WHERE slip_id = %s''' % (slip.id,))
                        self._cr.execute('''UPDATE input_with_share_line SET timbre = True WHERE slip_id = %s''' % (slip.id,))
                        self._cr.execute('''UPDATE hr_payroll_pension_deductions SET timbre = True WHERE slip_id = %s''' % (slip.id,))
                        self._cr.execute('''UPDATE hr_fonacot_credit_line_payslip SET timbre = True WHERE slip_id = %s''' % (slip.id,))
                        self._cr.execute('''UPDATE hr_provisions SET timbre = True WHERE payslip_run_id = %s AND contract_id = %s''' % (slip.payslip_run_id.id,slip.contract_id.id))
                        self._cr.execute('''UPDATE hr_payslip SET code_error = '',  error = '', cfdi_id = %s, invoice_status = 'right_bill' WHERE id = %s''' % (cfdi_id.id,slip.id,))
                    else:
                        vals = {
                             'invoice_status':'invoice_problems',
                              'code_error':payroll.error_timbrado['codigoError'],
                             'error':payroll.error_timbrado['error'],
                            }
                        slip.write(vals)
            except Exception as e:
                slip.error = '%s' % e
                slip.invoice_status = 'invoice_problems'
                pass
        return

    
    def action_payslip_done(self):
        if self.settlement:
            val = {
                'contract_id':self.contract_id.id,
                'employee_id':self.employee_id.id,
                'type':'02',
                'date': self.contract_id.date_end,
                'wage':self.contract_id.wage,
                'salary':self.contract_id.sdi,
                'sbc':self.contract_id.sbc,
                'reason_liquidation':self.reason_liquidation,
                }
            if not self.movements_id:
                movements_id = self.env['hr.employee.affiliate.movements'].create(val)
                self.movements_id = movements_id.id
            else:
                self.movements_id.write(val)
            self.state = 'done'
            self.contract_id.state = 'close'
            self.employee_id.position_id.employee_id = False
            self.employee_id.position_id.change_employees(date_end=self.contract_id.date_end)
    
    def run_example(self):
        prueba = self.contract_id.get_leaves_last_year(self)
        print(prueba)
        print(prueba)
        print(prueba)
        print(prueba)


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'
    
    type_leave = fields.Selection([
        ('leave', 'Leave'),
        ('holidays', 'Holidays'),
        ('personal_days', 'Personal Days'),
        ('inability', 'Inability')
        ], string='Type of leave')
        
        
class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batches')
    timbre = fields.Boolean('Timbre?', default=False)
    pending_amount = fields.Float(string='Pending amount')
    isn_amount = fields.Float(string='Isn')
    tax_amount = fields.Float(string='Taxable')
    datas = fields.Text(string='Datas')
    days = fields.Float(string='Days')


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batches')
    timbre = fields.Boolean('Timbre?', default=False)


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'
    
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batches')
    timbre = fields.Boolean('Timbre?', default=False)


class HrPayslipCfdi(models.Model):
    _name = 'hr.payslip.cfdi'
    
    
    payslip_id = fields.Many2one('hr.payslip', string='Payslip')
    invoice_status = fields.Selection([
        ('invoice_not_generated', 'Invoice not Generated'),
        ('right_bill', 'Right bill'),
        ('invoice_problems', 'Problems with the invoice'),
        ('problems_canceled', 'Canceled bill'),
    ], string='Invoice Status', default="invoice_not_generated", required=False, readonly=True, tracking=True)
    uuid_sat = fields.Char(string='UUID', readonly=True)
    
    certificate_number = fields.Char(string='SAT CSD Serial Number', readonly=True)
    certificate_number_emisor = fields.Char(string="Issuer's CSD Serial Number", readonly=True)
    
    stamp_cfd = fields.Text(string='Sello CDF',readonly=False)
    stamp_sat = fields.Text(string='Sello SAT', readonly=False)
    
    original_string = fields.Text(string='Cadena Original', readonly=False)
    
    cfdi_issue_date = fields.Char(string='Date of issue', readonly=True)
    invoice_date = fields.Char(string='', readonly=True)
        
    qr_timbre = fields.Binary(string="Qr", readonly=True)
    xml_timbre = fields.Many2one('ir.attachment', string="Timbre (XML)", readonly=True)
    pdf = fields.Many2one('ir.attachment', string="PDF", copy=False, readonly=False)
    
    amount_total = fields.Float(string='Amount Total')
    
    xml_cancel_cfdi = fields.Many2one('ir.attachment', string="XML Cancel CFDI", copy=False, readonly=True)
    
    def action_cfdi_nomina_cancel(self):
        for cfdi in self:
            if cfdi.invoice_status == 'right_bill':
                payslip = cfdi.payslip_id
                tz = pytz.timezone(self.env.user.partner_id.tz)
                certificate = payslip.company_id.l10n_mx_edi_certificate_payroll_ids.sudo().get_valid_certificate()
                content = certificate.content
                key = certificate.key
                password_key = certificate.password
                
                if not certificate:
                    raise UserError(_('No valid certificate found'))
                
                if payslip.company_id.l10n_mx_edi_pac_test_env_payroll and payslip.company_id.l10n_mx_edi_pac_payrol == 'forsedi':
                    url = 'http://dev33.facturacfdi.mx/WSCancelacionService?wsdl'
                    username = 'pruebasWS'
                    password = 'pruebasWS'
                elif payslip.company_id.l10n_mx_edi_pac_payrol == 'forsedi':
                    url = 'https://v33.facturacfdi.mx/WSCancelacionService?wsdl'
                    username = payslip.company_id.l10n_mx_edi_pac_username
                    password = payslip.company_id.l10n_mx_edi_pac_password
                date =  datetime.now()
                UTC = pytz.timezone ("UTC") 
                UTC_date = UTC.localize(date, is_dst=None) 
                date_timbre = UTC_date.astimezone (tz)
                date_timbre = str(date_timbre.isoformat())[:19]
                cliente = zeep.Client(wsdl =url)
                total = cfdi.amount_total
                consult = cliente.service.ConsultarEstatusCFDI_2(
                                                        rfcEmisor=str(payslip.company_id.vat),
                                                        rfcReceptor=str(payslip.employee_id.address_home_id.rfc.replace('-', '')),
                                                        totalCFDI = str(total),
                                                        uuid = str(cfdi.uuid_sat),
                                                        selloCFDI = str(cfdi.stamp_cfd),
                                                        accesos={'password':password,'usuario':username},
                                                        )
                if consult['codigoEstatus'] == 'S - Comprobante obtenido satisfactoriamente.':
                    cfdi_cancel = cliente.service.Cancelacion_1(
                                                        folios=[cfdi.uuid_sat],
                                                        fecha=str(date_timbre),
                                                        rfcEmisor=str(payslip.company_id.vat),
                                                        publicKey=base64.decodebytes(content),
                                                        privateKey=base64.decodebytes(key),
                                                        password=str(password_key),
                                                        accesos={'password':password,'usuario':username},
                                                        )
                    if cfdi_cancel['folios'] and cfdi_cancel['folios']['folio'][0]['estatusUUID'] in ['201']:
                        if not payslip.company_id.l10n_mx_edi_pac_test_env_payroll:
                            document = ET.XML(cfdi_cancel['acuse'].encode('utf-8'))
                            document = ET.tostring(document, pretty_print=True, xml_declaration=True, encoding='utf-8')
                            cached = BytesIO()
                            cached.write(document is not None and document or u'')
                            cached.seek(0)
                            file=cached.read()
                            xml = base64.b64encode(file)
                            ir_attachment=self.env['ir.attachment']
                            folder_id = payslip.get_folder()
                            value={u'name': 'Cancelación_'+str(payslip.employee_id.complete_name)+'_'+str(payslip.date_from)+'_'+str(payslip.date_to), 
                                    u'url': False,
                                    u'company_id': payslip.company_id.id, 
                                    u'folder_id': folder_id, 
                                    u'datas_fname': 'Cancelación_'+str(payslip.employee_id.complete_name)+'_'+str(payslip.date_from)+'_'+str(payslip.date_to)+'.xml', 
                                    u'type': u'binary', 
                                    u'public': False, 
                                    u'datas':xml , 
                                    u'description': False}
                            xml_timbre_cancel = ir_attachment.create(value)
                            cfdi.xml_cancel_cfdi = xml_timbre_cancel.id
                            cfdi.invoice_status = 'problems_canceled'
                            self._cr.execute('''UPDATE hr_payslip_worked_days SET timbre = True WHERE payslip_id = %s''' % (payslip.id,))
                            self._cr.execute('''UPDATE hr_payslip_input SET timbre = True WHERE payslip_id = %s''' % (payslip.id,))
                            self._cr.execute('''UPDATE hr_payslip_line SET timbre = True WHERE slip_id = %s''' % (payslip.id,))
                            self._cr.execute('''UPDATE input_with_share_line SET timbre = True WHERE slip_id = %s''' % (payslip.id,))
                            self._cr.execute('''UPDATE hr_payroll_pension_deductions SET timbre = True WHERE slip_id = %s''' % (payslip.id,))
                            self._cr.execute('''UPDATE hr_fonacot_credit_line_payslip SET timbre = True WHERE slip_id = %s''' % (payslip.id,))
                            self._cr.execute('''UPDATE hr_provisions SET timbre = True WHERE payslip_run_id = %s AND contract_id = %s''' % (payslip.payslip_run_id.id,payslip.contract_id.id))
                            self._cr.execute('''UPDATE hr_payslip SET invoice_status = 'problems_canceled' WHERE id = %s''' % (payslip.id,))
                        else:
                            raise UserError(_('%s - %s') % (cfdi_cancel['codEstatus'], cfdi_cancel['mensaje']))
                    elif cfdi_cancel['folios'] and cfdi_cancel['folios']['folio'][0]['estatusUUID'] in ['202']:
                        raise UserError(_('%s - %s') % (cfdi_cancel['codEstatus'], cfdi_cancel['mensaje']))
                    else:
                        raise UserError(_('%s - %s') % (cfdi_cancel['codEstatus'], cfdi_cancel['mensaje']))
                else:
                    raise UserError(_('%s - %s') % (consult['codigoEstatus'], consult['estado']))
