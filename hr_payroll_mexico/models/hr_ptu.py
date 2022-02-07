# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrPTU(models.Model):
    _name = 'hr.ptu'
    _description = 'PTU Annual'

    name = fields.Integer(string='Year', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('approve', 'Approve')
    ], string="State", default='draft')
    tax_profit = fields.Float(string="Tax profit to distribute", required=True,
                              help="Corresponding amount to distribute among the workers")
    total_days = fields.Float(string="Total worked days", compute="_compute_totalize", store=True)
    total_salary = fields.Float(string="total annual salary", compute="_compute_totalize", store=True)
    total_ptu = fields.Float(string="Total PTU insured", compute="_compute_total_ptu")
    factor_days = fields.Float(string="Days factor", compute="_compute_factor", store=True)
    factor_salary = fields.Float(string="Salary factor", compute="_compute_factor", store=True)
    highest_salary = fields.Float(string="Highest unionized salary")
    company_id = fields.Many2one("res.company", string="Company")
    line_ids = fields.One2many("hr.ptu.line", 'ptu_id', strint="Lines")

    def _compute_total_ptu(self):
        for res in self:
            res.total_ptu = sum(res.line_ids.mapped('total_amount'))

    @api.depends('line_ids.total_amount', 'line_ids.total_days', 'line_ids.total_salary')
    def _compute_totalize(self):
        for res in self:
            res.total_days = sum(res.line_ids.mapped('total_days'))
            res.total_salary = sum(res.line_ids.mapped('total_salary'))

    @api.depends('total_days', 'total_salary', 'tax_profit')
    def _compute_factor(self):
        for res in self:
            res.factor_days = (res.tax_profit / 2) / res.total_days if res.total_days != 0 else 0
            res.factor_salary = (res.tax_profit / 2) / res.total_salary if res.total_salary != 0 else 0

    def calculate_ptu(self, options):
        self.env.cr.execute("""
                                SELECT
                                    line.id                             AS id,
                                    line.contract_id                    AS contract,
                                    line.limit                          AS limit,
                                    line.total_days                     AS total_days,
                                    line.total_salary                   AS total_salary
                                FROM hr_ptu_line                        AS line
                                WHERE line.ptu_id = %s
                                    AND calculated IS NOT TRUE
                                LIMIT %s
                            """, (self.id, options.get('limit')))
        res = self.env.cr.dictfetchall()

        lines = []
        for line in res:
            factor_days = line['total_days'] * self.factor_days
            factor_salary = line['total_salary'] * self.factor_salary
            total_amount = factor_days + factor_salary
            total_amount = total_amount if total_amount < line['limit'] else line['limit']
            self._cr.execute('''UPDATE 
                                    hr_ptu_line 
                                SET 
                                    calculated = True, 
                                    factor_days = %s, 
                                    factor_salary = %s,
                                    total_amount = %s
                                WHERE id = %s''' % (factor_days, factor_salary, total_amount, line['id']))
            lines.append(line['id'])
        if not len(lines) and len(self.line_ids):
            self.write({'state': 'done'})
        return {
            'ids': lines,
            'messages': [],
            'continues': 1 if len(lines) else 0,
        }

    def recalculate_ptu(self, options):
        if not options.get('first'):
            self._cr.execute('''UPDATE hr_ptu_line SET calculated = False WHERE ptu_id = %s''' % (self.id,))
        return self.calculate_ptu(options)

    def action_approve(self):
        self.write({'state': 'approve'})

    def action_done(self):
        self.write({'state': 'done'})

    def unlink(self):
        for res in self:
            if res.state == "approve":
                raise UserError(_("You cannot delete approved PTU records."))
        return super(HrPTU, self).unlink()


class HrPTULine(models.Model):
    _name = 'hr.ptu.line'
    _description = 'PTU Line Annual'

    ptu_id = fields.Many2one("hr.ptu", string="PTU", ondelete='cascade')
    contract_id = fields.Many2one("hr.contract", string="Contract")
    employee_id = fields.Many2one(related="contract_id.employee_id", string="Employee")
    total_days = fields.Float(string="Total worked days")
    total_salary = fields.Float(string="total annual salary")
    factor_days = fields.Float(string="Days factor")
    factor_salary = fields.Float(string="Salary factor")
    total_amount = fields.Float(string="total PTU")
    calculated = fields.Boolean(string="Calculated")
    limit = fields.Float(string="Limit")
