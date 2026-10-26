# Models — Power BI Odoo Connector
Status: [ACTIVE]
Backlink: [[00_overview]]

## res.company (extension)
Status: [ACTIVE]
Purpose: Holds the company scoped Power BI integration settings.
Key Fields:
- `sh_powerbi_api_key` (Char): Readonly copy of the encrypted API key used by the `.mez` connector.
- `sh_powerbi_fetch_mode` (Selection): `all` (every model the API key user may read) or `configured` (only models listed in Model Access).
- `sh_powerbi_relation_format` (Selection): `id_and_display` (default) / `id_only` / `display_only`. Controls how relational fields are exported to Power BI. See [[02_data_flow#Flow 2b: Relational Field Format]].

---

## sh.powerbi.push.config
Status: [ACTIVE]
Purpose: Manages credentials and authentication details required to push Odoo data to Power BI workspaces.
Key Fields:
- `client_id` (Char): Client App ID registered in Microsoft Azure portal.
- `tenant_id` (Char): Tenant ID of the Azure Active Directory.
- `client_secret` (Char): Client secret key generated in Azure App Registrations.
- `workspace_id` (Char): Target Power BI workspace UUID.
- `access_token` (Char): Current active OAuth access token.
- `access_token_write_date` (Datetime): Timestamp of last token refresh.
- `state` (Selection): Status ('draft', 'authorized', 'error').
Critical Methods:
- `action_authenticate`: Authenticates with Microsoft Identity platform to acquire an access token.
- `action_test_connection`: Verifies the API token is valid by fetching Power BI workspace properties.

---

## sh.powerbi.model.access
Status: [ACTIVE]
Purpose: Configures data push schemas, model selection, filters, and allowed fields.
Key Fields:
- `model_id` (Many2one): The Odoo model to sync (e.g. `sale.order`).
- `display_alias` (Char): Alias used for the dataset table name in Power BI.
- `domain_filter` (Char): Domain string to filter Odoo records before sync.
- `allowed_field_ids` (Many2many): Specific stored fields to synchronize.
- `enable_delta` (Boolean): Enable incremental delta changes sync.
- `enable_realtime` (Boolean): Instantly queues a push job on record updates.
- `powerbi_selected_field_count` (Integer): Count of selected fields.
- `powerbi_table_count` (Integer): Number of split tables on Power BI side (due to column limit).
- `target_mode` (Selection): Selects `powerbi_push`, `fabric_kql`, or `fabric_pipeline`.
- `fabric_config_id` / `fabric_item_id`: Optional Fabric target references.
- `fabric_target_name`: Optional target table/item name for Fabric-oriented sync.
- `checkpoint_ids`: Per-target sync checkpoints.
Critical Methods:
- `action_push_schema`: Checks columns layout, creates push dataset schema payload, and makes REST call to create/update Power BI datasets.
- `action_run_target_sync`: Runs either existing Power BI push or Fabric sync based on target mode.
- `action_validate_data_quality`: Opens the validation wizard for domain/field checks.
- `action_rebuild_all_datasets`: Recreates every Power BI dataset of the configuration. Required after a relational field format change, because Power BI push datasets cannot alter an existing column type.

---

## sh.powerbi.push.queue
Status: [ACTIVE]
Purpose: Decouples Odoo transaction saves from Power BI API calls during real-time updates.
Key Fields:
- `model_access_id` (Many2one): Reference to the Model Access config.
- `record_id` (Integer): ID of the mutated Odoo record.
- `action` (Selection): Mutation type ('write', 'unlink', 'create').
- `state` (Selection): Queue state ('ready', 'processing', 'done', 'failed').
Critical Methods:
- `process_queue_batch`: Fetches ready queue items, groups them by model, formats row changes, updates Power BI tables, and marks items done.

---

## sh.powerbi.log
Status: [ACTIVE]
Purpose: Audits sync results, recording success counts and error messages.
Key Fields:
- `name` (Char): Log reference sequence.
- `model_access_id` (Many2one): Reference to the Model Access config.
- `push_config_id` (Many2one): Push configuration reference.
- `state` (Selection): Sync state ('done', 'failed').
- `message` (Text): HTTP error body or status details.
- `record_count` (Integer): Total records pushed in the transaction.

---

## sh.powerbi.embedded.report
Status: [ACTIVE]
Purpose: Contains URLs and workspace details to embed interactive Power BI reports in Odoo.
Key Fields:
- `name` (Char): Title of report.
- `report_id` (Char): Power BI Report UUID.
- `embed_url` (Text): Secured embed URL for iframe placement.

---

## sh.powerbi.fabric.config
Status: [ACTIVE]
Purpose: Optional Microsoft Fabric service-principal configuration and workspace target.
Key Fields:
- `azure_tenant_id`, `azure_client_id`, `azure_client_secret`: Fabric OAuth client credentials.
- `fabric_access_token`, `fabric_token_expiry`: Runtime token cache.
- `workspace_id`, `workspace_name`, `capacity_id`: Fabric workspace context.
- `default_target_type`: Default Fabric target type for created items.
Critical Methods:
- `action_authorize`: Requests a Fabric OAuth token.
- `action_test_connection`: Verifies workspace read access.
- `action_discover_items`: Discovers Fabric workspaces/items.
- `action_create_fabric_item`: Creates supported Fabric items through REST API.

---

## sh.powerbi.fabric.item
Status: [ACTIVE]
Purpose: Cached Fabric workspace/item metadata.
Key Fields:
- `external_id`: Fabric item ID.
- `workspace_id`: Fabric workspace ID.
- `item_type`: Workspace, Lakehouse, Warehouse, Eventhouse, KQL Database, Pipeline, Copy Job, semantic model, report, or other.
- `is_default_target`: Default item for Fabric actions.
Critical Methods:
- `action_set_default_target`: Marks the item as the config default.
- `action_run_item`: Starts Fabric Pipeline or Copy Job items.

---

## sh.powerbi.fabric.pipeline.run
Status: [ACTIVE]
Purpose: Tracks Fabric Pipeline and Copy Job runs started from Odoo.
Key Fields:
- `run_id`, `status_url`, `state`, `started_at`, `finished_at`, `duration_seconds`, `record_count`, `message`.
Critical Methods:
- `action_poll_status`: Polls the Microsoft status URL and updates run state.

---

## sh.powerbi.workspace / sh.powerbi.dataset / sh.powerbi.report / sh.powerbi.export.job
Status: [ACTIVE]
Purpose: Cache Power BI REST metadata and audit refresh/export/embed operations.
Key Methods:
- Workspaces: `action_use_workspace`.
- Datasets: `action_refresh_dataset`, `action_get_refresh_history`.
- Reports: `action_generate_embed_token`, `action_rebind_to_dataset`, export actions.
- Export Jobs: `action_start_export`, `action_poll_export`, `action_download_export`.

---

## sh.powerbi.sync.checkpoint / sh.powerbi.tombstone / sh.powerbi.validation.wizard
Status: [ACTIVE]
Purpose: Adds governance support for target sync state, deleted Odoo record markers, and configuration validation.
