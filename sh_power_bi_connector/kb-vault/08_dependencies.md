# Dependencies — Power BI Odoo Connector
Status: [ACTIVE]
Backlink: [[00_overview]]

## Manifest Dependencies
* **`base`**: Core Odoo framework. Essential for modeling, ORM registry, and company-specific configurations.
* **`web`**: Core Odoo web client. Provides assets structures, OWL component registers, and main interface components.
* **`rpc`**: Used to enable RPC connectivity configuration tools.
* **`sh_integration_base`**: Integration HUB compatibility and menu/entity registration.

## External Services
* **Microsoft Power BI REST APIs:** Used for service-principal authorization, workspace/dataset/report discovery, dataset refresh, PBIX import, report embed-token generation, rebind, and export jobs.
* **Microsoft Fabric REST APIs:** Used for optional Fabric authorization, workspace/item discovery, item creation, and Pipeline/Copy Job run tracking.
* **No code dependency on `sh_odoo_fabric_connector`:** Fabric support is isolated inside `sh_power_bi_connector` models/views and does not import or call `sh_fabric.*` models.

## Monkey-Patches / Core Inheritances
The module performs a global inherit on Odoo's `base` model in `models/sh_models.py` (`SHBaseReadMixin` inherits `base`):
* **Why:** To capture database mutations across all synchronized models.
* **Mechanism:** Overrides the standard `create`, `write`, and `unlink` methods:
  * Intercepts mutations on active target models (checked via `_sh_powerbi_get_model_access`).
  * If a target model has real-time sync enabled (`enable_realtime`), it automatically registers a job in `sh.powerbi.push.queue`.
  * On unlink, records deleted-record tombstones for active Model Access configurations so downstream delete handling can be audited.
