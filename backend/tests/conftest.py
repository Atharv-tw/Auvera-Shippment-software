from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - register tables on Base
from app.database import Base, get_db
from app.main import app

# Z project root holds the sample workbooks (backend/tests -> parents[2])
SAMPLES = Path(__file__).resolve().parents[2]

CUSTOMER_FILES = [
    "Customer-Order ^N D579-27-04-2026.xlsx",
    "Order Confirmation # D579-1 - Style - 20271008 & T1 - sent on 27.02.26.xlsx",
    "Order Confirmation-D579-Style-10242608-20271108- sent-27-06-2026.xlsx",
    "Customer-Order-D652-18.04.2026.xlsx",
]
VENDOR_FILES = [str(Path("different sheets") / "Vendor-Order-D652-18.04.2026.xlsx")]


@pytest.fixture()
def TestingSession(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path/'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db(TestingSession):
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(TestingSession):
    def override():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client, email, role=None, admin=None, password="secret123"):
    """Register a user and return their bearer token.

    Registration no longer grants a role: the first user becomes ``admin`` and
    everyone after lands on the waitlist as ``pending``. So to get a user of a
    given role, this registers them and then has an ``admin`` token approve them
    via the admin API - which is how it happens for real. The bootstrap admin is
    never promoted/demoted here, so ``role="merchant"`` on the first user still
    yields the forced admin.
    """
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": email.split("@")[0]},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    token, uid, actual = data["access_token"], data["user"]["id"], data["user"]["role"]
    if role is not None and actual == "pending" and role != "pending":
        assert admin is not None, f"promoting {email} to {role} needs an admin token"
        pr = client.patch(
            f"/api/admin/users/{uid}", json={"role": role}, headers=auth_header(admin)
        )
        assert pr.status_code == 200, pr.text
    return token
