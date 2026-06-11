{
    'name': 'Sale Order Extended Metrics (Odoo 19)',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Fulfillment %, Returns, and Payment Breakdown on SO',
    'author': 'Alphaqueb Consulting',
    'website': 'https://www.alphaqueb.com',
    'depends': ['sale', 'sale_management', 'stock', 'account', 'stock_transit_allocation'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sale_order_extended_metrics/static/src/css/metrics_widget.css',
            'sale_order_extended_metrics/static/src/js/metrics_widget.js',
            'sale_order_extended_metrics/static/src/xml/metrics_widget.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}