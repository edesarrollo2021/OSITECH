# -*- coding: utf-8 -*-

{
    'name': 'Time Off Mexico',
    'version': '1.5',
    'category': 'Human Resources/Time Off',
    'sequence': 85,
    'summary': 'Allocate time off and follow time off requests for mx',
    'author': 'Soluciones Softhard, C.A.',
    'website': 'https://www.odoo.com/page/leaves',
    'description': """ """,
    'depends': ['hr_holidays', 'documents', 'hr_employe_mexico', 'import_employees', 'hr_work_entry_contract', 'sign'],
    'data': [
        'data/inhability_data.xml',

        'security/ir.model.access.csv',

        'views/menuitem.xml',
        'views/res_users_views.xml',
        'views/hr_leave_type_view.xml',
        'views/mail_templates.xml',
        'views/hr_leave_views.xml',
        'views/hr_employee_views.xml',
        'views/history_templates.xml',
        'views/leaves_availability_actions.xml',
        'wizard/holidays_assignment_views.xml',
        'wizard/hr_leave_import_view.xml',
        'wizard/sicoss_report_views.xml',

        'report/report_holidays.xml',

        'data/leave_type_data.xml',
    ],
    'demo': [
        # 'data/hr_holidays_demo.xml',
    ],
    'qweb': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
