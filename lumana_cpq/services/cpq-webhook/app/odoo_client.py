import os
import time
import xmlrpc.client

ODOO_URL = os.environ["ODOO_URL"].rstrip("/")
ODOO_DB = os.environ["ODOO_DB"]
ODOO_USERNAME = os.environ["ODOO_USERNAME"]
ODOO_PASSWORD = os.environ["ODOO_PASSWORD"]

def _get_proxies():
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    return common, models

def _auth(retries: int = 10, delay_s: float = 1.0) -> tuple[int, xmlrpc.client.ServerProxy]:
    """
    Authenticate lazily with retry to avoid crashing the app at import time.
    Returns (uid, models_proxy).
    """
    last_err = None
    for _ in range(retries):
        try:
            common, models = _get_proxies()
            uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
            if not uid:
                raise RuntimeError("Odoo authentication failed (bad DB/username/password).")
            return uid, models
        except Exception as e:
            last_err = e
            time.sleep(delay_s)
    raise RuntimeError(f"Unable to connect/authenticate to Odoo after {retries} retries: {last_err}")

def read_sale_order(order_id: int) -> dict:
    uid, models = _auth()
    fields = ["name", "partner_id", "currency_id", "amount_untaxed", "amount_tax", "amount_total", "date_order", "user_id", "order_line"]
    res = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, "sale.order", "read", [[order_id]], {"fields": fields})
    if not res:
        raise ValueError(f"sale.order {order_id} not found")
    return res[0]

def read_sale_order_lines(line_ids: list[int]) -> list[dict]:
    uid, models = _auth()
    if not line_ids:
        return []
    fields = ["name", "display_type", "product_id", "product_uom_qty", "price_unit", "price_subtotal"]
    return models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, "sale.order.line", "read", [line_ids], {"fields": fields})

def product_default_codes(product_ids: list[int]) -> dict[int, str]:
    uid, models = _auth()
    if not product_ids:
        return {}
    fields = ["default_code", "name"]
    rows = models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, "product.product", "read", [product_ids], {"fields": fields})
    out = {}
    for r in rows:
        out[r["id"]] = r.get("default_code") or r.get("name") or ""
    return out
