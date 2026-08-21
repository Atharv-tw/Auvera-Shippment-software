"""Which selling season a purchase order belongs to.

The order paperwork never states it, so it has to come from the merchant. On
upload we suggest a season from the PO's earliest buyer delivery date - March
to August is Spring/Summer, the rest of the year Autumn/Winter - and the
merchant confirms or overrides it.

An Autumn/Winter season runs across the new year, so goods landing in January
2027 belong to AW26, not AW27.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Order, OrderLine, POSeason, TrackerRow

SPRING_SUMMER = "SS"
AUTUMN_WINTER = "AW"
_SS_MONTHS = range(3, 9)  # March..August

SEASON_NAMES = {SPRING_SUMMER: "Spring-Summer", AUTUMN_WINTER: "Autumn-Winter"}


def season_code(season_type: str, season_year: int) -> str:
    return f"{season_type}{season_year % 100:02d}"


def season_label(season_type: str, season_year: int) -> str:
    return f"{SEASON_NAMES.get(season_type, season_type)} '{season_year % 100:02d}"


def season_for_date(value: date) -> tuple[str, int]:
    """Map one date onto ``(season_type, season_year)``."""
    if value.month in _SS_MONTHS:
        return SPRING_SUMMER, value.year
    # Sep-Dec starts the AW season named for that year; Jan-Feb finishes it
    return AUTUMN_WINTER, value.year if value.month >= 9 else value.year - 1


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip()).date()
        except ValueError:
            return None
    return None


def po_dates(db: Session, buyer_po: str) -> tuple[date | None, str]:
    """The date a season suggestion should be based on, and where it came from.

    Preference order: the earliest buyer delivery date on the PO's tracker rows,
    then the earliest order date on its order lines.
    """
    rows = db.query(TrackerRow).filter(TrackerRow.buyer_po == buyer_po).all()
    delivery = [
        d for d in (_as_date((r.data or {}).get("buyer_po_delivery_date")) for r in rows)
        if d is not None
    ]
    if delivery:
        return min(delivery), "buyer delivery date"

    ordered = (
        db.query(OrderLine.order_date_d)
        .join(Order, OrderLine.order_id == Order.id)
        .filter(Order.order_number == buyer_po, OrderLine.order_date_d.isnot(None))
        .all()
    )
    dates = [d for (d,) in ordered if d is not None]
    if dates:
        return min(dates), "order date"
    return None, "upload date"


def suggest_for_po(db: Session, buyer_po: str) -> dict:
    """Existing assignment if there is one, otherwise a date-based suggestion."""
    existing = db.query(POSeason).filter(POSeason.buyer_po == buyer_po).first()
    if existing is not None:
        return {
            "buyer_po": buyer_po,
            "season_type": existing.season_type,
            "season_year": existing.season_year,
            "confirmed": existing.confirmed,
            "basis": "already assigned",
        }
    basis_date, basis = po_dates(db, buyer_po)
    season_type, season_year = season_for_date(basis_date or date.today())
    return {
        "buyer_po": buyer_po,
        "season_type": season_type,
        "season_year": season_year,
        "confirmed": False,
        "basis": basis,
    }


def assign(
    db: Session, buyer_po: str, season_type: str, season_year: int,
    user_id: int | None, confirmed: bool = True,
) -> POSeason:
    record = db.query(POSeason).filter(POSeason.buyer_po == buyer_po).first()
    if record is None:
        record = POSeason(buyer_po=buyer_po)
        db.add(record)
    record.season_type = season_type
    record.season_year = season_year
    record.confirmed = confirmed
    record.assigned_by = user_id
    db.flush()
    return record


def seasons_by_po(db: Session) -> dict[str, POSeason]:
    return {s.buyer_po: s for s in db.query(POSeason).all()}
