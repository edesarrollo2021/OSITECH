# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError, UserError


class EmployeeAffiliateMovements(models.Model):
    _name = 'hr.employee.affiliate.movements'
    _rec_name = 'type'
    _order = "create_date desc"

    contract_id = fields.Many2one('hr.contract', index=True, string='Contract')
    employee_id = fields.Many2one('hr.employee', index=True, string='Employee')
    company_id = fields.Many2one('res.company', "Company", store=True, related='employee_id.company_id')
    type = fields.Selection([
        ('08', 'High or Reentry'),
        ('07', 'Salary change'),
        ('02', 'Low'),
    ], string='Type', index=True, default='08')
    date = fields.Date(string="Date")
    reason_liquidation = fields.Selection([
        ('1', 'TERMINACIÓN DE CONTRATO'),
        ('2', 'SEPARACIÓN VOLUNTARIA'),
        ('3', 'ABANDONO DE EMPLEO'),
        ('4', 'DEFUNCIÓN'),
        ('7', 'AUSENTISMOS'),
        ('8', 'RESICIÓN DE CONTRATO'),
        ('9', 'JUBILACIÓN'),
        ('A', 'PENSIÓN'),
        ('5', 'CLAUSURA'),
        ('6', 'OTROS')],
        string='Reason for liquidation')
    origin_move = fields.Selection([
        ('371', 'REVISIÓN POR ART. 18'),
        ('373', 'VISITA INTEGRAL ART. 46'),
        ('374', 'REVISIÓN DE GABINETE ART. 48'),
        ('375', 'REVISIÓN POR ART. 12 A'),
        ('376', 'VISITA ESPECÍFICA ART. 46'),
        ('397', 'REVISIÓN ÁGIL ART. 17'),
        ('400', 'DISPOSITIVOS MAGNÉTICOS (REINTEGROS, MODIFICACIONES DE SALARIOS Y BAJAS)'),
        ('405', 'CORRECIÓN POR INVITACIÓN, CORRECIÓN ESPONTÁNEA SATICA O SATICB.'),
        ('406', 'PROGRAMA DE DICTAMEN (OBLIGADO Y VOLUNTARIO) PROCEDIMIENTO DE REVISIÓN INTERNA (RO Y RV).'),
    ], default='400', string='Origin of movement')
    wage = fields.Float('Wage', digits=(16, 2), help="Employee's monthly gross wage.")
    salary = fields.Float('SDI', digits=(16, 2), copy=False, help="SDI")
    sbc = fields.Float(string="SBC",  digits=(16, 2), copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('cancel', 'Cancel'),
    ], string='State', default='draft')
    contracting_regime = fields.Selection(string='Contracting Regime',
                                          related="contract_id.contracting_regime", store=True)
    type_change_salary = fields.Selection([
        ('0', 'Fixed'),
        ('1', 'Variable'),
        ('2', 'Mixted')
    ], string="Salary type")
    variable = fields.Boolean(string="Variable", default=False)

    def action_move_draft(self):
        self.filtered(lambda mov: mov.state == 'generated').write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    # @api.model
    # def create(self, vals):
    #     Movements = super(EmployeeAffiliateMovements, self).create(vals)
    #     today = Movements.date or date.today()
    #     table_id = self.env['table.settings'].search([('year', '=', int(today.year))], limit=1)
    #     uma = self.env['table.uma'].search_uma(today)
    #     limit_imss = uma * table_id.sbcm_general
    #     if Movements.salary > limit_imss:
    #         Movements.salary = limit_imss
    #     return Movements

    def unlink(self):
        for movements in self:
            if movements.state not in ['draft']:
                raise UserError(_('You cannot delete affiliate movements that are not in "Draft" status.'))
        return super(EmployeeAffiliateMovements, self).unlink()
