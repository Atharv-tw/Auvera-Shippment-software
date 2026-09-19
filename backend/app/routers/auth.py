from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app import email_policy, permissions
from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_session, get_current_user, require_audit
from app.models import AuthEvent, User, UserSession, utcnow
from app.schemas import (
    AuthEventOut,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.security import hash_password, verify_password
from app.services import sessions as session_service

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _token_response(db: Session, user: User) -> TokenResponse:
    access, refresh = session_service.start_session(db, user)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


def _guard_email_domain(email: str) -> None:
    if not email_policy.is_allowed_login_email(email):
        raise HTTPException(status.HTTP_403_FORBIDDEN, email_policy.refusal_message())


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    _guard_email_domain(body.email)
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    # The first user becomes admin so a fresh install is bootstrappable. Everyone
    # after that signs up with no role and waits on the waitlist until an admin
    # approves them and assigns one - registration never grants access itself.
    is_first_user = db.query(User.id).first() is None
    role = permissions.ADMIN if is_first_user else permissions.PENDING
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        name=body.name,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_response(db, user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    # The domain rule is checked on sign-in, not only on registration: turning
    # it on has to shut out accounts that already exist.
    _guard_email_domain(body.email)

    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    locked_until = session_service.aware(user.locked_until)
    if locked_until is not None and locked_until > utcnow():
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed sign-in attempts. Try again shortly.",
        )

    # Checked before the password is verified: answering "wrong password" for a
    # disabled account tells an attacker the password was right.
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    if not verify_password(body.password, user.password_hash):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= settings.max_failed_logins:
            user.locked_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return _token_response(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """Trade a refresh token for a new access token.

    Deliberately takes no bearer token - it is called precisely when the access
    token is dead. Every failure answers the same flat 401, so it never reveals
    whether a token was unknown, revoked or merely expired.
    """
    session = session_service.resolve_refresh(db, body.refresh_token)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session ended - please sign in again")

    user = session.user
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session ended - please sign in again")

    access = session_service.touch(db, session)
    return TokenResponse(
        access_token=access,
        refresh_token=body.refresh_token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: LogoutRequest | None = None,
    db: Session = Depends(get_db),
    session: UserSession | None = Depends(get_current_session),
):
    """Always 204, whatever state the caller is in.

    Accepts the refresh token in the body as well as the bearer header, because
    an access token now lasts minutes and someone signing out after lunch will
    not have a live one.
    """
    if session is None and body is not None and body.refresh_token:
        parts = session_service.split_refresh_token(body.refresh_token)
        if parts is not None:
            session = db.get(UserSession, parts[0])

    if session is not None and session_service.is_live(session):
        session_service.revoke(db, session, reason="logout", event="logout")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all")
def logout_all(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Sign out everywhere. One event in the feed, however many sessions die."""
    revoked = session_service.revoke_all(db, user, reason="logout_all")
    return {"revoked": revoked}


@router.get("/activity", response_model=list[AuthEventOut])
def activity(
    response: Response,
    db: Session = Depends(get_db),
    user_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: User = Depends(require_audit),
):
    """Who signed in and out, newest first. CEO and admin only.

    Lives here rather than under /api/admin because that whole router is
    admin-only and this audience is admin *and* CEO - which is exactly what
    require_audit already means.
    """
    q = db.query(AuthEvent)
    if user_id is not None:
        q = q.filter(AuthEvent.user_id == user_id)
    response.headers["X-Total-Count"] = str(q.count())
    return (
        q.order_by(AuthEvent.created_at.desc(), AuthEvent.id.desc())
        .offset(offset)
        .limit(max(0, min(limit, 200)))
        .all()
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
