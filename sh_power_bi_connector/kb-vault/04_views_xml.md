# Views XML — Power BI Odoo Connector
Status: [ACTIVE]
Backlink: [[00_overview]]

## Push Configuration Views (`sh_powerbi_push_config_views.xml`)
* **Form View:** Displays credentials settings grouped into cards: Azure App Client Secret, Tenant details, Workspace targets, Token values. Contains active trigger buttons:
  * **"Authenticate"** (`action_authenticate`): Fetches Azure OAuth token.
  * **"Test Connection"** (`action_test_connection`): Verifies REST connectivity.
  * **"Sync Model Schemas"**: Syncs all configured models' layout to Power BI.
  * **"Show Dashboard"**: Redirects user to OWL dashboard.
  * **"Discover Workspaces/Datasets/Reports"**: Caches Power BI REST metadata.
  * **PBIX Import page:** Lets admins upload a PBIX file to the selected Power BI workspace.

## Model Access Views (`sh_powerbi_model_access_views.xml`)
* **List View:** Lists all model endpoints, displaying model path, sync mode status (Delta/Realtime), selected fields count, split tables count, and last synchronized record count.
* **Form View:** Divided into tabs:
  * **General Settings:** Model model selection dropdown and target table display name mapping.
  * **Sync Settings:** Toggle settings for incremental delta and real-time event updates.
  * **Allowed Fields:** Many2many tag widget mapping stored fields of the target model. Non-stored fields and binary/HTML field types are excluded via Domain filter:
    `domain="[('model_id','=',model_id),('store','=',True),('ttype','not in',['binary','html','json','properties','properties_definition'])]"`
  * **Warning Notes Alert:** Displays warning alerts if the fields count exceeds 75 columns, highlighting that the system will split records into multiple Power BI tables.
  * **Fabric Target:** Displays Fabric configuration, item, target name, sync state, and last message when target mode is not Power BI Push.
  * **Checkpoints:** Shows per-target sync checkpoints.
  * **Header actions:** Run Target Sync, Validate Data, Preview Data, and Export CSV.

## Queue Tracking Views (`sh_powerbi_push_queue_views.xml`)
* **List View:** Shows pending, processing, completed, and failed job batches. Allows developers to manually process queue entries or clear success logs.

## Audit Log Views (`sh_powerbi_log_views.xml`)
* **List & Form View:** Logs sync status. Displays exact HTTP response payload or traceback dumps if an API call fails.

## Fabric Views (`sh_powerbi_fabric_views.xml`)
* Fabric Configurations: authorize/test/discover/create/run Fabric items.
* Fabric Items: cache workspaces/items and run supported Pipeline or Copy Job targets.
* Fabric Pipeline Runs: track run IDs, status URLs, state, duration, record counts, and error/status messages.

## Power BI REST Asset Views (`sh_powerbi_rest_asset_views.xml`)
* Workspaces: discovered workspace cache with "Use Workspace" action.
* Datasets: refresh and refresh-history actions.
* Reports: embed-token, rebind, PDF/PPTX/PNG export actions.
* Export Jobs: poll and download export-to-file results.

## Governance Views (`sh_powerbi_governance_views.xml`)
* Sync Checkpoints: per-model target checkpoint status.
* Deleted Records: tombstone records generated from unlink tracking.
* Data Quality Validation Wizard: validates domains, field types, and target configuration before sync.
