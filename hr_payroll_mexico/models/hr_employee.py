# -*- coding: utf-8 -*-

from datetime import date, datetime, timedelta, time
from dateutil.relativedelta import relativedelta

from collections import defaultdict
from odoo import api, fields, models, _
from odoo.addons.resource.models.resource import datetime_to_string, string_to_datetime, Intervals
import pytz


class Employee(models.Model):
    _inherit = 'hr.employee'
    
    
    def calculate_alimony(self, gross, isr, imss, payslip):
        print (payslip)
        print (payslip)
        print (payslip)
        print (payslip)
        print (payslip)
        print (payslip.id)
        self.env.cr.execute("""
                                DELETE FROM 
                                    hr_payroll_pension_deductions 
                                WHERE slip_id = %s
                            """, (payslip.id,))
        alimony_amount_total = 0
        for alimony in self.alimony_ids:
            alimony_amount = 0
            if alimony.state == 'active':
                if alimony.type == 'gross-isr-imss':
                    alimony_amount = ((gross+isr+imss)*alimony.amount)/100
                elif alimony.type == 'gross':
                    alimony_amount = (gross*alimony.amount)/100
                else:
                    alimony_amount = alimony.amount
                    
                vals = {'slip_id':payslip.id,'alimony_id':alimony.id,'amount':alimony_amount,'timbre':False}
                if payslip.payslip_run_id:
                    vals['payslip_run_id'] = payslip.payslip_run_id.id
                self.env['hr.payroll.pension.deductions'].create(vals)
                alimony_amount_total += alimony_amount
        return alimony_amount_total


class HrPayrollPensionDeductions(models.Model):
    _name = "hr.payroll.pension.deductions"

    slip_id = fields.Many2one("hr.payslip", string="Paylsip", required=True)
    alimony_id = fields.Many2one("hr.alimony", string="Alimony", required=True)
    amount = fields.Float(string="Amount", required=True)
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip')
    timbre = fields.Boolean(string="Timbrado?", dafault=False)
   


