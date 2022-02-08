# -*- coding: utf-8 -*-

{
    'name': 'HR employee mexico',
    'version': '1.0',
    'summary': 'Module for HR Aeromar changes',
    'description': 'Module for HR Aeromar changes',
    'author': 'Soluciones Softhard, C.A.',
    'website': 'http://www.solucionesofthard.com',
    'depends': ['base', 'sign', 'hr', 'hr_contract', 'documents', 'base_mexico', 'report_extend_bf', 'account_reports', 'hr_payroll'],

    'data': [
        'security/employee_security.xml',
        'security/ir.model.access.csv',

        'data/ir_cron_methods.xml',

        'views/res_config_settings_views.xml',
        'views/res_company_views.xml',
        'views/res_users_views.xml',
        'wizard/employee_change_view.xml',

        'wizard/contract_change_view.xml',
        'wizard/hr_employee_document_import_view.xml',
        'wizard/import_signatures_users_views.xml',
        'wizard/import_images_employees_views.xml',
        'wizard/massive_employee_modification_view.xml',
        'wizard/wizard_generate_reports.xml',
        'wizard/change_salary_tab_view.xml',
        'wizard/tab_change_view.xml',
        'wizard/wizard_low_position_view.xml',

        'views/hr_job_position_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_alimony_views.xml',
        'views/insurance_major_medical_views.xml',
        # 'views/hr_workplace_views.xml',
        # ~ 'views/hr_cost_center_views.xml',
        'views/table_antiquity.xml',
        'views/pilot_tab_view.xml',
        'views/attachment_layout.xml',
        'views/contract_salary_change_views.xml',
        'views/hr_contract.xml',
        'views/report_views.xml',
        'views/history_changes_employee_views.xml',
        'views/hr_employee_affiliate_views.xml',
        'views/report_affiliate_movements.xml',
        'views/affiliate_movements_actions.xml',
        'views/assets.xml',

        # Data
        'data/resource_calendar_data.xml',
        'data/sequence_data.xml',
        'data/data_table_antiquity.xml',
        'data/data_pilot_tab.xml',
        'data/templates_contracts.xml',
        'data/reports.xml',
    ],
    'qweb': [
        'static/src/xml/employee_templates.xml',
    ],
    'installable': True,
    'auto_install': False
}
