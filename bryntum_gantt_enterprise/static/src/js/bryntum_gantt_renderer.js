import {Component} from "@odoo/owl";

export class BryntumGanttRenderer extends Component {
    static components = {};
    static props = {};
    static template = "bryntum_gantt_enterprise.BryntumGanttRenderer";
    async setup() {
        console.log("Bypassing Setup in renderer with noop override");
    }
}

BryntumGanttRenderer.template = "bryntum_gantt_enterprise.Renderer";
