# -*- coding: utf-8 -*-

import io
import base64
import zipfile

from xlrd import open_workbook
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

try:
    import xlrd
    try:
        from xlrd import xlsx
    except ImportError:
        xlsx = None
except ImportError:
    xlrd = xlsx = None


class MassiveEmployeeModifcation(models.TransientModel):
    _name = "massive.employee.modification"
    _description = "Wizard for massive employee modification"

    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company)
    change_fields = fields.Selection([
        ('department', 'Department'),
        ('job', 'Job'),
        # ('cost_center', 'Cost Center'),
        ('salary', 'Salary'),
        ('seniority_premium', 'Seniority Premium'),
        # ('workplace', 'Workplace'),
    ], string="Field Change", required=True)
    file_id = fields.Many2many('ir.attachment', string='File excel', required=False)
    date = fields.Date(string="Date", default=fields.Date.today())

    def generate_change(self):
        if not self.file_id:
            raise UserError(_("There is no EXCEL file"))
        file = self.file_id[0]
        datafile = base64.b64decode(file.datas)
        book = open_workbook(file_contents=datafile)

        if self.change_fields == 'salary':
            return self._change_salary(book)
        if self.change_fields == 'department':
            return self._change_department(book)
        if self.change_fields == 'job':
            return self._change_job(book)
        # if self.change_fields == 'cost_center':
        #     return self._change_cost_center(book)
        if self.change_fields == 'seniority_premium':
            return self._change_seniority_premium(book)
        # if self.change_fields == 'workplace':
        #     return self._change_workplace(book)

    def _create_history(self, type, employee_id, date, record, contract_id=None):
        vals = {
            'contract_id': contract_id.id if contract_id else None,
            'employee_id': employee_id.id,
            'type': type,
            'date': date,
        }
        if record._name == 'hr.department':
            vals['department_id'] = employee_id.department_id.id
            vals['new_department_id'] = record.id
            for contract in self.env['hr.contract'].search([('employee_id','=',employee_id.id),('state','in',['draft','open'])]):
                contract.write({'department_id': record.id})
            employee_id.write({'department_id': record.id})
        if record._name == 'hr.job.position':
            vals['position_id'] = employee_id.position_id.id
            vals['new_position_id'] = record.id
            vals['job_id'] = employee_id.job_id.id
            vals['new_job_id'] = record.job_id.id
            # change position
            employee_id.position_id.change_employees(date_end=date + relativedelta(days=-1))
            record.change_employees(employee=employee_id, date_end=date + relativedelta(days=-1))
            employee_id.write({'job_id': record.job_id.id, 'position_id': record.id})
            if contract_id:
                contract_id.write({'job_id': record.job_id.id})
        # if record._name == 'hr.workplace':
        #     vals['workplace_id'] = employee_id.workplace_center.id
        #     vals['new_workplace_id'] = record.id
        #     employee_id.write({'workplace_center': record.id})
        # if record._name == 'hr.cost.center':
        #     vals['cost_center_id'] = employee_id.cost_center_id.id
        #     vals['new_cost_center_id'] = record.id
        #     employee_id.write({'cost_center_id': record.id})
        return self.env['history.changes.employee'].create(vals)

    def _change_department(self, book):
        Histories = self.env['history.changes.employee']

        sheet = book.sheet_by_index(0)
        msg_not_found = [_('\nNo results were found for: \n')]
        msg_required = [_('\nThe following fields are mandatory: \n')]
        msg_invalidad_format = [_('\nInvalid format: \n')]

        list_vals = []
        for row in range(1, sheet.nrows):
            if sheet.cell_value(row, 0):
                try:
                    enrollment = float(sheet.cell_value(row, 0))
                    enrollment = int(enrollment)
                except:
                    enrollment = sheet.cell_value(row, 0)

                employee_id = self.env['hr.employee'].search([('registration_number', '=', str(enrollment)), ('company_id', '=', self.company_id.id)])
                if not employee_id:
                    msg_not_found.append(_('Employee registration %s in the row %s. \n') % (enrollment, str(row + 1)))

                department_id = False
                if sheet.cell_value(row, 1):
                    department_id = self.env['hr.department'].search([('name', '=', str(sheet.cell_value(row, 1)).upper())])
                if not department_id:
                    msg_required.append(_('The name of the department in the row %s not exist. \n') % (str(row + 1)))

                # ~ contract_id = None
                # ~ if sheet.ncols - 1 >= 2:
                    # ~ if sheet.cell_value(row, 2):
                        # ~ contract_id = self.env['hr.contract'].search([('code', '=', str(sheet.cell_value(row, 2))), ('company_id', '=', self.company_id.id)])
                    # ~ if not contract_id:
                        # ~ msg_required.append(_('The code of the contract in the row %s not exist. \n') % (str(row + 1)))
                    # ~ if contract_id.employee_id != employee_id:
                        # ~ msg_required.append(_('the employee in row %s does not belong to the specified contract. \n') % (str(row + 1)))

                list_vals.append(('department', employee_id, self.date, department_id))

        msgs = []
        if len(msg_required) > 1:
            msgs += msg_required
        if len(msg_not_found) > 1:
            msgs += msg_not_found
        if len(msg_invalidad_format) > 1:
            msgs += msg_invalidad_format
        if len(msgs):
            msg_raise = "".join(msgs)
            raise UserError(_(msg_raise))
        
        for value in list_vals:
            history = self._create_history(value[0], value[1], value[2], value[3])
            Histories |= history
        return {
            'name': _('History Changes Employees'),
            'domain': [('id', 'in', Histories.ids)],
            'res_model': 'history.changes.employee',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'limit': 80,
        }

    def _change_job(self, book):
        Histories = self.env['history.changes.employee']

        sheet = book.sheet_by_index(0)
        msg_not_found = [_('\nNo results were found for: \n')]
        msg_required = [_('\nThe following fields are mandatory: \n')]
        msg_invalidad_format = [_('\nInvalid format: \n')]
        msg_not_available = [_('\nThe selected place is not available: \n')]

        list_vals = []
        for row in range(1, sheet.nrows):
            if sheet.cell_value(row, 0):
                try:
                    enrollment = float(sheet.cell_value(row, 0))
                    enrollment = int(enrollment)
                except:
                    enrollment = sheet.cell_value(row, 0)

                employee_id = self.env['hr.employee'].search([('registration_number', '=', str(enrollment)), ('company_id', '=', self.company_id.id)])
                if not employee_id:
                    msg_not_found.append(_('Employee registration %s in the row %s. \n') % (enrollment, str(row + 1)))

                job_id = False
                if sheet.cell_value(row, 1):
                    job_id = self.env['hr.job'].search([('name', '=', str(sheet.cell_value(row, 1)).upper())])
                if not job_id:
                    msg_required.append(_('The name of the job in the row %s not exist. \n') % (str(row + 1)))

                position_id = False
                if sheet.cell_value(row, 2):
                    position_id = self.env['hr.job.position'].search([('name', '=', str(sheet.cell_value(row, 2)).upper()), ('job_id', '=', job_id.id)])
                if not position_id:
                    msg_required.append(_('The name of the position in the row %s not exist. \n') % (str(row + 1)))               
                if position_id and position_id.employee_id:
                    msg_not_available.append(_('The position in row %s is taken. \n') % (str(row + 1)))

                contract_id = None
                if sheet.ncols - 1 >= 3:
                    if sheet.cell_value(row, 3):
                        contract_id = self.env['hr.contract'].search([('code', '=', str(sheet.cell_value(row, 3))), ('company_id', '=', self.company_id.id)])
                    if not contract_id:
                        msg_required.append(_('The code of the contract in the row %s not exist. \n') % (str(row + 1)))
                    if contract_id and contract_id.employee_id != employee_id:
                        msg_required.append(_('the employee in row %s does not belong to the specified contract. \n') % (str(row + 1)))

                list_vals.append(('position', employee_id, self.date, job_id, contract_id, position_id))

        msgs = []
        if len(msg_required) > 1:
            msgs += msg_required
        if len(msg_not_found) > 1:
            msgs += msg_not_found
        if len(msg_invalidad_format) > 1:
            msgs += msg_invalidad_format
        if len(msg_not_available) > 1:
            msgs += msg_not_available
        if len(msgs):
            msg_raise = "".join(msgs)
            raise UserError(_(msg_raise))
        
        if self.date > fields.Date.today():
            raise UserError(_('The change date must be less than today.'))
        for value in list_vals:
            history = self._create_history(value[0], value[1], value[2], value[5], contract_id=value[4])
            Histories |= history

        return {
            'name': _('History Changes Employees'),
            'domain': [('id', 'in', Histories.ids)],
            'res_model': 'history.changes.employee',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'limit': 80,
        }

    def _change_cost_center(self, book):
        Histories = self.env['history.changes.employee']

        sheet = book.sheet_by_index(0)
        msg_not_found = [_('\nNo results were found for: \n')]
        msg_required = [_('\nThe following fields are mandatory: \n')]
        msg_invalidad_format = [_('\nInvalid format: \n')]

        list_vals = []
        for row in range(1, sheet.nrows):
            if sheet.cell_value(row, 0):
                try:
                    enrollment = float(sheet.cell_value(row, 0))
                    enrollment = int(enrollment)
                except:
                    enrollment = sheet.cell_value(row, 0)

                employee_id = self.env['hr.employee'].search([('registration_number', '=', str(enrollment)), ('company_id', '=', self.company_id.id)])
                if not employee_id:
                    msg_not_found.append(_('Employee registration %s in the row %s. \n') % (enrollment, str(row + 1)))

                cost_center_id = False
                if sheet.cell_value(row, 1):
                    cost_center_id = self.env['hr.cost.center'].search([('name', '=', str(sheet.cell_value(row, 1)).upper())])
                if not cost_center_id:
                    msg_required.append(_('The name of the cost center in the row %s not exist. \n') % (str(row + 1)))

                contract_id = None
                if sheet.ncols >= 3 and sheet.cell_value(row, 2):
                    contract_id = self.env['hr.contract'].search([('code', '=', str(sheet.cell_value(row, 2))), ('company_id', '=', self.company_id.id)])
                    if not contract_id:
                        msg_required.append(_('The code of the contract in the row %s not exist. \n') % (str(row + 1)))
                    if contract_id and contract_id.employee_id != employee_id:
                        msg_required.append(_('the employee in row %s does not belong to the specified contract. \n') % (str(row + 1)))

                list_vals.append(('cost_center', employee_id, self.date, cost_center_id, contract_id))

        msgs = []
        if len(msg_required) > 1:
            msgs += msg_required
        if len(msg_not_found) > 1:
            msgs += msg_not_found
        if len(msg_invalidad_format) > 1:
            msgs += msg_invalidad_format
        if len(msgs):
            msg_raise = "".join(msgs)
            raise UserError(_(msg_raise))
        for value in list_vals:
            history = self._create_history(value[0], value[1], value[2], value[3], contract_id=value[4])
            Histories |= history

        return {
            'name': _('History Changes Employees'),
            'domain': [('id', 'in', Histories.ids)],
            'res_model': 'history.changes.employee',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'limit': 80,
        }

    def _change_workplace(self, book):
        Histories = self.env['history.changes.employee']

        sheet = book.sheet_by_index(0)
        msg_not_found = [_('\nNo results were found for: \n')]
        msg_required = [_('\nThe following fields are mandatory: \n')]
        msg_invalidad_format = [_('\nInvalid format: \n')]

        list_vals = []
        for row in range(1, sheet.nrows):
            if sheet.cell_value(row, 0):
                try:
                    enrollment = float(sheet.cell_value(row, 0))
                    enrollment = int(enrollment)
                except:
                    enrollment = sheet.cell_value(row, 0)

                employee_id = self.env['hr.employee'].search([('registration_number', '=', str(enrollment)), ('company_id', '=', self.company_id.id)])
                if not employee_id:
                    msg_not_found.append(_('Employee registration %s in the row %s. \n') % (enrollment, str(row + 1)))

                workplace_id = False
                if sheet.cell_value(row, 1):
                    workplace_id = self.env['hr.workplace'].search([('name', '=', str(sheet.cell_value(row, 1)).upper())])
                if not workplace_id:
                    msg_required.append(_('The name of the cost center in the row %s not exist. \n') % (str(row + 1)))

                contract_id = None
                if sheet.ncols >= 3 and sheet.cell_value(row, 2):
                    contract_id = self.env['hr.contract'].search([('code', '=', str(sheet.cell_value(row, 2))), ('company_id', '=', self.company_id.id)])
                    if not contract_id:
                        msg_required.append(_('The code of the contract in the row %s not exist. \n') % (str(row + 1)))
                    if contract_id and contract_id.employee_id != employee_id:
                        msg_required.append(_('the employee in row %s does not belong to the specified contract. \n') % (str(row + 1)))

                list_vals.append(('workplace', employee_id, self.date, workplace_id, contract_id))

        msgs = []
        if len(msg_required) > 1:
            msgs += msg_required
        if len(msg_not_found) > 1:
            msgs += msg_not_found
        if len(msg_invalidad_format) > 1:
            msgs += msg_invalidad_format
        if len(msgs):
            msg_raise = "".join(msgs)
            raise UserError(_(msg_raise))
        for value in list_vals:
            history = self._create_history(value[0], value[1], value[2], value[3], contract_id=value[4])
            Histories |= history

        return {
            'name': _('History Changes Employees'),
            'domain': [('id', 'in', Histories.ids)],
            'res_model': 'history.changes.employee',
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'limit': 80,
        }

    def _change_salary(self, book):
        EmployeeAffiliateMovements = self.env['hr.employee.affiliate.movements']
        SalaryChange = self.env['contract.salary.change.line']

        sheet = book.sheet_by_index(0)
        msg_not_found = [_('\nNo results were found for: \n')]
        msg_required = [_('\nThe following fields are mandatory: \n')]
        msg_invalidad_format = [_('\nInvalid format: \n')]

        list_vals = []
        for row in range(1, sheet.nrows):
            if sheet.cell_value(row, 0):
                try:
                    enrollment = float(sheet.cell_value(row, 0))
                    enrollment = int(enrollment)
                except:
                    enrollment = sheet.cell_value(row, 0)

                employee_id = self.env['hr.employee'].search([('registration_number', '=', str(enrollment)), ('company_id', '=', self.company_id.id)])
                if not employee_id:
                    msg_not_found.append(_('Employee registration %s in the row %s. \n') % (enrollment, str(row + 1)))

                salary = False
                if sheet.cell_value(row, 1):
                    salary = sheet.cell_value(row, 1)

                contract_id = None
                if sheet.ncols >= 3 and sheet.cell_value(row, 2):
                    contract_id = self.env['hr.contract'].search([('code', '=', str(sheet.cell_value(row, 2))), ('company_id', '=', self.company_id.id)])
                    if not contract_id:
                        msg_required.append(_('The code of the contract in the row %s not exist. \n') % (str(row + 1)))
                    if contract_id and contract_id.employee_id != employee_id:
                        msg_required.append(_('the employee in row %s does not belong to the specified contract. \n') % (str(row + 1)))


                list_vals.append(('salary', employee_id, self.date, salary, contract_id))

        msgs = []
        if len(msg_required) > 1:
            msgs += msg_required
        if len(msg_not_found) > 1:
            msgs += msg_not_found
        if len(msg_invalidad_format) > 1:
            msgs += msg_invalidad_format
        if len(msgs):
            msg_raise = "".join(msgs)
            raise UserError(_(msg_raise))
        for value in list_vals:
            diferents = value[4].wage != value[3]

            # Change contract
            value[4].write({
                'wage': value[3],
                'daily_salary': value[3] / self.env.company.days_factor if value[3] else False,
            })
            value[4].integral_salary = value[4]._calculate_integral_salary()
            value[4].sdi = value[4].integral_salary + value[4].variable_salary
            limit_imss = value[4].company_id.uma * value[4].company_id.general_uma
            if value[4].sdi > limit_imss:
                value[4].sbc = limit_imss
            else:
                value[4].sbc = value[4].sdi

            movements = self.env['hr.employee.affiliate.movements'].search([
                ('contract_id', '=', value[4].id),
                ('type', '=', '08'),
            ], limit=1)

            if not movements:
                EmployeeAffiliateMovements.create({
                    'contract_id': value[4].id,
                    'employee_id': value[1].id,
                    'company_id': value[4].company_id.id,
                    'type': '08',
                    'date': value[2],
                    'wage': value[3],
                    'sbc': value[4].sbc,
                    'salary': value[4].sdi,
                })

            if diferents:
                EmployeeAffiliateMovements.create({
                    'contract_id': value[4].id,
                    'employee_id': value[1].id,
                    'company_id': value[4].company_id.id,
                    'type': '07',
                    'date': value[2],
                    'wage': value[3],
                    'salary': value[4].sdi,
                    'sbc': value[4].sbc,
                })

            change_salary = SalaryChange.search([
                ('contract_id', '=', value[4].id),
                ('wage', '=', value[4].wage),
                ('daily_salary', '=', value[4].daily_salary),
                ('sdi', '=', value[4].sdi),
                ('sbc', '=', value[4].sbc),
                ('integrated_salary', '=', value[4].integral_salary),
                ('seniority_premium', '=', value[4].seniority_premium),
                ('date_end', '=', False),
            ])
            previous_change = SalaryChange.search([('date_end', '=', False), ('contract_id', '=', value[4].id)])  # Previous Record
            if not change_salary:
                previous_change.write({'date_end': value[2] + relativedelta(days=-1)})
                SalaryChange.create({
                    'contract_id': value[4].id,
                    'wage': value[4].wage,
                    'daily_salary': value[4].daily_salary,
                    'sdi': value[4].sdi,
                    'sbc': value[4].sbc,
                    'integrated_salary': value[4].integral_salary,
                    'seniority_premium': value[4].seniority_premium,
                    'date_start': value[2],
                })

        return True

    def _change_seniority_premium(self, book):
        SalaryChange = self.env['contract.salary.change.line']

        sheet = book.sheet_by_index(0)
        msg_not_found = [_('\nNo results were found for: \n')]
        msg_required = [_('\nThe following fields are mandatory: \n')]
        msg_invalidad_format = [_('\nInvalid format: \n')]

        list_vals = []
        for row in range(1, sheet.nrows):
            if sheet.cell_value(row, 0):
                try:
                    enrollment = float(sheet.cell_value(row, 0))
                    enrollment = int(enrollment)
                except:
                    enrollment = sheet.cell_value(row, 0)

                employee_id = self.env['hr.employee'].search([('registration_number', '=', str(enrollment)), ('company_id', '=', self.company_id.id)])
                if not employee_id:
                    msg_not_found.append(_('Employee registration %s in the row %s. \n') % (enrollment, str(row + 1)))

                salary = False
                if sheet.cell_value(row, 1):
                    salary = sheet.cell_value(row, 1)

                contract_id = None
                if sheet.ncols >= 3 and sheet.cell_value(row, 2):
                    contract_id = self.env['hr.contract'].search([('code', '=', str(sheet.cell_value(row, 2))), ('company_id', '=', self.company_id.id)])
                    if not contract_id:
                        msg_required.append(_('The code of the contract in the row %s not exist. \n') % (str(row + 1)))
                    if contract_id and contract_id.employee_id != employee_id:
                        msg_required.append(_('the employee in row %s does not belong to the specified contract. \n') % (str(row + 1)))


                list_vals.append(('seniority_premium', employee_id, self.date, salary, contract_id))

        msgs = []
        if len(msg_required) > 1:
            msgs += msg_required
        if len(msg_not_found) > 1:
            msgs += msg_not_found
        if len(msg_invalidad_format) > 1:
            msgs += msg_invalidad_format
        if len(msgs):
            msg_raise = "".join(msgs)
            raise UserError(_(msg_raise))
        for value in list_vals:
            # Change contract
            value[4].write({'seniority_premium': value[3]})

            change_salary = SalaryChange.search([
                ('contract_id', '=', value[4].id),
                ('wage', '=', value[4].wage),
                ('daily_salary', '=', value[4].daily_salary),
                ('sdi', '=', value[4].sdi),
                ('sbc', '=', value[4].sbc),
                ('integrated_salary', '=', value[4].integral_salary),
                ('seniority_premium', '=', value[4].seniority_premium),
                ('date_end', '=', False),
            ])
            previous_change = SalaryChange.search([('date_end', '=', False), ('contract_id', '=', value[4].id)])  # Previous Record
            if not change_salary:
                previous_change.write({'date_end': value[2] + relativedelta(days=-1)})
                SalaryChange.create({
                    'contract_id': value[4].id,
                    'wage': value[4].wage,
                    'daily_salary': value[4].daily_salary,
                    'sdi': value[4].sdi,
                    'sbc': value[4].sbc,
                    'integrated_salary': value[4].integral_salary,
                    'seniority_premium': value[4].seniority_premium,
                    'date_start': value[2],
                })

        return True
