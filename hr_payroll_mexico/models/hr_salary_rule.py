# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'

    trusted_staff = fields.Boolean(string="Trusted staff")
    percentage_discount_covid = fields.Float('Percentage discount covid')


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'
    
    settlement = fields.Boolean(string='Settlement', tracking=True)
    payroll_type = fields.Selection([
        ('O', 'Ordinary'),
        ('E', 'Extraordinary'),
    ], string="Type of Payroll", required=True)
    assa_report = fields.Boolean(string="ASSA Report")
    aspa_report = fields.Boolean(string="ASPA Report")
    social_objective = fields.Boolean(string="Social objective")
    payslip_code = fields.Selection([
        ('01', 'NÓMINA GENERAL'),
        ('02', 'SINDICALIZADOS PILOTOS ATR'),
        ('03', 'SINDICALIZADOS SOBRECARGOS B'),
        ('SB', 'SINDICALIZADOS SOBRECARGOS A'),
        ('NC', 'NÓMINA CONFIDENCIAL'),
        ('TR', 'NÓMINA PARA PERSONAL EN TIERRA'),
        ('AS', 'ASIMILADOS A SALARIOS'),
    ], string="Payslip Code", required=False, help="Information Needed for ASSA and ASPA reports")
    ptu_payslip = fields.Boolean(string="PTU Payslip")

class SalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    taxable = fields.Boolean(string='Tax Report', default=False,
                             help='If it is checked, it indicates that it is reflected in the details in the excel reports of taxed and exempt.')
    consolidate = fields.Boolean(string='Do not Consolidate', default=False,
                                 help='If checked, it indicates that it was NOT sum to the payroll report.')
    # generated = fields.Boolean(string='generated en excel?', default=False,
    #                            help='Si está marcado indica que se se imprimiran los detalles en los reportes excel.')
    print_to_excel = fields.Boolean(string='Print to excel?', default=False,
                                    help='If it is checked, it indicates that details will be printed in the excel reports.')
    report_imss = fields.Boolean(string='IMMS Imprimir en excel?', default=False,
                                 help='Si está marcado indica que se se imprimiran los detalles en los reportes excel.')
    report_isn = fields.Boolean(string='Print ISN in excel?', default=False,
                                help='If it is checked, it indicates that details will be printed in the excel reports.')

    type = fields.Selection([
        ('not_apply', 'Does not apply'),
        ('perception', 'Perception'),
        ('deductions', 'Deductions'),
        ('other_payment', 'Others Paiments')
    ], string='Type', default="not_apply")
    type_perception = fields.Selection(
        selection=[('001', 'Sueldos, Salarios  Rayas y Jornales'),
                   ('002', 'Gratificación Anual (Aguinaldo)'),
                   ('003', 'Participación de los Trabajadores en las Utilidades PTU'),
                   ('004', 'Reembolso de Gastos Médicos Dentales y Hospitalarios'),
                   ('005', 'Fondo de ahorro'),
                   ('006', 'Caja de ahorro'),
                   ('009', 'Contribuciones a Cargo del Trabajador Pagadas por el Patrón'),
                   ('010', 'Premios por puntualidad'),
                   ('011', 'Prima de Seguro de vida'),
                   ('012', 'Seguro de Gastos Médicos Mayores'),
                   ('013', 'Cuotas Sindicales Pagadas por el Patrón'),
                   ('014', 'Subsidios por incapacidad'),
                   ('015', 'Becas para trabajadores y/o hijos'),
                   ('019', 'Horas extra'),
                   ('020', 'Prima dominical'),
                   ('021', 'Prima vacacional'),
                   ('022', 'Prima por antigüedad'),
                   ('023', 'Pagos por separación'),
                   ('024', 'Seguro de retiro'),
                   ('025', 'Indemnizaciones'),
                   ('026', 'Reembolso por funeral'),
                   ('027', 'Cuotas de seguridad social pagadas por el patrón'),
                   ('028', 'Comisiones'),
                   ('029', 'Vales de despensa'),
                   ('030', 'Vales de restaurante'),
                   ('031', 'Vales de gasolina'),
                   ('032', 'Vales de ropa'),
                   ('033', 'Ayuda para renta'),
                   ('034', 'Ayuda para artículos escolares'),
                   ('035', 'Ayuda para anteojos'),
                   ('036', 'Ayuda para transporte'),
                   ('037', 'Ayuda para gastos de funeral'),
                   ('038', 'Otros ingresos por salarios'),
                   ('039', 'Jubilaciones, pensiones o haberes de retiro'),
                   ('044', 'Jubilaciones, pensiones o haberes de retiro en parcialidades'),
                   ('045', 'Ingresos en acciones o títulos valor que representan bienes'),
                   ('046', 'Ingresos asimilados a salarios'),
                   ('047', 'Alimentación diferentes a los establecidos en el Art 94 último párrafo LISR'),
                   ('048', 'Habitación'),
                   ('049', 'Premios por asistencia'),
                   ('050', 'Viáticos'),
                   ('051',
                    'Pagos por gratificaciones, primas, compensaciones, recompensas u otros a extrabajadores derivados de jubilación en parcialidades'),
                   ('052',
                    'Pagos que se realicen a extrabajadores que obtengan una jubilación en parcialidades derivados de la ejecución de resoluciones judicial o de un laudo'),
                   ('053',
                    'Pagos que se realicen a extrabajadores que obtengan una jubilación en una sola exhibición derivados de la ejecución de resoluciones judicial o de un laudo'),
                   ],
        string=_('Type of perception'),
    )
    type_deduction = fields.Selection(
        selection=[('001', 'Seguridad social'),
                   ('002', 'ISR'),
                   ('003', 'Aportaciones a retiro, cesantía en edad avanzada y vejez.'),
                   ('004', 'Otros'),
                   ('005', 'Aportaciones a Fondo de vivienda'),
                   ('006', 'Descuento por incapacidad'),
                   ('007', 'Pensión alimenticia'),
                   ('008', 'Renta'),
                   ('009', 'Préstamos provenientes del Fondo Nacional de la Vivienda para los Trabajadores'),
                   ('010', 'Pago por crédito de vivienda'),
                   ('011', 'Pago de abonos INFONACOT'),
                   ('012', 'Anticipo de salarios'),
                   ('013', 'Pagos hechos con exceso al trabajador'),
                   ('014', 'Errores'),
                   ('015', 'Pérdidas'),
                   ('016', 'Averías'),
                   ('017', 'Adquisición de artículos producidos por la empresa o establecimiento'),
                   ('018', 'Cuotas para la constitución y fomento de sociedades cooperativas y de cajas de ahorro'),
                   ('019', 'Cuotas sindicales'),
                   ('020', 'Ausencia (Ausentismo)'),
                   ('021', 'Cuotas obrero patronales'),
                   ('022', 'Impuestos Locales'),
                   ('023', 'Aportaciones voluntarias'),
                   ('024', 'Ajuste en Gratificación Anual (Aguinaldo) Exento'),
                   ('025', 'Ajuste en Gratificación Anual (Aguinaldo) Gravado'),
                   ('026', 'Ajuste en Participación de los Trabajadores en las Utilidades PTU Exento'),
                   ('027', 'Ajuste en Participación de los Trabajadores en las Utilidades PTU Gravado'),
                   ('028', 'Ajuste en Reembolso de Gastos Médicos Dentales y Hospitalarios Exento'),
                   ('029', 'Ajuste en Fondo de ahorro Exento'),
                   ('030', 'Ajuste en Caja de ahorro Exento'),
                   ('031', 'Ajuste en Contribuciones a Cargo del Trabajador Pagadas por el Patrón Exento'),
                   ('032', 'Ajuste en Premios por puntualidad Gravado'),
                   ('033', 'Ajuste en Prima de Seguro de vida Exento'),
                   ('034', 'Ajuste en Seguro de Gastos Médicos Mayores Exento'),
                   ('035', 'Ajuste en Cuotas Sindicales Pagadas por el Patrón Exento'),
                   ('036', 'Ajuste en Subsidios por incapacidad Exento'),
                   ('037', 'Ajuste en Becas para trabajadores y/o hijos Exento'),
                   ('038', 'Ajuste en Horas extra Exento'),
                   ('039', 'Ajuste en Horas extra Gravado'),
                   ('040', 'Ajuste en Prima dominical Exento'),
                   ('041', 'Ajuste en Prima dominical Gravado'),
                   ('042', 'Ajuste en Prima vacacional Exento'),
                   ('043', 'Ajuste en Prima vacacional Gravado'),
                   ('044', 'Ajuste en Prima por antigüedad Exento'),
                   ('045', 'Ajuste en Prima por antigüedad Gravado'),
                   ('046', 'Ajuste en Pagos por separación Exento'),
                   ('047', 'Ajuste en Pagos por separación Gravado'),
                   ('048', 'Ajuste en Seguro de retiro Exento'),
                   ('049', 'Ajuste en Indemnizaciones Exento'),
                   ('050', 'Ajuste en Indemnizaciones Gravado'),
                   ('051', 'Ajuste en Reembolso por funeral Exento'),
                   ('052', 'Ajuste en Cuotas de seguridad social pagadas por el patrón Exento'),
                   ('053', 'Ajuste en Comisiones Gravado'),
                   ('054', 'Ajuste en Vales de despensa Exento'),
                   ('055', 'Ajuste en Vales de restaurante Exento'),
                   ('056', 'Ajuste en Vales de gasolina Exento'),
                   ('057', 'Ajuste en Vales de ropa Exento'),
                   ('058', 'Ajuste en Ayuda para renta Exento'),
                   ('059', 'Ajuste en Ayuda para artículos escolares Exento'),
                   ('060', 'Ajuste en Ayuda para anteojos Exento'),
                   ('061', 'Ajuste en Ayuda para transporte Exento'),
                   ('062', 'Ajuste en Ayuda para gastos de funeral Exento'),
                   ('063', 'Ajuste en Otros ingresos por salarios Exento'),
                   ('064', 'Ajuste en Otros ingresos por salarios Gravado'),
                   ('065', 'Ajuste en Jubilaciones, pensiones o haberes de retiro en una sola exhibición Exento '),
                   ('066', 'Ajuste en Jubilaciones, pensiones o haberes de retiro en una sola exhibición Gravado '),
                   ('067', 'Ajuste en Pagos por separación Acumulable '),
                   ('068', 'Ajuste en Pagos por separación No acumulable'),
                   ('069', 'Ajuste en Jubilaciones, pensiones o haberes de retiro en parcialidades Exento'),
                   ('070', 'Ajuste en Jubilaciones, pensiones o haberes de retiro en parcialidades Gravado'),
                   ('071', 'Ajuste en Subsidio para el empleo (efectivamente entregado al trabajador)'),
                   ('072', 'Ajuste en Ingresos en acciones o títulos valor que representan bienes Exento'),
                   ('073', 'Ajuste en Ingresos en acciones o títulos valor que representan bienes Gravado'),
                   ('074', 'Ajuste en Alimentación Exento'),
                   ('075', 'Ajuste en Alimentación Gravado'),
                   ('076', 'Ajuste en Habitación Exento'),
                   ('077', 'Ajuste en Habitación Gravado'),
                   ('078', 'Ajuste en Premios por asistencia'),
                   ('079',
                    'Ajuste en Pagos distintos a los listados y que no deben considerarse como ingreso por sueldos, salarios o ingresos asimilados.'),
                   ('080', 'Ajuste en Viáticos gravados.'),
                   ('081', 'Ajuste en Viáticos (entregados al trabajador)'),
                   ('082', 'Ajuste en Fondo de ahorro Gravado'),
                   ('083', 'Ajuste en Caja de ahorro Gravado'),
                   ('084', 'Ajuste en Prima de Seguro de vida Gravado'),
                   ('085', 'Ajuste en Seguro de Gastos Médicos Mayores Gravado'),
                   ('086', 'Ajuste en Subsidios por incapacidad Gravado'),
                   ('087', 'Ajuste en Becas para trabajadores y/o hijos Gravado'),
                   ('088', 'Ajuste en Seguro de retiro Gravado'),
                   ('089', 'Ajuste en Vales de despensa Gravado'),
                   ('090', 'Ajuste en Vales de restaurante Gravado'),
                   ('091', 'Ajuste en Vales de gasolina Gravado'),
                   ('092', 'Ajuste en Vales de ropa Gravado'),
                   ('093', 'Ajuste en Ayuda para renta Gravado'),
                   ('094', 'Ajuste en Ayuda para artículos escolares Gravado'),
                   ('095', 'Ajuste en Ayuda para anteojos Gravado'),
                   ('096', 'Ajuste en Ayuda para transporte Gravado'),
                   ('097', 'Ajuste en Ayuda para gastos de funeral Gravado'),
                   ('098', 'Ajuste a ingresos asimilados a salarios gravados'),
                   ('099', 'Ajuste a ingresos por sueldos y salarios gravados'),
                   ('100', 'Ajuste en Viáticos exentos'),
                   ('101', 'ISR Retenido de ejercicio anterior'),
                   ('102',
                    'Ajuste a pagos por gratificaciones, primas, compensaciones, recompensas u otros a extrabajadores derivados de jubilación en parcialidades, gravados'),
                   ('103',
                    'Ajuste a pagos que se realicen a extrabajadores que obtengan una jubilación en parcialidades derivados de la ejecución de una resolución judicial o de un laudo gravados'),
                   ('104',
                    'Ajuste a pagos que se realicen a extrabajadores que obtengan una jubilación en parcialidades derivados de la ejecución de una resolución judicial o de un laudo exentos'),
                   ('105',
                    'Ajuste a pagos que se realicen a extrabajadores que obtengan una jubilación en una sola exhibición derivados de la ejecución de una resolución judicial o de un laudo gravados'),
                   ('106',
                    'Ajuste a pagos que se realicen a extrabajadores que obtengan una jubilación en una sola exhibición derivados de la ejecución de una resolución judicial o de un laudo exentos'),
                   ('107', 'Ajuste al Subsidio Causado '),
                   ],
        string=_('Type of deduction'),
    )
    type_other_payment = fields.Selection(
        selection=[('001', 'Reintegro de ISR pagado en exceso'),
                   ('002', 'Subsidio para el empleo'),
                   ('003', 'Viáticos.'),
                   ('004', 'Apliación de saldo a favor por compensación anual'),
                   ('005', 'Reintegro de ISR retenido en exceso de ejercicio anterior'),
                   ('006', 'Alimentos en bienes (Servicios de comedor y comida) Art 94 último párrafo LISR'),
                   ('007', 'ISR ajustado por subsidio'),
                   ('008',
                    'Subsidio efectivamente entregado que no correspondía (Aplica sólo cuando haya ajuste al cierre de mes en relación con el Apéndice 7 de la guía de llenado de nómina)'),
                   ('999',
                    'Pagos distintos a los listados y que no deben considerarse como ingreso por sueldos, salarios o ingresos asimilados.')],
        string=_('Otros Pagos'),)
    type_overtime = fields.Selection([
        ('01', 'Double'),
        ('02', 'Triples'),
        ('03', 'Simple'),
    ], string='Overtime Type')
    type_disability = fields.Selection([
        ('01', 'Occupational risk.'),
        ('02', 'General illness.'),
        ('03', 'Maternity.'),
        ('04', 'Leave for medical care of children diagnosed with cancer.'),
    ], string='Type of disability')
    payment_type = fields.Selection([
        ('01', 'Species.'),
        ('02', 'Cash.'),
    ], string='Payment Type', default="02")
    payroll_tax = fields.Boolean('Apply payroll tax?', default=False,
                                 help="If selected, this rule will be taken for the calculation of payroll tax.")
    # settlement = fields.Boolean(string='Settlement structure?')
    # code_category_id = fields.Char(related='category_id.code')
    apply_variable_compute = fields.Boolean(string='Apply for variable salary calculation')
    country_id = fields.Many2one('res.country', string="Country",
                                 default=lambda self: self.env.user.company_id.country_id.id)
    state_ids = fields.Many2many('res.country.state.isn', string='Stations')
    provision = fields.Boolean(string="Provision?")
    provision_type = fields.Selection([
        ('bonus', 'Bonus'),
        ('holidays', 'Holidays'),
        ('premium', 'Vacation Premium')
    ], string="Provision Type")
    union_dues = fields.Boolean(string="Union Dues")
    social_objective = fields.Boolean(string="Social objective")
    saving_fund = fields.Boolean(string="Saving Fund")
    # print_excel_settlement = fields.Boolean(string='Print excel settlement?')
    # account_debit = fields.Many2one('account.account', 'Debit Account', domain=[('deprecated', '=', False)])
    # account_credit = fields.Many2one('account.account', 'Credit Account', domain=[('deprecated', '=', False)])

    @api.onchange('payroll_tax')
    def onchange_payroll_tax(self):
        for res in self:
            if res.payroll_tax:
                stations = self.env['res.country.state.isn'].search([])
                res.state_ids = stations
            else:
                res.state_ids = False

    # ~ @api.constrains('code', 'struct_id')
    # ~ def _check_code_by_struct(self):
        # ~ for record in self:
            # ~ other_res = self.search([
                # ~ ('id', '!=', record.id),
                # ~ ('code', '=', record.code),
                # ~ ('struct_id', '=', record.struct_id.id),
            # ~ ])
            # ~ if other_res:
                # ~ raise UserError(_('There cannot be two rules with the same code in the same salary structure'))

    def _compute_rule(self, localdict):
        """
        :param localdict: dictionary containing the current computation environment
        :return: returns a tuple (amount, qty, rate)
        :rtype: (float, float, float)
        """
        self.ensure_one()
        if self.amount_select == 'fix':
            try:
                return self.amount_fix or 0.0, float(safe_eval(self.quantity, localdict)), 100.0, 0, 0, 0, {}, 0
            except Exception as e:
                raise UserError(_('Wrong quantity defined for salary rule %s (%s).\nError: %s') % (self.name, self.code, e))
        if self.amount_select == 'percentage':
            try:
                return (float(safe_eval(self.amount_percentage_base, localdict)),
                        float(safe_eval(self.quantity, localdict)),
                        self.amount_percentage or 0.0)
            except Exception as e:
                raise UserError(_('Wrong percentage base or quantity defined for salary rule %s (%s).\nError: %s') % (self.name, self.code, e))
        else:  # python code
            try:
                safe_eval(self.amount_python_compute or 0.0, localdict, mode='exec', nocopy=True)
                return float(localdict['result']), localdict.get('result_qty', 1.0), localdict.get('result_rate', 100.0), float(localdict['pending_amount']), float(localdict['isn_amount']), float(localdict['tax_amount']), localdict['datas'], localdict['days']
            except Exception as e:
                raise UserError(_('Wrong python code defined for salary rule %s (%s).\nError: %s') % (self.name, self.code, e))


class HrSalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    def _sum_salary_rule_category(self, localdict, amount, isn_amount, tax_amount):
        self.ensure_one()
        if self.parent_id:
            localdict = self.parent_id._sum_salary_rule_category(localdict, amount)
        localdict['categories'].dict[self.code] = localdict['categories'].dict.get(self.code, 0) + amount
        localdict['categories'].dict[self.code+'ISN'] = localdict['categories'].dict.get(self.code+'ISN', 0) + isn_amount
        localdict['categories'].dict[self.code+'ISR'] = localdict['categories'].dict.get(self.code+'ISR', 0) + tax_amount
        return localdict
