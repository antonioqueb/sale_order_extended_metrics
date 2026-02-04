{
    'name': 'Sale Order Extended Metrics (Odoo 19)',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Fulfillment %, Returns, and Payment Breakdown on SO',
    'author': 'Assistant',
    'depends': ['sale', 'sale_management', 'stock', 'account'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
