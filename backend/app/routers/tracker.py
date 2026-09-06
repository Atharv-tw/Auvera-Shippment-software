from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import permissions
from app.database import get_db
from app.dependencies import (
    require_admin,
    require_audit,
    require_tracker_read,
    require_tracker_view,
)
from app.models import AuditLog, TrackerRow, User
from app.schemas import (
    AuditEntryOut,
    TrackerColumnOut,
    TrackerExportRequest,
    TrackerRowBulkUpdate,
    TrackerRowCreate,
    TrackerRowOut,
    TrackerRowUpdate,
)
from app.services import paste_map, tracker_map as tm
from app.services.tracker_edit import apply_tracker_fields
from app.services.tracker_export import tracker_workbook_bytes

router = APIRouter(prefix="/api/tracker", tags=["tracker"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/columns", response_model=list[TrackerColumnOut])
def columns(user: User = Depends(require_tracker_view)):
    # Which columns this user may write is settled here and sent with the
    # column list, so the grid never has to work it out a second time.
    editable = permissions.editable_tracker_keys(user.role)
    return [
        TrackerColumnOut(
            **c,
            editable=c["key"] in editable,
            is_price=c["key"] in tm.PRICE_KEYS,
            is_identity=c["key"] in tm.IDENTITY_KEYS,
            is_payment_terms=c["key"] in tm.PAYMENT_TERMS_KEYS,
            is_derived=c["key"] in tm.DERIVED_KEYS,
            derived_from=tm.derived_from_labels(c["key"]),
            aliases=paste_map.ALIASES.get(c["key"], []),
        )
        for c in tm.TRACKER_COLUMNS
    ]


@router.get("/export")
def export_tracker(db: Session = Depends(get_db), user: User = Depends(require_tracker_view)):
    rows = db.query(TrackerRow).order_by(TrackerRow.buyer_po, TrackerRow.style_no, TrackerRow.colour).all()
    data = tracker_workbook_bytes(rows)
    filename = f"Shipment Tracker - {datetime.now():%d-%m-%Y}.xlsx"
    return Response(
        content=data,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Columns `search` looks in. Factory and status are here because they are what
# people actually type; before these were real columns the query could not reach
# them, so the dashboard filtered client-side instead and the two behaved
# differently. Same list now serves both.
_SEARCHABLE = (
    TrackerRow.buyer_po,
    TrackerRow.style_no,
    TrackerRow.colour,
    TrackerRow.factory_name,
    TrackerRow.shipment_status,
)

# Sortable via ?sort=. Restricted to an allow-list rather than accepting any
# column name, so the parameter cannot be used to probe the schema.
_SORTABLE = {
    "buyer_po": TrackerRow.buyer_po,
    "style_no": TrackerRow.style_no,
    "colour": TrackerRow.colour,
    "factory_name": TrackerRow.factory_name,
    "shipment_status": TrackerRow.shipment_status,
    "etd": TrackerRow.etd,
    "buyer_po_delivery_date": TrackerRow.buyer_po_delivery_date,
    "updated_at": TrackerRow.updated_at,
}


@router.get("", response_model=list[TrackerRowOut])
def list_tracker(
    response: Response,
    search: str | None = None,
    reconciled: bool | None = None,
    sort: str | None = None,
    order: str = "asc",
    limit: int | None = None,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_tracker_read),
):
    """List tracker rows.

    Paging is opt-in: the tracker page wants every row in hand so AG Grid can
    filter and sort locally, while the dashboard panel wants 15 at a time. Callers
    that pass no ``limit`` get the full set exactly as before, so this stayed a
    plain list response - the total for pagers rides along in ``X-Total-Count``.
    """
    q = db.query(TrackerRow)

    if search:
        like = f"%{search}%"
        q = q.filter(or_(*(col.ilike(like) for col in _SEARCHABLE)))

    if reconciled is not None:
        both = TrackerRow.has_buyer.is_(True) & TrackerRow.has_vendor.is_(True)
        q = q.filter(both if reconciled else ~both)

    total = q.count()
    response.headers["X-Total-Count"] = str(total)

    if sort:
        column = _SORTABLE.get(sort)
        if column is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Cannot sort by {sort!r}. Sortable: {', '.join(sorted(_SORTABLE))}",
            )
        q = q.order_by(column.desc() if order.lower() == "desc" else column.asc())
    else:
        q = q.order_by(TrackerRow.buyer_po, TrackerRow.style_no, TrackerRow.colour)

    if offset:
        q = q.offset(offset)
    if limit is not None:
        q = q.limit(limit)
    return q.all()


@router.post("/export")
def export_tracker_view(
    body: TrackerExportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_tracker_view),
):
    """Export the current view - the filtered rows, the visible columns, in the
    order they are on screen. This is the escape hatch that removes the last
    reason to rebuild the sheet by hand in Excel."""
    q = db.query(TrackerRow)
    if body.row_ids is not None:
        q = q.filter(TrackerRow.id.in_(body.row_ids))
    rows = q.all()

    if body.row_ids is not None:
        # preserve the on-screen order, which the IN clause does not
        position = {row_id: i for i, row_id in enumerate(body.row_ids)}
        rows.sort(key=lambda r: position.get(r.id, len(position)))
    else:
        rows.sort(key=lambda r: (r.buyer_po or "", r.style_no or "", r.colour or ""))

    keys = [k for k in (body.keys or []) if k in tm.COL_BY_KEY] or None
    data = tracker_workbook_bytes(rows, keys)
    filename = f"Shipment Tracker - {datetime.now():%d-%m-%Y}.xlsx"
    return Response(
        content=data,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{row_id}", response_model=TrackerRowOut)
def get_tracker_row(row_id: int, db: Session = Depends(get_db), user: User = Depends(require_tracker_view)):
    row = db.get(TrackerRow, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracker row not found")
    return row


@router.get("/{row_id}/audit", response_model=list[AuditEntryOut])
def row_audit(
    row_id: int,
    field: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_audit),
):
    """Field-level change trail for a tracker row (CEO / admin only)."""
    if db.get(TrackerRow, row_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracker row not found")
    q = db.query(AuditLog).filter(
        AuditLog.entity_type == "tracker", AuditLog.entity_id == row_id
    )
    if field:
        q = q.filter(AuditLog.field_key == field)
    return q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).all()


@router.post("", response_model=TrackerRowOut, status_code=status.HTTP_201_CREATED)
def create_tracker_row(
    body: TrackerRowCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_tracker_view),
):
    if not permissions.can_edit_identity(user.role):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Creating a tracker row sets its PO/Style/Colour identity; only CEO / admin may do this",
        )
    f = body.fields
    match = tm.match_key(f.get("buyer_po"), f.get("style_no"), f.get("colour"))
    if db.query(TrackerRow).filter(TrackerRow.match_key == match).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A tracker row with this PO/Style/Colour already exists")
    row = TrackerRow(match_key=match, raw={}, edited_keys=[], has_buyer=True, created_by=user.id)
    db.add(row)
    db.flush()  # obtain row.id for audit entries
    apply_tracker_fields(db, row, f, user, action="manual")
    db.commit()
    db.refresh(row)
    return row


@router.patch("/lines", response_model=list[TrackerRowOut])
def bulk_update(
    body: TrackerRowBulkUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_tracker_view),
):
    out: list[TrackerRow] = []
    for row_id, fields in body.updates.items():
        row = db.get(TrackerRow, int(row_id))
        if row is None:
            continue
        apply_tracker_fields(db, row, fields, user, action="edit")
        out.append(row)
    db.commit()
    for r in out:
        db.refresh(r)
    return out


@router.patch("/{row_id}", response_model=TrackerRowOut)
def update_tracker_row(
    row_id: int,
    body: TrackerRowUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_tracker_view),
):
    row = db.get(TrackerRow, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracker row not found")
    apply_tracker_fields(db, row, body.fields, user, action="edit")
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tracker_row(row_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    row = db.get(TrackerRow, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracker row not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
