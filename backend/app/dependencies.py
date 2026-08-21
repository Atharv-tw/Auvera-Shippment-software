import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import permissions
from app.database import get_db
from app.models import User
from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


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
