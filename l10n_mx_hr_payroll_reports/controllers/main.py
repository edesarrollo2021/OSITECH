# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import content_disposition, request
from werkzeug.exceptions import NotFound


class EmployeeReportController(http.Controller):

    @http.route('/aspa_report/<int:run_id>/', type='http', auth="user")
    def get_report(self, run_id, **kw):
        uid = request.session.uid
        report_model = request.env['hr.payslip.run']
        report_obj = report_model.with_user(uid)
        if run_id and run_id != 'null':
            report_obj = report_obj.browse(int(run_id))
        try:
            file_name = "ASPA TXT" + report_obj.name
            content = report_obj.get_aspa_txt()
            response = request.make_response(
                content,
                headers=[
                    ('Content-Type', report_obj.get_export_mime_type('txt')),
                    ('Content-Disposition', content_disposition(file_name + '.txt')),
                    ('Content-Length', len(content))
                ]
            )
            return response
        except Exception:
            raise NotFound()
