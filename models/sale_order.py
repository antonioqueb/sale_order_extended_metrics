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
            # Obtener facturas publicadas vinculadas a la orden
            invoices = order.invoice_ids.filtered(lambda inv: inv.state == 'posted')
            
            # Encontrar pagos conciliados
            # Buscamos en las lineas de conciliacion parcial para obtener los pagos reales
            payment_set = set()
            total_paid = 0.0

            for invoice in invoices:
                # Obtener info de pagos a traves del widget de conciliacion o relaciones directas
                # Estrategia robusta: buscar creditos conciliados (si es factura de cliente)
                reconciled_partials = invoice.line_ids.mapped('matched_credit_ids')
                for partial in reconciled_partials:
                    if partial.credit_move_id.payment_id:
                        payment_set.add(partial.credit_move_id.payment_id.id)
                        # Sumamos lo que este pago cubrio de la factura (amount es la totalidad del pago, amount_currency lo aplicado)
                        # Usamos la cantidad conciliada en la moneda de la orden si es posible
                        total_paid += partial.amount

            order.payment_ids = [fields.Command.set(list(payment_set))]
            
            # Calculo del pendiente:
            # Opcion A: Total Orden - Total Pagado (Independiente de si se facturo todo)
            # Opcion B: Suma de residuos de facturas.
            # Según requerimiento: "cuanto le falta al cliente para cubrir el total restante"
            # Asumimos Total Orden - Pagos detectados.
            
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
            if line.product_uom_qty > 0:
                line.fulfillment_percent = (line.qty_delivered / line.product_uom_qty) * 100
            else:
                line.fulfillment_percent = 0.0

            # 2. Logica de Devoluciones
            # Buscamos movimientos donde el origen sea un movimiento de esta linea (devoluciones)
            # Stock move relations: move_orig_ids (de donde viene) y move_dest_ids (a donde va)
            # Una devolucion suele tener como 'origin_returned_move_id' el movimiento de salida original.
            
            returned_qty = 0.0
            
            # Obtenemos los movimientos de salida de esta linea
            out_moves = line.move_ids.filtered(lambda m: m.state == 'done' and m.picking_code == 'outgoing')
            
            if out_moves:
                # Buscamos en todo stock.move aquellos que sean retornos de estos movimientos
                returns = self.env['stock.move'].search([
                    ('origin_returned_move_id', 'in', out_moves.ids),
                    ('state', '=', 'done')
                ])
                returned_qty = sum(returns.mapped('product_uom_qty'))
            
            line.returned_qty_m2 = returned_qty
            line.returned_amount = returned_qty * line.price_unit
