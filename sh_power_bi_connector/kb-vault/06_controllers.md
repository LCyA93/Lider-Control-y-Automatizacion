# Controllers — Power BI Odoo Connector
Status: [ACTIVE]
Backlink: [[00_overview]]

This module does not declare custom HTTP routes or Python Web Controllers. Instead, it interacts with Odoo's standard built-in XML-RPC / JSON-RPC endpoints to interface with external clients (like Power BI Desktop using the `.mez` file).

## /xmlrpc/2/common [POST]
Status: [ACTIVE]
Auth: public
Called by: [[00_overview#Pull Connectivity]] (Power Query Custom Connector)
Returns: User session uid integer or validation code.
Description: Handles authentication handshake using Database Name, Username, and API Key / Password.

## /xmlrpc/2/object [POST]
Status: [ACTIVE]
Auth: user
Called by: [[00_overview#Pull Connectivity]] (Power Query Custom Connector)
Returns: JSON response containing database record attributes or schema listings.
Description: Allows Power BI Desktop client to invoke ORM methods such as `search_read` or `fields_get` to dynamically load fields.
