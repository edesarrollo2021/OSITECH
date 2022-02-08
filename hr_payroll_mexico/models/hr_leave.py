# -*- coding: utf-8 -*-

import logging
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from odoo import api, fields, models, SUPERUSER_ID, tools, _
from odoo.tools import float_compare
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)

class HolidaysRequest(models.Model):
    _inherit = "hr.leave"

    out_of_date = fields.Boolean(string="Out of Date", default=False)
    payroll_period_id = fields.Many2one('hr.payroll.period', string='Payroll Period', tracking=True)

    @api.constrains('out_of_date', 'payroll_period_id')
    def validate_out_of_date(self):
        for record in self:
            if record.out_of_date and record.payroll_period_id:
                if record.payroll_period_id.date_start <= record.request_date_from:
                    raise ValidationError(_("You must select a period prior to the date of absence."))

    def _create_resource_leave(self):
        """
        Add a resource leave in calendars of contracts running at the same period.
        This is needed in order to compute the correct number of hours/days of the leave
        according to the contract's calender.
        """
        resource_leaves = super(HolidaysRequest, self)._create_resource_leave()
        for resource_leave in resource_leaves:
            resource_leave.out_of_date = resource_leave.holiday_id.out_of_date
            if resource_leave.out_of_date:
                resource_leave.payroll_period_id = resource_leave.holiday_id.payroll_period_id.id
        return resource_leaves
    
    def _cancel_work_entry_conflict(self):
        """
        Creates a leave work entry for each hr.leave in self.
        Check overlapping work entries with self.
        Work entries completely included in a leave are archived.
        e.g.:
            |----- work entry ----|---- work entry ----|
                |------------------- hr.leave ---------------|
                                    ||
                                    vv
            |----* work entry ****|
                |************ work entry leave --------------|
        """
        if not self:
            return

        # 1. Create a work entry for each leave
        work_entries_vals_list = []
        for leave in self:
            contracts = leave.employee_id.sudo()._get_contracts(leave.date_from, leave.date_to, states=['open', 'close'])
            for contract in contracts:
                # Generate only if it has aleady been generated
                # ~ if leave.date_to >= contract.date_generated_from and leave.date_from <= contract.date_generated_to:
                work_entries_vals_list += contracts.with_context(holiday_status_id=leave.holiday_status_id.time_type)._get_work_entries_values(leave.date_from, leave.date_to)

        new_leave_work_entries = self.env['hr.work.entry'].create(work_entries_vals_list)
        if new_leave_work_entries:
            # 2. Fetch overlapping work entries, grouped by employees
            start = min(self.mapped('date_from'), default=False)
            stop = max(self.mapped('date_to'), default=False)
            work_entry_groups = self.env['hr.work.entry'].read_group([
                ('date_start', '<', stop),
                ('date_stop', '>', start),
                ('employee_id', 'in', self.employee_id.ids),
            ], ['work_entry_ids:array_agg(id)', 'employee_id'], ['employee_id', 'date_start', 'date_stop'], lazy=False)
            work_entries_by_employee = defaultdict(lambda: self.env['hr.work.entry'])
            for group in work_entry_groups:
                employee_id = group.get('employee_id')[0]
                work_entries_by_employee[employee_id] |= self.env['hr.work.entry'].browse(group.get('work_entry_ids'))

            # 3. Archive work entries included in leaves
            included = self.env['hr.work.entry']
            overlappping = self.env['hr.work.entry']
            for work_entries in work_entries_by_employee.values():
                # Work entries for this employee
                new_employee_work_entries = work_entries & new_leave_work_entries
                previous_employee_work_entries = work_entries - new_leave_work_entries

                # Build intervals from work entries
                leave_intervals = new_employee_work_entries._to_intervals()
                conflicts_intervals = previous_employee_work_entries._to_intervals()

                # Compute intervals completely outside any leave
                # Intervals are outside, but associated records are overlapping.
                outside_intervals = conflicts_intervals - leave_intervals

                overlappping |= self.env['hr.work.entry']._from_intervals(outside_intervals)
                included |= previous_employee_work_entries - overlappping
            overlappping.write({'leave_id': False})
            included.write({'active': False})


class HrWorkEntry(models.Model):
    _inherit = "hr.work.entry"

    out_of_date = fields.Boolean(string="Out of Date", default=False)
    payroll_period_id = fields.Many2one('hr.payroll.period', string='Payroll Period', tracking=True)
    
    def _mark_leaves_outside_schedule(self):
        return
    
    def _get_duration(self, date_start, date_stop):
        if not date_start or not date_stop:
            return 0
        if self._get_duration_is_valid():
            calendar = self.contract_id.resource_calendar_id
            if self.leave_id and self.leave_id.holiday_status_id.time_type not in ['holidays','personal']:
                calendar = self.employee_id.company_id.resource_calendar_leave_id
            if not calendar:
                return 0
            employee = self.contract_id.employee_id
            contract_data = employee._get_work_days_data_batch(
                date_start, date_stop, compute_leaves=False, calendar=calendar
            )[employee.id]
            return contract_data.get('hours', 0)
        return super()._get_duration(date_start, date_stop)


class ResourceCalendarLeaves(models.Model):
    _inherit = "resource.calendar.leaves"

    out_of_date = fields.Boolean(string="Out of Date", default=False)
    payroll_period_id = fields.Many2one('hr.payroll.period', string='Payroll Period', tracking=True)
