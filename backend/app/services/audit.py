"""Record field-level changes to tracker rows into the audit log."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.services import tracker_map as tm


def _stringify(value) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def record_change(
    db: Session,
    *,
    row_id: int,
    key: str,
    old,
    new,
    action: str,  # import | manual | edit
    user_id: int | None,
    user_name: str | None,
) -> None:
    """Append an audit entry for one changed field (no-op if nothing changed)."""
    old_s, new_s = _stringify(old), _stringify(new)
    if old_s == new_s:
        return
    db.add(AuditLog(
        entity_type="tracker",
        entity_id=row_id,
        field_key=key,
        field_label=tm.LABEL_BY_KEY.get(key, key),
        field_class=tm.field_class(key),
        old_value=old_s,
        new_value=new_s,
        action=action,
        user_id=user_id,
        user_name=user_name,
    ))
