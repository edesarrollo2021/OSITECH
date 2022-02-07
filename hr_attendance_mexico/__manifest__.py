# -*- coding: utf-8 -*-
{
    "name": "Customization of the attendance process for Mexico.",
    'author': 'Soluciones Softhard, C.A.',
    'website': 'http://www.solucionesofthard.com',
    "category": "Human Resources",
    "description": "Module that adapts attendances",
    "depends": ['base', 'hr_payroll_mexico', 'hr_attendance'],
    "data": [
        'security/ir.model.access.csv',

        'wizard/massive_attendance.xml',
        # 'data/data_isn.xml',
    ],
    "active": True,
    "installable": True,
}

