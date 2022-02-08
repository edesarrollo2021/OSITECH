# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import content_disposition, request
from odoo.addons.web.controllers.main import _serialize_exception
from odoo.tools import html_escape

import json


class EmployeeReportController(http.Controller):

    @http.route('/employee_reports', type='http', auth='user', methods=['POST'], csrf=False)
    def get_report(self, model, options, output_format, token, report_id=None, **kw):
        uid = request.session.uid
        employee_report_model = request.env['report.affiliate.movements']
        options = json.loads(options)
        # cids = request.httprequest.cookies.get('cids', str(request.env.user.company_id.ids))
        # allowed_company_ids = [int(cid) for cid in cids.split(',')]
        allowed_company_ids = request.env.user.company_id.ids
        if model != 'null':
            report_obj = request.env[model].with_user(uid).with_context(allowed_company_ids=allowed_company_ids)
        else:
            report_obj = employee_report_model.with_user(uid)
        if report_id and report_id != 'null':
            report_obj = report_obj.browse(int(report_id))
        report_name = report_obj.get_report_filename(options)
        try:
            if output_format == 'xlsx':
                response = request.make_response(
                    None,
                    headers=[
                        ('Content-Type', employee_report_model.get_export_mime_type('xlsx')),
                        ('Content-Disposition', content_disposition(report_name + '.xlsx'))
                    ]
                )
                response.stream.write(report_obj.get_xlsx(options))
            if output_format == 'txt':
                content = report_obj.get_txt(options)

                response = request.make_response(
                    content,
                    headers=[
                        ('Content-Type', employee_report_model.get_export_mime_type('txt')),
                        ('Content-Disposition', content_disposition(report_name + '.txt')),
                        ('Content-Length', len(content))
                    ]
                )
            if output_format == 'csv':
                content = report_obj.get_csv(options)
                response = request.make_response(
                    content,
                    headers=[
                        ('Content-Type', employee_report_model.get_export_mime_type('txt')),
                        ('Content-Disposition', content_disposition(report_name + '.txt')),
                        ('Content-Length', len(content))
                    ]
                )
            if output_format == 'sicoss':
                content = report_obj.get_sicoss(options)
                response = request.make_response(
                    content,
                    headers=[
                        ('Content-Type', employee_report_model.get_export_mime_type('txt')),
                        ('Content-Disposition', content_disposition(report_name + '.txt')),
                        ('Content-Length', len(content))
                    ]
                )
            response.set_cookie('fileToken', token)
            return response
        except Exception as e:
            se = _serialize_exception(e)
            error = {
                'code': 200,
                'message': 'Odoo Server Error',
                'data': se
            }
            return request.make_response(html_escape(json.dumps(error)))
