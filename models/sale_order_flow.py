# -*- coding: utf-8 -*-
"""Semáforo de flujo de dinero por orden de venta.

Regla de negocio (SOM, 28 ago 2026): una orden confirmada sin ningún pago
después del plazo de un apartado (10 días) es mal uso de la orden de venta;
con anticipo pero sin movimiento de dinero durante meses también degrada.
El semáforo se ALMACENA para poder filtrar/agrupar en la lista y lo
recalcula un cron diario (la edad cambia sola) y cualquier cambio de pago o
factura (depends)."""
from datetime import date

from odoo import models, fields, api
from odoo.tools.float_utils import float_compare

FLOW_STATES = [
    ('new', 'Nueva'),
    ('ok', 'Al día'),
    ('paid', 'Pagada'),
    ('slow', 'Lenta'),
    ('stalled', 'Estancada'),
    ('nopay', 'Sin pago'),
    ('dead', 'Dejado'),
    ('none', 'N/A'),
]
# Orden del semáforo: 0 = peor (más viejo/sin dinero) … 6 = mejor.
FLOW_RANK = {'dead': 0, 'nopay': 1, 'stalled': 2, 'slow': 3, 'new': 4, 'ok': 5, 'paid': 6, 'none': 9}

PARAMS = {
    'no_payment_days': ('sale_order_extended_metrics.no_payment_days', 10),
    'dead_days': ('sale_order_extended_metrics.dead_days', 30),
    'stale_days': ('sale_order_extended_metrics.stale_days', 60),
    'stalled_days': ('sale_order_extended_metrics.stalled_days', 90),
}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_flow_status = fields.Selection(
        FLOW_STATES, string='Semáforo', compute='_compute_flow_light', store=True, index=True,
        help='Nueva/Sin pago/Dejado: sin ningún pago, por días desde la orden. '
             'Al día/Lenta/Estancada: con pago pero saldo pendiente, por días desde el último pago. '
             'Pagada: 100% cubierta.')
    x_flow_rank = fields.Integer(string='Orden semáforo', compute='_compute_flow_light', store=True,
                                 help='0 = peor … 6 = mejor. Sirve para ordenar la lista.')
    x_flow_days = fields.Integer(string='Días sin dinero', compute='_compute_flow_light', store=True,
                                 help='Días desde la orden (sin pago) o desde el último pago (con saldo).')
    x_flow_last_payment = fields.Date(string='Último pago', compute='_compute_flow_light', store=True)
    x_flow_paid_pct = fields.Float(string='% Pagado', compute='_compute_flow_light', store=True, digits=(5, 1))
    # Asignación de placas (fuente única: tc_qty_assigned_lots de la línea,
    # stock_transit_allocation). En vivo (no almacenado): la asignación cambia
    # con cada placa que se asigna o se libera.
    x_flow_assigned_pct = fields.Float(
        string='% Asignado', compute='_compute_flow_assigned', digits=(5, 1),
        help='Cantidad cubierta por placas/lotes asignados ÷ cantidad vendida (líneas de producto).')
    x_flow_assigned_m2 = fields.Float(
        string='Apartado (m²)', compute='_compute_flow_assigned', digits='Product Unit of Measure',
        help='Suma de la cantidad asignada (placas/lotes) en las líneas de producto de la orden.')

    def _compute_flow_assigned(self):
        Line = self.env['sale.order.line']
        has_tc = 'tc_qty_assigned_lots' in Line._fields
        for order in self:
            lines = order.order_line.filtered(
                lambda l: not l.display_type and l.product_id and l.product_id.type != 'service')
            ordered = sum(lines.mapped('product_uom_qty'))
            assigned = sum(lines.mapped('tc_qty_assigned_lots')) if has_tc else 0.0
            order.x_flow_assigned_m2 = assigned
            order.x_flow_assigned_pct = round(max(min(assigned / ordered * 100.0, 100.0), 0.0), 1) if ordered > 0 else 0.0

    x_flow_delivered_pct = fields.Float(
        string='% Entregado', compute='_compute_flow_light', store=True, digits=(5, 1),
        help='Cantidad entregada ÷ cantidad vendida (líneas de producto). Entregar sin cobrar AGRAVA el semáforo.')

    # ------------------------------------------------------------------
    @api.model
    def _flow_thresholds(self):
        P = self.env['ir.config_parameter'].sudo()
        out = {}
        for key, (param, default) in PARAMS.items():
            try:
                out[key] = int(float(P.get_param(param, default) or default))
            except (TypeError, ValueError):
                out[key] = default
        return out

    def _flow_last_payment_date(self):
        """Fecha del último DINERO recibido: conciliación de la cuenta por
        cobrar de facturas publicadas contra pagos (no contra notas de
        crédito)."""
        self.ensure_one()
        invoices = self.invoice_ids.filtered(
            lambda m: m.state == 'posted' and m.move_type in ('out_invoice', 'out_refund'))
        if not invoices:
            return False
        recv = invoices.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
        if not recv:
            return False
        partials = self.env['account.partial.reconcile'].sudo().search([
            '|', ('debit_move_id', 'in', recv.ids), ('credit_move_id', 'in', recv.ids)])
        dates = []
        for p in partials:
            other = p.credit_move_id.move_id if p.debit_move_id in recv else p.debit_move_id.move_id
            if other.move_type in ('out_invoice', 'out_refund'):
                continue   # factura ↔ nota de crédito: no es dinero
            if p.max_date:
                dates.append(p.max_date)
        return max(dates) if dates else False

    def _flow_delivered_pct(self):
        """% entregado ponderado por cantidad (solo líneas de producto)."""
        self.ensure_one()
        lines = self.order_line.filtered(
            lambda l: not l.display_type and l.product_id and l.product_id.type != 'service')
        ordered = sum(lines.mapped('product_uom_qty'))
        if ordered <= 0:
            return 0.0
        delivered = sum(lines.mapped('qty_delivered'))
        return max(min(delivered / ordered * 100.0, 100.0), 0.0)

    # Entregar material sin tener el dinero es lo más grave: el % entregado
    # AGRAVA un nivel el semáforo (28 ago 2026).
    _ESCALATE = {'new': 'nopay', 'nopay': 'dead', 'ok': 'slow', 'slow': 'stalled'}

    @api.depends('state', 'date_order', 'amount_total', 'currency_id',
                 'delivery_paid_amount', 'delivery_is_fully_paid',
                 'invoice_ids.state', 'invoice_ids.amount_residual', 'invoice_ids.payment_state',
                 'order_line.qty_delivered', 'order_line.product_uom_qty')
    def _compute_flow_light(self):
        th = self._flow_thresholds()
        today = fields.Date.context_today(self)
        for order in self:
            status, days, last_pay, pct = 'none', 0, False, 0.0
            delivered_pct = order._flow_delivered_pct() if order.state == 'sale' else 0.0
            total = order.amount_total or 0.0
            if order.state == 'sale' and total > 0:
                paid = order.delivery_paid_amount or 0.0
                pct = max(min(paid / total * 100.0, 100.0), 0.0)
                rounding = order.currency_id.rounding or 0.01
                order_day = fields.Datetime.context_timestamp(order, order.date_order).date() if order.date_order else today
                if float_compare(paid, total, precision_rounding=rounding) >= 0:
                    status, days = 'paid', 0
                    last_pay = order._flow_last_payment_date()
                elif paid <= 0:
                    days = max((today - order_day).days, 0)
                    if days <= th['no_payment_days']:
                        status = 'new'
                    elif days <= th['dead_days']:
                        status = 'nopay'
                    else:
                        status = 'dead'
                else:
                    last_pay = order._flow_last_payment_date() or order_day
                    days = max((today - last_pay).days, 0)
                    if days <= th['stale_days']:
                        status = 'ok'
                    elif days <= th['stalled_days']:
                        status = 'slow'
                    else:
                        status = 'stalled'
                # ── Agravante por entrega ──
                # Sin ningún pago y ya se entregó algo: sube un nivel de
                # inmediato (Nueva→Sin pago, Sin pago→Dejado).
                # Con pago parcial: si lo entregado va muy por delante de lo
                # pagado (más de 20 puntos), sube un nivel (Al día→Lenta,
                # Lenta→Estancada).
                if status in ('new', 'nopay') and delivered_pct >= 1.0:
                    status = self._ESCALATE[status]
                elif status in ('ok', 'slow') and delivered_pct > pct + 20.0:
                    status = self._ESCALATE[status]
            order.x_flow_status = status
            order.x_flow_delivered_pct = round(delivered_pct, 1)
            order.x_flow_rank = FLOW_RANK.get(status, 9)
            order.x_flow_days = days
            order.x_flow_last_payment = last_pay
            order.x_flow_paid_pct = round(pct, 1)

    @api.model
    def _cron_flow_light_refresh(self):
        """La edad cambia sola: recalcula a diario las órdenes confirmadas
        que no están pagadas al 100 %."""
        orders = self.search([('state', '=', 'sale'), ('x_flow_status', 'not in', ('paid', 'none'))])
        orders += self.search([('state', '=', 'sale'), ('x_flow_status', '=', False)])
        if orders:
            orders._compute_flow_light()
        return True
