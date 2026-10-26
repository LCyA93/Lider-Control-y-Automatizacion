# CSV Data — Power BI Odoo Connector
Status: [ACTIVE]
Backlink: [[00_overview]]

No seed data CSV files are defined in the `data/` folder. The configuration structures are seeded via XML files.

## security/ir.model.access.csv
Status: [ACTIVE]
* Defines model permissions and access rights for Power BI Connector models.
* Maps access controls for groups `group_powerbi_manager` (which grants full create, read, write, and delete permissions on configs, log tables, and queue items).
