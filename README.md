# Lumana CPQ → RevOps Webhook Pipeline (Odoo + FastAPI + Postgres)

A lightweight, end-to-end demo of how Revenue Operations can turn **“quote accepted”** events into **reliable, auditable revenue data** that powers provisioning, billing, analytics, and forecasting.

## Executive summary (why this exists)
When a customer accepts a quote, multiple systems need consistent answers—**what was sold, to whom, in what quantity, and under what entitlements**. This demo shows a proven integration pattern that:
- **captures the event** from CPQ (Odoo),
- **validates commercial rules** (packaging/entitlements),
- **standardizes the data** into a clean revenue model,
- and **stores it once** for downstream systems to trust.

**Outcome:** fewer manual handoffs, fewer “systems don’t match” escalations, and a single source of truth for what was sold.

---

## What this demo proves (business outcomes + engineering patterns)

### Business outcomes
- **Faster order-to-cash & provisioning**: downstream systems can trigger automatically from normalized records.
- **Better data quality**: business rules are enforced at the integration boundary.
- **Auditability**: every accepted quote becomes a durable record in a database.

### Engineering patterns demonstrated
- **Event capture**: Odoo triggers a webhook from the UI (contextual action).
- **Reliability**: webhook sends only an **order/quote ID**; the service fetches full details from Odoo (authoritative source).
- **Validation**: enforces packaging/entitlement rules (e.g., *license quantity must equal camera quantity*).
- **Normalization**: writes clean `orders` and `order_lines` into Postgres.
- **Idempotency**: safe replays—duplicate quote IDs don’t insert twice.

---

## Architecture (high-level)

```text
+-------------------+          POST (order_id only)      +------------------------+
|       Odoo        |  ------------------------------>   |  cpq_webhook (FastAPI) |
|  Quotes / Orders  |                                    |  - pulls full order    |
|  Sections = Sites |                                    |    via XML-RPC         |
+---------+---------+                                    |  - validates rules     |
          |                                              |  - normalizes data     |
          | XML-RPC (read sale.order + lines)            |  - idempotent insert   |
          +------------------------------------------->  +-----------+------------+
                                                                      |
                                                                      | SQLAlchemy
                                                                      v
                                                            +---------------------+
                                                            |   Postgres (cpq)    |
                                                            |  orders             |
                                                            |  order_lines        |
                                                            +---------------------+
