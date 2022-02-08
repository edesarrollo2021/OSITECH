# -*- coding: utf-8 -*-

{
    "name": "Customization of the human resources process for Mexico.",
    'author': 'Soluciones Softhard, C.A.',
    'website': 'http://www.solucionesofthard.com',
    "category": "HR Portal Mexico",
    "description": "Portal module adapted to Mexico.",
    'summary': "Portal module adapted to Mexico.",
    "depends": ['website',
                'portal',
                'website_form',
                'hr_employe_mexico',
                'hr_holidays_edi_mx',
                'hr_payroll_mexico',],
    "data": [
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/portal_templates.xml',
        # 'views/res_users_views.xml',
    ],
    'qweb': [
        'static/src/xml/portal_mexico.xml',
    ],
    "active": True,
    "installable": True,
}

