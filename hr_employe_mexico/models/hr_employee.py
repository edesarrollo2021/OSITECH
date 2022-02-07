# -*- coding: utf-8 -*-

from datetime import date

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

from odoo.addons.base_mexico.pyfiscal.generate import GenerateRFC, GenerateCURP, GenerateNSS, GenericGeneration


def calculate_age(date_birthday):
    today = date.today()
    try:
        birthday = date_birthday.replace(year=today.year)
    except ValueError:
        birthday = date_birthday.replace(year=today.year, day=date_birthday.day - 1)
    if birthday > today:
        return today.year - date_birthday.year - 1
    else:
        return today.year - date_birthday.year


class Job(models.Model):
    _inherit = 'hr.job'

    code = fields.Char("Code", copy=False, default='/', required=True)
    sat_code = fields.Char("Clave SAT", copy=False, default='/', required=True)
    
    overhead_compensation = fields.Boolean("Overhead compensation")
    amount_compensation = fields.Float('Amount Compensation')
    
    pilot_compensation = fields.Boolean("Pilot compensation")
    percentage_compensation = fields.Selection([
        ('9', '9%'),
        ('15', '15%'),
        ('20', '20%'),
        ('23', '23%'),
        ('24', '24%'),
        ('26', '26%'),
        ], string='Percentage of compensation', required=False)

    candidate = fields.Boolean(string="Candidate")
    position_ids = fields.One2many("hr.job.position", "job_id", string="Positions")
    no_of_recruitment = fields.Integer(compute="_compute_employees")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The job name must be unique!'),
        ('code_uniq', 'unique(code)', 'The job number must be unique!')
    ]

    @api.depends('employee_ids.job_id', 'employee_ids.active', 'position_ids.employee_id')
    def _compute_employees(self):
        all_position_data = self.env['hr.job.position'].read_group([('job_id', 'in', self.ids), ('employee_id', '!=', False)], ['job_id'], ['job_id'])
        position_data = self.env['hr.job.position'].read_group([('job_id', 'in', self.ids), ('employee_id', '=', False)], ['job_id'], ['job_id'])
        result = dict((data['job_id'][0], data['job_id_count']) for data in all_position_data)
        result2 = dict((data['job_id'][0], data['job_id_count']) for data in position_data)
        for job in self:
            job.no_of_employee = result.get(job.id, 0)
            job.no_of_recruitment = result2.get(job.id, 0)
            job.expected_employees = result.get(job.id, 0) + result2.get(job.id, 0)

    @api.model
    def create(self, vals):
        result = super(Job, self).create(vals)
        if result.code == '/':
            result.code = self.env['ir.sequence'].next_by_code('hr.job')
        result.name = result.name.upper()
        result.code = result.code.upper()
        return result

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = vals.get('name').upper()
        if vals.get('code'):
            vals['code'] = vals.get('code').upper()

        res = super(Job, self).write(vals)
        return res

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
        return self._search(expression.AND([args, domain]), limit=limit, access_rights_uid=name_get_uid)


class Department(models.Model):
    _inherit = "hr.department"

    code = fields.Char("Code", copy=False, required=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'The department name must be unique !'),
        ('code_uniq', 'unique(code)', 'The department number  must be unique !')
    ]

    @api.model
    def create(self, vals):
        result = super(Department, self).create(vals)
        if result.code == '/' or result.code == '' or result.code == False:
            result.code = self.env['ir.sequence'].next_by_code('hr.department')
        print(result.code)
        result.name = result.name.upper()
        result.code = result.code.upper()
        return result

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = vals.get('name').upper()
        if vals.get('code'):
            vals['code'] = vals.get('code').upper()

        res = super(Department, self).write(vals)
        return res

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
        return self._search(expression.AND([args, domain]), limit=limit, access_rights_uid=name_get_uid)


