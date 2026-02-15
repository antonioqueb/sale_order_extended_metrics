/** @odoo-module **/

import { Component, useState, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class SaleMetricsWidget extends Component {
    static template = "sale_order_extended_metrics.SaleMetricsWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.actionService = useService("action");
        const data = this._parse(this.props.record.data[this.props.name]);
        this.state = useState({
            lines: data.lines,
            payments: data.payments,
            summary: data.summary,
            showLines: true,
            showPayments: true,
        });
        onWillUpdateProps((next) => {
            const d = this._parse(next.record.data[next.name]);
            this.state.lines = d.lines;
            this.state.payments = d.payments;
            this.state.summary = d.summary;
        });
    }

    _defaultSummary() {
        return {
            total_ordered: 0, total_delivered: 0, overall_fulfillment: 0,
            total_returned_qty: 0, total_returned_amount: 0,
            amount_total: 0, total_paid: 0, amount_pending: 0,
            currency: '$', has_returns: false, has_payments: false,
        };
    }

    _parse(value) {
        const empty = { lines: [], payments: [], summary: this._defaultSummary() };
        try {
            if (!value || value === "false" || value === false) return empty;
            let parsed = value;
            if (typeof value === "string") {
                parsed = JSON.parse(value);
            }
            return {
                lines: parsed.lines || [],
                payments: parsed.payments || [],
                summary: Object.assign(this._defaultSummary(), parsed.summary || {}),
            };
        } catch (e) {
            console.error("SaleMetricsWidget parse error:", e);
            return empty;
        }
    }

    toggleLines() {
        this.state.showLines = !this.state.showLines;
    }

    togglePayments() {
        this.state.showPayments = !this.state.showPayments;
    }

    async openPayment(id) {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "account.payment",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    getFulfillmentClass(pct) {
        if (pct >= 100) return "sm-fill-done";
        if (pct > 0) return "sm-fill-partial";
        return "sm-fill-zero";
    }

    getFulfillmentBadge(pct) {
        if (pct >= 100) return "sm-badge-done";
        if (pct > 0) return "sm-badge-partial";
        return "sm-badge-zero";
    }

    formatNumber(val) {
        if (val === undefined || val === null) return "0";
        return parseFloat(val).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    formatQty(val) {
        if (val === undefined || val === null) return "0";
        const n = parseFloat(val);
        if (n === Math.floor(n)) return n.toLocaleString("es-MX");
        return n.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
}

registry.category("fields").add("sale_metrics_widget", {
    component: SaleMetricsWidget,
});