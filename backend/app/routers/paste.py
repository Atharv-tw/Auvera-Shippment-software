"""Paste a table of PO details straight from an e-mail.

Two entry points, same engine: pinned to one PO from that PO's page, or
standalone for a block covering many POs (which then needs a PO column).

Update-only. A PO the paste names but we do not have is reported, never
created, and writes go through the tracker's own edit path so the price gate
and the audit trail apply exactly as they would to a typed edit.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import permissions
from app.database import get_db
from app.dependencies import require_paste
from app.models import TrackerRow, User
from app.schemas import (
    PasteApplyOut,
    PasteColumnReport,
    PastePreviewOut,
    PasteRequest,
    PasteRowPreview,
)
from app.services import paste_map as pm
from app.services import tracker_map as tm
from app.services.cleaners import clean_date, clean_number
from app.services.tracker_edit import apply_tracker_fields

router = APIRouter(prefix="/api/paste", tags=["paste"])

MAX_PREVIEW_ROWS = 50


def _coerce(key: str, value):
    """Cast a pasted string to the column's type; leave junk as text."""
    if value is None or str(value).strip() == "":
        return None
    kind = tm.TYPE_BY_KEY.get(key)
    if kind == "date":
        parsed = clean_date(value)
        return parsed.isoformat() if parsed else str(value).strip()
    if kind == "number":
        parsed = clean_number(value)
        return parsed if parsed is not None else str(value).strip()
    return str(value).strip()


def _resolve_rows(db: Session, buyer_po: str, record: dict, mapping: dict[str, str]):
    """The tracker rows in a PO that a pasted line refers to.

    A PO usually has several lines (style x colour x topup), so if the paste
    carries a style or colour we narrow with it. If it does not and the PO has
    more than one line, we refuse rather than write the same value to all of
    them.
    """
    rows = db.query(TrackerRow).filter(TrackerRow.buyer_po == buyer_po).all()
    if not rows:
        return [], f"PO {buyer_po} is not in the system"
    if len(rows) == 1:
        return rows, None

    narrowed = rows
    used: list[str] = []
    for key, attr in (("style_no", "style_no"), ("colour", "colour")):
        header = next((h for h, k in mapping.items() if k == key), None)
        value = str(record.get(header) or "").strip() if header else ""
        if not value:
            continue
        used.append(f"{key}={value}")
        narrowed = [
            r for r in narrowed
            if str(getattr(r, attr) or "").strip().upper() == value.upper()
        ]

    if not used:
        return [], (
            f"PO {buyer_po} has {len(rows)} lines - add a Style or Colour column "
            "so the right one can be picked"
        )
    if not narrowed:
        return [], f"no line on PO {buyer_po} matches {', '.join(used)}"
    return narrowed, None


def _prepare(db: Session, body: PasteRequest, user: User):
    """Shared work between preview and apply."""
    if not body.text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Paste some data first")

    headers, data = pm.extract_table(pm.parse_tsv(body.text))
    if not headers:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Could not find a header row in that paste")

    allowed = set(permissions.editable_tracker_keys(user.role))
    report = pm.map_columns(headers, allowed_keys=allowed)
    mapping = pm.apply_overrides(report, body.column_overrides, allowed_keys=allowed)

    po_header = pm.detect_po_column(headers)
    if body.buyer_po is None and po_header is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No PO column found in that paste - include a 'PO No.' column, or "
            "paste it from the purchase order's own page",
        )

    # A paste says *which* line it is about with PO / Style / Colour, and those
    # columns are read even when the pasting role could never write them - they
    # locate the row, they are not an edit of it. For the same reason nobody
    # writes them from a paste: re-keying a row is not what a booking e-mail is
    # for.
    locator = {
        c["excel_header"]: c["matched_field_key"]
        for c in report.columns if c["matched_field_key"]
    }
    for header, key in body.column_overrides.items():
        if key:
            locator[header] = key
        else:
            locator.pop(header, None)

    mapping = {
        h: k for h, k in mapping.items()
        if h != po_header and k not in tm.IDENTITY_KEYS
    }

    # Say what each pasted column is actually doing, so a Style column does not
    # look like a permission failure when it is simply how we find the row.
    for column in report.columns:
        header, key = column["excel_header"], column["matched_field_key"]
        if header == po_header or (key and key in tm.IDENTITY_KEYS):
            column.update(
                purpose="locator",
                will_import=False,
                blocked_reason=None,
                matched_field_key=key or "buyer_po",
                matched_field_label=tm.LABEL_BY_KEY.get(key or "buyer_po"),
            )
        elif header in mapping:
            column.update(purpose="write", will_import=True)
        elif column["blocked_reason"]:
            column.update(purpose="blocked", will_import=False)
        else:
            column.update(purpose="ignored", will_import=False)

    return headers, data, report, mapping, locator, po_header


