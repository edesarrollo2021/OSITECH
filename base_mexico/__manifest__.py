{
    'name': 'Base Mexico',
    'version': '1.0',
    'summary': 'basic things for Mexico',
    'description': 'basic things for Mexico',
    'author': 'Soluciones Softhard, C.A.',
    'website': 'http://www.solucionesofthard.com',
    'depends': ['base', 'l10n_mx_edi_extended', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/localitation_views.xml',
        'views/res_company_views.xml',
        'views/res_bank.xml',
        'data/data_delegacion.xml',
    ],
    'installable': True,
    'auto_install': False
}
