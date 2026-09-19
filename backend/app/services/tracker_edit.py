"""Apply user edits to tracker rows, with role enforcement and an audit trail.

Shared by every path that writes a tracker row by hand - the tracker's own
endpoints, the per-PO view, and the paste ingest - so the price gate, the
"never clobber a manual edit on re-import" flag and the change trail can only
be applied one way.

Sheet imports deliberately do *not* come through here (see ``reconcile``): a
price on an uploaded sheet is the sheet's own figure, not a hand edit, so it is
written whoever uploads it.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import permissions
from app.models import TrackerRow, User
from app.services import audit, tracker_map as tm


def _forbid(user: User, submitted, allowed, labeller) -> None:
    forbidden = {k for k in submitted if k not in allowed}
    if not forbidden:
        return
    labels = ", ".join(sorted(labeller(k) for k in forbidden))
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        f"Your role ({user.role}) cannot edit: {labels}",
    )


def apply_tracker_fields(
    db: Session, row: TrackerRow, fields: dict, user: User, action: str,
    allowed: frozenset[str] | None = None,
) -> int:
    """Write tracker columns onto a row. Returns how many fields changed.

    Raises 403 if the caller submits any valid tracker column they are not
    allowed to edit. Unknown keys are ignored.

    ``allowed`` overrides the role's usual edit rights, for the one caller that
    needs a different answer: creating a row may set its identity, editing one
    may not.
    """
    valid = set(tm.TRACKER_KEYS)
    submitted = {k for k in fields if k in valid}
    if allowed is None:
        allowed = permissions.editable_tracker_keys(user.role)
    _forbid(user, submitted, allowed, lambda k: tm.LABEL_BY_KEY.get(k, k))

    data = dict(row.data or {})
    edited = set(row.edited_keys or [])
    changed = 0
    for key, val in fields.items():
        if key not in valid:
            continue
        # a blank submission means "clear this cell" - normalise to None so the
        # value is genuinely empty (exports, derived columns) rather than ""
        if isinstance(val, str) and not val.strip():
            val = None
        if data.get(key) != val:
            changed += 1
        audit.record_change(
            db, row_id=row.id, key=key, old=data.get(key), new=val,
            action=action, user_id=user.id, user_name=user.name,
        )
        data[key] = val
        edited.add(key)

    # denormalised columns + match key
    for key in ("buyer_po", "style_no", "colour"):
        if key in fields:
            setattr(row, key, fields[key])

    # Derived columns follow from the values above, so they are recalculated on
    # every edit rather than typed. Each still gets an audit entry, because "why
    # did the delay change?" is answered by the edit that moved its inputs.
    before = {k: data.get(k) for k in tm.DERIVED_KEYS}
    tm.compute_derived(data)
    for key, was in before.items():
        if data.get(key) != was:
            audit.record_change(
                db, row_id=row.id, key=key, old=was, new=data.get(key),
                action=action, user_id=user.id, user_name=user.name,
            )
    edited -= set(tm.DERIVED_KEYS)

    row.set_tracker_values(data)
    row.edited_keys = sorted(edited)
    row.match_key = tm.match_key(row.buyer_po, row.style_no, row.colour)
    return changed
