"""Seed an initial admin user.  Run: ``uv run python -m app.seed``"""

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin12345"


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == ADMIN_EMAIL).first():
            print(f"Admin already exists: {ADMIN_EMAIL}")
            return
        db.add(User(
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            name="Admin",
            role="admin",
        ))
        db.commit()
        print(f"Created admin {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
