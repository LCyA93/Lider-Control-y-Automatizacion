# Power BI Odoo Connector — Overview
Status: [ACTIVE]
Version: 19.0.6.0.0
Last Updated: 2026-10-21

## Purpose
This module integrates Odoo ERP with Microsoft Power BI, allowing users to synchronize Odoo model data to Power BI. It supports both pull-based queries using a custom M connector (.mez) and real-time/scheduled push-based datasets in the Power BI Service via Microsoft REST APIs.

## What It Achieves
* **Data Synchronization:** Syncs Odoo records seamlessly to Power BI workspaces.
* **Pull Connectivity:** Provides a custom Power Query connector file (`OdooConnectorBySofthealerTechnologiesV19.mez`) to query Odoo models and records directly using Odoo XML-RPC and load them into Power BI Desktop.
* **Push Datasets:** Creates, updates, and populates push-based real-time datasets in Power BI Service using Azure App registration credentials.
* **Column-Limit Safeguard:** Automatically monitors the Power BI 75-column limitation on push datasets. Splits Odoo schemas exceeding 75 fields into multiple related tables or validates fields using custom access configurations.
* **Sync Auditing:** Log queue system, synchronization status, and schema diff tools to easily track and debug data transmission.
* **Fabric Integration:** Optional Microsoft Fabric service-principal configuration, workspace/item discovery, item creation, pipeline/copy-job execution, and run status logging. This is implemented inside `sh_power_bi_connector` and does not depend on `sh_odoo_fabric_connector`.
* **Power BI REST Assets:** Workspace, dataset/semantic model, report, embed-token, PBIX import, refresh history, rebind, and export job tracking.
* **Governance:** Per-model checkpoints, deleted-record tombstones, and a validation wizard for unsupported fields/domains before push or Fabric sync.
* **Relational Modeling (Star Schema):** Foreign keys are exported as their **numeric record id** so Power BI can build direct PK–FK relationships between tables. A companion `<field>_display` column carries the readable name for visuals. The behaviour is configurable per company through `res.company.sh_powerbi_relation_format` — see [[09_known_issues]].

## Key Concepts
* **Push Configuration (`sh.powerbi.push.config`):** Holds Azure connection credentials (Client ID, Workspace ID, Client Secret, Tenant ID, and Tokens) used for API interaction.
* **Model Access (`sh.powerbi.model.access`):** Configures sync modes (Delta, Real-time, Pull/Push), defines field domains/filters, and defines the list of allowed fields.
* **Push Queue (`sh.powerbi.push.queue`):** Manages asynchronous data batches for push operations.
* **Schema Difference Wizard (`sh.powerbi.schema.diff.wizard`):** Helps identify schema mismatch between Odoo and Power BI datasets.
* **Fabric Configuration (`sh.powerbi.fabric.config`):** Holds Microsoft Fabric tenant/client credentials and workspace defaults.
* **Fabric Item (`sh.powerbi.fabric.item`):** Caches Fabric workspaces and items such as Lakehouse, Warehouse, Eventhouse, KQL Database, Pipeline, and Copy Job.
* **Power BI Assets (`sh.powerbi.workspace`, `sh.powerbi.dataset`, `sh.powerbi.report`):** Cached REST metadata used for discovery, refresh, embed, export, and report operations.
* **Sync Checkpoint / Tombstone:** Tracks target sync state and deleted Odoo record markers.
* **Relational Field Format (`res.company.sh_powerbi_relation_format`):** Controls how relational fields are exposed to Power BI — `id_and_display` (default, numeric id + `<field>_display` companion), `id_only` (numeric id only) or `display_only` (legacy, readable name in the `_id` column).

## Module Map
[[01_architecture]] | [[02_data_flow]] | [[03_models]] | [[04_views_xml]] | [[05_owl_components]] | [[06_controllers]] | [[07_csv_data]] | [[08_dependencies]] | [[09_known_issues]]
