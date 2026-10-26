About
============
Connect Odoo with Microsoft Power BI. This connector synchronizes Odoo ERP data with Power BI so users can build interactive reports, schedule updates, and make informed business decisions.

Version 19.0.5.0.0 adds optional Microsoft Fabric support inside this same module without depending on `sh_odoo_fabric_connector`. Existing Power BI push datasets, queues, dashboard, embedded reports, and the Power BI Desktop `.mez` pull connector remain available.

Version 19.0.6.0.0 adds relational modeling (Star Schema) support: foreign keys are exported as their numeric record id so Power BI can build direct primary key / foreign key relationships between tables.

Key Features
============
- Power BI service-principal authorization, workspace discovery, dataset discovery, report discovery, dataset refresh, PBIX import, report rebind, embed-token generation, and export job tracking.
- Optional Fabric configurations for service-principal authorization, workspace/item discovery, Lakehouse/Warehouse/Eventhouse/KQL/Pipeline/Copy Job item tracking, and pipeline/copy-job run logging.
- Model Access target modes for existing Power BI push, Fabric KQL-oriented tracking, and Fabric pipeline/copy-job execution.
- Sync checkpoints, deleted-record tombstones, data-quality validation wizard, retry/rate-limit handling, and multi-company rules for new records.
- Odoo 19 Community-compatible backend views and OWL dashboard health cards for Power BI and Fabric status.
- Relational field format: foreign keys are returned as numeric IDs with an optional companion `<field>_display` column carrying the readable name.

Installation
============
1) Copy module files to addon folder.
2) Restart odoo service (sudo service odoo-server restart).
3) Go to your odoo instance and open apps (make sure to activate debug mode).
4) click on update app list. 
5) search module name and hit install button.

Relational Field Format (Star Schema)
=====================================
Odoo ➔ Power BI relationships need a common numeric key. Version 19.0.6.0.0 exports every Many2one as its numeric record id, so tables can be linked directly, for example `product.product[product_tmpl_id]` ➔ `product.template[id]`.

The behaviour is configurable per company in **Odoo Settings ➔ Integrations ➔ Power BI Connector ➔ Relational Field Format**:

| Option | Foreign key column | Companion column | Use case |
|---|---|---|---|
| ID and Display Name (default) | numeric id | `<field>_display` = readable name | Recommended — relationships plus readable visuals |
| Numeric ID Only | numeric id | — | Pure star schema, smallest payload |
| Display Name Only (legacy) | readable name | — | Pre 19.0.6.0.0 behaviour |

Notes
=====
- After switching to a numeric format, refresh the query in Power BI Desktop and set **Change Type ➔ Whole Number** on the foreign key columns, then drag the foreign key onto the target table's `id` column.
- Power BI push datasets cannot change the type of an existing column. After switching the relation format, use the **Rebuild Datasets** button on the push configuration, or let the scheduled push recreate the dataset automatically.
- Fabric setup is optional. Admins can use Power BI only and ignore the Fabric menus.
- Fabric operations use Microsoft Fabric REST APIs and require the service principal to have matching tenant, workspace, and item permissions.
- Power BI export-to-file behavior depends on Microsoft licensing/capacity support and will show API errors returned by Microsoft.

Softhealer Technologies Support Team
=====================================
Skype: live:softhealertechnologies
What's app: +917984575681
E-Mail: support@softhealer.com
Website: https://softhealer.com
