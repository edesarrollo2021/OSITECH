# -*- coding: utf-8 -*-

{
    "name" : "Management of INFONAVIT and FONACOT",
    "author": "SH",
    "category": "Human Resources",
    "website" : "",
    "description": "Module for capturing infonavit and fonacot credits",
    "depends": ['base', 'hr_employe_mexico', 'hr_payroll_mexico'],
    "data": [
        'security/ir.model.access.csv',
        'views/hr_credit_infonavit_fonacot.xml',
        'views/reports_credits_actions.xml',
        'views/credits_templates.xml',
    ],
    "active": True,
    "installable": True,
}
