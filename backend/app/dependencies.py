import logging

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import permissions
from app.config import get_settings
from app.database import get_db
from app.models import User, UserSession
from app.security import decode_access_token
from app.services import sessions as session_service

bearer = HTTPBearer(auto_error=False)
settings = get_settings()
log = logging.getLogger("app")

_NOT_AUTHED = "Not authenticated"
_BAD_TOKEN = "Invalid or expired token"
_SESSION_OVER = "Session ended - please sign in again"


def _payload(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _NOT_AUTHED)
    try:
        return decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_TOKEN)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    payload = _payload(credentials)
    sid = payload.get("sid")

    if sid is None:
        # A token issued before session control existed. Self-expiring: none can
        # outlive the old 24h lifetime, so unset ALLOW_SESSIONLESS_TOKENS once
        # this stops being logged and delete this branch.
        if not settings.allow_sessionless_tokens:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_TOKEN)
        log.warning("Accepting a pre-session token for user %s", payload.get("sub"))
        user = db.get(User, int(payload["sub"]))
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
        return user

    # One joined lookup, so validating the session costs the same round trip
    # the plain user fetch used to.
    row = db.execute(
        select(User, UserSession)
        .join(UserSession, UserSession.user_id == User.id)
        .where(User.id == int(payload["sub"]), UserSession.id == sid)
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _SESSION_OVER)
    user, session = row
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    if not session_service.is_live(session):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _SESSION_OVER)
    # Role is read off the row, never off the claim, so a role change lands on
    # the next request rather than at the next sign-in.
    return user


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserSession | None:
    """The caller's own session, for sign-out.

    Never raises: it answers ``None`` for a missing, expired or legacy token
    alike. Sign-out has to work when the access token has already run out -
    that is the common case now it lasts minutes - so the endpoint falls back to
    the refresh token in the body instead of turning the caller away.

    Separate from ``get_current_user`` so its ~20 call sites keep returning a
    plain User and pay for nothing they do not use.
    """
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        return None
    sid = payload.get("sid")
    return db.get(UserSession, sid) if sid is not None else None


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def require_upload(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_upload(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to upload order sheets")
    return user


def require_tracker_view(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_view_tracker(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view the tracker")
    return user


def require_tracker_create(user: User = Depends(get_current_user)) -> User:
    """Creating a row is its own right - merchants have it, shipping does not."""
    if not permissions.can_create_tracker_row(user.role):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Not allowed to create tracker rows"
        )
    return user


def require_tracker_read(user: User = Depends(get_current_user)) -> User:
    """Read-only tracker rows - merchants included, for the dashboard panel."""
    if not permissions.can_read_tracker_rows(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view the tracker")
    return user


def require_audit(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_view_audit(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view the audit trail")
    return user


def require_customer_view(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_view_customers(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view customers")
    return user


def require_customer_manage(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_manage_customers(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to manage customers")
    return user


def require_vendor_view(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_view_vendors(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view vendors")
    return user


def require_vendor_manage(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_manage_vendors(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to manage vendors")
    return user


def require_po_view(user: User = Depends(get_current_user)) -> User:
    """The per-PO view - open to merchants, unlike the tracker itself."""
    if not permissions.can_view_pos(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view purchase orders")
    return user


def require_paste(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_paste(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to paste PO details")
    return user


def require_season_assign(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_assign_season(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to assign seasons")
    return user


def require_reports(user: User = Depends(get_current_user)) -> User:
    if not permissions.can_view_reports(user.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view reports")
    return user
