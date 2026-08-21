"""The per-PO view: a purchase order as the business sees it.

Distinct from the Shipment Tracker. The tracker is the shipping team's fixed
56-column sheet, one row per style/colour/topup line. A *purchase order* is the
thing everyone else talks about - D579 - and it spans many of those rows. So
this section lists POs and shows one PO whole: its buyer terms, its factories,
its product detail and size ratios, and its shipping status, grouped into the
four sections defined in ``services/field_groups``.

Merchants reach this without any tracker access at all.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import permissions
from app.database import get_db
from app.dependencies import require_audit, require_po_view
from app.models import (
    AuditLog,
    Order,
    OrderLine,
    POSeason,
    TrackerRow,
    User,
    VendorOrder,
    VendorOrderLine,
)
from app.schemas import (
    AuditEntryOut,
    PoDetailOut,
    PoFieldSpec,
    PoLineOut,
    PoRowUpdate,
    PoSchemaOut,
    PoSummaryOut,
    SeasonOut,
)
from app.services import audit, field_groups as fg
from app.services.tracker_edit import apply_tracker_fields

router = APIRouter(prefix="/api/pos", tags=["purchase-orders"])


def _season_out(record: POSeason | None) -> SeasonOut | None:
    if record is None:
        return None
    return SeasonOut(
        buyer_po=record.buyer_po, season_type=record.season_type,
        season_year=record.season_year, confirmed=record.confirmed,
        code=record.code, label=record.label,
    )


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _first(rows, key: str) -> str | None:
    for row in rows:
        value = (row.data or {}).get(key)
        if value:
            return str(value)
    return None


def _line_payload(line) -> dict:
    """The order-sheet fields we show, read off an Order/VendorOrder line."""
    if line is None:
        return {}
    return {f["key"]: getattr(line, f["key"], None) for f in fg.LINE_FIELDS}


def _lines_for(db: Session, row: TrackerRow):
    """The buyer-side and factory-side order lines behind a tracker row."""
    buyer = db.get(OrderLine, row.order_line_id) if row.order_line_id else None
    vendor = (
        db.get(VendorOrderLine, row.vendor_order_line_id)
        if row.vendor_order_line_id else None
    )
    return buyer, vendor


def _parent_of(db: Session, buyer_line, vendor_line):
    """The workbook record a line came from, for its size-ratio grid."""
    if buyer_line is not None:
        return db.get(Order, buyer_line.order_id)
    if vendor_line is not None:
        return db.get(VendorOrder, vendor_line.vendor_order_id)
    return None


def _po_field_specs(role: str) -> list[PoFieldSpec]:
    """Every PO field, each carrying whether *this* role may write it.

    A PO field is stored either on the tracker row or on the order line behind
    it, and the two are gated separately, so each field is checked against the
    set for its own origin.
    """
    allowed = {
        "tracker": permissions.editable_tracker_keys(role),
        "order_line": permissions.editable_line_keys(role),
    }
    return [
        PoFieldSpec(**f, editable=f["key"] in allowed[f["origin"]])
        for f in fg.po_field_specs()
    ]


def _line_out(db: Session, row: TrackerRow) -> PoLineOut:
    buyer_line, vendor_line = _lines_for(db, row)
    source = buyer_line or vendor_line
    parent = _parent_of(db, buyer_line, vendor_line)
    return PoLineOut(
        tracker_row_id=row.id,
        style_no=row.style_no,
        colour=row.colour,
        article=row.article,
        has_buyer=row.has_buyer,
        has_vendor=row.has_vendor,
        tracker=row.data or {},
        line=_line_payload(source),
        sizes=(source.sizes if source is not None else {}) or {},
        size_header=(parent.size_header if parent is not None else []) or [],
    )


@router.get("/schema", response_model=PoSchemaOut)
def po_schema(user: User = Depends(require_po_view)):
    """Every field the PO view shows, which of the four sections it sits in,
    and whether the caller may edit it."""
    return PoSchemaOut(groups=fg.GROUPS, fields=_po_field_specs(user.role))


@router.get("", response_model=list[PoSummaryOut])
def list_pos(
    search: str | None = None,
    season: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_po_view),
):
    q = db.query(TrackerRow).filter(TrackerRow.buyer_po.isnot(None))
    if search:
        q = q.filter(TrackerRow.buyer_po.ilike(f"%{search}%"))

    seasons = {s.buyer_po: s for s in db.query(POSeason).all()}
    grouped: dict[str, list[TrackerRow]] = {}
    for row in q.all():
        grouped.setdefault(row.buyer_po, []).append(row)

    out: list[PoSummaryOut] = []
    for buyer_po, rows in grouped.items():
        record = seasons.get(buyer_po)
        if season and (record is None or record.code != season):
            continue
        statuses: dict[str, int] = {}
        for row in rows:
            label = str((row.data or {}).get("shipment_status") or "Not set")
            statuses[label] = statuses.get(label, 0) + 1
        out.append(PoSummaryOut(
            buyer_po=buyer_po,
            customer_name=_first(rows, "customer_name"),
            factories=sorted({
                str((r.data or {}).get("factory_name")) for r in rows
                if (r.data or {}).get("factory_name")
            }),
            line_count=len(rows),
            order_qty=sum(_num((r.data or {}).get("order_qty")) for r in rows),
            buyer_total_value=sum(_num((r.data or {}).get("buyer_total_value")) for r in rows),
            vendor_total_value=sum(_num((r.data or {}).get("vendor_total_value")) for r in rows),
            season=_season_out(record),
            statuses=statuses,
        ))
    out.sort(key=lambda p: p.buyer_po)
    return out


@router.get("/{buyer_po}", response_model=PoDetailOut)
def get_po(
    buyer_po: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_po_view),
):
    rows = (
        db.query(TrackerRow)
        .filter(TrackerRow.buyer_po == buyer_po)
        .order_by(TrackerRow.style_no, TrackerRow.colour)
        .all()
    )
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No purchase order with that number")

    # PO-level context: every order / vendor-order header filed under this PO
    headers: list[dict] = []
    for order in db.query(Order).filter(Order.order_number == buyer_po).all():
        headers.append({
            "side": "buyer",
            **{f["key"]: getattr(order, f["key"], None) for f in fg.HEADER_FIELDS},
        })
    for vo in db.query(VendorOrder).filter(VendorOrder.order_number == buyer_po).all():
        headers.append({
            "side": "vendor",
            **{f["key"]: getattr(vo, f["key"], None) for f in fg.HEADER_FIELDS},
        })

    return PoDetailOut(
        buyer_po=buyer_po,
        customer_name=_first(rows, "customer_name"),
        season=_season_out(db.query(POSeason).filter(POSeason.buyer_po == buyer_po).first()),
        headers=headers,
        lines=[_line_out(db, row) for row in rows],
        totals={
            "order_qty": sum(_num((r.data or {}).get("order_qty")) for r in rows),
            "ship_qty": sum(_num((r.data or {}).get("ship_qty")) for r in rows),
            "buyer_total_value": sum(_num((r.data or {}).get("buyer_total_value")) for r in rows),
            "vendor_total_value": sum(_num((r.data or {}).get("vendor_total_value")) for r in rows),
        },
    )


@router.get("/{buyer_po}/rows/{row_id}/audit", response_model=list[AuditEntryOut])
def po_row_audit(
    buyer_po: str,
    row_id: int,
    field: str | None = None,
    origin: str = "tracker",
    db: Session = Depends(get_db),
    _user: User = Depends(require_audit),
):
    """Who changed a field on this line, and what it was before.

    A PO line spans two records, so the trail does too: tracker columns are
    logged against the tracker row, order-sheet fields against the order line
    behind it. ``origin`` picks which, matching the field's own ``origin``.
    """
    row = db.get(TrackerRow, row_id)
    if row is None or row.buyer_po != buyer_po:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That line is not on this purchase order")

    if origin == "order_line":
        buyer_line, vendor_line = _lines_for(db, row)
        target = buyer_line or vendor_line
        if target is None:
            return []
        entity_type, entity_id = "order_line", target.id
    else:
        entity_type, entity_id = "tracker", row.id

    q = db.query(AuditLog).filter(
        AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id
    )
    if field:
        q = q.filter(AuditLog.field_key == field)
    return q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).all()


@router.patch("/{buyer_po}/rows/{row_id}", response_model=PoLineOut)
def update_po_row(
    buyer_po: str,
    row_id: int,
    body: PoRowUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_po_view),
):
    """Edit one line of a PO - tracker columns and/or order-sheet fields.

    Goes through the same gate as the tracker's own endpoints, so the price
    columns stay CEO/admin-only however the edit arrives.
    """
    row = db.get(TrackerRow, row_id)
    if row is None or row.buyer_po != buyer_po:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That line is not on this purchase order")

    if body.tracker_fields:
        apply_tracker_fields(db, row, body.tracker_fields, user, action="edit")

    if body.line_fields:
        buyer_line, vendor_line = _lines_for(db, row)
        target = buyer_line or vendor_line
        if target is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This line has no order sheet behind it, so its product details "
                "cannot be edited",
            )
        allowed = permissions.editable_line_keys(user.role)
        labels = {f["key"]: f["label"] for f in fg.LINE_FIELDS}
        forbidden = {k for k in body.line_fields if k in fg.LINE_KEYS and k not in allowed}
        if forbidden:
            named = ", ".join(sorted(labels.get(k, k) for k in forbidden))
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Your role ({user.role}) cannot edit: {named}",
            )
        for key, value in body.line_fields.items():
            if key not in fg.LINE_KEYS:
                continue
            if isinstance(value, str) and not value.strip():
                value = None
            old = getattr(target, key, None)
            if old != value:
                audit.record_line_change(
                    db, line=target, key=key, label=labels.get(key, key),
                    old=old, new=value, user=user,
                )
                setattr(target, key, value)

    db.commit()
    db.refresh(row)
    return _line_out(db, row)
