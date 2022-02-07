# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime, date, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPTUEmployees(models.TransientModel):
    _name = 'hr.ptu.employees'
    _description = 'Select Employees for all selected employees'

    def default_all_employees(self):
        ptu_id = self.env[self.env.context['active_model']].browse(self.env.context['active_id'])
        employee_out = ptu_id.line_ids.mapped('employee_id')
        if employee_out:
            employee_out_id = "employee.id NOT IN %s" % (employee_out._ids,) if len(
                employee_out) > 1 else "employee.id <> %s" % employee_out.id
        else:
            employee_out_id = 'TRUE'
        year = ptu_id.name
        date_start = fields.Date.to_string(date(year, 1, 1))
        date_end = fields.Date.to_string(date(year, 12, 31))

        days_60 = """
                    AND 
                        (
                            (contract.date_end IS NOT NULL AND contract.date_end <= '%s' AND 
                            (
                                (contract.date_start < '%s' AND (contract.date_end - DATE '%s' + 1) >= 60) 
                                OR 
                                (contract.date_start >= '%s' AND (contract.date_end - contract.date_start + 1) >= 60)
                            ))
                        OR
                            ((contract.date_end IS NULL OR contract.date_end > '%s') AND 
                            (
                                (contract.date_start < '%s' AND (DATE '%s' - DATE '%s' + 1) >= 60) 
                                OR 
                                (contract.date_start >= '%s' AND (DATE '%s' - contract.date_start + 1) >= 60)
                            ))
                        )
                """ % (date_end, date_start, date_start, date_start, date_end, date_start, date_end, date_start, date_start,
            date_end)

        query = """
                    SELECT
                        employee.id
                    FROM hr_employee                        AS employee
                    JOIN hr_contract contract               ON contract.employee_id = employee.id
                    JOIN hr_payroll_structure_type struct   ON contract.structure_type_id = struct.id
                    WHERE employee.is_manager IS NOT TRUE
                        AND contract.state IN ('open', 'close')
                        AND contract.contracting_regime = '02'
                        AND (struct.trusted_staff IS NOT TRUE OR 
                        (struct.trusted_staff IS TRUE AND contract.wage >= %s))
                        AND ((contract.date_start, contract.date_end) OVERLAPS (%s, %s)
                        OR (contract.date_end IS NULL AND (contract.date_start, CURRENT_DATE) OVERLAPS (%s, %s)))
                        AND 
                """ + employee_out_id + days_60
        self.env.cr.execute(query, (ptu_id.highest_salary, date_start, date_end, date_start, date_end))
        sal = self.env.cr.fetchall()
        ids_sal = [item for t in sal for item in t]
        return self.env['hr.employee'].browse(ids_sal)

    ptu_id = fields.Many2one("hr.ptu", string="PTU", required=True)
    employee_ids = fields.Many2many('hr.employee', 'hr_employees_ptu_group_rel', 'ptu_id', 'employee_id', 'Employees',
                                    required=True, default=default_all_employees)

    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')

    @api.onchange('ptu_id')
    def onchange_ptu(self):
        ptu_id = self.env[self.env.context['active_model']].browse(self.env.context['active_id'])
        employee_out = ptu_id.line_ids.mapped('employee_id')
        if employee_out:
            employee_out_id = "employee.id NOT IN %s" % (employee_out._ids,) if len(
                employee_out) > 1 else "employee.id <> %s" % employee_out.id
        else:
            employee_out_id = 'TRUE'
        year = ptu_id.name
        date_start = fields.Date.to_string(date(year, 1, 1))
        date_end = fields.Date.to_string(date(year, 12, 31))

        days_60 = """
                    AND 
                        (
                            (contract.date_end IS NOT NULL AND contract.date_end <= '%s' AND 
                            (
                                (contract.date_start < '%s' AND (contract.date_end - DATE '%s' + 1) >= 60) 
                                OR 
                                (contract.date_start >= '%s' AND (contract.date_end - contract.date_start + 1) >= 60)
                            ))
                        OR
                            ((contract.date_end IS NULL OR contract.date_end > '%s') AND 
                            (
                                (contract.date_start < '%s' AND (DATE '%s' - DATE '%s' + 1) >= 60) 
                                OR 
                                (contract.date_start >= '%s' AND (DATE '%s' - contract.date_start + 1) >= 60)
                            ))
                        )
                """ % (
        date_end, date_start, date_start, date_start, date_end, date_start, date_end, date_start, date_start,
        date_end)

        query = """
                    SELECT
                        employee.id
                    FROM hr_employee                        AS employee
                    JOIN hr_contract contract               ON contract.employee_id = employee.id
                    JOIN hr_payroll_structure_type struct   ON contract.structure_type_id = struct.id
                    WHERE employee.is_manager IS NOT TRUE
                        AND contract.state IN ('open', 'close')
                        AND contract.contracting_regime = '02'
                        AND (struct.trusted_staff IS NOT TRUE OR 
                        (struct.trusted_staff IS TRUE AND contract.wage >= %s))
                        AND ((contract.date_start, contract.date_end) OVERLAPS (%s, %s)
                        OR (contract.date_end IS NULL AND (contract.date_start, CURRENT_DATE) OVERLAPS (%s, %s)))
                        AND 
                """ + employee_out_id + days_60

        self.env.cr.execute(query, (ptu_id.highest_salary, date_start, date_end, date_start, date_end))
        sal = self.env.cr.fetchall()
        ids_sal = [item for t in sal for item in t]
        return {'domain': {'employee_ids': [('id', 'in', ids_sal)]}}

    def save(self):
        self.write({'state': 'done'})
        employees = self.with_context(active_test=False).employee_ids
        if not employees:
            raise UserError(_("You must select employee(s) to generate ptu(s)."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.ptu.employees',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
            'context': self.env.context
        }

    def compute_ptu(self, options):
        contract_out = self.ptu_id.line_ids.mapped("contract_id")
        query = """
                    SELECT
                        SUM(line.amount)                        AS salary,
                        contract.id                             AS contract_id,
                        COALESCE(SUM(work_days.leaves), 0)      AS leaves,
                        payslip_last.amount                     AS amount_last,
                        payslip_last.year                       AS year_last
                    FROM hr_payslip slip
                    JOIN hr_contract contract                   ON slip.contract_id = contract.id
                    JOIN hr_payslip_line line                   ON line.slip_id = slip.id AND line.code = 'P001'
                    JOIN hr_payroll_structure struct            ON struct.id = slip.struct_id
                    JOIN hr_payroll_structure_type struct_type  ON struct_type.id = struct.type_id
                    
                    JOIN (SELECT 
                            days.payslip_id,
                            SUM(CASE
                                WHEN work_type.is_leave IS TRUE 
                                AND work_type.code NOT IN ('F02', 'F03', 'F06')
                                AND work_type.type_leave NOT IN ('holidays', 'personal_days') THEN days.number_of_days
                                ELSE 0
                            END) leaves
                        FROM hr_payslip_worked_days days
                        JOIN hr_work_entry_type work_type       ON days.work_entry_type_id = work_type.id
                        GROUP BY days.payslip_id
                    ) work_days
                    ON work_days.payslip_id = slip.id
                    
                    LEFT JOIN (SELECT
                            SUM(line_p.amount)                  AS amount,
                            COUNT(DISTINCT payslip.year)        AS year,
                            line_p.contract_id                  AS contract_id
                        FROM hr_payslip payslip
                        JOIN hr_payslip_line line_p             ON line_p.slip_id = payslip.id AND line_p.code = 'P001'
                        WHERE
                            payslip.year IN %s
                        GROUP BY line_p.contract_id 
                    ) payslip_last
                    ON payslip_last.contract_id = contract.id
                    WHERE slip.year = %s
                        AND contract.contracting_regime = '02'
                        AND contract.state IN ('open', 'close')
                        AND slip.state = 'done'
                        AND (struct_type.trusted_staff IS NOT TRUE OR 
                        (struct_type.trusted_staff IS TRUE AND contract.wage >= %s))
                """
        group_by = """ GROUP BY contract.id, payslip_last.amount, payslip_last.year """
        limit = " LIMIT %s" % options.get('limit')
        last_years = (self.ptu_id.name - 1, self.ptu_id.name - 2, self.ptu_id.name - 3)

        if contract_out:
            query += " AND contract.id not in %s" % (contract_out._ids,) if len(
                contract_out) > 1 else "contract.id <> %s" % contract_out.id

        self.env.cr.execute(query + group_by + limit, (last_years, self.ptu_id.name, self.ptu_id.highest_salary))
        res = self.env.cr.dictfetchall()

        date_start = date(self.ptu_id.name, 1, 1)
        date_end = date(self.ptu_id.name, 12, 31)
        lines = []
        for contract in res:
            contract_id = self.env['hr.contract'].browse(contract['contract_id'])

            contract_date = contract_id.previous_contract_date if contract_id.previous_contract_date else contract_id.date_start
            date_from = date_start
            date_to = date_end
            if contract_date > date_start:
                date_from = contract_date
            if contract_id.date_end and contract_id.date_end < date_end:
                date_to = contract_id.date_end
            days_for_year = (date_to - date_from).days + 1
            days_work = days_for_year - contract.get('leaves', 0)
            if days_work < 60:
                continue
            if contract['salary'] == None or contract['salary'] == 0:
                continue
            limit = contract_id.wage * 3
            if contract['amount_last'] and contract['year_last']:
                amount_last = contract['amount_last'] / contract['year_last']
                limit = amount_last if amount_last > limit else limit

            line = self.env['hr.ptu.line'].create({
                'ptu_id': self.ptu_id.id,
                'contract_id': contract['contract_id'],
                'total_days': days_work,
                'total_salary': contract['salary'],
                'limit': limit
            })
            lines.append(line.id)

        return {
            'ids': lines,
            'messages': [],
            'continues': 1 if len(lines) else 0,
        }
