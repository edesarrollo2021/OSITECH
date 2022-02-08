# -*- coding: utf-8 -*-

{
    "name": "HR Payroll Reports",
    "author": "SH",
    "category": "Human Resources",
    "website": "",
    "description": "Module To Payroll Reports",
    "depends": [
        'hr_payroll',
        'hr_payroll_mexico',
        'hr_infonavit_fonacot',
        'payroll_sign'
    ],
    "data": [
        'security/ir.model.access.csv',
        'wizard/wizard_file_download_view.xml',
        'wizard/wizard_payment_file_view.xml',
        'wizard/wizard_payslip_run_report_view.xml',
        'wizard/wizard_credit_reports.xml',
        'wizard/wizard_payroll_run_details_cfdi.xml',
        'views/payslip_run_report_view.xml',
        'wizard/reports_consolidate_views.xml',
    ],
    "active": True,
    "installable": True,
}
