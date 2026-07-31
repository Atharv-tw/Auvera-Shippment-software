from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import TrackerRow, User
from app.schemas import (
    TrackerColumnOut,
    TrackerRowBulkUpdate,
    TrackerRowCreate,
    TrackerRowOut,
    TrackerRowUpdate,
)
from app.services import tracker_map as tm
from app.services.tracker_export import tracker_workbook_bytes

router = APIRouter(prefix="/api/tracker", tags=["tracker"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/columns", response_model=list[TrackerColumnOut])
def columns(user: User = Depends(get_current_user)):
    return [TrackerColumnOut(**c) for c in tm.TRACKER_COLUMNS]


@router.get("/export")
def export_tracker(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
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
    user: User = Depends(get_current_user),
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
def get_tracker_row(row_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(TrackerRow, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracker row not found")
    return row


def _apply_fields(row: TrackerRow, fields: dict) -> None:
    """Apply user edits: write values, mark keys edited, refresh denormalised/derived."""
    valid = set(tm.TRACKER_KEYS)
    data = dict(row.data or {})
    edited = set(row.edited_keys or [])
    for key, val in fields.items():
        if key not in valid:
            continue
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
                data["price_difference"] = round(float(b) - float(f), 4)
            except (TypeError, ValueError):
                pass
    row.data = data
    row.edited_keys = sorted(edited)
    row.match_key = tm.match_key(row.buyer_po, row.style_no, row.colour)


@router.post("", response_model=TrackerRowOut, status_code=status.HTTP_201_CREATED)
def create_tracker_row(
    body: TrackerRowCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    f = body.fields
    match = tm.match_key(f.get("buyer_po"), f.get("style_no"), f.get("colour"))
    if db.query(TrackerRow).filter(TrackerRow.match_key == match).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A tracker row with this PO/Style/Colour already exists")
    row = TrackerRow(match_key=match, data={}, edited_keys=[], has_buyer=True, created_by=user.id)
    db.add(row)
    _apply_fields(row, f)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/lines", response_model=list[TrackerRowOut])
def bulk_update(
    body: TrackerRowBulkUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    out: list[TrackerRow] = []
    for row_id, fields in body.updates.items():
        row = db.get(TrackerRow, int(row_id))
        if row is None:
            continue
        _apply_fields(row, fields)
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
    user: User = Depends(get_current_user),
):
    row = db.get(TrackerRow, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracker row not found")
    _apply_fields(row, body.fields)
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
