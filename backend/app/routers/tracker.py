from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import permissions
from app.database import get_db
from app.dependencies import (
    require_admin,
    require_audit,
    require_tracker_view,
)
from app.models import AuditLog, TrackerRow, User
from app.schemas import (
    AuditEntryOut,
    TrackerColumnOut,
    TrackerRowBulkUpdate,
    TrackerRowCreate,
    TrackerRowOut,
    TrackerRowUpdate,
)
from app.services import audit, tracker_map as tm
from app.services.tracker_export import tracker_workbook_bytes

router = APIRouter(prefix="/api/tracker", tags=["tracker"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/columns", response_model=list[TrackerColumnOut])
def columns(user: User = Depends(require_tracker_view)):
    return [TrackerColumnOut(**c) for c in tm.TRACKER_COLUMNS]


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


@router.get("", response_model=list[TrackerRowOut])
def list_tracker(
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_tracker_view),
):
    q = db.query(TrackerRow).order_by(TrackerRow.buyer_po, TrackerRow.style_no, TrackerRow.colour)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            TrackerRow.buyer_po.ilike(like),
            TrackerRow.style_no.ilike(like),
            TrackerRow.colour.ilike(like),
        ))
    return q.all()


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


def _apply_fields(db: Session, row: TrackerRow, fields: dict, user: User, action: str) -> None:
    """Apply user edits with role enforcement + audit; refresh denormalised/derived.

    Raises 403 if the caller submits any valid tracker column they are not allowed
    to edit (order-detail vs operational is decided by ``permissions``).
    """
    valid = set(tm.TRACKER_KEYS)
    allowed = permissions.editable_tracker_keys(user.role)
    forbidden = {k for k in fields if k in valid and k not in allowed}
    if forbidden:
        labels = ", ".join(sorted(tm.LABEL_BY_KEY.get(k, k) for k in forbidden))
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Your role ({user.role}) cannot edit: {labels}",
        )

    data = dict(row.data or {})
    edited = set(row.edited_keys or [])
    for key, val in fields.items():
        if key not in valid:
            continue
        audit.record_change(
            db, row_id=row.id, key=key, old=data.get(key), new=val,
            action=action, user_id=user.id, user_name=user.name,
        )
        data[key] = val
        edited.add(key)
    # denormalised columns + match key
    if "buyer_po" in fields:
        row.buyer_po = fields["buyer_po"]
    if "style_no" in fields:
        row.style_no = fields["style_no"]
    if "colour" in fields:
        row.colour = fields["colour"]
    # recompute price difference unless the user set it explicitly
    if "price_difference" not in edited:
        b, f = data.get("buyer_net_price"), data.get("factory_price")
        if b is not None and f is not None:
            try:
                new_diff = round(float(b) - float(f), 4)
                audit.record_change(
                    db, row_id=row.id, key="price_difference",
                    old=data.get("price_difference"), new=new_diff,
                    action=action, user_id=user.id, user_name=user.name,
                )
                data["price_difference"] = new_diff
            except (TypeError, ValueError):
                pass
    row.data = data
    row.edited_keys = sorted(edited)
    row.match_key = tm.match_key(row.buyer_po, row.style_no, row.colour)


@router.post("", response_model=TrackerRowOut, status_code=status.HTTP_201_CREATED)
def create_tracker_row(
    body: TrackerRowCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_tracker_view),
):
    if not permissions.can_edit_order_details(user.role):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Creating a tracker row sets its order identity; only CEO / admin may do this",
        )
    f = body.fields
    match = tm.match_key(f.get("buyer_po"), f.get("style_no"), f.get("colour"))
    if db.query(TrackerRow).filter(TrackerRow.match_key == match).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A tracker row with this PO/Style/Colour already exists")
    row = TrackerRow(match_key=match, data={}, edited_keys=[], has_buyer=True, created_by=user.id)
    db.add(row)
    db.flush()  # obtain row.id for audit entries
    _apply_fields(db, row, f, user, action="manual")
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
        _apply_fields(db, row, fields, user, action="edit")
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
    _apply_fields(db, row, body.fields, user, action="edit")
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
