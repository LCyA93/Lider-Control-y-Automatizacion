# Known Issues — Power BI Odoo Connector
Status: [ACTIVE]
Backlink: [[00_overview]]

## Issue: Power BI Push Table Column Count Limit (75 Columns)
* **Status:** [RESOLVED]
* **Discovered:** 2026-05-28
* **Description:** Microsoft Power BI REST API restricts a single table to a maximum of 75 columns. Pushing more than 75 fields returns a `400 Bad Request` validation error from Azure.
* **Workaround:** 
  * Select specific required fields in **Model Access > Allowed Fields** to stay under 75.
  * If more fields are needed, the backend automatically splits the Odoo model's schema into multiple sub-tables, linking them using the shared Odoo `id` field.
* **See changelog:** [[changelog/v19.0.4.0.0]]

---

## Issue: Datatype conversion errors for Boolean columns
* **Status:** [RESOLVED]
* **Discovered:** 2026-06-02
* **Description:** Pushing Odoo records with empty values for boolean fields converts them to empty strings (`""`), which causes a datatype mismatched exception on Power BI Service (since it requires native JSON boolean values: `true`/`false`).
* **Workaround:** Fixed in python serialization by keeping false values as native JSON `false` rather than empty strings.
* **See changelog:** [[changelog/v19.0.4.0.0]]

---

## Issue: Temporal Table Timestamp conflicts
* **Status:** [OPEN]
* **Discovered:** 2026-06-02
* **Description:** Real-time sync updates pushed concurrently in rapid succession (within milliseconds) can trigger Azure temporal table conflicts due to matching timestamps.
* **Workaround:** Retry the dataset push or rely on delta/scheduled cron batches.

---

## Issue: Power BI Export-to-File Licensing
* **Status:** [EXTERNAL LIMITATION]
* **Discovered:** 2026-06-23
* **Description:** Microsoft Power BI export-to-file APIs depend on tenant settings, workspace permissions, and supported licensing/capacity.
* **Workaround:** The connector stores export jobs and surfaces Microsoft API errors. Verify service-principal permissions and Fabric/Power BI capacity licensing when exports fail.

---

## Issue: Fabric API Surface Varies by Item Type
* **Status:** [EXTERNAL LIMITATION]
* **Discovered:** 2026-06-23
* **Description:** Microsoft Fabric REST create/run/status behavior is not identical for every Fabric item type.
* **Workaround:** Use Odoo discovery first, then create/run only item types supported by the tenant and Microsoft API. Pipeline/Copy Job runs store raw response/status details for troubleshooting.

---

## Issue: Relational fields exported as display names (no PK-FK relationships)
* **Status:** [RESOLVED]
* **Discovered:** 2026-10-21
* **Description:** The connector flattened every Many2one to its readable name and every One2many/Many2many to a comma separated list of names. The numeric foreign key was discarded, so Power BI could not build any direct relationship between tables (reported by the client for `product.product.product_tmpl_id` ↔ `product.template.id`, `account.move.line.move_id` ↔ `account.move.id`, `stock.move.picking_id` ↔ `stock.picking.id`, and others).
* **Resolution:** Relational fields now expose the numeric record id. With the `id_and_display` format a companion `<field>_display` column carries the readable name for visuals. The format is configurable per company through `res.company.sh_powerbi_relation_format` and is resolved from the **target** company so a background push never inherits the executing user's settings.
* **Notes:** `sh_powerbi_fetch_rows` and `sh_powerbi_search_read` now share a single formatter (`_sh_powerbi_format_rows`) so both endpoints return an identical payload shape. The push dataset schema is mode aware, and schema drift detection compares `dataType` so a `String → Int64` change is detected instead of failing silently.
* **See changelog:** [[changelog/v19.0.6.0.0]]

---

## Issue: Background push silently skipped after a schema change
* **Status:** [RESOLVED]
* **Discovered:** 2026-10-21
* **Description:** `action_push_model` returned the schema drift wizard before creating the push queue. The cron discarded that return value, so every scheduled push stopped **silently** after a schema change — no error and no log entry.
* **Resolution:** A background push (cron) now recreates the dataset automatically and writes an entry to `sh.powerbi.log`. The manual "Push Now" button still opens the schema diff wizard. The **Rebuild Datasets** button on the push configuration recreates every dataset on demand.

---

## Issue: `.mez` context key `modify_fields` has no effect in Odoo 19
* **Status:** [OPEN — external to the Odoo module]
* **Discovered:** 2026-10-21
* **Description:** The bundled Power Query connector sends `context = [lang = "en_US", modify_fields = true]`. Odoo 19 has **no** `modify_fields` context key, so the flag is silently ignored. The flag was presumably the original author's attempt to switch Many2one values to their id. The working Odoo 19 mechanism is the `load` parameter of `read()` / `search_read()`.
* **Workaround:** None needed — the server side now returns ids directly. The flag can be removed on the next `.mez` rebuild.

---

## Issue: `.mez` model discovery fails on Odoo 19 — `ir.model/search` does not accept `fields`
* **Status:** [OPEN — requires a new `.mez` release]
* **Discovered:** 2026-10-21
* **Description:** The bundled Power Query connector discovers models and fields with `ir.model/search` and `ir.model.fields/search` while passing a `fields` argument. Odoo 19's `search(domain, offset, limit, order)` no longer accepts `fields`, so the JSON-2 dispatcher answers **HTTP 422 UNPROCESSABLE_ENTITY** (`got an unexpected keyword argument 'fields'`). Verified live against `/json/2/ir.model/search`.
* **Impact:** the **"All Accessible Models"** browse mode of the connector returns an empty model list on Odoo 19. The **"Configured Models Only"** mode is unaffected, because it uses the dedicated `sh.powerbi.model.access/get_powerbi_model_config` endpoint instead of `ir.model/search`. This is why a client working in configured mode can still extract tables while the browse mode looks empty.
* **Additional incompatibility:** even without `fields`, `/json/2/ir.model/search` returns a list of **ids**, while the M code expects a list of **records** (`_[name]`, `_[model]`). A record list requires `search_read`.
* **Workaround:** keep the company in **Configured Models Only** mode, or rebuild the `.mez` so that model and field discovery use `search_read` (or the dedicated model access endpoint).
* **Note:** rebuilding the `.mez` requires the client to reinstall the connector. The relationship fix itself does **not** require any `.mez` change — the `.mez` is byte identical between `19.0.5.0.0` and `19.0.6.0.0`.
