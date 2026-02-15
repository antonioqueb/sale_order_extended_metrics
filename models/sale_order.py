from odoo import models, fields, api
import json


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    metrics_data = fields.Text(
        string='Metrics Data',
        compute='_compute_metrics_data',
    )

    amount_pending_to_pay = fields.Monetary(
        string='Pendiente por Pagar',
        compute='_compute_metrics_data',
        currency_field='currency_id',
    )

    @api.depends(
        'order_line.qty_delivered',
        'order_line.product_uom_qty',
        'order_line.move_ids',
        'order_line.move_ids.state',
        'order_line.price_unit',
        'invoice_ids',
        'invoice_ids.state',
        'invoice_ids.amount_residual',
        'invoice_ids.line_ids.matched_credit_ids',
        'amount_total',
    )
    def _compute_metrics_data(self):
        for order in self:
            # --- Line metrics ---
            lines_data = []
            total_ordered = 0.0
            total_delivered = 0.0
            total_returned_qty = 0.0
            total_returned_amount = 0.0

            for line in order.order_line.filtered(lambda l: not l.display_type):
                # Fulfillment
                fulfillment = 0.0
                if line.product_uom_qty > 0:
                    fulfillment = round((line.qty_delivered / line.product_uom_qty) * 100, 1)

                # Returns
                returned_qty = 0.0
                out_moves = line.move_ids.filtered(
                    lambda m: m.state == 'done' and m.picking_code == 'outgoing'
                )
                if out_moves:
                    returns = self.env['stock.move'].search([
                        ('origin_returned_move_id', 'in', out_moves.ids),
                        ('state', '=', 'done'),
                    ])
                    returned_qty = sum(returns.mapped('product_uom_qty'))

                returned_amount = returned_qty * line.price_unit

                total_ordered += line.product_uom_qty
                total_delivered += line.qty_delivered
                total_returned_qty += returned_qty
                total_returned_amount += returned_amount

                lines_data.append({
                    'product': line.product_id.display_name or line.name,
                    'ordered': line.product_uom_qty,
                    'delivered': line.qty_delivered,
                    'fulfillment': fulfillment,
                    'returned_qty': returned_qty,
                    'returned_amount': returned_amount,
                    'price_unit': line.price_unit,
                    'uom': line.product_uom_id.name if line.product_uom_id else '',
                })

            # --- Payment metrics ---
            invoices = order.invoice_ids.filtered(lambda inv: inv.state == 'posted')
            payments_data = []
            payment_ids_seen = set()
            total_paid = 0.0

            for invoice in invoices:
                reconciled_partials = invoice.line_ids.mapped('matched_credit_ids')
                for partial in reconciled_partials:
                    pay = partial.credit_move_id.payment_id
                    if pay and pay.id not in payment_ids_seen:
                        payment_ids_seen.add(pay.id)
                        payments_data.append({
                            'id': pay.id,
                            'date': pay.date.strftime('%d/%m/%Y') if pay.date else '',
                            'name': pay.name or '',
                            'journal': pay.journal_id.name or '',
                            'amount': pay.amount,
                            'currency': pay.currency_id.symbol or '$',
                        })
                    if pay:
                        total_paid += partial.amount

            amount_pending = order.amount_total - total_paid

            # --- Summary ---
            overall_fulfillment = 0.0
            if total_ordered > 0:
                overall_fulfillment = round((total_delivered / total_ordered) * 100, 1)

            order.metrics_data = json.dumps({
                'lines': lines_data,
                'payments': payments_data,
                'summary': {
                    'total_ordered': total_ordered,
                    'total_delivered': total_delivered,
                    'overall_fulfillment': overall_fulfillment,
                    'total_returned_qty': total_returned_qty,
                    'total_returned_amount': round(total_returned_amount, 2),
                    'amount_total': order.amount_total,
                    'total_paid': round(total_paid, 2),
                    'amount_pending': round(amount_pending, 2),
                    'currency': order.currency_id.symbol or '$',
                    'has_returns': total_returned_qty > 0,
                    'has_payments': len(payments_data) > 0,
                },
            })
            order.amount_pending_to_pay = amount_pending

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    fulfillment_percent = fields.Float(
        string='% Cumplimiento',
        compute='_compute_line_metrics',
        store=True,
    )
    returned_qty_m2 = fields.Float(
        string='Devuelto',
        compute='_compute_line_metrics',
        store=True,
    )
    returned_amount = fields.Monetary(
        string='Monto Devuelto',
        compute='_compute_line_metrics',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('qty_delivered', 'product_uom_qty', 'move_ids', 'move_ids.state', 'price_unit')
    def _compute_line_metrics(self):
        for line in self:
            # Fulfillment
            if line.product_uom_qty > 0:
                line.fulfillment_percent = line.qty_delivered / line.product_uom_qty
            else:
                line.fulfillment_percent = 0.0

            # Returns
            returned_qty = 0.0
            out_moves = line.move_ids.filtered(
                lambda m: m.state == 'done' and m.picking_code == 'outgoing'
            )
            if out_moves:
                returns = self.env['stock.move'].search([
                    ('origin_returned_move_id', 'in', out_moves.ids),
                    ('state', '=', 'done'),
                ])
                returned_qty = sum(returns.mapped('product_uom_qty'))

            line.returned_qty_m2 = returned_qty
            line.returned_amount = returned_qty * line.price_unit