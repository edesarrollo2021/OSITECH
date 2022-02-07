# -*- coding: utf-8 -*-

import base64
import datetime
from datetime import timedelta, time, date
import json

from odoo import http, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.website_form.controllers.main import WebsiteForm
from odoo.exceptions import AccessError, MissingError, ValidationError, UserError
from collections import OrderedDict
from odoo.http import request, content_disposition
from odoo.osv.expression import OR
from odoo.tools.float_utils import float_round


class WebsiteFormMx(WebsiteForm):

    ##################
    # Inabilities
    ##################
    @http.route('''/inability/new/''', type='http', auth="user", website=True)
    def portal_leave_new(self, **kwargs):
        default_values = {}
        user = request.env.user
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        holiday_status_ids = request.env['hr.leave.type'].search([('time_type', '=', 'inability')])
        type_inhability_ids = request.env['hr.leave.inhability'].search([])
        inhability_classification_ids = request.env['hr.leave.classification'].search([])
        inhability_category_ids = request.env['hr.leave.category'].search([])
        inhability_subcategory_ids = request.env['hr.leave.subcategory'].search([])
        default_values.update({
            'employee_id': employee_id,
            'holiday_status_ids': holiday_status_ids,
            'type_inhability_ids': type_inhability_ids,
            'inhability_classification_ids': inhability_classification_ids,
            'inhability_category_ids': inhability_category_ids,
            'inhability_subcategory_ids': inhability_subcategory_ids,
        })
        return request.render("hr_portal_mx.leave_submit", {'default_values': default_values, 'page_name': 'inabilities'})

    @http.route('''/leave-submited''', type='http', auth="user", website=True)
    def portal_leave_submited(self, **kwargs):
        return request.render("hr_portal_mx.leave_submited", {'default_values': kwargs})

    @http.route('/leave/save/', type='http', auth="user", website=True)
    def portal_leave_save(self, **kwargs):
        user = request.env.user
        model_record = request.env.ref('hr_holidays.model_hr_leave').sudo()
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        contract_id = request.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee_id.id),
            ('state', '=', 'open')
        ], limit=1)
        try:
            data = self.extract_data(model_record, kwargs)
        except ValidationError as e:
            return json.dumps({'error_fields': e.args[0]})
        vals = {
            'employee_id': employee_id.id,
            'contract_id': contract_id.id,
            'name': kwargs['name'],
            'folio': kwargs['folio'],
            'request_date_from': datetime.datetime.strptime(kwargs['request_date_from'], '%Y-%m-%d').date(),
            'date_from': datetime.datetime.strptime(kwargs['request_date_from'], '%Y-%m-%d').date(),
            'request_date_to': datetime.datetime.strptime(kwargs['request_date_to'], '%Y-%m-%d').date(),
            'date_to': datetime.datetime.strptime(kwargs['request_date_to'], '%Y-%m-%d').date(),
            'holiday_status_id': int(kwargs.get('holiday_status_id')) if kwargs.get('holiday_status_id') else False,
            'type_inhability_id': int(kwargs.get('type_inhability_id')) if kwargs.get('type_inhability_id') else False,
            'inhability_classification_id': int(kwargs.get('inhability_classification_id')) if kwargs.get('inhability_classification_id') else False,
            'inhability_category_id': int(kwargs.get('inhability_category_id')) if kwargs.get('inhability_category_id') else False,
            'inhability_subcategory_id': int(kwargs.get('inhability_subcategory_id')) if kwargs.get('inhability_subcategory_id') else False,
        }
        if not vals['date_from'] <= vals['date_to']:
            return json.dumps({'error': _('Validation Error : The start date must be before the end date.')})
        try:
            leave_id = request.env['hr.leave'].sudo().create(vals)
        except ValidationError as e:
            request.env.cr.rollback()
            error = {
                'error': 'Validation Error : %s' % e,
            }
            return json.dumps(error)
        if leave_id:
            for file in data['attachments']:
                attachment_value = {
                    'name': file.filename,
                    'datas': base64.encodebytes(file.read()),
                    'type': 'binary',
                    'res_model': 'hr.leave',
                    'res_id': leave_id.id,
                }
                attachment_id = request.env['ir.attachment'].sudo().create(attachment_value)
                document = request.env['documents.document'].sudo().create({
                    'name': file.filename,
                    'folder_id': employee_id.folder_id.id,
                    'res_model': leave_id._name,
                    'res_id': leave_id.id,
                    'attachment_id': attachment_id.id,
                    'leave_id': leave_id.id
                })
        return json.dumps({'id': leave_id.id})

    ##################
    # Holidays
    ##################
    @http.route('''/holiday/new/''', type='http', auth="user", website=True)
    def portal_holiday_new(self, **kwargs):
        default_values = {}
        user = request.env.user
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        holiday_status_ids = request.env['hr.leave.type'].search([('time_type', '=', 'holidays')])
        holiday_status_ids, holiday_remaining_days = self.filter_holiday_type_id(holiday_status_ids)
        default_values.update({
            'employee_id': employee_id,
            'holiday_status_ids': holiday_status_ids,
            'holiday_remaining_days': holiday_remaining_days,
        })
        return request.render("hr_portal_mx.holiday_submit", {'default_values': default_values, 'page_name': 'holidays'})

    def filter_holiday_type_id(self, holidays_status_ids):
        user = request.env.user
        holidays_status_filtered = []
        holiday_remaining_days = {}
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        number_of_periods = 0
        for holiday_status in holidays_status_ids:
            data_days = holiday_status.get_days(employee_id.id)
            result = data_days.get(holiday_status.id, {})
            max_leaves = result.get('max_leaves', 0)
            remaining_leaves = result.get('remaining_leaves', 0)
            virtual_remaining_leaves = result.get('virtual_remaining_leaves', 0)
            if virtual_remaining_leaves:
                holidays_status_filtered.append(holiday_status)
                holiday_remaining_days[holiday_status.id] = {
                    'remaining_leaves': float_round(remaining_leaves, precision_digits=2) or 0.0,
                    'virtual_remaining_leaves': float_round(virtual_remaining_leaves, precision_digits=2) or 0.0,
                    'total_days': float_round(max_leaves, precision_digits=2) or 0.0,
                    'disabled': True if number_of_periods > 0 else False
                }
                number_of_periods = number_of_periods + 1
        return holidays_status_filtered, holiday_remaining_days

    @http.route('''/holidays/get_available_days_holidays''', type='json', auth="user", website=True)
    def get_available_days_holidays(self, **kwargs):
        user = request.env.user
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        holiday_status = request.env['hr.leave.type'].browse(int(kwargs.get('holiday_type_id')))
        data_days = holiday_status.get_days(employee_id.id)
        result = data_days.get(holiday_status.id, {})
        max_leaves = result.get('max_leaves', 0)
        remaining_leaves = result.get('remaining_leaves', 0)
        virtual_remaining_leaves = result.get('virtual_remaining_leaves', 0)
        date_from = datetime.datetime.strptime(kwargs.get('date_from'), '%Y-%m-%d') if kwargs.get('date_from') else False
        date_to = datetime.datetime.strptime(kwargs.get('date_to'), '%Y-%m-%d') if kwargs.get('date_to') else False
        days_holidays = 0
        if date_from and date_to:
            if not date_from <= date_to:
                return {'error': _('Validation Error : The start date must be before the end date.')}
            else:
                days_holidays = self._get_days_holidays(employee_id, date_from, date_to)['days']
                if not (virtual_remaining_leaves - days_holidays) < 0:
                    virtual_remaining_leaves = virtual_remaining_leaves - days_holidays
                else:
                    return {'error': _('Validation Error : You are selecting more days than are available for the selected period.')}
        return {
            'remaining_leaves': float_round(remaining_leaves, precision_digits=2) or 0.0,
            'virtual_remaining_leaves': float_round(virtual_remaining_leaves, precision_digits=2) or 0.0,
            'total_days': float_round(max_leaves, precision_digits=2) or 0.0,
            'days_holidays': days_holidays,
        }

    def _get_days_holidays(self, employee_id, date_from, date_to):
        datetime_from = datetime.datetime.combine(date_from, time.min)
        datetime_to = datetime.datetime.combine(date_to, time.max)
        holidays_obj = request.env['hr.leave'].sudo()
        number_of_days = holidays_obj._get_number_of_days(datetime_from, datetime_to, employee_id.id)
        return number_of_days

    @http.route('''/holiday-submited''', type='http', auth="user", website=True)
    def portal_holiday_submited(self, **kwargs):
        return request.render("hr_portal_mx.holiday_submited", {'default_values': kwargs})

    @http.route('/holiday/save/', type='http', auth="public", website=True)
    def portal_holiday_save(self, **kwargs):
        user = request.env.user
        model_record = request.env.ref('hr_holidays.model_hr_leave').sudo()
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        contract_id = request.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee_id.id),
            ('state', '=', 'open')
        ], limit=1)
        try:
            data = self.extract_data(model_record, kwargs)
        except ValidationError as e:
            return json.dumps({'error_fields': e.args[0]})

        # if (datetime.datetime.strptime(kwargs['request_date_from'], '%Y-%m-%d').date() - datetime.date.today()).days < 5:
        #     return json.dumps({'error': 'Validation Error : Holidays must be requested 5 days in advance.'})

        if (datetime.datetime.strptime(kwargs['request_date_from'], '%Y-%m-%d').date() - datetime.date.today()).days <= 1:
            return json.dumps({'error': _('Validation Error : Holidays must be requested 1 days in advance.')})

        date_from = (datetime.datetime.strptime(kwargs['request_date_from'], '%Y-%m-%d').date())
        date_time_from = (datetime.datetime.strptime(kwargs['request_date_from'], '%Y-%m-%d') + timedelta(hours=5, minutes=00, seconds=00))
        date_time_to = (datetime.datetime.strptime(kwargs['request_date_to'], '%Y-%m-%d') + timedelta(hours=23, minutes=59, seconds=59))
        date_to = (datetime.datetime.strptime(kwargs['request_date_to'], '%Y-%m-%d').date())

        vals = {
            'employee_id': employee_id.id,
            'contract_id': contract_id.id,
            'name': kwargs['name'],
            'request_date_from': date_from,
            'date_from': date_time_from,
            'request_date_to': date_to,
            'date_to': date_time_to,
            'holiday_status_id': int(kwargs.get('holiday_status_id')) if kwargs.get('holiday_status_id') else False,
        }
        if not vals['date_from'] <= vals['date_to']:
            return json.dumps({'error': _('Validation Error : The start date must be before the end date.')})
        try:
            holiday_id = request.env['hr.leave'].sudo().create(vals)
        except ValidationError as e:
            request.env.cr.rollback()
            error = {
                'error': 'Validation Error : %s' % e,
            }
            return json.dumps(error)
        if holiday_id:
            for file in data['attachments']:
                attachment_value = {
                    'name': file.filename,
                    'datas': base64.encodebytes(file.read()),
                    'type': 'binary',
                    'res_model': 'hr.leave',
                    'res_id': holiday_id.id,
                }
                attachment_id = request.env['ir.attachment'].sudo().create(attachment_value)
                document = request.env['documents.document'].sudo().create({
                    'name': file.filename,
                    'folder_id': employee_id.folder_id.id,
                    'res_model': holiday_id._name,
                    'res_id': holiday_id.id,
                    'attachment_id': attachment_id.id,
                    'leave_id': holiday_id.id
                })
        return json.dumps({'id': holiday_id.id})

    @http.route('/holidays/cancellation', type='http', auth="public", website=True)
    def holidays_request_cancellation(self, **kwargs):
        leave_id = int(kwargs.get('holiday_id'))
        res_leave = request.env['hr.leave'].browse(leave_id)
        try:
            if kwargs.get('state') == 'cancel':
                res_leave.description_cancellation = kwargs.get('description_cancellation', '')
                res_leave.cancellation = True
        except Exception as e:
            error = {
                'error': _('Validation Error : %s') % e,
            }
            return json.dumps(error)
        except ValidationError as e:
            request.env.cr.rollback()
            error = {
                'error': _('Validation Error : %s') % e,
            }
            return json.dumps(error)
        if res_leave:
            return json.dumps({'id': res_leave.id})

    @http.route('/holidays_request/send', type='http', auth="public", website=True)
    def holidays_request_send(self, **kwargs):
        leave_id = int(kwargs.get('holiday_id'))
        res_leave = request.env['hr.leave'].browse(leave_id)
        res = False
        try:
            if kwargs.get('description_cancellation', ''):
                res_leave.reject_cancellation = kwargs.get('description_cancellation', '')
                res = res_leave.sudo().action_reject_cancellation()
            elif int(kwargs.get('cancellation', 0)):
                res = res_leave.sudo().action_cancel()
            elif kwargs.get('state', '') == 'refuse':
                res_leave.reason_reject = int(kwargs.get('reason_reject'))
                res_leave.description_reject = kwargs.get('description_reject', '')
                res = res_leave.sudo().action_refuse()
            else:
                res = res_leave.sudo().action_validate()
        except Exception as e:
            error = {
                'error': _('Validation Error : %s') % e,
            }
            return json.dumps(error)
        except ValidationError as e:
            request.env.cr.rollback()
            error = {
                'error': _('Validation Error : %s') % e,
            }
            return json.dumps(error)
        if res:
            return json.dumps({'id': res_leave.id})

    ##################
    # Personal Days
    ##################
    @http.route('''/personal_days/new/''', type='http', auth="user", website=True)
    def portal_personal_day_new(self, **kwargs):
        default_values = {}
        user = request.env.user
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        holiday_status_ids = request.env['hr.leave.type'].search([('time_type', '=', 'personal')])
        holiday_status_ids, holiday_remaining_days = self.filter_holiday_type_id(holiday_status_ids)
        if not len(holiday_status_ids):
            return request.render("hr_portal_mx.personal_days_unavailable")
        default_values.update({
            'employee_id': employee_id,
            'holiday_status_ids': holiday_status_ids,
            'holiday_remaining_days': holiday_remaining_days,
        })
        return request.render("hr_portal_mx.personal_days_submit", {'default_values': default_values, 'page_name': 'personal'})

    @http.route('''/personal_days-submited''', type='http', auth="user", website=True)
    def portal_personal_day_submited(self, **kwargs):
        return request.render("hr_portal_mx.personal_days_submited", {'default_values': kwargs})

    @http.route('/personal_days/save/', type='http', auth="public", website=True)
    def portal_personal_day_save(self, **kwargs):
        user = request.env.user
        model_record = request.env.ref('hr_holidays.model_hr_leave').sudo()
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        contract_id = request.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee_id.id),
            ('state', '=', 'open')
        ], limit=1)
        try:
            data = self.extract_data(model_record, kwargs)
        except ValidationError as e:
            return json.dumps({'error_fields': e.args[0]})

        if (datetime.datetime.strptime(kwargs['request_date_from'], '%Y-%m-%d').date() - datetime.date.today()).days <= 1:
            return json.dumps({'error': _('Validation Error : Personal Days must be requested 1 days in advance.')})

        date_from = (datetime.datetime.strptime(kwargs['request_date_from'], '%Y-%m-%d').date())
        date_time_from = (datetime.datetime.strptime(kwargs['request_date_from'], '%Y-%m-%d') + timedelta(hours=5, minutes=00, seconds=00))
        date_time_to = (datetime.datetime.strptime(kwargs['request_date_to'], '%Y-%m-%d') + timedelta(hours=23, minutes=59, seconds=59))
        date_to = (datetime.datetime.strptime(kwargs['request_date_to'], '%Y-%m-%d').date())

        vals = {
            'employee_id': employee_id.id,
            'contract_id': contract_id.id,
            'name': kwargs['name'],
            'request_date_from': date_from,
            'date_from': date_time_from,
            'request_date_to': date_to,
            'date_to': date_time_to,
            'holiday_status_id': int(kwargs.get('holiday_status_id')) if kwargs.get('holiday_status_id') else False,
        }
        if not vals['date_from'] <= vals['date_to']:
            return json.dumps({'error': _('Validation Error : The start date must be before the end date.')})
        if (vals['date_to'] - vals['date_from']).days > 1:
            return json.dumps({'error': _('Validation Error : You cannot request more than one personal day.')})
        try:
            personal_day_id = request.env['hr.leave'].sudo().create(vals)
        except ValidationError as e:
            request.env.cr.rollback()
            error = {
                'error': _('Validation Error : %s') % e,
            }
            return json.dumps(error)
        if personal_day_id:
            for file in data['attachments']:
                attachment_value = {
                    'name': file.filename,
                    'datas': base64.encodebytes(file.read()),
                    'type': 'binary',
                    'res_model': 'hr.leave',
                    'res_id': personal_day_id.id,
                }
                attachment_id = request.env['ir.attachment'].sudo().create(attachment_value)
                document = request.env['documents.document'].sudo().create({
                    'name': file.filename,
                    'folder_id': employee_id.folder_id.id,
                    'res_model': personal_day_id._name,
                    'res_id': personal_day_id.id,
                    'attachment_id': attachment_id.id,
                    'leave_id': personal_day_id.id
                })
        return json.dumps({'id': personal_day_id.id})

    @http.route('/personal_days/cancellation', type='http', auth="public", website=True)
    def personal_days_request_cancellation(self, **kwargs):
        leave_id = int(kwargs.get('personal_day_id'))
        res_leave = request.env['hr.leave'].browse(leave_id)
        try:
            if kwargs.get('state') == 'cancel':
                res_leave.description_cancellation = kwargs.get('description_cancellation', '')
                res_leave.cancellation = True
        except Exception as e:
            error = {
                'error': _('Validation Error : %s') % e,
            }
            return json.dumps(error)
        except ValidationError as e:
            request.env.cr.rollback()
            error = {
                'error': _('Validation Error : %s') % e,
            }
            return json.dumps(error)
        if res_leave:
            return json.dumps({'id': res_leave.id})

    @http.route('/personal_days_requests/send', type='http', auth="public", website=True)
    def personal_days_request_send(self, **kwargs):
        leave_id = int(kwargs.get('personal_day_id'))
        res_leave = request.env['hr.leave'].browse(leave_id)
        res = False
        try:
            if kwargs.get('description_cancellation', ''):
                res_leave.reject_cancellation = kwargs.get('description_cancellation', '')
                res = res_leave.sudo().action_reject_cancellation()
            elif int(kwargs.get('cancellation', 0)):
                res = res_leave.sudo().action_cancel()
            elif kwargs.get('state', '') == 'refuse':
                res_leave.reason_reject = int(kwargs.get('reason_reject'))
                res_leave.description_reject = kwargs.get('description_reject', '')
                res = res_leave.sudo().action_refuse()
            else:
                res = res_leave.sudo().action_validate()
        except Exception as e:
            error = {
                'error': _('Validation Error : %s') % e,
            }
            return json.dumps(error)
        except ValidationError as e:
            request.env.cr.rollback()
            error = {
                'error': _('Validation Error : %s') % e,
            }
            return json.dumps(error)
        if res:
            return json.dumps({'id': res_leave.id})


