Lumana CPQ → RevOps Webhook Pipeline (Odoo + FastAPI + Postgres)
This project is a lightweight end-to-end example of how a Revenue Operations Engineer can architect GTM system integrations:

capture CPQ “quote accepted” events,
validate packaging/entitlement rules,
normalize quote data into a clean revenue data model,
store it in a database for downstream provisioning, billing, analytics, and forecasting.
What this demo proves
Automation: Odoo triggers a webhook action from the UI (contextual action).
Reliability pattern: Webhook sends minimal payload (order id) → service pulls authoritative data from Odoo via XML-RPC.
Validation: Enforces business rules (e.g., license qty must equal camera qty).
Data modeling: Writes normalized orders and order_lines into Postgres.
Idempotency: Safe replays—duplicate quote IDs don’t insert twice.
Architecture
+-------------------+          POST (id only)           +----------------------+
|       Odoo        |  ------------------------------>  |  cpq_webhook (FastAPI)|
|  Quotes / Orders  |                                   |  - pulls full order   |
|  Sections = Sites |                                   |    via XML-RPC        |
+---------+---------+                                   |  - validates rules    |
          |                                             |  - normalizes data    |
          | XML-RPC (read sale.order + lines)           |  - idempotent insert  |
          +-------------------------------------------> +----------+-----------+
                                                                     |
                                                                     | SQLAlchemy
                                                                     v
                                                           +-------------------+
                                                           |   Postgres (cpq)  |
                                                           |  orders           |
                                                           |  order_lines      |
                                                           +-------------------+
