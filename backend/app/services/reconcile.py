"""Persist parsed orders and reconcile them into the shipment tracker.

Each Customer-Order / Vendor-Order upload is stored as its own record (with the
source filename for provenance). Their lines are then merged into shared
``TrackerRow``s keyed by Buyer PO# + Style No.(+TopUp) + Colour. Buyer uploads
fill buyer-side columns, vendor uploads fill factory-side columns, and columns a
user has manually edited are never overwritten on re-import.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Order, OrderLine, TrackerRow, VendorOrder, VendorOrderLine
from app.services import audit, tracker_map as tm
from app.services.masters import upsert_customer_from_buyer_block, upsert_vendor_from_header

_LINE_KEYS = [
    "row_index", "order_date", "order_date_d", "raw",
    "article", "description", "colour", "style_no",
    "topup", "lot", "garment_code", "sizes", "quantity", "price",
    "packing_method", "etd", "sleeve_length", "shoulder_pad", "hanger_foam",
    "composition", "lining", "brand", "swing_ticket_type", "label_extra",
    "factory", "store",
]
_HEADER_KEYS = [
    "order_number", "supplier", "code", "country_of_payment", "payment_terms",
    "currency", "terms_of_delivery", "factory_town", "port_of_loading", "buyer_block",
    # everything the block header carried, and the size-ratio grid spec
    "raw_header", "size_header",
]


def _serialize(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _line_kwargs(line: dict, keys: list[str]) -> dict:
    return {k: line.get(k) for k in keys}


def _upsert_tracker(
    db: Session,
    *,
    buyer_po,
    style_no,
    colour,
    article,
    fields: dict,
    side: str,  # "buyer" | "vendor"
    line_id: int | None,
    user_id: int | None,
    user_name: str | None,
    warnings: list[str],
) -> TrackerRow:
    match = tm.match_key(buyer_po, style_no, colour)
    row = db.query(TrackerRow).filter(TrackerRow.match_key == match).first()
    if row is None:
        row = TrackerRow(
            match_key=match, buyer_po=buyer_po, style_no=style_no, colour=colour,
            raw={}, edited_keys=[], created_by=user_id,
        )
        db.add(row)
        db.flush()  # obtain row.id for audit entries
    data = dict(row.data or {})
    edited = set(row.edited_keys or [])
    for key, val in fields.items():
        if key.startswith("_") or val is None:
            continue
        if key in edited:
            continue  # preserve manual edits
        new_val = _serialize(val)
        old_val = data.get(key)
        if old_val not in (None, "") and old_val != new_val:
            warnings.append(f"{buyer_po}/{style_no}/{colour}: {key} {old_val!r} -> {new_val!r}")
        audit.record_change(
            db, row_id=row.id, key=key, old=old_val, new=new_val,
            action="import", user_id=user_id, user_name=user_name,
        )
        data[key] = new_val
    # traceability
    if article and not row.article:
        row.article = article
    # Derived columns, always recomputed from the merged values. Not guarded by
    # `edited`: they are formulas, so a hand-entered figure is not a preference
    # to protect, it is a value that has gone stale.
    tm.compute_derived(data)
    edited -= set(tm.DERIVED_KEYS)
    # one write path for the 56 columns; unmodelled keys fall through to raw
    row.set_tracker_values(data)
    row.buyer_po = row.buyer_po or buyer_po
    row.style_no = row.style_no or style_no
    row.colour = row.colour or colour
    if side == "buyer":
        row.has_buyer = True
        if line_id is not None:
            row.order_line_id = line_id
    else:
        row.has_vendor = True
        if line_id is not None:
            row.vendor_order_line_id = line_id
    return row


def import_customer_order(
    db: Session, parsed: dict, filename: str,
    user_id: int | None, user_name: str | None = None,
):
    header = parsed["header"]
    customer = upsert_customer_from_buyer_block(db, header.get("buyer_block"))
    order = Order(
        **{k: header.get(k) for k in _HEADER_KEYS},
        is_confirmation=True,
        customer_id=customer.id if customer else None,
        source_filename=filename,
        created_by=user_id,
    )
    db.add(order)
    db.flush()  # get order.id
    warnings: list[str] = []
    touched: set[str] = set()
    for line in parsed["lines"]:
        ol = OrderLine(order_id=order.id, total_spent=line.get("total_spent"),
                       **_line_kwargs(line, _LINE_KEYS))
        db.add(ol)
        db.flush()
        style = tm.style_with_topup(line.get("style_no"), line.get("topup"))
        fields = tm.buyer_fields(header, line)
        row = _upsert_tracker(
            db, buyer_po=header.get("order_number"), style_no=style,
            colour=line.get("colour"), article=line.get("article"),
            fields=fields, side="buyer", line_id=ol.id,
            user_id=user_id, user_name=user_name, warnings=warnings,
        )
        touched.add(row.match_key)
    db.commit()
    return order, len(touched), warnings


def import_vendor_order(
    db: Session, parsed: dict, filename: str,
    user_id: int | None, user_name: str | None = None,
):
    orders: list[VendorOrder] = []
    warnings: list[str] = []
    touched: set[str] = set()
    for i, block in enumerate(parsed["blocks"]):
        header = block["header"]
        vendor = upsert_vendor_from_header(db, header)
        vo = VendorOrder(
            **{k: header.get(k) for k in _HEADER_KEYS},
            block_index=i,
            vendor_id=vendor.id if vendor else None,
            source_filename=filename,
            created_by=user_id,
        )
        db.add(vo)
        db.flush()
        orders.append(vo)
        for line in block["lines"]:
            vl = VendorOrderLine(vendor_order_id=vo.id, **_line_kwargs(line, _LINE_KEYS))
            db.add(vl)
            db.flush()
            style = tm.style_with_topup(line.get("style_no"), line.get("topup"))
            fields = tm.vendor_fields(header, line)
            row = _upsert_tracker(
                db, buyer_po=header.get("order_number"), style_no=style,
                colour=line.get("colour"), article=line.get("article"),
                fields=fields, side="vendor", line_id=vl.id,
                user_id=user_id, user_name=user_name, warnings=warnings,
            )
            touched.add(row.match_key)
    db.commit()
    return orders, len(touched), warnings
