# OWL Components — Power BI Odoo Connector
Status: [ACTIVE]
Backlink: [[00_overview]]

## SHPowerBIDashboard (registry action "sh_powerbi_dashboard")
Status: [ACTIVE]
Purpose: Renders a control dashboard with real-time status stats, connection states, sync queue charts, and manual processing actions.
Props: Extends standard Odoo ActionService props.
Emits: None (Direct ORM RPC calls are made).

### State Management
Utilizes OWL `useState` to store loading indicators and retrieve metrics:
```javascript
this.state = useState({
    loading: true,
    data: {},
});
```

### Remote Procedure Calls (RPC)
The component executes Odoo ORM methods on `sh.powerbi.push.config`:
* **`sh_powerbi_get_dashboard_data`**: Renders counts of success/failed logs, queue sizing, and charts array.
* **`sh_powerbi_dashboard_push_now`**: Triggers immediate data push for a specific `model.access`.
* **`sh_powerbi_dashboard_test_connection`**: Executes authorization tokens check with Microsoft Azure.
* **`sh_powerbi_dashboard_run_cron_now`**: Triggers back-end scheduled cron process immediately.
* **`sh_powerbi_dashboard_toggle_cron`**: Toggles cron active state (True/False).
* **`sh_powerbi_dashboard_process_queue`**: Executes processing for a selected batch queue item.
* **`sh_powerbi_dashboard_open_model`**: Returns action dictionary to navigate to Odoo form views.

### Critical Implementation Note
Event handlers in `sh_powerbi_dashboard.xml` (like `t-on-click`) must call component methods bound to `this` context (e.g. `this.pushNow`) to prevent JS reference errors.