class Employee(models.Model):
    _inherit = "hr.employee"
    # ~ _rec_name = "complete_name"
    
    @api.depends('birthday')
    def calculate_age_compute(self):
        for employee in self:
            if employee.birthday:
                employee.age = calculate_age(employee.birthday)
            else:
                employee.age = 0
        return

    is_manager = fields.Boolean(string="Is Manager")
    registration_number = fields.Char(default='/', required=True)
    department_id = fields.Many2one(required=True)
    job_id = fields.Many2one(required=True)
    position_id = fields.Many2one("hr.job.position", string="Position")
    place_of_birth = fields.Many2one('res.country.state', string='Place of Birth', groups="hr.group_hr_user")
    complete_name = fields.Char(compute='_compute_complete_name', string='Complete Name', store=True)
    last_name = fields.Char("Last Name", required=True)
    mothers_last_name = fields.Char("Mother's Last Name")
    bank_account_ids = fields.One2many('bank.account.employee', 'employee_id', "Bank account", required=True)
    family_ids = fields.One2many('hr.family.burden', 'employee_id', "Family")
    family_medicine_unit = fields.Char(string="Family Medicine Unit")
    blood_type = fields.Selection([
        ('O-', 'O-'),
        ('O+', 'O+'),
        ('A-', 'A-'),
        ('A+', 'A+'),
        ('B-', 'B-'),
        ('B+', 'B+'),
        ('AB-', 'AB-'),
        ('AB+', 'AB+'),
        ], string='Blood type', required=False)
    salary_type = fields.Selection([('0', 'Fixed'), ('1', 'Variable'), ('2', 'Mixed')], string="Salary Type", default='0')
    working_day_week = fields.Selection([('0', 'Complete'),
                                         ('1', 'Work one day'),
                                         ('2', 'Mixed'),
                                         ('3', 'Work three days'),
                                         ('4', 'Work four days'),
                                         ('5', 'Work five days'),
                                         ('6', 'Reduced working hours'),
                                         ],
                                        string="Weekly shift",
                                        default='0')
    type_working_day = fields.Selection([
        ('01', 'Daytime'),
        ('02', 'Nightly'),
        ('03', 'Mixed'),
        ('04', 'Per hour'),
        ('05', 'Reduced'),
        ('06', 'Continued'),
        ('07', 'Departure'),
        ('08', 'By turns'),
        ('99', 'Another day'),
    ], string="Type Working Day", default='01')
    type_worker = fields.Selection([('1', 'Job permanent'),
                                    ('2', 'Job Ev. Town'),
                                    ('3', 'Job Ev. Construction'),
                                    ('4', 'Eventual from the field'),
                                    ],
                                   string="Type of worker", default='1')
    deceased = fields.Boolean('Deceased?', default=False, help="If checked, the employee is considered deceased")
    syndicalist = fields.Boolean('Syndicalist?', default=False, help="If checked, the employee is considered part of the union")
    cost_center_id = fields.Many2one('hr.cost.center', "Cost Center", required=True, copy=False)
    # workplace_center = fields.Many2one('hr.workplace', "Workplace Center", required=True, copy=False)
    payment_holidays_bonus = fields.Selection([('0', 'Pay at the expiration of the vacation'),
                                               ('1', 'Pay with the enjoyment of the holidays'),
                                               ('2', 'Advance payment to enjoy the holidays'),
                                               ],
                                              string='Vacation premium payment', default='0')
    # Extra Payments
    pay_extra_hours = fields.Boolean('Pay extra hours?', default=False, help="If checked, extra hours are paid to the employee")
    insurance_medical_ids = fields.One2many('insurance.major.medical.expenses', 'employee_id', string="Insurance Major Medical Expenses")
    alimony_ids = fields.One2many('hr.alimony', 'employee_id', string="Alimony")

    age = fields.Integer("Age", compute='calculate_age_compute')
    employer_register_id = fields.Many2one('res.employer.register', "Employer Register", required=False)
    antiquity_id = fields.Many2one('hr.table.antiquity', "Table of antiquity", required=True)

    folder_id = fields.Many2one('documents.folder')
    partner_document_count = fields.Integer(related="address_home_id.document_count")
    isr_adjustment = fields.Boolean(string="ISR Adjustment", help="Apply Annual ISR Adjustment?", default=True)
    marital = fields.Selection(selection_add=[('free_union', 'Free Union')])
    
    personal_savings_bank = fields.Float("Personal savings bank")
    resistance_bottom_new = fields.Float("Resistance fund ASSA new income")
    fixed_resistance_background = fields.Float("Fixed ASSA resistance fund")
    
    salary_reduction = fields.Boolean(string="Salary reduction?", help="Employee with definitive salary reduction.")
    previous_salary = fields.Float("Previous salary")

    pilot_tab_id = fields.Many2one('hr.pilot.tab', string='Pilor Tab')
    pilot_category = fields.Selection([
        ('captains', 'Captains'),
        ('official', 'First Official'),
    ], string="Pilot Category")

    @api.constrains('address_home_id')
    def check_address_home(self):
        for res in self:
            total_res = self.search_count([('address_home_id', '=', res.address_home_id.id),])
            if total_res > 1:
                raise UserError(_('An employee with this private address already exists'))

    def calculate_insurance_medical(self, date):
        self.env.cr.execute("""
                                SELECT 
                                    insurance.amount
                                FROM insurance_major_medical_expenses insurance
                                WHERE 
                                    insurance.employee_id = %s
                                    AND (insurance.date_start, insurance.date_end) OVERLAPS (%s, %s)
                            """, (self.id, date, date))
        sal = self.env.cr.fetchall()
        if len(sal):
            return sal[0][0]
        else:
            return 0

    def _get_document_folder(self):
        if not self.folder_id:
            folder = self.env['documents.folder'].create({
                'name': self.complete_name.replace(' ', '_') + '_' + self.registration_number,
                'parent_folder_id': self.company_id.documents_hr_folder.id,
            })
            self.folder_id = folder.id
        return self.folder_id

    def set_required_field(self, field_name):
        raise UserError(_('The following fields are required: %s.') % field_name)

    def set_gender_format(self, gender):
        if gender == 'male':
            return 'H'
        if gender == 'female':
            return 'M'

    def set_city(self):
        if not self.place_of_birth:
            return self.set_required_field(self.fields_get()['place_of_birth']['string'])
        else:
            if self.place_of_birth.country_id.code != 'MX':
                return 'NACIDO EXTRANJERO'
            else:
                return self.place_of_birth.name

    def get_rfc_curp_data(self):
        kwargs = {
            "complete_name": self.name if self.name else self.set_required_field(self.fields_get()['name']['string']),
            "last_name": self.last_name if self.last_name else self.set_required_field(self.fields_get()['last_name']['string']),
            "mother_last_name": self.mothers_last_name if self.mothers_last_name else None,
            "birth_date": self.birthday.strftime('%d-%m-%Y') if self.birthday else self.set_required_field(self.fields_get()['birthday']['string']),
            "gender": self.set_gender_format(self.gender) if self.gender else self.set_required_field(self.fields_get()['gender']['string']),
            "city": self.set_city(),
            "state_code": None
        }
        curp = GenerateCURP(**kwargs)
        rfc = GenerateRFC(**kwargs)
        self.identification_id = curp.data
        self.rfc = rfc.data

    @api.depends('name', 'last_name', 'mothers_last_name')
    @api.onchange('complete_name')
    def _compute_complete_name(self):
        for employee in self:
            name = '%s %s %s' % (
                employee.name.upper() if employee.name else '',
                employee.last_name.upper() if employee.last_name else '',
                employee.mothers_last_name.upper() if employee.mothers_last_name else '')
            employee.complete_name = name

    @api.model
    def create(self, vals):

        if vals.get('registration_number') and vals.get('registration_number') == '/':
            vals['registration_number'] = self.env['ir.sequence'].next_by_code('hr.employee')
        res = super(Employee, self).create(vals)
        
        if vals.get('cost_center_id'):
            vals = {
                'employee_id': res.id,
                'type': 'cost_center',
                'date': fields.Date.today(),
                'new_cost_center_id': vals['cost_center_id'],
            }
            self.env['history.changes.employee'].create(vals)

        # Generate folder
        res.folder_id = res._get_document_folder()
        if res.position_id:
            res.position_id.change_employees(employee=res)
        return res

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('complete_name', operator, name), ('registration_number', operator, name)]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    def name_get(self):
        result = []
        for employee in self:
            name = '%s %s %s' % (
                employee.name.upper() if employee.name else '',
                employee.last_name.upper() if employee.last_name else '',
                employee.mothers_last_name.upper() if employee.mothers_last_name else '')
            result.append((employee.id, name))
        return result

    def unlink(self):
        partner = self.mapped('address_home_id')
        super(Employee, self).unlink()
        return partner.unlink()


class EmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    is_manager = fields.Boolean(string="Is Manager")
    place_of_birth = fields.Many2one('res.country.state', readonly=True)
    complete_name = fields.Char(readonly=True)
    last_name = fields.Char(readonly=True)
    position_id = fields.Many2one("hr.job.position", string="Position")
    mothers_last_name = fields.Char(readonly=True)
    family_medicine_unit = fields.Char(readonly=True)
    blood_type = fields.Selection([
        ('O-', 'O-'),
        ('O+', 'O+'),
        ('A-', 'A-'),
        ('A+', 'A+'),
        ('B-', 'B-'),
        ('B+', 'B+'),
        ('AB-', 'AB-'),
        ('AB+', 'AB+'),
    ], readonly=True)
    salary_type = fields.Selection([('0', 'Fixed'), ('1', 'Variable'), ('2', 'Mixed')], readonly=True)
    working_day_week = fields.Selection([('0', 'Complete'),
                                         ('1', 'Work one day'),
                                         ('2', 'Mixed'),
                                         ('3', 'Work three days'),
                                         ('4', 'Work four days'),
                                         ('5', 'Work five days'),
                                         ('6', 'Reduced working hours'),
                                         ], readonly=True)
    type_working_day = fields.Selection([
        ('01', 'Daytime'),
        ('02', 'Nightly'),
        ('03', 'Mixed'),
        ('04', 'Per hour'),
        ('05', 'Reduced'),
        ('06', 'Continued'),
        ('07', 'Departure'),
        ('08', 'By turns'),
        ('99', 'Another day'),
    ], readonly=True)
    type_worker = fields.Selection([('1', 'Job permanent'),
                                    ('2', 'Job Ev. Town'),
                                    ('3', 'Job Ev. Construction'),
                                    ('4', 'Eventual from the field'),
                                    ], readonly=True)
    deceased = fields.Boolean(readonly=True)
    syndicalist = fields.Boolean(readonly=True)
    cost_center_id = fields.Many2one('hr.cost.center', readonly=True)
    payment_holidays_bonus = fields.Selection([('0', 'Pay at the expiration of the vacation'),
                                               ('1', 'Pay with the enjoyment of the holidays'),
                                               ('2', 'Advance payment to enjoy the holidays'),
                                               ], readonly=True)
    pay_extra_hours = fields.Boolean(readonly=True)
    employer_register_id = fields.Many2one('res.employer.register', readonly=True)
    antiquity_id = fields.Many2one('hr.table.antiquity', readonly=True)
    folder_id = fields.Many2one('documents.folder', readonly=True)
    isr_adjustment = fields.Boolean(readonly=True)
    personal_savings_bank = fields.Float(readonly=True)
    resistance_bottom_new = fields.Float(readonly=True)
    fixed_resistance_background = fields.Float(readonly=True)

    salary_reduction = fields.Boolean(string="Salary reduction?", help="Employee with definitive salary reduction.")
    previous_salary = fields.Float("Previous salary")

    pilot_tab_id = fields.Many2one('hr.pilot.tab', string='Pilor Tab')
    pilot_category = fields.Selection([
        ('captains', 'Captains'),
        ('official', 'First Official'),
    ], string="Pilot Category")


