{
    'name': 'Sale Order Extended Metrics (Odoo 19)',
    'version': '19.0.2.1.0',
    'category': 'Sales',
    'summary': 'Fulfillment %, Returns, Payment Breakdown y Semáforo de flujo de dinero en la orden de venta',
    'author': 'Alphaqueb Consulting',
    'website': 'https://www.alphaqueb.com',
    # sale_delivery_auth: fuente única del pagado real (delivery_paid_amount) para el semáforo
    'depends': ['sale', 'sale_management', 'stock', 'account', 'stock_transit_allocation', 'sale_delivery_auth'],
    'data': [
        'data/ir_cron_flow_light.xml',
        'views/sale_order_views.xml',
        'views/sale_order_flow_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sale_order_extended_metrics/static/src/css/metrics_widget.css',
            'sale_order_extended_metrics/static/src/js/metrics_widget.js',
            'sale_order_extended_metrics/static/src/xml/metrics_widget.xml',
            'sale_order_extended_metrics/static/src/flow_light/flow_light.js',
            'sale_order_extended_metrics/static/src/flow_light/flow_light.xml',
            'sale_order_extended_metrics/static/src/flow_light/flow_light.scss',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}