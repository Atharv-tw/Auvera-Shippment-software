"""Aggregate the tracker into the numbers the CEO asks for.

Three ways to slice it - by season, by customer, by vendor - over the same
measures, so "shipping report for Spring-Summer '26" and "numbers for Crimson"
are the same query with a different ``group_by`` and filter.

Season comes from ``POSeason`` joined on Buyer PO; customer and vendor come
from the tracker's own Customer Name and Factory's Name columns, which the
imports now fill from the sheets rather than a hardcoded constant.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import POSeason, TrackerRow
from app.services import seasons as sn

GROUP_BY = ("season", "customer", "vendor")

_SHIPPED_HINTS = ("shipped", "delivered", "complete")


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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


def _blank_bucket(key: str, label: str) -> dict:
    return {
        "key": key, "label": label,
        "po_count": 0, "line_count": 0,
        "order_qty": 0.0, "ship_qty": 0.0, "short_extra_qty": 0.0,
        "buyer_value": 0.0, "vendor_value": 0.0,
        "margin": 0.0, "margin_pct": None,
        "shipped_lines": 0, "pending_lines": 0,
        "avg_shipment_delay": None, "avg_docs_delay": None,
        "_pos": set(), "_ship_delays": [], "_docs_delays": [],
    }


def _is_shipped(row: TrackerRow) -> bool:
    status = str((row.data or {}).get("shipment_status") or "").lower()
    return any(hint in status for hint in _SHIPPED_HINTS)


def _accumulate(bucket: dict, row: TrackerRow) -> None:
    data = row.data or {}
    bucket["line_count"] += 1
    if row.buyer_po:
        bucket["_pos"].add(row.buyer_po)
    bucket["order_qty"] += _num(data.get("order_qty"))
    bucket["ship_qty"] += _num(data.get("ship_qty"))
    bucket["short_extra_qty"] += _num(data.get("short_extra_qty"))
    bucket["buyer_value"] += _num(data.get("buyer_total_value"))
    bucket["vendor_value"] += _num(data.get("vendor_total_value"))
    if _is_shipped(row):
        bucket["shipped_lines"] += 1
    else:
        bucket["pending_lines"] += 1
    delay = data.get("delay_shipment")
    if delay not in (None, ""):
        bucket["_ship_delays"].append(_num(delay))
    docs = data.get("docs_delay_days")
    if docs not in (None, ""):
        bucket["_docs_delays"].append(_num(docs))


def _finalise(bucket: dict) -> dict:
    bucket["po_count"] = len(bucket.pop("_pos"))
    ship_delays = bucket.pop("_ship_delays")
    docs_delays = bucket.pop("_docs_delays")
    bucket["avg_shipment_delay"] = (
        round(sum(ship_delays) / len(ship_delays), 2) if ship_delays else None
    )
    bucket["avg_docs_delay"] = (
        round(sum(docs_delays) / len(docs_delays), 2) if docs_delays else None
    )
    bucket["margin"] = round(bucket["buyer_value"] - bucket["vendor_value"], 4)
    bucket["margin_pct"] = (
        round(100 * bucket["margin"] / bucket["buyer_value"], 2)
        if bucket["buyer_value"] else None
    )
    for key in ("order_qty", "ship_qty", "short_extra_qty"):
        bucket[key] = round(bucket[key], 2)
    # money values follow the 4-decimal prices they are summed from
    for key in ("buyer_value", "vendor_value"):
        bucket[key] = round(bucket[key], 4)
    return bucket


def _season_labels(db: Session) -> dict[str, tuple[str, str]]:
    """Buyer PO -> (season code, season label)."""
    return {
        s.buyer_po: (s.code, s.label)
        for s in db.query(POSeason).all()
    }


def build_report(
    db: Session,
    group_by: str = "season",
    season: str | None = None,
    customer: str | None = None,
    vendor: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Group every tracker row into buckets and roll the measures up."""
    if group_by not in GROUP_BY:
        raise ValueError(f"group_by must be one of {', '.join(GROUP_BY)}")

    seasons = _season_labels(db)
    buckets: dict[str, dict] = {}
    totals = _blank_bucket("__all__", "All")

    for row in db.query(TrackerRow).all():
        data = row.data or {}
        code, label = seasons.get(row.buyer_po or "", ("UNASSIGNED", "Season not set"))
        row_customer = str(data.get("customer_name") or "Unknown customer")
        row_vendor = str(data.get("factory_name") or "Unknown vendor")

        if season and code != season:
            continue
        if customer and row_customer.lower() != customer.lower():
            continue
        if vendor and row_vendor.lower() != vendor.lower():
            continue
        if date_from or date_to:
            # the shipment's own date, falling back to the buyer's delivery date
            when = _as_date(data.get("etd")) or _as_date(data.get("buyer_po_delivery_date"))
            if when is None:
                continue
            if date_from and when < date_from:
                continue
            if date_to and when > date_to:
                continue

        if group_by == "season":
            bucket_key, bucket_label = code, label
        elif group_by == "customer":
            bucket_key = bucket_label = row_customer
        else:
            bucket_key = bucket_label = row_vendor

        bucket = buckets.setdefault(bucket_key, _blank_bucket(bucket_key, bucket_label))
        _accumulate(bucket, row)
        _accumulate(totals, row)

    ordered = sorted(buckets.values(), key=lambda b: -b["buyer_value"])
    return {
        "group_by": group_by,
        "buckets": [_finalise(b) for b in ordered],
        "totals": _finalise(totals),
        "filters": {
            "season": season, "customer": customer, "vendor": vendor,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
    }


def filter_options(db: Session) -> dict:
    """The values the report filters can actually take, for the UI's dropdowns."""
    customers, vendors = set(), set()
    for row in db.query(TrackerRow).all():
        data = row.data or {}
        if data.get("customer_name"):
            customers.add(str(data["customer_name"]))
        if data.get("factory_name"):
            vendors.add(str(data["factory_name"]))
    season_rows = db.query(POSeason).all()
    codes = {(s.season_type, s.season_year) for s in season_rows}
    return {
        "seasons": [
            {"code": sn.season_code(t, y), "label": sn.season_label(t, y)}
            for t, y in sorted(codes, key=lambda ty: (-ty[1], ty[0]))
        ],
        "customers": sorted(customers),
        "vendors": sorted(vendors),
    }
