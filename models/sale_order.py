from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_ids = fields.Many2many(
        'account.payment',
        string='Desglose de Pagos',
        compute='_compute_payments_and_balance',
        store=False
    )
    
    amount_pending_to_pay = fields.Monetary(
        string='Pendiente por Pagar',
        compute='_compute_payments_and_balance',
        currency_field='currency_id'
    )

    @api.depends('invoice_ids', 'invoice_ids.state', 'invoice_ids.amount_residual')
    def _compute_payments_and_balance(self):
        for order in self:
            invoices = order.invoice_ids.filtered(lambda inv: inv.state == 'posted')
            payment_set = set()
            total_paid = 0.0

            for invoice in invoices:
                reconciled_partials = invoice.line_ids.mapped('matched_credit_ids')
                for partial in reconciled_partials:
                    if partial.credit_move_id.payment_id:
                        payment_set.add(partial.credit_move_id.payment_id.id)
                        total_paid += partial.amount

            order.payment_ids = [fields.Command.set(list(payment_set))]
            order.amount_pending_to_pay = order.amount_total - total_paid

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    fulfillment_percent = fields.Float(
        string='Fulfillment %',
        compute='_compute_line_metrics',
        store=False
    )
    
    returned_qty_m2 = fields.Float(
        string='Cant. Devuelta (m2)',
        compute='_compute_line_metrics',
        store=False,
        help='Cantidad devuelta basada en movimientos de retorno.'
    )
    
    returned_amount = fields.Monetary(
        string='Cant. Devuelta ($)',
        compute='_compute_line_metrics',
        store=False,
        currency_field='currency_id'
    )

    @api.depends('qty_delivered', 'product_uom_qty', 'move_ids')
    def _compute_line_metrics(self):
        for line in self:
            # 1. Fulfillment %
            # CORRECCIÓN: No multiplicar por 100. El widget percentage espera 0.5 para 50%, 1.0 para 100%.
            if line.product_uom_qty > 0:
                line.fulfillment_percent = line.qty_delivered / line.product_uom_qty
            else:
                line.fulfillment_percent = 0.0

            # 2. Lógica de Devoluciones
            returned_qty = 0.0
            out_moves = line.move_ids.filtered(lambda m: m.state == 'done' and m.picking_code == 'outgoing')
            
            if out_moves:
                returns = self.env['stock.move'].search([
                    ('origin_returned_move_id', 'in', out_moves.ids),
                    ('state', '=', 'done')
                ])
                returned_qty = sum(returns.mapped('product_uom_qty'))
            
            line.returned_qty_m2 = returned_qty
            line.returned_amount = returned_qty * line.price_unit