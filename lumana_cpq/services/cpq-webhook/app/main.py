from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from .odoo_client import read_sale_order, read_sale_order_lines, product_default_codes
from .db import SessionLocal, engine
from .models import Base, Order, OrderLine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lumana CPQ Webhook Service")

CAMERA_PREFIX = "CAM-"
LICENSE_PREFIX = "LIC-"
RETENTION_PREFIX = "RET-"


# ---------- Pydantic models (internal normalized schema) ----------

class LineItem(BaseModel):
    sku: str
    qty: int = Field(ge=0)
    unit_price: float = 0
    total_price: float = 0


class SiteBlock(BaseModel):
    site_name: str
    items: List[LineItem]


class Totals(BaseModel):
    subtotal: float = 0
    discount_total: float = 0
    tax_total: float = 0
    grand_total: float = 0


class QuoteAcceptedPayload(BaseModel):
    quote_id: str
    account_name: str
    currency: str = "USD"
    term_months: int = 12
    sites: List[SiteBlock]
    totals: Totals
    metadata: Dict[str, Any] = {}


# ---------- Validation ----------

def validate_payload(p: QuoteAcceptedPayload) -> None:
    all_items = [item for s in p.sites for item in s.items]

    camera_qty = sum(i.qty for i in all_items if i.sku.startswith(CAMERA_PREFIX))
    license_items = [i for i in all_items if i.sku.startswith(LICENSE_PREFIX)]
    retention_items = [i for i in all_items if i.sku.startswith(RETENTION_PREFIX)]

    # Rule 1: exactly one license line, qty matches total cameras
    if len(license_items) != 1:
        raise HTTPException(status_code=400, detail=f"Expected exactly 1 license line; found {len(license_items)}")

    if license_items[0].qty != camera_qty:
        raise HTTPException(
            status_code=400,
            detail=f"License qty ({license_items[0].qty}) must equal total camera qty ({camera_qty})"
        )

    # Rule 2: retention requires a license
    if retention_items and not license_items:
        raise HTTPException(status_code=400, detail="Retention requires a license tier")


# ---------- DB insert helper ----------

def insert_order(payload: QuoteAcceptedPayload) -> dict:
    db = SessionLocal()
    try:
        existing = db.query(Order).filter(Order.quote_id == payload.quote_id).first()
        if existing:
            return {"status": "ok", "message": "duplicate ignored", "order_id": existing.id, "quote_id": payload.quote_id}

        order = Order(
            quote_id=payload.quote_id,
            account_name=payload.account_name,
            currency=payload.currency,
            term_months=payload.term_months,
            subtotal=payload.totals.subtotal,
            discount_total=payload.totals.discount_total,
            tax_total=payload.totals.tax_total,
            grand_total=payload.totals.grand_total,
        )
        db.add(order)
        db.flush()  # get order.id

        for s in payload.sites:
            for i in s.items:
                db.add(OrderLine(
                    order_id=order.id,
                    site_name=s.site_name,
                    sku=i.sku,
                    qty=i.qty,
                    unit_price=i.unit_price,
                    total_price=i.total_price,
                ))

        db.commit()
        return {"status": "ok", "order_id": order.id, "quote_id": payload.quote_id}
    finally:
        db.close()


# ---------- Endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


# Existing endpoint (your manual/test payload format)
@app.post("/webhooks/odoo/quote-accepted")
def quote_accepted(payload: QuoteAcceptedPayload):
    validate_payload(payload)
    return insert_order(payload)


# New endpoint: Odoo Server Action webhook sends only sale.order ID (and maybe a few fields)
class OdooWebhookPayload(BaseModel):
    id: int  # sale.order id


@app.post("/webhooks/odoo/quote-accepted-odoo")
def quote_accepted_from_odoo(payload: OdooWebhookPayload):
    # Pull authoritative details from Odoo using XML-RPC
    so = read_sale_order(payload.id)
    lines = read_sale_order_lines(so.get("order_line", []))

    # Build sites by using the most recent section line as the current site
    sites_map: Dict[str, List[dict]] = {}
    current_site = "Org"

    # Map product_id -> default_code (SKU)
    prod_ids = [l["product_id"][0] for l in lines if l.get("product_id")]
    code_map = product_default_codes(list(set(prod_ids)))

    for l in lines:
        display_type = l.get("display_type")

        if display_type == "line_section":
            current_site = l.get("name") or "Site"
            continue

        # skip notes/other display-only rows
        if display_type:
            continue

        pid = l["product_id"][0] if l.get("product_id") else None
        sku = code_map.get(pid, "") if pid else ""

        item = {
            "sku": sku,
            "qty": int(l.get("product_uom_qty") or 0),
            "unit_price": float(l.get("price_unit") or 0),
            "total_price": float(l.get("price_subtotal") or 0),
        }
        sites_map.setdefault(current_site, []).append(item)

    normalized = QuoteAcceptedPayload(
        quote_id=so["name"],
        account_name=so["partner_id"][1] if so.get("partner_id") else "Unknown",
        currency=so["currency_id"][1] if so.get("currency_id") else "USD",
        term_months=12,
        sites=[SiteBlock(site_name=k, items=[LineItem(**i) for i in v]) for k, v in sites_map.items()],
        totals=Totals(
            subtotal=float(so.get("amount_untaxed") or 0),
            discount_total=0.0,
            tax_total=float(so.get("amount_tax") or 0),
            grand_total=float(so.get("amount_total") or 0),
        ),
        metadata={
            "accepted_at": str(so.get("date_order") or ""),
        },
    )

    validate_payload(normalized)
    return insert_order(normalized)

