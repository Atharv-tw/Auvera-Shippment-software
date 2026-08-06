"""Idempotent user seeding.  Run: ``uv run python -m app.seed``

Always ensures one admin exists (from ``ADMIN_EMAIL`` / ``ADMIN_PASSWORD``).
Set ``SEED_DEMO_USERS=true`` to also create one demo user per non-admin role —
handy for local/testing, leave it off in production.
"""

import os

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin12345")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Admin")
SEED_DEMO_USERS = os.getenv("SEED_DEMO_USERS", "").strip().lower() in ("1", "true", "yes")

# (email, password, name, role) — only created when SEED_DEMO_USERS is set
DEMO_USERS = [
    ("ceo@example.com", "ceo12345", "Casey (CEO)", "ceo"),
    ("shipping@example.com", "ship12345", "Sam (Shipping Manager)", "shipping_manager"),
    ("merchant@example.com", "merch12345", "Morgan (Merchant)", "merchant"),
]


def _ensure(db, email: str, password: str, name: str, role: str) -> None:
    if db.query(User).filter(User.email == email.lower()).first():
        print(f"Exists: {email} ({role})")
        return
    db.add(User(
        email=email.lower(),
        password_hash=hash_password(password),
        name=name,
        role=role,
    ))
    print(f"Created {email} ({role})")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _ensure(db, ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME, "admin")
        if SEED_DEMO_USERS:
            for email, password, name, role in DEMO_USERS:
                _ensure(db, email, password, name, role)
        db.commit()
    finally:
        db.close()

    if ADMIN_PASSWORD == "admin12345":
        print("WARNING: using the default admin password — set ADMIN_PASSWORD for production.")


if __name__ == "__main__":
    main()
