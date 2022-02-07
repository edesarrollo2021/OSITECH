# -*- coding: utf-8 -*-

import locale
import pytz
from datetime import date, datetime, timedelta, time
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.osv import expression
from odoo.addons.base_mexico.models.tool_convert_numbers_letters import numero_to_letras

# locale.setlocale(locale.LC_TIME, 'es_MX.UTF-8')


class Contract(models.Model):
    _inherit = 'hr.contract'
    
    
    def _get_years_antiquity(self, end=None, date_to=None):
        '''
        This method obtains the age of the contract
        :return:
        '''
        date_end = date_to if date_to else fields.Date.today()
        if end and self.date_end:
            date_end = self.date_end
        if self.date_end and self.date_end < date_end:
            date_end = self.date_end
        date_start_contract = self.previous_contract_date if self.previous_contract_date else self.date_start
        years_antiquity = self.num_years(date_start_contract,date_end)
        bisiesto = 0
        ano_bisiesto = date_start_contract.year
        if ano_bisiesto % 4 == 0 and (ano_bisiesto % 100 != 0 or ano_bisiesto % 400 == 0):
            if date_start_contract.month == 2 and date_start_contract.day == 29:
                bisiesto = 1
        date_start_current_year = date(date_start_contract.year + years_antiquity,
                                       date_start_contract.month, date_start_contract.day-bisiesto)
        days_rest = (date_end - date_start_current_year).days + 1
        days_rest = days_rest if years_antiquity >= 0 else 0
        years_antiquity = years_antiquity if years_antiquity >= 0 else 0
        self.years_antiquity = years_antiquity
        self.days_rest = days_rest
        return [years_antiquity, days_rest]

    def num_years(self, begin, end=None):
        num_years = int(((end - begin).days + 1)/ 365.25)
        if begin > self.yearsago(num_years, end):
            return num_years - 1
        else:
            return num_years

    def yearsago(self, years, from_date=None):
        return from_date - relativedelta(years=years)

    # Changes
    date_start = fields.Date(tracking=True)
    date_end = fields.Date(tracking=True)

    code = fields.Char('Code', required=False, default='/')
    salary_changes_line_ids = fields.One2many('contract.salary.change.line', 'contract_id', string="Salary Change Lines")
    bank_account_id = fields.Many2one('bank.account.employee', "Bank Account", required=True, copy=False, ondelete="restrict",
                                      domain="['|',('employee_id', '=', employee_id), ('employee_id', '=', False)]")
    contracting_regime = fields.Selection([
        ('02', 'Sueldos y Salarios'),
        ('05', 'Libre'),
        ('07', 'Asimilados Miembros consejos'),
        ('08', 'Asimilados comisionistas'),
        ('09', 'Asimilados a honorarios'),
        ('11', 'Asimilados otros'),
        ('99', 'Otro Regimen'),
    ], string='Contracting Regime', required=True, default="02", tracking=True)
    
    contract_type = fields.Selection([
        ('01', 'Contrato de trabajo por tiempo indeterminado'),
        ('02', 'Contrato de trabajo por obra determinada'),
        ('03', 'Contrato de trabajo por tiempo determinado'),
        ('04', 'Contrato de trabajo por temporada'),
        ('05', 'Contrato de trabajo sujeto a prueba'),
        ('06', 'Contrato de trabajo con capacitación inicial'),
        ('07', 'Modalidad de contratación por pago de hora laborada'),
        ('08', 'Modalidad de trabajo por comisión laboral'),
    ], string='Contracting Type', required=True, tracking=True)
    
    previous_contract_date = fields.Date('Previous Contract Date', help="Start date of the previous contract for antiquity.", tracking=True)

    years_antiquity = fields.Integer(string='Antiquity', compute='_get_years_antiquity', store=False)
    days_rest = fields.Integer(string='Days of seniority last year', compute='_get_years_antiquity', store=False)
    
    wage = fields.Monetary('Monthly Wage', required=True, tracking=True, help="Employee's monthly gross wage.")
    daily_salary = fields.Monetary('Daily salary', required=False, tracking=True, help="Employee daily salary.")
    sdi = fields.Float(string="SDI", copy=False, tracking=True)
    integral_salary = fields.Float(string="Integrated Salary", copy=False, tracking=True)
    variable_salary = fields.Float(string="Variable Salary", copy=False, tracking=True)
    sbc = fields.Float(string="SBC", copy=False, tracking=True)
    payment_period = fields.Selection([
        ('01','Diario'),
        ('02','Semanal'),
        ('03','Catorcenal'),
        ('04','Quincenal'),
        ('10','Decenal'),
        ('06','Mensual'),
    ], string='Payment Period', tracking=True, default="04")
    
    monthly_savings_fund = fields.Float(string="Monthly Savings Fund", tracking=True)
    
    seniority_premium = fields.Float(string='Seniority premium', tracking=True)

    discount_covid = fields.Float(string="Discount Covid-19", tracking=True)

    days_duration = fields.Integer(string="Days of Duration", compute="_compute_days_duration", store=True)
    training_end_date = fields.Date(string="Training End Date", tracking=True)
    days_duration_training = fields.Integer(string="Training Days of Duration", compute="_compute_days_duration", store=True)
    date_start_letter = fields.Char(string="Date start on letters for reports", compute="_compute_date_letters")
    date_end_letter = fields.Char(string="Date end on letters for reports", compute="_compute_date_letters")
    prev_date_end_letter = fields.Char(string="Date Previous contract on letters for reports", compute="_compute_date_letters")
    wage_letters = fields.Char(string="Wage in letters", compute="_convert_wage_to_letters")
    
    def format_dates(self, date):
        months = {
            '01': 'enero',
            '02': 'febrero',
            '03': 'marzo',
            '04': 'abril',
            '05': 'mayo',
            '06': 'junio',
            '07': 'julio',
            '08': 'agosto',
            '09': 'septiembre',
            '10': 'octubre',
            '11': 'noviembre',
            '12': 'diciembre'
        }
        date_format = _("%s of %s of %s") % (date.day, months[date.strftime("%m")], date.year)
        return date_format

    @api.depends('date_start', 'date_end')
    def _compute_date_letters(self):
        for res in self:
            res.date_start_letter = self.format_dates(res.date_start) if res.date_start else ""
            res.date_end_letter = self.format_dates(res.date_end) if res.date_end else ""
            res.prev_date_end_letter = self.format_dates(res.previous_contract_date) if res.previous_contract_date else ""

    @api.depends('wage')
    def _convert_wage_to_letters(self):
        for res in self:
            res.wage_letters = numero_to_letras(res.wage, res.company_id.currency_id.name) if res.wage else ""

    @api.depends('date_start', 'date_end', 'training_end_date')
    def _compute_days_duration(self):
        for res in self:
            if res.date_end:
                days = res.date_end - res.date_start
                res.days_duration = days.days
            if res.training_end_date:
                days = res.training_end_date - res.date_start
                res.days_duration_training = days.days

    def _calculate_integral_salary(self, date_to=None):
        current_date = fields.Date.context_today(self)
        start_date_contract = self.previous_contract_date if self.previous_contract_date else self.date_start
        res_years_antiquity = self._get_years_antiquity(date_to=date_to)
        years_antiquity = res_years_antiquity[0]
        days_rest = res_years_antiquity[1]
        if days_rest == 0 and years_antiquity == 0:
            years_antiquity += 1
        if days_rest > 0:
            years_antiquity += 1
        antiquity = self.env['hr.table.antiquity.line'].search([('year','=',years_antiquity),('antiquity_line_id','=',self.employee_id.antiquity_id.id)])
        employee = self.employee_id
        integral_salary = self.daily_salary * (round(antiquity.factor, 4))
        return float("{0:.2f}".format(integral_salary))

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name.split(' ')[0] + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    def post_create(self):
        for contract in self:
            contract.daily_salary = contract.wage / contract.env.company.days_factor if contract.wage else False
            contract.integral_salary = contract._calculate_integral_salary()
            contract.sdi = contract.integral_salary + contract.variable_salary
            limit_imss = contract.company_id.uma * contract.company_id.general_uma
            if contract.sdi > limit_imss:
                contract.sbc = limit_imss
            else:
                contract.sbc = contract.sdi

    @api.model
    def create(self, vals):
        result = super(Contract, self).create(vals)
        if result.code == '/':
            result.code = self.env['ir.sequence'].next_by_code('hr.contract')
        result.post_create()
        if self._context.get('contract_import', False) and self._context.get('import_file', False):
            result.write({'state': 'open'})
            result._onchange_state()

        # Department
        vals = {
            'employee_id': result.employee_id.id,
            'contract_id': result.id,
            'type': 'department',
            'date': result.date_start,
            'new_department_id': result.department_id.id,
        }
        self.env['history.changes.employee'].create(vals)
        # Job
        vals = {
            'employee_id': result.employee_id.id,
            'contract_id': result.id,
            'type': 'position',
            'date': result.date_start,
            'new_job_id': result.job_id.id,
            'new_position_id': result.employee_id.position_id.id if result.employee_id.position_id else False,
        }
        self.env['history.changes.employee'].create(vals)
        return result

    def write(self, vals):
        res = super(Contract, self).write(vals)
        SalaryChange = self.env['contract.salary.change.line']
        previous_change = SalaryChange.search([('contract_id', '=', self.id)])
        if len(previous_change) == 1:
            previous_change.date_start = self.date_start
        return res

    def aniversary_employee(self):
        SalaryChange = self.env['contract.salary.change.line']
        actual_year = fields.Date.today().year
        leaveType = self.env['hr.leave.type']
        leaveAllocation = self.env['hr.leave.allocation']

        for res in self.search([('state', '=', 'open')]):
            date_any = res.previous_contract_date if res.previous_contract_date else res.date_start
            month = date_any.month
            day = date_any.day
            if month == 2 and day == 29:
                day = calendar.monthrange(int(actual_year), int(month))[1]
            if date_any.replace(year=actual_year, day=day) == fields.Date.today():
                print (date_any.replace(year=actual_year, day=day))
                # Calculate antiquity
                res_years_antiquity = res._get_years_antiquity()
                years_antiquity = res_years_antiquity[0]
                days_rest = res_years_antiquity[1]
                if days_rest == 0 and years_antiquity == 0:
                    years_antiquity += 1
                if days_rest > 0:
                    years_antiquity += 1
                antiquity = self.env['hr.table.antiquity.line'].search(
                    [('year', '=', years_antiquity), ('antiquity_line_id', '=', res.employee_id.antiquity_id.id)])

                # Generate Salary Changes
                if res.num_years(res.date_start, fields.Date.today()) > 0 and res.employee_id.pilot_tab_id:
                    years_antiquity = res.num_years(res.date_start, fields.Date.today())

                    pilot_tab = self.env['hr.pilot.tab.line'].search([
                        ('year', '=', years_antiquity),
                        ('pilot_tab_id', '=', res.employee_id.pilot_tab_id.id)
                    ])
                    salary = pilot_tab.salary
                    seniority_premium = pilot_tab.seniority_premium

                    diferents = res.wage != salary

                    res.wage = salary
                    res.daily_salary = salary / res.company_id.days_factor if salary else False
                    res.integral_salary = res._calculate_integral_salary()
                    res.sdi = res.integral_salary + res.variable_salary
                    res.seniority_premium = seniority_premium
                    limit_imss = res.company_id.uma * res.company_id.general_uma
                    if res.sdi > limit_imss:
                        res.sbc = limit_imss
                    else:
                        res.sbc = res.sdi

                    movements = self.env['hr.employee.affiliate.movements'].search([
                        ('contract_id', '=', res.id),
                        ('type', '=', '08'),
                    ], limit=1)
                    if diferents:
                        if not movements:
                            self.env['hr.employee.affiliate.movements'].create({
                                'contract_id': res.id,
                                'employee_id': res.employee_id.id,
                                'company_id': res.company_id.id,
                                'type': '08',
                                'date': fields.Date.today(),
                                'wage': res.wage,
                                'sbc': res.sbc,
                                'salary': res.sdi,
                            })

                        self.env['hr.employee.affiliate.movements'].create({
                            'contract_id': res.id,
                            'employee_id': res.employee_id.id,
                            'company_id': res.company_id.id,
                            'type': '07',
                            'date': fields.Date.today(),
                            'wage': res.wage,
                            'salary': res.sdi,
                            'sbc': res.sbc,
                        })

                    change_salary = SalaryChange.search([
                        ('contract_id', '=', res.id),
                        ('wage', '=', res.wage),
                        ('daily_salary', '=', res.daily_salary),
                        ('sdi', '=', res.sdi),
                        ('sbc', '=', res.sbc),
                        ('integrated_salary', '=', res.integral_salary),
                        ('seniority_premium', '=', res.seniority_premium),
                        ('date_end', '=', False),
                    ])
                    previous_change = SalaryChange.search(
                        [('date_end', '=', False), ('contract_id', '=', res.id)])  # Previous Record
                    if not change_salary:
                        previous_change.write({'date_end': fields.Date.today() + relativedelta(days=-1)})
                        SalaryChange.create({
                            'contract_id': res.id,
                            'wage': res.wage,
                            'daily_salary': res.daily_salary,
                            'sdi': res.sdi,
                            'sbc': res.sbc,
                            'integrated_salary': res.integral_salary,
                            'seniority_premium': res.seniority_premium,
                            'date_start': fields.Date.today(),
                        })

                # Generate Holidays and Personal Days
                # search
                type_personal = leaveType.search([
                    ('time_type', '=', 'personal'),
                    '|', ('validity_stop', '>', fields.Date.today()), ('validity_stop', '=', False)
                ], limit=1)
                type_holidays = leaveType.search([
                    ('time_type', '=', 'holidays'),
                    '|', ('validity_stop', '>', fields.Date.today()), ('validity_stop', '=', False)
                ], limit=1)

                personal_days = leaveAllocation.search([
                    ('employee_id', '=', res.employee_id.id),
                    ('state', 'not in', ['draft', 'cancel', 'refuse']),
                    ('holiday_status_id', '=', type_personal.id)
                ])
                holidays = leaveAllocation.search([
                    ('employee_id', '=', res.employee_id.id),
                    ('state', 'not in', ['draft', 'cancel', 'refuse']),
                    ('holiday_status_id', '=', type_holidays.id)
                ])

                # Holidays
                if not holidays:
                    leaveAllocation.sudo().create({
                        'name': 'Holidays %s %s' % (res.employee_id.complete_name, actual_year),
                        'employee_id': res.employee_id.id,
                        'holiday_status_id': type_holidays.id,
                        'allocation_type': 'regular',
                        'number_of_days': antiquity.holidays,
                    })
                # Personal Days
                if not personal_days:
                    leaveAllocation.sudo().create({
                        'name': 'Personal Days %s %s' % (res.employee_id.complete_name, actual_year),
                        'employee_id': res.employee_id.id,
                        'holiday_status_id': type_personal.id,
                        'allocation_type': 'regular',
                        'number_of_days': self.env.company.personal_days_factor,
                    })

    def contract_salary_change(self, date_move=None):
        SalaryChange = self.env['contract.salary.change.line']
        change_salary = SalaryChange.search([
            ('contract_id', '=', self.id),
            ('wage', '=', self.wage),
            ('daily_salary', '=', self.daily_salary),
            ('sdi', '=', self.sdi),
            ('sbc', '=', self.sbc),
            ('integrated_salary', '=', self.integral_salary),
            ('seniority_premium', '=', self.seniority_premium),
            ('date_end', '=', False),
        ])
        # Previous Record
        previous_change = SalaryChange.search([('date_end', '=', False), ('contract_id', '=', self.id)])
        first_change = SalaryChange.search([('contract_id', '=', self.id)])
        date_move = date_move or fields.Date.today()
        if not change_salary:
            previous_change.write({'date_end': date_move + relativedelta(days=-1)})
            SalaryChange.create({
                'contract_id': self.id,
                'wage': self.wage,
                'daily_salary': self.daily_salary,
                'sdi': self.sdi,
                'sbc': self.sbc,
                'integrated_salary': self.integral_salary,
                'seniority_premium': self.seniority_premium,
                'date_start': date_move if first_change else self.date_start,
            })

    @api.onchange('state')
    def _onchange_state(self):
        SalaryChange = self.env['contract.salary.change.line']
        EmployeeAffiliateMovements = self.env['hr.employee.affiliate.movements']
        self_contract = self.env['hr.contract'].search([('code', '=', self.code)])

        if self.state == 'draft':
            print('draft')
        if self.state == 'open':
            movements = EmployeeAffiliateMovements.search([('contract_id', '=', self_contract.id), ('type', '=', '08')])
            if not movements:
                EmployeeAffiliateMovements.create({
                    'contract_id': self_contract.id,
                    'employee_id': self.employee_id.id,
                    'company_id': self.company_id.id,
                    'type': '08',
                    'date': fields.Date.today(),
                    'wage': self.wage,
                    'sbc': self.sbc,
                    'salary': self.sdi,
                })
            change_salary = SalaryChange.search([
                ('contract_id', '=', self_contract.id),
                ('wage', '=', self.wage),
                ('daily_salary', '=', self.daily_salary),
                ('sdi', '=', self.sdi),
                ('sbc', '=', self.sbc),
                ('integrated_salary', '=', self.integral_salary),
                ('seniority_premium', '=', self.seniority_premium),
                ('date_end', '=', False)
            ])
            previous_change = SalaryChange.search([('date_end', '=', False), ('contract_id', '=', self_contract.id)])  # Previous Record
            first_change = SalaryChange.search([('contract_id', '=', self_contract.id)])
            if not change_salary:
                previous_change.write({'date_end': fields.Date.today() + relativedelta(days=-1)})
                SalaryChange.create({
                    'contract_id': self_contract.id,
                    'wage': self.wage,
                    'daily_salary': self.daily_salary,
                    'sdi': self.sdi,
                    'sbc': self.sbc,
                    'integrated_salary': self.integral_salary,
                    'seniority_premium': self.seniority_premium,
                    'date_start': fields.Date.today() if first_change else self.date_start,
                })

        if self.state == 'close':
            self.employee_id.position_id.change_employees()
        if self.state == 'cancel':
            self.employee_id.position_id.change_employees()
    
