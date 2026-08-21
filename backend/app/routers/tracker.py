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
    TrackerRowBulkUpdate,
    TrackerRowCreate,
    TrackerRowOut,
    TrackerRowUpdate,
)
from app.services import tracker_map as tm
from app.services.tracker_edit import apply_tracker_fields
from app.services.tracker_export import tracker_workbook_bytes

router = APIRouter(prefix="/api/tracker", tags=["tracker"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/columns", response_model=list[TrackerColumnOut])
def columns(user: User = Depends(require_tracker_view)):
    return [
        TrackerColumnOut(
            **c,
            is_price=c["key"] in tm.PRICE_KEYS,
            is_identity=c["key"] in tm.IDENTITY_KEYS,
            is_derived=c["key"] in tm.DERIVED_KEYS,
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


@router.get("", response_model=list[TrackerRowOut])
def list_tracker(
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_tracker_read),
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
    row = TrackerRow(match_key=match, data={}, edited_keys=[], has_buyer=True, created_by=user.id)
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
