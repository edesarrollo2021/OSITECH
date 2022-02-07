# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, modules, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'
    _order = 'create_date desc'

    payroll_period_id = fields.Many2one('hr.payroll.period', 'Payroll Period', required=True)
    structure_id = fields.Many2one('hr.payroll.structure', 'Structure', required=False)
    year = fields.Integer(string='Year', related="payroll_period_id.year")
    month = fields.Selection(related="payroll_period_id.month")
    payroll_period = fields.Selection(related="payroll_period_id.payroll_period")
    date_start = fields.Date(related="payroll_period_id.date_start")
    date_end = fields.Date(related="payroll_period_id.date_end")
    payment_date = fields.Date(string="Payment Date")
    
    payslips_total = fields.Integer('Payslips Total', compute='compute_progress_compute', copy=False)
    payslips_computed = fields.Integer('Payslips computed', compute='compute_progress_compute', copy=False)
    progress_compute = fields.Float('% Payslips processed', compute='compute_progress_compute', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Verify'),
        ('cancel', 'Cancel'),
        ('close', 'Done'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft')
    posted_payroll = fields.Boolean('posted payroll')
    
    cfdi_total = fields.Integer('Payslips Total', compute='compute_progress_cfdi_compute', copy=False)
    cfdi_computed = fields.Integer('Payslips computed', compute='compute_progress_cfdi_compute', copy=False)
    cfdi_compute = fields.Float('% Payslips processed', compute='compute_progress_cfdi_compute', copy=False)
    
    cfdi_error_count = fields.Float('CFDI Error', compute='compute_progress_cfdi_compute', copy=False)
    
    type = fields.Selection([
        ('ordinary', 'Ordinary'),
        ('settlement', 'Settlement'),
        ('special', 'Special'),
    ], string="Type", related="payroll_period_id.type")
    
    year_ptu = fields.Integer(string='PTU Year')
    ptu_payslip = fields.Boolean(string='PTU Payslip', related="structure_id.ptu_payslip")
    
    annual_adjustment = fields.Boolean('Apply Annual isr Adjustment')
    adjustment_id = fields.Many2one("annual.isr.adjustment", string="ISR adjustment")
    
    @api.constrains('payroll_period_id', 'structure_id')
    def _check_payroll_period_id(self):
        for run in self:
            if run.type == 'settlement' and not run.structure_id.settlement:
                raise ValidationError(_('You must select a settlement structure for a settlement period.'))
    
    def compute_progress_compute(self):
        if not self.slip_ids:
            self.payslips_total = 0
            self.payslips_computed = 0
            self.progress_compute = 0
        else:
            self.payslips_total = len(self.slip_ids)
            self._cr.execute('''select count(payslip.id) from hr_payslip as payslip where  payslip.payslip_run_id = %d and payslip.calculated=True
            ''' % self.id)
            res = self._cr.fetchone()[0]
            self.payslips_computed = res
            self.progress_compute = float(self.payslips_computed/self.payslips_total)*100
        return 
        
    def compute_progress_cfdi_compute(self):
        if not self.slip_ids:
            self.cfdi_total = 0
            self.cfdi_computed = 0
            self.cfdi_compute = 0
            self.cfdi_error_count = 0
        else:
            self._cr.execute('''select count(payslip.id) from hr_payslip as payslip where  payslip.payslip_run_id = %d and payslip.calculated=True and payslip.state = 'done' and payslip.contracting_regime not in ('05')
            ''' % self.id)
            res = self._cr.fetchone()[0]
            self.cfdi_total = res
            self._cr.execute('''select count(payslip.id) from hr_payslip as payslip where  payslip.payslip_run_id = %d and payslip.invoice_status = 'right_bill'
            ''' % self.id)
            res = self._cr.fetchone()[0]
            self.cfdi_computed = res
            self.cfdi_compute = float(self.cfdi_computed/self.cfdi_total if self.cfdi_total > 0 else 1)*100
            self._cr.execute('''select count(payslip.id) from hr_payslip as payslip where  payslip.payslip_run_id = %d and payslip.invoice_status = 'invoice_problems'
            ''' % self.id)
            res = self._cr.fetchone()[0]
            self.cfdi_error_count = res
        return 
            
    def compute_payslips(self):
        return 
    
    def recalculate_payslip_run(self, options):
        if not options.get('first') and options.get('type') == 'button':
            slip_ids = self.slip_ids.filtered(lambda o: o.invoice_status not in ['right_bill'])
            self._cr.execute('''DELETE FROM hr_payslip_worked_days WHERE  payslip_run_id = %s AND timbre != True''' % self.id)
            self._cr.execute('''DELETE FROM hr_payslip_line where  payslip_run_id = %s AND timbre != True''' % self.id)
            self._cr.execute('''DELETE FROM hr_payslip_input WHERE  payslip_run_id = %s AND timbre != True''' % self.id)
            self.env.cr.execute("""DELETE FROM input_with_share_line WHERE payslip_run_id = %s AND timbre != True""" % self.id)
            self.env.cr.execute("""DELETE FROM hr_payroll_pension_deductions WHERE payslip_run_id = %s AND timbre != True""" % self.id)
            self.env.cr.execute("""DELETE FROM hr_provisions WHERE payslip_run_id = %s AND timbre != True""" % self.id)
            self.env.cr.execute("""DELETE FROM hr_fonacot_credit_line_payslip WHERE payslip_run_id = %s AND timbre != True""" % self.id)
            self._cr.execute('''UPDATE hr_payslip SET calculated = False, computed_error = False WHERE payslip_run_id = %s AND invoice_status != 'right_bill' ''' % self.id)
            for payslip in slip_ids:
                payslip.with_context(payslip_run_id=self.id)._onchange_employee()
        payslips = self.env['hr.payslip'].search([
            ('payslip_run_id', 'in', self.ids),
            ('calculated', '=', False),
            ('computed_error', '=', False),
            ('state', 'in', ['draft', 'verify']),
            ('invoice_status', 'not in', ['right_bill'])
        ], limit=options.get('limit'))
        payslips.with_context(payslip_run_id=self.id).compute_sheet()
        self.state = 'verify'

        return {
            'ids': payslips.ids,
            'messages': [],
            'continues': 0 if not payslips else 1,
        }
    
    def action_calcel(self):
        slip_ids = self.mapped('slip_ids').filtered(lambda slip: slip.invoice_status == 'right_bill')
        if slip_ids:
            raise ValidationError(_("You cannot cancel a batch with stamped payroll."))
        self.env.cr.execute("""DELETE FROM input_with_share_line WHERE payslip_run_id = %s AND timbre != True""" % self.id)
        self.env.cr.execute("""DELETE FROM hr_payroll_pension_deductions WHERE payslip_run_id = %s AND timbre != True""" % self.id)
        self.env.cr.execute("""DELETE FROM hr_provisions WHERE payslip_run_id = %s AND timbre != True""" % self.id)
        self.env.cr.execute("""DELETE FROM hr_fonacot_credit_line_payslip WHERE payslip_run_id = %s AND timbre != True""" % self.id)
        self._cr.execute('''UPDATE hr_payslip SET state = 'cancel', calculated = False WHERE payslip_run_id = %s AND invoice_status != 'right_bill' ''' % self.id)
        self.state = 'cancel'
        return 
    
    def action_verify(self):
        if self.posted_payroll:
            raise ValidationError(_("You cannot open an already posted batch.."))
        self._cr.execute('''UPDATE hr_payslip SET state = 'verify' WHERE payslip_run_id = %s AND invoice_status != 'right_bill' ''' % self.id)
        self.state = 'verify'
        return 
        
    def action_verify_settlement(self):
        self.state = 'verify'
        return 
    
    def action_validate(self):
        self._cr.execute('''UPDATE hr_payslip SET state = 'done', invoice_status = 'invoice_not_generated' WHERE payslip_run_id = %s AND invoice_status != 'right_bill' and state in ('draft','verify') ''' % self.id)
        self.state = 'close'
        return 

    def generate_cfdi_lots(self, options):
        slip_ids = self.env['hr.payslip'].search([
            ('invoice_status', 'in', ['invoice_not_generated']),
            ('state', '=', 'done'),
            ('payslip_run_id', '=', self.id),
            ('contracting_regime', '!=', '05'),
        ], limit=options.get('limit'))
        slip_ids.action_cfdi_nomina_generate()
        return {
            'ids': slip_ids.ids,
            'messages': [],
            'continues': 0 if not slip_ids else 1,
        }
    
    def action_open_payslips_cfdi_error(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip",
            'view_mode': 'form',
            'views': [(False, 'tree'),(False, 'form')],
            "domain": [['id', 'in', self.slip_ids.ids],['invoice_status', '=', 'invoice_problems']],
            "name": "Payslips",
            "context": {'group_by':'error'},
        }
