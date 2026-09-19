import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user_id: int, role: str, session_id: int | None = None) -> str:
    """Short-lived bearer token.

    ``sid`` names the session row this token belongs to, which is what makes
    revocation possible at all — without it a token is valid until it expires
    and nothing can call it back.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict = {"sub": str(user_id), "role": role, "exp": expire}
    if session_id is not None:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# --- refresh tokens -----------------------------------------------------------
#
# Opaque, not a JWT. A refresh token has to be looked up in the database on
# every use — that lookup *is* the revocation check — so signing it would add
# bytes and a second, disagreeable source of truth about expiry without saving
# a query. Carrying the session id in front of the secret turns that lookup
# into a primary-key fetch instead of a scan over hashes.

def generate_refresh_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def refresh_secret_matches(secret: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_refresh_secret(secret), stored_hash)


def build_refresh_token(session_id: int, secret: str) -> str:
    return f"{session_id}.{secret}"


def split_refresh_token(token: str) -> tuple[int, str] | None:
    """``"12.abc"`` -> ``(12, "abc")``; ``None`` when it is not that shape."""
    session_id, _, secret = (token or "").partition(".")
    if not session_id or not secret:
        return None
    try:
        return int(session_id), secret
    except ValueError:
        return None
