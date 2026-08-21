"""Season assignment for purchase orders.

Seasons are not in the paperwork - the merchant supplies them, one per Buyer
PO, prompted after each upload with a date-based default already filled in.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_po_view, require_season_assign
from app.models import POSeason, TrackerRow, User
from app.schemas import (
    SeasonAssignRequest,
    SeasonOut,
    SeasonSuggestion,
    SeasonSummary,
)
from app.services import seasons as sn

router = APIRouter(prefix="/api/seasons", tags=["seasons"])


def _out(record: POSeason) -> SeasonOut:
    return SeasonOut(
        buyer_po=record.buyer_po,
        season_type=record.season_type,
        season_year=record.season_year,
        confirmed=record.confirmed,
        code=record.code,
        label=record.label,
    )


@router.get("", response_model=list[SeasonSummary])
def list_seasons(db: Session = Depends(get_db), _user: User = Depends(require_po_view)):
    """Every season in use, with how many POs sit in it."""
    counts: dict[tuple[str, int], int] = {}
    for record in db.query(POSeason).all():
        counts[(record.season_type, record.season_year)] = (
            counts.get((record.season_type, record.season_year), 0) + 1
        )
    return [
        SeasonSummary(
            code=sn.season_code(t, y),
            label=sn.season_label(t, y),
            season_type=t,
            season_year=y,
            po_count=n,
        )
        for (t, y), n in sorted(counts.items(), key=lambda kv: (-kv[0][1], kv[0][0]))
    ]


@router.get("/pending", response_model=list[SeasonSuggestion])
def pending(db: Session = Depends(get_db), _user: User = Depends(require_po_view)):
    """POs nobody has categorised yet, each with its suggested season."""
    assigned = {
        s.buyer_po for s in db.query(POSeason).filter(POSeason.confirmed.is_(True)).all()
    }
    pos = [
        po for (po,) in db.query(TrackerRow.buyer_po).distinct().all()
        if po and po not in assigned
    ]
    return [SeasonSuggestion(**sn.suggest_for_po(db, po)) for po in sorted(pos)]


@router.get("/{buyer_po}", response_model=SeasonOut)
def get_season(buyer_po: str, db: Session = Depends(get_db), _user: User = Depends(require_po_view)):
    record = db.query(POSeason).filter(POSeason.buyer_po == buyer_po).first()
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No season assigned to this PO")
    return _out(record)


@router.post("/assign", response_model=list[SeasonOut])
def assign_seasons(
    body: SeasonAssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_season_assign),
):
    """Confirm a season for one or more POs (what the upload dialog posts)."""
    out = [
        sn.assign(db, a.buyer_po, a.season_type, a.season_year, user.id, confirmed=True)
        for a in body.assignments
    ]
    db.commit()
    return [_out(r) for r in out]
