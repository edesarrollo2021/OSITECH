# -*- coding: utf-8 -*-

{
    "name": "HR Payroll Variability",
    "author": "SH",
    "category": "Human Resources",
    "website": "",
    "description": "Module To Payroll MX Variability",
    "depends": [
        'l10n_mx_hr_payroll_reports',
    ],
    "data": [
        'security/ir.model.access.csv',
        'wizard/wizard_hr_payroll_variability_view.xml',
        'views/hr_payroll_variability_view.xml',
        'views/report_affiliate_movements.xml',
    ],
    "active": True,
    "installable": True,
}
