from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 - ensure models are registered on Base
from app.config import get_settings
from app.database import Base, engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # local dev convenience; production would use alembic migrations
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


from app.routers import (  # noqa: E402
    auth,
    customers,
    orders,
    paste,
    pos,
    reports,
    seasons,
    tracker,
    vendors,
)

# browsable DB view for admins (SQLAlchemy is the ORM, this is its GUI)
from app.admin import mount_admin  # noqa: E402

mount_admin(app)

for _router in (
    auth.router,
    customers.router,
    vendors.router,
    orders.router,
    seasons.router,
    pos.router,
    paste.router,
    reports.router,
    tracker.router,
):
    app.include_router(_router)
