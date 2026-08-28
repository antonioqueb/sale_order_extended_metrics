/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const META = {
    new: { label: "Nueva", hint: "Sin pago, dentro del plazo del apartado" },
    ok: { label: "Al corriente", hint: "Con pago reciente y saldo pendiente" },
    paid: { label: "Pagada", hint: "Cubierta al 100 %" },
    slow: { label: "Lenta", hint: "Con anticipo, pero sin pagos recientes" },
    stalled: { label: "Estancada", hint: "Con anticipo, meses sin dinero nuevo" },
    nopay: { label: "Sin pago", hint: "Fuera del plazo del apartado y sin ningún pago" },
    dead: { label: "Abandonada", hint: "Muy vieja y sin ningún pago" },
    none: { label: "", hint: "" },
};

export class FlowLightField extends Component {
    static template = "sale_order_extended_metrics.FlowLightField";
    static props = { ...standardFieldProps };

    get value() {
        return this.props.record.data[this.props.name] || "none";
    }
    get meta() {
        return META[this.value] || META.none;
    }
    get days() {
        return this.props.record.data.x_flow_days;
    }
    get title() {
        const d = this.days;
        const m = this.meta;
        if (!m.label) return "";
        return d ? `${m.label} · ${d} día(s) — ${m.hint}` : `${m.label} — ${m.hint}`;
    }
}

registry.category("fields").add("flow_light", {
    component: FlowLightField,
    supportedTypes: ["selection"],
});
