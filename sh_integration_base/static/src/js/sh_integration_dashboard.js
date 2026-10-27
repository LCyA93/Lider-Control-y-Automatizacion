/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

import { Component, onWillStart, onMounted, onPatched, onWillUnmount, useState, useRef } from "@odoo/owl";

export class ShIntegrationDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.detailSyncCanvas = useRef("detailSyncCanvas");
        this.detailEntityCanvas = useRef("detailEntityCanvas");
        this.syncChart = null;
        this.entityChart = null;
        this._refreshTimer = null;

        this.state = useState({
            view: "overview",       // "overview" | "detail"
            loading: true,
            connectors: [],         // kanban cards data
            detail: null,           // selected connector detail
        });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this._loadOverview();
        });

        onMounted(() => {
            if (this.state.view === "detail") this._renderDetailCharts();
            this._refreshTimer = setInterval(() => {
                if (this.state.view === "overview") this._loadOverview();
            }, 5 * 60 * 1000);
        });

        onPatched(() => {
            if (this.state.view === "detail") this._renderDetailCharts();
        });

        onWillUnmount(() => {
            if (this._refreshTimer) clearInterval(this._refreshTimer);
            this._destroyCharts();
        });
    }

    // ── Data loading ────────────────────────────────────────────────────────

    async _loadOverview() {
        try {
            const data = await this.orm.call(
                "sh.integration.overview", "get_dashboard_data", []
            );
            this.state.connectors = data;
            this.state.loading = false;
        } catch (e) {
            console.error("Integration overview load error:", e);
            this.state.loading = false;
        }
    }

    async openDetail(connectorId) {
        const con = this.state.connectors.find(c => c.id === connectorId);
        if (con && con.dashboard_action) {
            this.action.doAction(con.dashboard_action);
            return;
        }
        // fallback: open internal detail view if no own dashboard registered
        this.state.loading = true;
        this.state.view = "detail";
        try {
            const data = await this.orm.call(
                "sh.integration.overview", "get_connector_detail", [connectorId]
            );
            this.state.detail = data;
        } catch (e) {
            console.error("Connector detail load error:", e);
        }
        this.state.loading = false;
    }

    async openConfig(connectorId) {
        const con = this.state.connectors.find(c => c.id === connectorId);
        if (con && con.config_action) {
            this.action.doAction(con.config_action);
        }
    }

    backToOverview() {
        this._destroyCharts();
        this.state.view = "overview";
        this.state.detail = null;
    }

    async refreshDetail() {
        if (!this.state.detail) return;
        await this.openDetail(this.state.detail.id);
    }

    async openEntity(model, domain) {
        if (!model) return;
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: Array.isArray(domain) ? domain : [],
            target: 'current',
        });
    }

    async openLogs(connectorId) {
        try {
            const action = await this.orm.call(
                "sh.integration.overview", "get_log_action", [connectorId]
            );
            if (action) {
                this.action.doAction(action);
            }
        } catch (e) {
            console.error("Open logs error:", e);
        }
    }

    // ── Detail Charts ───────────────────────────────────────────────────────

    _destroyCharts() {
        if (this.syncChart) { this.syncChart.destroy(); this.syncChart = null; }
        if (this.entityChart) { this.entityChart.destroy(); this.entityChart = null; }
    }

    _renderDetailCharts() {
        this._renderSyncChart();
        this._renderEntityChart();
    }

    _renderSyncChart() {
        if (!this.detailSyncCanvas.el) return;
        this._destroySyncChart();
        const d = this.state.detail;
        if (!d) return;

        this.syncChart = new Chart(this.detailSyncCanvas.el.getContext("2d"), {
            type: "bar",
            data: {
                labels: d.chart_labels || [],
                datasets: [
                    {
                        label: "Success",
                        data: d.chart_success || [],
                        backgroundColor: "rgba(0,152,121,0.85)",
                        borderRadius: 4,
                        stack: "s",
                    },
                    {
                        label: "Error",
                        data: d.chart_error || [],
                        backgroundColor: "rgba(220,53,69,0.75)",
                        borderRadius: 4,
                        stack: "s",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top", labels: { font: { size: 11 }, boxWidth: 12 } },
                    tooltip: {
                        mode: "index", intersect: false,
                        backgroundColor: "rgba(255,255,255,0.95)",
                        titleColor: "#1e293b", bodyColor: "#475569",
                        borderColor: "#e2e8f0", borderWidth: 1,
                        padding: 10, cornerRadius: 8,
                    },
                },
                scales: {
                    x: { grid: { display: false }, stacked: true },
                    y: { beginAtZero: true, stacked: true, grid: { color: "#f1f5f9" }, ticks: { precision: 0 } },
                },
            },
        });
    }

    _destroySyncChart() {
        if (this.syncChart) { this.syncChart.destroy(); this.syncChart = null; }
    }

    _renderEntityChart() {
        if (!this.detailEntityCanvas.el) return;
        if (this.entityChart) { this.entityChart.destroy(); this.entityChart = null; }
        const d = this.state.detail;
        if (!d || !d.entities || !d.entities.length) return;

        const PALETTE = ["#009879","#0dbaa3","#3490dc","#9b59b6","#e67e22","#2ecc71","#e74c3c","#f39c12"];

        this.entityChart = new Chart(this.detailEntityCanvas.el.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: d.entities.map((e) => e.label),
                datasets: [{
                    data: d.entities.map((e) => e.count),
                    backgroundColor: PALETTE.slice(0, d.entities.length),
                    borderWidth: 2, borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: {
                    legend: { position: "bottom", labels: { font: { size: 10 }, padding: 8, boxWidth: 12 } },
                },
            },
        });
    }

    // ── Kanban card helpers ──────────────────────────────────────────────────

    successRate(con) {
        const success = (con.chart_success || []).reduce((a, b) => a + b, 0);
        const error = (con.chart_error || []).reduce((a, b) => a + b, 0);
        const total = success + error;
        if (!total) return null; // no sync data in last 7 days
        return Math.round((success / total) * 100);
    }

    totalApiCalls(con) {
        const success = (con.chart_success || []).reduce((a, b) => a + b, 0);
        const error = (con.chart_error || []).reduce((a, b) => a + b, 0);
        return success + error;
    }

    avatarColor(con) {
        const COLORS = [
            '#6c757d', '#dc3545', '#fd7e14', '#ffc107', '#0dcaf0',
            '#6f42c1', '#d63384', '#20c997', '#198754', '#0d6efd',
            '#009879', '#6610f2',
        ];
        return COLORS[(con.color || 0) % COLORS.length];
    }

    avatarLetter(con) {
        return (con.name || '?')[0].toUpperCase();
    }

    // ── Mini sparkline helpers (kanban cards — CSS bars, no Chart.js) ───────

    /**
     * Returns an array of {successH, errorH} (pixel heights 4–48) for 7-day bars.
     */
    miniBarHeights(connector) {
        const success = connector.chart_success || [];
        const error = connector.chart_error || [];
        const maxVal = Math.max(...success.map((v, i) => v + (error[i] || 0)), 1);
        const MAX_H = 44;
        return success.map((s, i) => {
            const e = error[i] || 0;
            const total = s + e;
            const totalH = Math.max(Math.round((total / maxVal) * MAX_H), total > 0 ? 4 : 0);
            const eH = total > 0 ? Math.round((e / total) * totalH) : 0;
            return {
                successH: totalH - eH,
                errorH: eH,
                label: (connector.chart_labels || [])[i] || "",
                success: s,
                error: e,
            };
        });
    }

    // ── Queue helpers ───────────────────────────────────────────────────────

    queueTotal(q) {
        if (!q) return 0;
        return (q.pending || 0) + (q.done || 0) + (q.error || 0);
    }

    queuePct(q, key) {
        const t = this.queueTotal(q);
        if (!t) return 0;
        return Math.round(((q[key] || 0) / t) * 100);
    }

    // ── Time helpers ─────────────────────────────────────────────────────────

    formatRelativeTime(dateStr) {
        if (!dateStr) return "Never";
        const date = new Date(dateStr.replace(" ", "T") + "Z");
        const diff = Math.floor((Date.now() - date.getTime()) / 1000);
        if (diff < 60) return "Just now";
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    }
}

ShIntegrationDashboard.template = "sh_integration_base.OverviewDashboard";
registry.category("actions").add("sh_integration_overview_action", ShIntegrationDashboard);
