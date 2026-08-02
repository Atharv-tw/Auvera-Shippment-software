"""Seed initial users, one per role.  Run: ``uv run python -m app.seed``"""

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

# (email, password, name, role)
SEED_USERS = [
    ("admin@example.com", "admin12345", "Admin", "admin"),
    ("ceo@example.com", "ceo12345", "Casey (CEO)", "ceo"),
    ("shipping@example.com", "ship12345", "Sam (Shipping Manager)", "shipping_manager"),
    ("merchant@example.com", "merch12345", "Morgan (Merchant)", "merchant"),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for email, password, name, role in SEED_USERS:
            if db.query(User).filter(User.email == email).first():
                print(f"Exists: {email} ({role})")
                continue
            db.add(User(
                email=email,
                password_hash=hash_password(password),
                name=name,
                role=role,
            ))
            print(f"Created {email} / {password}  ({role})")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
