from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    flow_no_payment_days = fields.Integer(
        string='Días sin pago → "Sin pago"', config_parameter='sale_order_extended_metrics.no_payment_days', default=10,
        help='Días desde la orden sin ningún pago para dejar de ser "Nueva" (duración de un apartado).')
    flow_dead_days = fields.Integer(
        string='Días sin pago → "Abandonada"', config_parameter='sale_order_extended_metrics.dead_days', default=30)
    flow_stale_days = fields.Integer(
        string='Días desde el último pago → "Lenta"', config_parameter='sale_order_extended_metrics.stale_days', default=60)
    flow_stalled_days = fields.Integer(
        string='Días desde el último pago → "Estancada"', config_parameter='sale_order_extended_metrics.stalled_days', default=90)
