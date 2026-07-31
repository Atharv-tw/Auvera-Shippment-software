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