class bankDetailsEmployee(models.Model):
    _name = "bank.account.employee"
    _description = 'bank_id'

    employee_id = fields.Many2one('hr.employee', "Employee", required=False, ondelete='cascade')
    bank_id = fields.Many2one('res.bank', "Bank", required=True)
    beneficiary = fields.Char("Beneficiary", copy=False, related='employee_id.name', required=False)
    bank_account = fields.Char("Bank account", copy=False, required=False)
    reference = fields.Char("Reference", copy=False, required=False)
    location_branch = fields.Char("Location / Branch")
    account_type = fields.Selection([
        ('001', 'Account'),
        ('040', 'CLABE'),
        ('003', 'Debit'),
        ('099', 'Check'),
    ], "Account type", required=False)
    employee_code = fields.Char("Employee code", copy=False, required=False)

    _sql_constraints = [
        ('bank_account_uniq', 'unique(bank_account)', "There is already a bank account with this number.!"),
    ]

    def name_get(self):
        result = []
        for account in self:
            name = '%s - %s' % (account.bank_id.name, account.bank_account)
            result.append((account.id, name))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('bank_id.name', operator, name), ('bank_account', operator, name)]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
   

class hrFamilyBurden(models.Model):
    _name = "hr.family.burden"
    _description = 'Family Burden'

    employee_id = fields.Many2one('hr.employee', "Employee", required=False)
    name = fields.Char("Name", copy=False, required=True)
    birthday = fields.Date("Birthday", required=True)
    age = fields.Integer("Age", compute='calculate_age_compute')
    relationship_id = fields.Many2one("hr.relationship", "Relationship", required=True)

    @api.depends('birthday')
    def calculate_age_compute(self):
        for family in self:
            if family.birthday:
                family.age = calculate_age(family.birthday)
            else:
                family.age = False


class hrRelationship(models.Model):
    _name = "hr.relationship"

    name = fields.Char("Name", copy=False, required=True)