class HrPortalMx(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'leaves_count' in counters:
            leaves_count = request.env['hr.leave'].search_count(self._get_inabilities_domain()) \
                if request.env['hr.leave'].check_access_rights('read', raise_exception=False) else 0
            values['leaves_count'] = leaves_count
        if 'holidays_count' in counters:
            holidays_count = request.env['hr.leave'].search_count(self._get_holidays_domain()) \
                if request.env['hr.leave'].check_access_rights('read', raise_exception=False) else 0
            values['holidays_count'] = holidays_count
        if 'holidays_requests_count' in counters:
            holidays_requests_count = request.env['hr.leave'].search_count(self._get_holidays_request_domain()) \
                if request.env['hr.leave'].check_access_rights('read', raise_exception=False) else 0
            values['holidays_requests_count'] = holidays_requests_count
        if 'personals_count' in counters:
            personals_count = request.env['hr.leave'].search_count(self._get_personal_days_domain()) \
                if request.env['hr.leave'].check_access_rights('read', raise_exception=False) else 0
            values['personals_count'] = personals_count
        if 'personals_requests_count' in counters:
            personals_requests_count = request.env['hr.leave'].search_count(self._get_personal_days_request_domain()) \
                if request.env['hr.leave'].check_access_rights('read', raise_exception=False) else 0
            values['personals_requests_count'] = personals_requests_count
        return values

    ########################
    # inabilities
    ########################
    def _inability_get_page_view_values(self, leave, access_token, **kwargs):
        values = {
            'page_name': 'leave',
            'leave': leave,
        }
        return self._get_page_view_values(leave, access_token, values, 'my_leaves_history', False, **kwargs)

    def _get_inabilities_domain(self):
        user = request.env['res.users'].browse(request.uid)
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        return [('holiday_status_id.time_type', '=', 'inability'), ('employee_id', '=', employee_id.id)]

    @http.route(['/my/inabilities', '/my/inabilities/page/<int:page>'], type='http', auth="user", website=True)
    def portal_inabilities_docs(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        searchbar_sortings = {
            'state': {'label': _('State'), 'order': 'state'},
            'reference': {'label': _('Folio'), 'order': 'folio'},
            'create_date': {'label': _('More Recent'), 'order': 'create_date desc'},
            'request_date_from': {'label': _('Date From'), 'order': 'request_date_from desc'},
            'request_date_to': {'label': _('Date To'), 'order': 'request_date_to desc'},
        }
        if not sortby:
            sortby = 'create_date'
        sort_order = searchbar_sortings[sortby]['order']
        leaves = request.env['hr.leave'].sudo().search(self._get_inabilities_domain(), order=sort_order,
            limit=self._items_per_page,
            offset=(page - 1) * self._items_per_page)
        inabilities_count = len(leaves)
        pager = portal_pager(
            url="/my/inabilities",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=inabilities_count,
            page=page,
            step=self._items_per_page
        )
        values.update({
            'date': date_begin,
            'leaves': leaves,
            'page_name': 'inabilities',
            'pager': pager,
            'default_url': '/my/inabilities',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render("hr_portal_mx.portal_my_inabilities", values)

    @http.route('/inabilities/detail/<int:leave_id>', type='http', auth="user", website=True)
    def portal_leave_details(self, leave_id):
        leave_id = request.env['hr.leave'].sudo().browse(leave_id)
        values = {
            'leave': leave_id,
            'page_name': 'inabilities',
            'default_url': '/my/inabilities',
        }
        return request.render("hr_portal_mx.portal_leave_details", values)

    ########################
    # holidays
    ########################
    def _holiday_get_page_view_values(self, holiday, access_token, **kwargs):
        values = {
            'page_name': 'holidays',
            'holiday': holiday,
        }
        return self._get_page_view_values(holiday, access_token, values, 'my_holidays_history', False, **kwargs)

    def _get_holidays_domain(self):
        user = request.env['res.users'].browse(request.uid)
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        return [('holiday_status_id.time_type', '=', 'holidays'), ('employee_id', '=', employee_id.id)]

    @http.route(['/my/holidays', '/my/holidays/page/<int:page>'], type='http', auth="user", website=True)
    def portal_holidays_docs(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        searchbar_sortings = {
            'state': {'label': _('State'), 'order': 'state'},
            'create_date': {'label': _('More Recent'), 'order': 'create_date desc'},
            'request_date_from': {'label': _('Date From'), 'order': 'request_date_from desc'},
            'request_date_to': {'label': _('Date To'), 'order': 'request_date_to desc'},
        }
        if not sortby:
            sortby = 'create_date'
        sort_order = searchbar_sortings[sortby]['order']
        holidays = request.env['hr.leave'].sudo().search(self._get_holidays_domain(), order=sort_order,
                                                       limit=self._items_per_page,
                                                       offset=(page - 1) * self._items_per_page)
        holidays_count = len(holidays)
        pager = portal_pager(
            url="/my/holidays",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=holidays_count,
            page=page,
            step=self._items_per_page
        )
        values.update({
            'date': date_begin,
            'holidays': holidays,
            'page_name': 'holidays',
            'pager': pager,
            'default_url': '/my/holidays',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render("hr_portal_mx.portal_my_holidays", values)

    @http.route('/holidays/detail/<int:holiday_id>', type='http', auth="user", website=True)
    def portal_holiday_details(self, holiday_id):
        holiday_id = request.env['hr.leave'].sudo().browse(holiday_id)
        values = {
            'holiday': holiday_id,
            'page_name': 'holidays',
            'default_url': '/my/holidays',
        }
        return request.render("hr_portal_mx.portal_holiday_details", values)

    ########################
    # holidays request
    ########################
    def _get_holidays_request_domain(self):
        user = request.env['res.users'].browse(request.uid)
        employee_ids = request.env['hr.employee'].sudo().search([('approver_kiosk_id', '=', user.id)])
        return [('holiday_status_id.time_type', '=', 'holidays'), ('employee_id', 'in', employee_ids.ids)]

    @http.route(['/my/holidays_requests'], type='http', auth="user", website=True)
    def portal_holidays_requests(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, search=None, search_in='content', **kw):
        user = request.env['res.users'].browse(request.uid)
        values = self._prepare_portal_layout_values()
        searchbar_sortings = {
            'state': {'label': _('State'), 'order': 'state'},
            'create_date': {'label': _('More Recent'), 'order': 'create_date desc'},
            'request_date_from': {'label': _('Date From'), 'order': 'request_date_from desc'},
            'request_date_to': {'label': _('Date To'), 'order': 'request_date_to desc'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'to_approve': {'label': _('To Approve'), 'domain': [('state', '=', 'confirm')]},
            'canceled': {'label': _('Canceled'), 'domain': [('state', '=', 'cancel')]},
            'rejected': {'label': _('Rejected'), 'domain': [('state', '=', 'refuse')]},
            'approved': {'label': _('Approved'), 'domain': [('state', '=', 'validate')]},
        }
        searchbar_inputs = {
            'content': {'input': 'content', 'label': _('Search <span class="nolabel"> (in Content)</span>')},
            'enrollment': {'input': 'enrollment', 'label': _('Search in Employee Enrollment')},
            'employee': {'input': 'employee', 'label': _('Search in Employee')},
            'period': {'input': 'period', 'label': _('Search in Period')},
            'all': {'input': 'all', 'label': _('Search in All')},
        }
        domain = self._get_holidays_request_domain()
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        if not sortby:
            sortby = 'create_date'
        if not filterby:
            filterby = 'all'
        sort_order = searchbar_sortings[sortby]['order']
        domain += searchbar_filters[filterby]['domain']

        if search and search_in:
            search_domain = []
            if search_in in ('content', 'all'):
                search_domain = OR([search_domain, ['|', ('employee_id.complete_name', 'ilike', search), ('employee_id.registration_number', 'ilike', search)]])
            if search_in in ('employee', 'all'):
                search_domain = OR([search_domain, [('employee_id.complete_name', 'ilike', search)]])
            if search_in in ('enrollment', 'all'):
                search_domain = OR([search_domain, [('employee_id.registration_number', 'ilike', search)]])
            if search_in in ('period', 'all'):
                search_domain = OR([search_domain, [('holiday_status_id.name', 'ilike', search)]])
            domain += search_domain
        holidays_requests = request.env['hr.leave'].sudo().search(domain, order=sort_order, limit=self._items_per_page,
                                                                  offset=(page - 1) * self._items_per_page)
        holidays_count = len(holidays_requests)
        pager = portal_pager(
            url="/my/holidays_requests",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=holidays_count,
            page=page,
            step=self._items_per_page
        )
        values.update({
            'date': date_begin,
            'holidays_requests': holidays_requests,
            'page_name': 'holidays_requests',
            'pager': pager,
            'default_url': '/my/holidays_requests',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_inputs': searchbar_inputs,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'sortby': sortby,
            'filterby': filterby,
            'search_in': search_in,
        })
        if not user.approve_holidays:
            return request.render("hr_portal_mx.error_permission")
        return request.render("hr_portal_mx.holidays_requests", values)

    @http.route('/holidays_request/detail/<int:leave_id>', type='http', auth="user", website=True)
    def portal_holidays_request_details(self, leave_id):
        user = request.env['res.users'].browse(request.uid)
        leave_id = request.env['hr.leave'].sudo().browse(leave_id)
        reason_reject = request.env['hr.leave.reason.reject'].sudo().search([])
        values = {
            'holidays_request': leave_id,
            'page_name': 'holidays_requests',
            'default_url': '/my/holidays_requests',
            'reason_reject': reason_reject,
        }
        if not user.approve_holidays:
            return request.render("hr_portal_mx.error_permission")
        return request.render("hr_portal_mx.portal_holidays_request_details", values)

    ########################
    # personal days
    ########################
    def _personal_days_get_page_view_values(self, personal, access_token, **kwargs):
        values = {
            'page_name': 'personal',
            'personal': personal,
        }
        return self._get_page_view_values(personal, access_token, values, 'my_personal_history', False, **kwargs)

    def _get_personal_days_domain(self):
        user = request.env['res.users'].browse(request.uid)
        employee_id = request.env['hr.employee'].sudo().search([('address_home_id', '=', user.partner_id.id)])
        return [('holiday_status_id.time_type', '=', 'personal'), ('employee_id', '=', employee_id.id)]

    @http.route(['/my/personal_days', '/my/personal/page/<int:page>'], type='http', auth="user", website=True)
    def portal_personal_days_docs(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        searchbar_sortings = {
            'state': {'label': _('State'), 'order': 'state'},
            'create_date': {'label': _('More Recent'), 'order': 'create_date desc'},
            'request_date_from': {'label': _('Date From'), 'order': 'request_date_from desc'},
            'request_date_to': {'label': _('Date To'), 'order': 'request_date_to desc'},
        }
        if not sortby:
            sortby = 'create_date'
        sort_order = searchbar_sortings[sortby]['order']
        personals = request.env['hr.leave'].sudo().search(self._get_personal_days_domain(), order=sort_order,
                                                         limit=self._items_per_page,
                                                         offset=(page - 1) * self._items_per_page)
        personal_count = len(personals)
        pager = portal_pager(
            url="/my/personal_days",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=personal_count,
            page=page,
            step=self._items_per_page
        )
        values.update({
            'date': date_begin,
            'personals': personals,
            'page_name': 'personal',
            'pager': pager,
            'default_url': '/my/personal_days',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render("hr_portal_mx.portal_my_personals", values)

    @http.route('/personal_days/detail/<int:personal_id>', type='http', auth="user", website=True)
    def portal_personal_day_details(self, personal_id):
        personal_id = request.env['hr.leave'].sudo().browse(personal_id)
        values = {
            'personal': personal_id,
            'page_name': 'personal',
            'default_url': '/my/personal_days',
        }
        return request.render("hr_portal_mx.portal_personal_days_details", values)

    ########################
    # personal day request
    ########################
    def _get_personal_days_request_domain(self):
        user = request.env['res.users'].browse(request.uid)
        employee_ids = request.env['hr.employee'].sudo().search([('approver_kiosk_id', '=', user.id)])
        return [('holiday_status_id.time_type', '=', 'personal'), ('employee_id', 'in', employee_ids.ids)]

    @http.route(['/my/personal_days_requests'], type='http', auth="user", website=True)
    def portal_personal_days_requests(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, search=None, search_in='content', **kw):
        user = request.env['res.users'].browse(request.uid)
        values = self._prepare_portal_layout_values()
        searchbar_sortings = {
            'state': {'label': _('State'), 'order': 'state'},
            'create_date': {'label': _('More Recent'), 'order': 'create_date desc'},
            'request_date_from': {'label': _('Date From'), 'order': 'request_date_from desc'},
            'request_date_to': {'label': _('Date To'), 'order': 'request_date_to desc'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'to_approve': {'label': _('To Approve'), 'domain': [('state', '=', 'confirm')]},
            'canceled': {'label': _('Canceled'), 'domain': [('state', '=', 'cancel')]},
            'rejected': {'label': _('Rejected'), 'domain': [('state', '=', 'refuse')]},
            'approved': {'label': _('Approved'), 'domain': [('state', '=', 'validate')]},
        }
        searchbar_inputs = {
            'content': {'input': 'content', 'label': _('Search <span class="nolabel"> (in Content)</span>')},
            'enrollment': {'input': 'enrollment', 'label': _('Search in Employee Enrollment')},
            'employee': {'input': 'employee', 'label': _('Search in Employee')},
            'period': {'input': 'period', 'label': _('Search in Period')},
            'all': {'input': 'all', 'label': _('Search in All')},
        }
        domain = self._get_personal_days_request_domain()
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        if not sortby:
            sortby = 'create_date'
        if not filterby:
            filterby = 'all'
        sort_order = searchbar_sortings[sortby]['order']
        domain += searchbar_filters[filterby]['domain']

        if search and search_in:
            search_domain = []
            if search_in in ('content', 'all'):
                search_domain = OR([search_domain, ['|', ('employee_id.complete_name', 'ilike', search), ('employee_id.registration_number', 'ilike', search)]])
            if search_in in ('employee', 'all'):
                search_domain = OR([search_domain, [('employee_id.complete_name', 'ilike', search)]])
            if search_in in ('enrollment', 'all'):
                search_domain = OR([search_domain, [('employee_id.registration_number', 'ilike', search)]])
            if search_in in ('period', 'all'):
                search_domain = OR([search_domain, [('holiday_status_id.name', 'ilike', search)]])
            domain += search_domain
        personal_days_requests = request.env['hr.leave'].sudo().search(domain, order=sort_order,
                                                                  limit=self._items_per_page,
                                                                  offset=(page - 1) * self._items_per_page)
        holidays_count = len(personal_days_requests)
        pager = portal_pager(
            url="/my/personal_days_requests",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=holidays_count,
            page=page,
            step=self._items_per_page
        )
        values.update({
            'date': date_begin,
            'personal_days_requests': personal_days_requests,
            'page_name': 'personal_days_requests',
            'pager': pager,
            'default_url': '/my/personal_days_requests',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_inputs': searchbar_inputs,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'sortby': sortby,
            'filterby': filterby,
            'search_in': search_in,
        })
        if not user.approve_holidays:
            return request.render("hr_portal_mx.error_permission")
        return request.render("hr_portal_mx.personal_days_requests", values)

    @http.route('/personal_days_requests/detail/<int:leave_id>', type='http', auth="user", website=True)
    def portal_personal_days_requests_details(self, leave_id):
        user = request.env['res.users'].browse(request.uid)
        leave_id = request.env['hr.leave'].sudo().browse(leave_id)
        reason_reject = request.env['hr.leave.reason.reject'].sudo().search([])
        values = {
            'personal_days_request': leave_id,
            'page_name': 'personal_days_requests',
            'default_url': '/my/personal_days_requests',
            'reason_reject': reason_reject,
        }
        if not user.approve_holidays:
            return request.render("hr_portal_mx.error_permission")
        return request.render("hr_portal_mx.portal_personal_days_requests_details", values)

    @http.route('/report/personal_days/<int:leave_id>', type='http', auth="user", website=True)
    def portal_economic_days_report(self, leave_id):
        leave_id = request.env['hr.leave'].sudo().browse(leave_id)
        action_report_id = leave_id.pdf_sign if leave_id.pdf_sign else leave_id.pdf

        try:
            pdf = base64.b64decode(action_report_id.datas)
            pdf_name = action_report_id.name
        except UserError as e:
            return request.render("hr_portal_mx.error_dowload_economicdays", {'error_data': e})

        pdfhttpheaders = [('Content-Type', 'application/pdf'), ('Content-Length', len(pdf)),
                          ('Content-Disposition', content_disposition(pdf_name))]
        return request.make_response(pdf, headers=pdfhttpheaders)
