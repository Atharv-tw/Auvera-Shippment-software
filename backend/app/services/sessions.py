"""Sign-in sessions: issue them, check them, revoke them, record them.

Two tables, on purpose. ``UserSession`` is live state that gets stamped and
revoked; ``AuthEvent`` is the append-only history the CEO reads. Keeping them
apart is what lets "sign out everywhere" be *one* line in the activity view
while it revokes seven sessions, and lets spent sessions be deleted one day
without the record going with them.

Unlike ``audit``, these functions commit: a sign-in has no surrounding
transaction to ride on.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthEvent, User, UserSession, utcnow
from app.security import (
    build_refresh_token,
    create_access_token,
    generate_refresh_secret,
    hash_refresh_secret,
    refresh_secret_matches,
    split_refresh_token,
)

settings = get_settings()


def aware(dt: datetime | None) -> datetime | None:
    """Treat a stored datetime as UTC.

    ``utcnow()`` is timezone-aware but every ``DateTime`` column in this schema
    is naive, so anything read back from the database comes back naive.
    Comparing the two raises TypeError, and these are the first datetime
    comparisons in the codebase — so every one of them goes through here.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def record_event(
    db: Session, *, event: str, user: User | None,
    session_id: int | None = None, commit: bool = False,
) -> AuthEvent:
    entry = AuthEvent(
        event=event,
        user_id=getattr(user, "id", None),
        user_email=getattr(user, "email", None),
        user_name=getattr(user, "name", None),
        session_id=session_id,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry


def start_session(db: Session, user: User) -> tuple[str, str]:
    """Open a session for ``user``; returns ``(access_token, refresh_token)``."""
    secret = generate_refresh_secret()
    session = UserSession(
        user_id=user.id,
        refresh_hash=hash_refresh_secret(secret),
        expires_at=utcnow() + timedelta(days=settings.refresh_expire_days),
    )
    db.add(session)
    db.flush()  # obtain session.id for the token and the event

    record_event(db, event="login", user=user, session_id=session.id)
    db.commit()

    access = create_access_token(user.id, user.role, session_id=session.id)
    return access, build_refresh_token(session.id, secret)


def is_live(session: UserSession | None) -> bool:
    if session is None or session.revoked_at is not None:
        return False
    expires = aware(session.expires_at)
    return expires is None or expires > utcnow()


def resolve_refresh(db: Session, token: str) -> UserSession | None:
    """The live session a refresh token names, or ``None``."""
    parts = split_refresh_token(token)
    if parts is None:
        return None
    session_id, secret = parts
    session = db.get(UserSession, session_id)
    if session is None or not refresh_secret_matches(secret, session.refresh_hash):
        return None
    return session if is_live(session) else None


def touch(db: Session, session: UserSession) -> str:
    """Stamp the session and mint a fresh access token for it."""
    session.last_used_at = utcnow()
    db.commit()
    return create_access_token(session.user_id, session.user.role, session_id=session.id)


def revoke(
    db: Session, session: UserSession, *, reason: str,
    user: User | None = None, event: str | None = "logout",
) -> None:
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        session.revoked_reason = reason
    if event:
        record_event(db, event=event, user=user or session.user, session_id=session.id)
    db.commit()


def revoke_all(
    db: Session, user: User, *, reason: str, event: str | None = "logout_all",
) -> int:
    """Revoke every live session for ``user``. One event, however many rows."""
    live = [s for s in db.query(UserSession).filter(UserSession.user_id == user.id).all() if is_live(s)]
    now = utcnow()
    for session in live:
        session.revoked_at = now
        session.revoked_reason = reason
    if event and live:
        record_event(db, event=event, user=user)
    db.commit()
    return len(live)
