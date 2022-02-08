# -*- coding: utf-8 -*-

{
    "name": "Import Employee Layout",
    "author": "SH",
    "category": "Human Resources",
    "website": "",
    "description": "Module import employees",
    "depends": ['hr_employe_mexico'],
    "data": [
        'security/ir.model.access.csv',
        'views/hr_employee_import.xml',
        'views/assets_backend.xml',
    ],
    "active": True,
    "installable": True,
}
