# -*- coding: utf-8 -*-

{
    "name": "Base Extension",
    "summary": "Utilities functions for base model",
    "version": "1.0",
    "description": """
        Utilities functions for base model 
    """,
    "author": "Ingdesof",
    "license": "OPL-1",
    "installable": True,
    "depends": [
        'base',
        'web',
        'website_slides',
        'website_calendar',
        'auth_signup',
        'hr',
        'gamification',
        'ot_theme_blue',
        'website_livechat',
        'survey',
    ],
    "data": [
        'templates/ot_web_adresses.xml',
        'data/website_data.xml',
        'data/forum_data.xml',
        'data/ir_config_parameter.xml',
        'data/gamification_karma_rank_data.xml',
        'data/job_positions.xml',
        'data/adresses.xml',
        'security/ir.model.access.csv',
        'security/website_slides_security.xml',
        'view/website_templates.xml',
        'view/website_calendar_templates.xml',
        'view/website_forum.xml',
        'view/addresses.xml',
        'view/res_users_views.xml',
        'view/website_slides_templates_course.xml',
        'view/http_routing_template.xml',
        'view/slide_channel_views.xml',
        'view/website_slides_templates_homepage.xml',
        'view/ot_constancy.xml',
        'templates/website_delete_elements_templates.xml',
        'templates/web_client_templates.xml',
        'templates/template_welcome_aeromar.xml',
        'view/show_hide_password.xml',
        'templates/ot_web_user_register.xml',

    ],
    'css': [
        '/ot_website_slides/static/src/swiper/css/swiper-tema.css',
        ],
    'odoo-apps' : True
}

