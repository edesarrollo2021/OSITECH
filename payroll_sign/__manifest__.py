# -*- coding: utf-8 -*-
{
    "name": "Integration of the sign module with payroll.",
    "author": "Soluciones Softhard, C.A.",
    "category": "Human Resources",
    "website": "http://www.solucionesofthard.com",
    "description": "Module that adapts sign process for payroll documents.",
    'summary': "Module that adapts sign process for payroll documents.",
    "depends": ['base', 'hr_payroll_mexico', 'sign', 'website', 'hr_portal_mx'],
    "data": [
    'security/ir.model.access.csv',
    'views/assets.xml',
    'views/hr_payslip_views.xml',
    'wizard/documents_share_payslip_views.xml',
    ],
    "active": True,
    "installable": True,
}