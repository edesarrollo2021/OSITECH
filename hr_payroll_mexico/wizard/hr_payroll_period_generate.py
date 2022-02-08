# -*- coding: utf-8 -*-

import calendar
from datetime import date,datetime,timedelta

from odoo import tools, api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class HrPayrollPeriodGenerate(models.TransientModel):
    _name = "hr.payroll.period.generate"
    _description = "Payroll Period Generated "

    year = fields.Integer(string='Year')
    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], string='Month (Start)')
    payroll_period = fields.Selection([
        ('01', 'Daily'),
        ('02', 'Weekly'),
        ('03', 'Fourteen'),
        ('10', 'Decennial'),
        ('04', 'Biweekly'),
        ('05', 'Monthly'),
        ('99', 'Another Peridiocity')], string='Payroll period', default="99")
    type = fields.Selection([
        ('ordinary', 'Ordinary - Settlement'),
        ('extraordinary', 'Extraordinary and/or Special'),
    ], string="Type", default="ordinary", required=True)
    date_start = fields.Date(string="Date Start")
    date_end = fields.Date(string="Date End")
    company_ids = fields.Many2many('res.company', string='Company', default=lambda self: self.env.user.company_id.ids)

    def generate_payroll_period(self):
        payroll_period = self.env['hr.payroll.period']
        year = self.year
        list_month = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
        index = list_month.index(self.month) if self.month else 0
        list_month = list_month[index:]
        folder = self.env['documents.folder']
        list_period = []
        bimester_start = [1, 3, 5, 7, 9, 11]
        bimester_end = [2, 4, 6, 8, 10, 12]
        for company in self.company_ids:
            folfer_company = company.folder_document_id.parent_folder_id.id
            period = str(dict(self._fields['payroll_period']._description_selection(self.env)).get(self.payroll_period))
            name_folder_year = '%s - %s' % (str(self.year), period)
            folder_year = folder.create({'name': name_folder_year, 'parent_folder_id': folfer_company, 'company_id': company.id})
            if self.payroll_period == '04' and self.type == "ordinary":
                for month in list_month:
                    date1_start = datetime.strptime(str(str(year) + '-' + month + '-01'),
                                                    DEFAULT_SERVER_DATE_FORMAT).date()
                    date2_start = datetime.strptime(str(str(year) + '-' + month + '-16'),
                                                    DEFAULT_SERVER_DATE_FORMAT).date()
                    day = calendar.monthrange(int(year), int(month))[1]
                    date_end = datetime.strptime(str(str(year) + '-' + month + '-15'),
                                                 DEFAULT_SERVER_DATE_FORMAT).date()
                    date_end2 = datetime.strptime(str(str(year) + '-' + month + '-' + str(day)),
                                                  DEFAULT_SERVER_DATE_FORMAT).date()
                    payroll_period_ordinary = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', month), ('year', '=', year),
                             ('payroll_period', '=', '04'), ('type', '=', 'ordinary')])
                    payroll_period_settlement = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', month), ('year', '=', year),
                             ('payroll_period', '=', '04'), ('type', '=', 'settlement')])
                    if not payroll_period_ordinary or not payroll_period_settlement:
                        folder_1 = folder.create(
                            {'name': '%s  %s' % (date1_start, date_end), 'parent_folder_id': folder_year.id,
                             'company_id': company.id})
                        folder_2 = folder.create(
                            {'name': '%s - %s' % (date2_start, date_end2), 'parent_folder_id': folder_year.id,
                             'company_id': company.id})

                        # ordinary
                        if not payroll_period_ordinary:
                            pp1 = payroll_period.create({'name': _('%s - (%s / %s) Ordinary') % (year, date1_start, date_end),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'ordinary',
                                                         'date_start': date1_start,
                                                         'date_end': date_end,
                                                         'payroll_period': '04',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': True,
                                                         'start_bumonthly_period': True if int(
                                                             month) in bimester_start else False
                                                         })
                            pp2 = payroll_period.create({'name': _('%s - (%s / %s) Ordinary') % (year, date2_start, date_end2),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'ordinary',
                                                         'date_start': date2_start,
                                                         'date_end': date_end2,
                                                         'payroll_period': '04',
                                                         'folder_id': folder_2.id,
                                                         'end_monthly_period': True,
                                                         'end_bumonthly_period': True if int(
                                                             month) in bimester_end else False
                                                         })
                            list_period.append(pp1.id)
                            list_period.append(pp2.id)

                        # Settlement
                        if not payroll_period_settlement:
                            pp3 = payroll_period.create({'name': _('%s - (%s / %s) Settlement') % (year, date1_start, date_end),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'settlement',
                                                         'date_start': date1_start,
                                                         'date_end': date_end,
                                                         'payroll_period': '04',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': True,
                                                         'start_bumonthly_period': True if int(
                                                             month) in bimester_start else False
                                                         })
                            pp4 = payroll_period.create({'name': _('%s - (%s / %s) Settlement') % (year, date2_start, date_end2),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'settlement',
                                                         'date_start': date2_start,
                                                         'date_end': date_end2,
                                                         'payroll_period': '04',
                                                         'folder_id': folder_2.id,
                                                         'end_monthly_period': True,
                                                         'end_bumonthly_period': True if int(
                                                             month) in bimester_end else False
                                                         })
                            list_period.append(pp3.id)
                            list_period.append(pp4.id)

            if self.payroll_period == '05' and self.type == "ordinary":
                for month in list_month:
                    date_start = datetime.strptime(str(str(year) + '-' + month + '-01'),
                                                  DEFAULT_SERVER_DATE_FORMAT).date()
                    day = calendar.monthrange(int(year), int(month))[1]
                    date_end = datetime.strptime(str(str(year) + '-' + month + '-' + str(day)),
                                                 DEFAULT_SERVER_DATE_FORMAT).date()
                    payroll_period_ordinary = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', month), ('year', '=', year),
                             ('payroll_period', '=', '05'), ('type', '=', 'ordinary')])
                    payroll_period_settlement = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', month), ('year', '=', year),
                             ('payroll_period', '=', '05'), ('type', '=', 'settlement')])
                    if not payroll_period_ordinary or not payroll_period_settlement:
                        folder_1 = folder.create(
                            {'name': '%s - %s' % (date_start, date_end), 'parent_folder_id': folder_year.id,
                             'company_id': company.id})
                        if not payroll_period_ordinary:
                            pp1 = payroll_period.create({'name': _('%s - (%s / %s) Ordinary') % (year, date_start, date_end),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'ordinary',
                                                         'date_start': date_start,
                                                         'date_end': date_end,
                                                         'payroll_period': '05',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': True,
                                                         'start_bumonthly_period': True if int(month) in bimester_start else False,
                                                         'end_monthly_period': True,
                                                         'end_bumonthly_period': True if int(month) in bimester_end else False
                                                         })
                            list_period.append(pp1.id)
                        if not payroll_period_settlement:
                            pp2 = payroll_period.create({'name': _('%s - (%s / %s) Settlement') % (year, date_start, date_end),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'settlement',
                                                         'date_start': date_start,
                                                         'date_end': date_end,
                                                         'payroll_period': '05',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': True,
                                                         'start_bumonthly_period': True if int(month) in bimester_start else False,
                                                         'end_monthly_period': True,
                                                         'end_bumonthly_period': True if int(month) in bimester_end else False
                                                         })
                            list_period.append(pp2.id)

            if self.payroll_period == '01' and self.type == "ordinary":
                date_start = datetime.strptime(str(str(year) + '-' + self.month + '-01'),
                                               DEFAULT_SERVER_DATE_FORMAT).date()
                date_end = datetime.strptime(str(str(year) + '-12-31'), DEFAULT_SERVER_DATE_FORMAT).date()
                list_dates = [date_start + timedelta(days=d) for d in range((date_end - date_start).days + 1)]
                for day in list_dates:
                    start_monthly_period = False
                    start_bumonthly_period = False
                    end_monthly_period = False
                    end_bumonthly_period = False

                    payroll_period_ordinary = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', str(day.month)), ('year', '=', year),
                             ('payroll_period', '=', '01'), ('date_start', '=', day), ('type', '=', 'ordinary')])
                    payroll_period_settlement = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', str(day.month)), ('year', '=', year),
                             ('payroll_period', '=', '01'), ('date_start', '=', day), ('type', '=', 'settlement')])

                    if not payroll_period_ordinary or not payroll_period_settlement:
                        folder_1 = folder.create(
                            {'name': '%s' % (str(day)), 'parent_folder_id': folder_year.id, 'company_id': company.id})
                        if day.day == 1:
                            start_monthly_period = True
                            if day.month in bimester_start:
                                start_bumonthly_period = True
                        else:
                            day_last = calendar.monthrange(int(year), int(day.month))[1]
                            if day_last == day.day:
                                end_monthly_period = True
                                if day.month in bimester_end:
                                    end_bumonthly_period = True

                            date_end = datetime.strptime(str(str(year) + '-12-31'), DEFAULT_SERVER_DATE_FORMAT).date()

                        if not payroll_period_ordinary:
                            pp1 = payroll_period.create({'name': _('%s - (%s) Ordinary') % (year, str(day)),
                                                         'company_id': company.id,
                                                         'month': str(day.month),
                                                         'year': year,
                                                         'type': 'ordinary',
                                                         'date_start': day,
                                                         'date_end': day,
                                                         'payroll_period': '01',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': start_monthly_period,
                                                         'start_bumonthly_period': start_bumonthly_period,
                                                         'end_monthly_period': end_monthly_period,
                                                         'end_bumonthly_period': end_bumonthly_period
                                                         })
                            list_period.append(pp1.id)
                        if not payroll_period_settlement:
                            pp2 = payroll_period.create({'name': _('%s - (%s) Settlement') % (year, str(day)),
                                                         'company_id': company.id,
                                                         'month': str(day.month),
                                                         'year': year,
                                                         'type': 'settlement',
                                                         'date_start': day,
                                                         'date_end': day,
                                                         'payroll_period': '01',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': start_monthly_period,
                                                         'start_bumonthly_period': start_bumonthly_period,
                                                         'end_monthly_period': end_monthly_period,
                                                         'end_bumonthly_period': end_bumonthly_period
                                                         })
                            list_period.append(pp2.id)
            if self.payroll_period == '10' and self.type == "ordinary":

                for month in list_month:
                    date1_start = datetime.strptime(str(str(year) + '-' + month + '-01'),
                                                    DEFAULT_SERVER_DATE_FORMAT).date()
                    date2_start = datetime.strptime(str(str(year) + '-' + month + '-11'),
                                                    DEFAULT_SERVER_DATE_FORMAT).date()
                    date3_start = datetime.strptime(str(str(year) + '-' + month + '-21'),
                                                    DEFAULT_SERVER_DATE_FORMAT).date()
                    day = calendar.monthrange(int(year), int(month))[1]
                    date_end1 = datetime.strptime(str(str(year) + '-' + month + '-10'),
                                                  DEFAULT_SERVER_DATE_FORMAT).date()
                    date_end2 = datetime.strptime(str(str(year) + '-' + month + '-20'),
                                                  DEFAULT_SERVER_DATE_FORMAT).date()
                    date_end3 = datetime.strptime(str(str(year) + '-' + month + '-' + str(day)),
                                                  DEFAULT_SERVER_DATE_FORMAT).date()

                    payroll_period_ordinary = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', month), ('year', '=', year),
                             ('payroll_period', '=', '10'), ('type', '=', 'ordinary')])
                    payroll_period_settlement = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', month), ('year', '=', year),
                             ('payroll_period', '=', '10'), ('type', '=', 'settlement')])

                    if not payroll_period_ordinary or not payroll_period_settlement:
                        folder_1 = folder.create(
                            {'name': '%s - %s' % (date1_start, date_end1), 'parent_folder_id': folder_year.id,
                             'company_id': company.id})
                        folder_2 = folder.create(
                            {'name': '%s - %s' % (date2_start, date_end2), 'parent_folder_id': folder_year.id,
                             'company_id': company.id})
                        folder_3 = folder.create(
                            {'name': '%s - %s' % (date3_start, date_end3), 'parent_folder_id': folder_year.id,
                             'company_id': company.id})
                        if not payroll_period_ordinary:
                            pp1 = payroll_period.create({'name': _('%s - (%s / %s) Ordinary') % (year, date1_start, date_end1),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'ordinary',
                                                         'date_start': date1_start,
                                                         'date_end': date_end1,
                                                         'payroll_period': '10',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': True,
                                                         'start_bumonthly_period': True if int(
                                                             month) in bimester_start else False,
                                                         })
                            pp2 = payroll_period.create(
                                {'name': _('%s - (%s / %s) Ordinary') % (period, date2_start, date_end2), 'company_id': company.id,
                                 'month': month, 'year': year, 'type': 'ordinary', 'date_start': date2_start, 'date_end': date_end2,
                                 'payroll_period': '10', 'folder_id': folder_2.id})
                            pp3 = payroll_period.create({'name': _('%s - (%s / %s) Ordinary') % (year, date3_start, date_end3),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'ordinary',
                                                         'date_start': date3_start,
                                                         'date_end': date_end3,
                                                         'payroll_period': '10',
                                                         'folder_id': folder_3.id,
                                                         'end_monthly_period': True,
                                                         'end_bumonthly_period': True if int(
                                                             month) in bimester_end else False
                                                         })
                            list_period.append(pp1.id)
                            list_period.append(pp2.id)
                            list_period.append(pp3.id)
                        if not payroll_period_settlement:
                            pp4 = payroll_period.create({'name': _('%s - (%s / %s) Settlement') % (year, date1_start, date_end1),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'settlement',
                                                         'date_start': date1_start,
                                                         'date_end': date_end1,
                                                         'payroll_period': '10',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': True,
                                                         'start_bumonthly_period': True if int(
                                                             month) in bimester_start else False,
                                                         })
                            pp5 = payroll_period.create(
                                {'name': _('Settlement %s - (%s / %s)') % (period, date2_start, date_end2), 'company_id': company.id,
                                 'month': month, 'year': year, 'type': 'settlement', 'date_start': date2_start, 'date_end': date_end2,
                                 'payroll_period': '10', 'folder_id': folder_2.id})
                            pp6 = payroll_period.create({'name': _('%s - (%s / %s) Settlement') % (year, date3_start, date_end3),
                                                         'company_id': company.id,
                                                         'month': month,
                                                         'year': year,
                                                         'type': 'settlement',
                                                         'date_start': date3_start,
                                                         'date_end': date_end3,
                                                         'payroll_period': '10',
                                                         'folder_id': folder_3.id,
                                                         'end_monthly_period': True,
                                                         'end_bumonthly_period': True if int(
                                                             month) in bimester_end else False
                                                         })
                            list_period.append(pp4.id)
                            list_period.append(pp5.id)
                            list_period.append(pp6.id)

            if self.payroll_period == '02' and self.type == "ordinary":
                start_week_period = []
                date_start = datetime.strptime(str(str(year) + '-' + self.month + '-01'),
                                               DEFAULT_SERVER_DATE_FORMAT).date()
                if date_start.weekday() != 0:
                    date_start += timedelta(days=(7 - date_start.weekday()))
                while date_start.year == self.year:
                    start_monthly_period = False
                    start_bumonthly_period = False
                    end_monthly_period = False
                    end_bumonthly_period = False
                    date_end = date_start + timedelta(days=6)
                    if date_start.month not in start_week_period:
                        start_week_period.append(date_start.month)
                        start_monthly_period = True
                        if date_start.month in bimester_start:
                            start_bumonthly_period = True
                    else:
                        day = calendar.monthrange(int(year), int(date_start.month))[1]

                        if date_end.day == day or date_end.month != date_start.month:
                            end_monthly_period = True
                            if date_start.month in bimester_end:
                                end_bumonthly_period = True
                    payroll_period_ordinary = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', str(date_start.month)), ('year', '=', year),
                             ('payroll_period', '=', '02'), ('date_start', 'in', [date_start]), ('type', '=', 'ordinary')])
                    payroll_period_settlement = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', str(date_start.month)), ('year', '=', year),
                             ('payroll_period', '=', '02'), ('date_start', 'in', [date_start]), ('type', '=', 'settlement')])

                    if not payroll_period_ordinary or not payroll_period_settlement:
                        folder_1 = folder.create(
                            {'name': '%s - %s' % (date_start, date_end), 'parent_folder_id': folder_year.id,
                             'company_id': company.id})
                        if not payroll_period_ordinary:
                            pp1 = payroll_period.create({'name': _('%s - (%s / %s) Ordinary') % (year, date_start, date_end,),
                                                         'company_id': company.id,
                                                         'month': str(date_start.month),
                                                         'year': year,
                                                         'type': 'ordinary',
                                                         'date_start': date_start,
                                                         'date_end': date_end,
                                                         'payroll_period': '02',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': start_monthly_period,
                                                         'start_bumonthly_period': start_bumonthly_period,
                                                         'end_monthly_period': end_monthly_period,
                                                         'end_bumonthly_period': end_bumonthly_period
                                                         })
                            list_period.append(pp1.id)
                        if not payroll_period_settlement:
                            pp2 = payroll_period.create({'name': _('%s - (%s / %s) Settlement') % (year, date_start, date_end,),
                                                         'company_id': company.id,
                                                         'month': str(date_start.month),
                                                         'year': year,
                                                         'type': 'settlement',
                                                         'date_start': date_start,
                                                         'date_end': date_end,
                                                         'payroll_period': '02',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': start_monthly_period,
                                                         'start_bumonthly_period': start_bumonthly_period,
                                                         'end_monthly_period': end_monthly_period,
                                                         'end_bumonthly_period': end_bumonthly_period
                                                         })
                            list_period.append(pp2.id)

                    date_start += timedelta(days=7)

            if self.payroll_period == '03' and self.type == "ordinary":
                start_week_period = []
                date_start = datetime.strptime(str(str(year) + '-' + self.month + '-01'),
                                               DEFAULT_SERVER_DATE_FORMAT).date()
                if date_start.weekday() != 0:
                    date_start += timedelta(days=(7 - date_start.weekday()))
                while date_start.year == self.year:
                    start_monthly_period = False
                    start_bumonthly_period = False
                    end_monthly_period = False
                    end_bumonthly_period = False
                    date_end = date_start + timedelta(days=13)

                    if date_start.month not in start_week_period:
                        start_week_period.append(date_start.month)
                        start_monthly_period = True
                        if date_start.month in bimester_start:
                            start_bumonthly_period = True
                    else:
                        day = calendar.monthrange(int(year), int(date_start.month))[1]

                        if date_end.day == day or date_end.month != date_start.month:
                            end_monthly_period = True
                            if date_start.month in bimester_end:
                                end_bumonthly_period = True
                    payroll_period_ordinary = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', str(date_start.month)), ('year', '=', year),
                             ('payroll_period', '=', '03'), ('date_start', 'in', [date_start]), ('type', '=', 'ordinary')])
                    payroll_period_settlement = payroll_period.search(
                            [('company_id', '=', company.id), ('month', '=', str(date_start.month)), ('year', '=', year),
                             ('payroll_period', '=', '03'), ('date_start', 'in', [date_start]), ('type', '=', 'settlement')])

                    if not payroll_period_ordinary or not payroll_period_settlement:
                        folder_1 = folder.create(
                            {'name': '%s - %s' % (date_start, date_end), 'parent_folder_id': folder_year.id,
                             'company_id': company.id})
                        if not payroll_period_ordinary:
                            pp1 = payroll_period.create({'name': _('%s - (%s / %s) Ordinary') % (year, date_start, date_end),
                                                         'company_id': company.id,
                                                         'month': str(date_start.month),
                                                         'year': year,
                                                         'type': 'ordinary',
                                                         'date_start': date_start,
                                                         'date_end': date_end,
                                                         'payroll_period': '03',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': start_monthly_period,
                                                         'start_bumonthly_period': start_bumonthly_period,
                                                         'end_monthly_period': end_monthly_period,
                                                         'end_bumonthly_period': end_bumonthly_period
                                                         })
                            list_period.append(pp1.id)
                        if not payroll_period_settlement:
                            pp2 = payroll_period.create({'name': _('%s - (%s / %s) Settlement') % (year, date_start, date_end),
                                                         'company_id': company.id,
                                                         'month': str(date_start.month),
                                                         'year': year,
                                                         'type': 'settlement',
                                                         'date_start': date_start,
                                                         'date_end': date_end,
                                                         'payroll_period': '03',
                                                         'folder_id': folder_1.id,
                                                         'start_monthly_period': start_monthly_period,
                                                         'start_bumonthly_period': start_bumonthly_period,
                                                         'end_monthly_period': end_monthly_period,
                                                         'end_bumonthly_period': end_bumonthly_period
                                                         })
                            list_period.append(pp2.id)
                    date_start += timedelta(days=14)

            if self.type == 'extraordinary':
                folder_1 = folder.create({
                    'name': '%s - %s' % (self.date_start, self.date_end),
                    'parent_folder_id': folder_year.id,
                    'company_id': company.id})
                pp1 = payroll_period.create({'name': _('%s - (%s / %s) Another Peridiocity') % (self.date_start.year, self.date_start, self.date_end),
                                             'company_id': company.id,
                                             'month': str(self.date_start.month),
                                             'year': self.date_start.year,
                                             'type': 'special',
                                             'date_start': self.date_start,
                                             'date_end': self.date_end,
                                             'payroll_period': '99',
                                             'folder_id': folder_1.id,
                                             'start_monthly_period': False,
                                             'start_bumonthly_period': False,
                                             'end_monthly_period': False,
                                             'end_bumonthly_period': False
                                             })
                list_period.append(pp1.id)

        domain = [('id', 'in', list_period)]
        return {
            'name': _('Payroll Period'),
            'domain': domain,
            'res_model': 'hr.payroll.period',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'limit': 80,
        }
