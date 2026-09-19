"""Admin-only user management: approve waitlisted accounts and assign roles.

A new account signs up with role ``pending`` and can do nothing until an admin
gives it a real role here. These endpoints are the only place a role is granted
or an account is enabled/disabled, so they carry two lock-out guards: an admin
cannot strip their own access, and the last active admin cannot be removed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import permissions
from app.database import get_db
from app.dependencies import require_admin
from app.models import User
from app.services import sessions as session_service
from app.schemas import UserAdminOut, UserRoleUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])

# roles an admin may assign, plus `pending` so an account can be sent back to
# the waitlist (but never granted as an "access" role)
_ASSIGNABLE = set(permissions.ALL_ROLES) | {permissions.PENDING}


@router.get("/users", response_model=list[UserAdminOut])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # Pending accounts first - the whole point of the page is to clear them -
    # then newest first within each group.
    users = db.query(User).order_by(User.created_at.desc()).all()
    users.sort(key=lambda u: u.role != permissions.PENDING)
    return users


@router.patch("/users/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: int,
    body: UserRoleUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if body.role is not None and body.role not in _ASSIGNABLE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Role must be one of: {', '.join(sorted(_ASSIGNABLE))}",
        )

    # Would this change strip the account of admin access, or disable it?
    losing_admin = body.role is not None and user.role == permissions.ADMIN and body.role != permissions.ADMIN
    being_disabled = body.is_active is False

    if user.id == admin.id and (losing_admin or being_disabled):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You cannot remove your own admin access or disable your own account.",
        )

    # Never leave the system with no way back in.
    if losing_admin or being_disabled:
        other_active_admins = (
            db.query(User)
            .filter(
                User.id != user.id,
                User.role == permissions.ADMIN,
                User.is_active.is_(True),
            )
            .count()
        )
        if user.role == permissions.ADMIN and user.is_active and other_active_admins == 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "This is the last active admin - assign another admin first.",
            )

    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()

    # Disabling ends their sessions outright, so the refresh token cannot bring
    # the account back either.
    #
    # A role *change* deliberately does not: get_current_user reads the role off
    # the user row on every request, never off the token, so a new role already
    # takes effect on the next call. Revoking as well would only sign people out
    # at the moment they are approved off the waitlist.
    if being_disabled:
        session_service.revoke_all(db, user, reason="admin", event="admin_revoke")

    db.refresh(user)
    return user
