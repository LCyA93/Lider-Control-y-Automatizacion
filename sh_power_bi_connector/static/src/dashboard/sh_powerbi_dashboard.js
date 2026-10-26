/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, useState } from "@odoo/owl";

export class SHPowerBIDashboard extends Component {
    static props = { ...standardActionServiceProps };
    static template = "sh_power_bi_connector.SHPowerBIDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            data: {},
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "sh.powerbi.push.config",
                "sh_powerbi_get_dashboard_data",
                []
            );
        } finally {
            this.state.loading = false;
        }
    }

    async handleServerAction(result) {
        if (result && result.type) {
            await this.action.doAction(result);
        }
        await this.loadDashboard();
    }

    async pushNow(modelAccessId) {
        const result = await this.orm.call(
            "sh.powerbi.push.config",
            "sh_powerbi_dashboard_push_now",
            [modelAccessId]
        );
        await this.handleServerAction(result);
    }

    async testConnection(configId) {
        const result = await this.orm.call(
            "sh.powerbi.push.config",
            "sh_powerbi_dashboard_test_connection",
            [configId]
        );
        await this.handleServerAction(result);
    }

    async runCronNow() {
        const result = await this.orm.call(
            "sh.powerbi.push.config",
            "sh_powerbi_dashboard_run_cron_now",
            []
        );
        await this.handleServerAction(result);
    }

    async toggleCron() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "sh.powerbi.push.config",
                "sh_powerbi_dashboard_toggle_cron",
                [!this.cron.active]
            );
        } finally {
            this.state.loading = false;
        }
    }

    async processQueue(queueId) {
        const result = await this.orm.call(
            "sh.powerbi.push.config",
            "sh_powerbi_dashboard_process_queue",
            [queueId]
        );
        await this.handleServerAction(result);
    }

    async openModel(modelAccessId) {
        const result = await this.orm.call(
            "sh.powerbi.push.config",
            "sh_powerbi_dashboard_open_model",
            [modelAccessId]
        );
        await this.action.doAction(result);
    }

    openAction(xmlId) {
        return this.action.doAction(xmlId);
    }

    badgeClass(state) {
        const classes = {
            authorized: "text-bg-success",
            draft: "text-bg-warning",
            error: "text-bg-danger",
            done: "text-bg-success",
            failed: "text-bg-danger",
            cancelled: "text-bg-secondary",
            running: "text-bg-info",
            processing: "text-bg-info",
            ready: "text-bg-success",
            not_synced: "text-bg-secondary",
        };
        return classes[state] || "text-bg-secondary";
    }

    kpiToneClass(tone) {
        const classes = {
            success: "o_sh_powerbi_kpi_success",
            warning: "o_sh_powerbi_kpi_warning",
            danger: "o_sh_powerbi_kpi_danger",
            info: "o_sh_powerbi_kpi_info",
            muted: "o_sh_powerbi_kpi_muted",
        };
        return classes[tone] || classes.muted;
    }

    alertClass(level) {
        const classes = {
            danger: "alert-danger",
            warning: "alert-warning",
            info: "alert-info",
            success: "alert-success",
        };
        return classes[level] || "alert-info";
    }

    get data() {
        return this.state.data || {};
    }

    get cron() {
        return this.data.cron || {};
    }

    get queueChart() {
        return this.data.queue_chart || [];
    }

    get logChart() {
        return this.data.log_chart || [];
    }

    get hasDashboardData() {
        return Boolean(this.data.generated_at);
    }

    get emptyMessage() {
        return _t("No Power BI dashboard data is available yet.");
    }
}

registry.category("actions").add("sh_powerbi_dashboard", SHPowerBIDashboard);
