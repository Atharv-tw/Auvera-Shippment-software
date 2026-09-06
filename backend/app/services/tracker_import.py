"""Read the master Shipment Tracker workbook back into ``TrackerRow``s.

The normal flow fills the tracker from Customer-Order / Vendor-Order uploads,
which only carry the order-paperwork columns. The client's own tracker file is
ahead of that: it also holds the operational columns (invoices, BL, container,
booking, docs dates) that are typed into the sheet by hand, plus rows for POs
whose paperwork was never uploaded here. This module merges that file in.

Same merge rules as ``reconcile``: rows are keyed by ``match_key``, a column a
user has edited in the app is never overwritten, and the derived columns are
recomputed rather than trusted - the sheet's formulas leave artifacts (a blank
base date becomes 1900-01-30, day zero) that must not be persisted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models import TrackerRow
from app.services import audit, cleaners
from app.services import tracker_map as tm

# The tracker's own wording differs from ours in a couple of places (S is
# "Factory /  SAP Price", AY is a bare "Size"), so the header row is matched on
# a few unambiguous anchors rather than all 56 labels.
_HEADER_ANCHORS: dict[int, str] = {
    0: "company code",
    4: "buyer po#",
    6: "style no.",
    11: "order qty",
}

# Written by the sheet, never taken from it: each is a formula over other
# columns and is recomputed after the merge.
_SKIP_KEYS = frozenset(tm.DERIVED_KEYS)

_BUYER_KEYS = frozenset(c["key"] for c in tm.TRACKER_COLUMNS if c["source"] == "buyer")
_VENDOR_KEYS = frozenset(c["key"] for c in tm.TRACKER_COLUMNS if c["source"] == "vendor")


def _same_text(old: Any, new: Any) -> bool:
    """Case/whitespace-only differences are not a change worth recording.

    The tracker types everything in caps ("BLACK", "ROMAN ORIGINALS PLC") while
    the order sheets carry the readable casing. Rewriting one to the other would
    fill the audit log with noise and lose the nicer form for nothing - the row
    identity is case-folded anyway.
    """
    return (
        isinstance(old, str) and isinstance(new, str)
        and " ".join(old.split()).casefold() == " ".join(new.split()).casefold()
    )


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).lower()


def _pick_sheet(wb, sheet: str | None):
    if sheet:
        return wb[sheet]
    for name in wb.sheetnames:
        if name.lower().startswith("shipment"):
            return wb[name]
    return wb[wb.sheetnames[0]]


def _find_header_row(ws) -> int:
    """Row number of the 56-column header (row 1 is the Sub Total band)."""
    for r, row in enumerate(ws.iter_rows(min_row=1, max_row=20, max_col=56, values_only=True), 1):
        if all(_norm(row[i]) == label for i, label in _HEADER_ANCHORS.items()):
            return r
    raise ValueError("Could not find the tracker header row (Company code / Buyer PO# / Style No.)")


def _row_fields(values: tuple) -> dict[str, Any]:
    """Sheet row -> tracker fields, positionally: column A..BD is TRACKER_COLUMNS."""
    fields: dict[str, Any] = {}
    for i, col in enumerate(tm.TRACKER_COLUMNS):
        key = col["key"]
        if key in _SKIP_KEYS:
            continue
        value = values[i] if i < len(values) else None
        kind = col["type"]
        if kind == "date":
            value = cleaners.clean_date(value)
        elif kind == "number":
            value = cleaners.clean_number(value)
        else:
            value = cleaners.clean_text(value)
        if value is not None:
            fields[key] = value
    return fields


def import_tracker_workbook(
    db: Session,
    path: str | Path,
    *,
    sheet: str | None = None,
    user_id: int | None = None,
    user_name: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Merge the tracker workbook into the DB. Returns a summary of what changed."""
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = _pick_sheet(wb, sheet)
    header_row = _find_header_row(ws)

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    skipped_edits: list[str] = []
    changes: list[str] = []

    for values in ws.iter_rows(min_row=header_row + 1, max_col=56, values_only=True):
        buyer_po = cleaners.clean_text(values[4])
        style_no = cleaners.clean_text(values[6])
        if not buyer_po or not style_no:
            continue  # blank template rows carry a stray Mode/FOB and nothing else
        colour = cleaners.clean_text(values[5])
        fields = _row_fields(values)

        match = tm.match_key(buyer_po, style_no, colour)
        row = db.query(TrackerRow).filter(TrackerRow.match_key == match).first()
        is_new = row is None
        if is_new:
            row = TrackerRow(
                match_key=match, buyer_po=buyer_po, style_no=style_no, colour=colour,
                raw={}, edited_keys=[], created_by=user_id,
            )
            db.add(row)
            db.flush()  # obtain row.id for audit entries

        data = dict(row.data or {})
        edited = set(row.edited_keys or [])
        touched = False
        for key, value in fields.items():
            if key in edited:
                skipped_edits.append(f"{match}: {key} (edited in app)")
                continue
            new_val = value.isoformat() if hasattr(value, "isoformat") else value
            old_val = data.get(key)
            if old_val == new_val or _same_text(old_val, new_val):
                continue
            audit.record_change(
                db, row_id=row.id, key=key, old=old_val, new=new_val,
                action="import", user_id=user_id, user_name=user_name,
            )
            if not is_new and old_val not in (None, ""):
                changes.append(f"{match}: {key} {old_val!r} -> {new_val!r}")
            data[key] = new_val
            touched = True

        # The sheet row carries both sides of the order, so it evidences buyer
        # and factory data even where no paperwork was ever uploaded. Only ever
        # set, never cleared - an upload's flag is not the sheet's to withdraw.
        if fields.keys() & _BUYER_KEYS:
            row.has_buyer = True
        if fields.keys() & _VENDOR_KEYS:
            row.has_vendor = True

        # Formulas, recomputed from the merged values (see module docstring).
        tm.compute_derived(data)
        edited -= set(tm.DERIVED_KEYS)
        row.edited_keys = sorted(edited)
        row.set_tracker_values(data)

        if is_new:
            created.append(match)
        elif touched:
            updated.append(match)
        else:
            unchanged.append(match)

    wb.close()
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "overwritten": changes,
        "skipped_edits": skipped_edits,
        "sheet": ws.title,
        "header_row": header_row,
    }