def _walk(db: Session, body: PasteRequest, user: User):
    """Resolve every pasted row to its tracker rows and mapped values."""
    headers, data, report, mapping, locator, po_header = _prepare(db, body, user)

    previews: list[PasteRowPreview] = []
    matched: list[str] = []
    unmatched: list[str] = []
    resolved: list[tuple[PasteRowPreview, list[TrackerRow], dict]] = []

    for row_number, record in data:
        pasted_po = str(record.get(po_header) or "").strip() if po_header else ""
        buyer_po = body.buyer_po or pasted_po
        mapped = {k: _coerce(k, record.get(h)) for h, k in mapping.items()}
        mapped = {k: v for k, v in mapped.items() if v is not None}
        preview = PasteRowPreview(row_number=row_number, buyer_po=buyer_po or None, mapped=mapped)

        if not buyer_po:
            preview.error = "no PO on this row"
            previews.append(preview)
            continue
        if body.buyer_po and pasted_po and pasted_po.upper() != body.buyer_po.upper():
            preview.error = f"row is for PO {pasted_po}, not {body.buyer_po}"
            if pasted_po not in unmatched:
                unmatched.append(pasted_po)
            previews.append(preview)
            continue

        rows, problem = _resolve_rows(db, buyer_po, record, locator)
        if problem:
            preview.error = problem
            if not rows and buyer_po not in unmatched:
                unmatched.append(buyer_po)
            previews.append(preview)
            continue

        preview.tracker_row_id = rows[0].id
        if buyer_po not in matched:
            matched.append(buyer_po)
        resolved.append((preview, rows, mapped))
        previews.append(preview)

    return report, mapping, po_header, headers, previews, resolved, matched, unmatched


@router.post("/preview", response_model=PastePreviewOut)
def preview_paste(
    body: PasteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_paste),
):
    report, _mapping, po_header, headers, previews, resolved, matched, unmatched = _walk(
        db, body, user
    )
    return PastePreviewOut(
        po_column_header=po_header,
        headers=headers,
        columns=[PasteColumnReport(**{
            k: v for k, v in c.items() if k != "excel_index"
        }) for c in report.columns],
        rows=previews[:MAX_PREVIEW_ROWS],
        matched_pos=matched,
        unmatched_pos=unmatched,
        matched_row_count=len(resolved),
        error_row_count=sum(1 for p in previews if p.error),
    )


@router.post("/apply", response_model=PasteApplyOut)
def apply_paste(
    body: PasteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_paste),
):
    _report, _mapping, _po, _headers, previews, resolved, _matched, unmatched = _walk(
        db, body, user
    )

    updated_rows = 0
    updated_fields = 0
    for _preview, rows, mapped in resolved:
        if not mapped:
            continue
        for row in rows:
            changed = apply_tracker_fields(db, row, mapped, user, action="edit")
            if changed:
                updated_rows += 1
                updated_fields += changed
    db.commit()

    return PasteApplyOut(
        updated_rows=updated_rows,
        updated_fields=updated_fields,
        row_errors=[p for p in previews if p.error],
        unmatched_pos=unmatched,
    )
