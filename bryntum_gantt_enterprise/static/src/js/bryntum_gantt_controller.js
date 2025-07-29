import {Component, onMounted, onWillDestroy, onWillStart} from "@odoo/owl";
import {Layout} from "@web/search/layout";
import {loadJS} from "@web/core/assets";
import {standardViewProps} from "@web/views/standard_view_props";
import {useService} from "@web/core/utils/hooks";

export class BryntumGanttController extends Component {
    static components = {Layout};
    static props = {
        ...standardViewProps,
        Renderer: Function,
        Model: {
            type: Function,
            optional: true,
        },
    };
    async setup() {
        this.orm = useService("orm");

        onWillDestroy(() => {
            var ganttContainer = document.getElementById("bryntum-scheduler-component");
            if (window.o_gantt !== undefined) {
                // Linter did not accept window.x && window.x.destroy
                if (window.o_gantt.histogram) {
                    window.o_gantt.histogram.destroy();
                }
                if (window.o_gantt.gantt) {
                    window.o_gantt.gantt.destroy();
                }
                if (window.o_gantt.splitter) {
                    window.o_gantt.splitter.destroy();
                }
            }
            if (ganttContainer !== undefined) {
                while (ganttContainer.firstChild) {
                    ganttContainer.removeChild(ganttContainer.firstChild);
                }
            }
        });
        onWillStart(async () => {
            var val = await this.get_response_values();
            await this.load_libs(val);

            // Checking if this is a reload
            // if it is we reattach existing window.o_gantt
            try {
                // This part is fetching from odoo view. it activates when
                // accessing the gantt, from the upper right "view button"
                if (this.props && this.props.domain.length > 0) {
                    // We look for a leaf that has project_id
                    // projectID was an int, now is a list, modified also in Bryntum-lib
                    window.o_gantt.projectID = this.get_project_id(this.props.domain);
                    window.action_from_odoo = true;
                } else {
                    window.o_gantt.projectID = 0;
                    window.action_from_odoo = false;
                }
                const week_start = parseInt(val.week_start, 10);
                if (!isNaN(week_start)) {
                    window.o_gantt.week_start = week_start;
                }
                window.o_gantt.readOnly = val.bryntum_readonly_project;
                window.o_gantt.saveWbs = val.bryntum_save_wbs;
                window.o_gantt.lang = val.lang;
                window.o_gantt.copy_dependencies = val.bryntum_copy_dependencies;
                eval("window.o_gantt.config = " + val.bryntum_gantt_config); // eslint-disable-line no-eval
                window.o_gantt.bryntum_auto_scheduling = val.bryntum_auto_scheduling;
                window.o_gantt.user_config = val.bryntum_gantt_user_config;
                window.o_gantt.allow_user_view_edit = val.allow_user_view_edit;
            } catch (err) {
                console.log("Gantt configuration object not valid");
            }
        });
        onMounted(() => {
            var ganttContainer = document.getElementById("bryntum-scheduler-component");
            window.o_gantt.create_all_elements(ganttContainer);
        });
    }
    // Getting Values on Initialization from a separate function
    async load_libs(val) {
        console.log("Loading gantt library version " + val.lib_version);
        const r1 = await loadJS(
            "/bryntum_gantt_enterprise/static/gantt_src/js/app.js?" + val.lib_version
        );
        const r2 = await loadJS(
            "/bryntum_gantt_enterprise/static/gantt_src/js/chunk-vendors.js?" +
                val.lib_version
        );
        return [r1, r2];
    }

    async get_response_values() {
        const response = await this.orm.call(
            "project.project",
            "get_bryntum_values",
            []
        );
        return response;
    }
    get_project_id(propsdomain) {
        // A very limited implementation to fetch the currently loaded project_ids
        // from odoo to gantt_view. Does not cover all possible domains.
        // normal odoo views will understand the domain as-is, while gantt-view , just
        // needs to know the ids of projects in a list. this translation is far from
        // complete , but will cover common cases, and will not fail in case of weird
        // domains, it will just load gantt without projects selected.
        var only_prj_leafs = propsdomain.filter((value) => {
            return value.length === 3 && value[0] === "project_id";
        });
        var project_ids = [];
        only_prj_leafs.forEach((leaf) => {
            if (leaf[1] === "=") {
                project_ids.push(leaf[2]);
            }
            if (leaf[1] === "in" && leaf[2].constructor === Array) {
                project_ids.concat(leaf[2]);
            }
        });
        return project_ids;
    }
}

/*
    Controller has separate view, so need to create its view with layout component
*/
BryntumGanttController.template = "bryntum_gantt_enterprise.ControllerView";
