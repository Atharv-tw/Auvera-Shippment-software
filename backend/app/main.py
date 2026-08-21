import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401 - ensure models are registered on Base
from app.config import get_settings
from app.database import Base, engine

settings = get_settings()
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic - `alembic upgrade head`, run from prestart on a
    # deployment. Deliberately NOT create_all: it only ever adds tables, never
    # alters one, so leaving it here would silently paper over a missing
    # migration and the mismatch would resurface as a 500 (which, escaping past
    # CORSMiddleware, shows up in the browser as a bogus CORS error).
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


# Middleware order matters here. Starlette runs the *last* one added on the
# outside, and an unhandled exception normally escapes all the way out to
# Starlette's own error handler - past CORSMiddleware - so the 500 comes back
# with no Access-Control-Allow-Origin header at all. The browser then reports a
# CORS failure and the real error is invisible.
#
# So this catch-all is registered first (making it the inner one) and CORS
# second (the outer one): error responses now pass back out through CORS and
# arrive at the browser readable.
@app.middleware("http")
async def surface_errors_with_cors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001 - deliberately catching everything
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        body = {"detail": "Internal server error"}
        if settings.debug:
            body["error"] = f"{type(exc).__name__}: {exc}"
            body["traceback"] = traceback.format_exc().splitlines()[-12:]
        return JSONResponse(status_code=500, content=body)


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


@app.head("/ping")
@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/api/health/schema")
def schema_health():
    """Is the live database actually the shape the models expect?

    The usual cause of a blanket 500 after a deploy is a table that predates a
    new column, so this names the gap instead of making someone dig a stack
    trace out of the platform logs.
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing_tables: list[str] = []
    missing_columns: dict[str, list[str]] = {}

    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            missing_tables.append(table.name)
            continue
        live = {c["name"] for c in inspector.get_columns(table.name)}
        gaps = [c.name for c in table.columns if c.name not in live]
        if gaps:
            missing_columns[table.name] = gaps

    ok = not missing_tables and not missing_columns
    return {
        "status": "ok" if ok else "out_of_date",
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "hint": None if ok else (
            "The database predates the current models. While the data is "
            "throwaway, run `python -m app.rebuild_schema --yes`, or set "
            "REBUILD_SCHEMA=true for one deploy and unset it afterwards."
        ),
    }


@app.get("/api/health/cors")
def cors_health():
    """What origins this API will actually accept a browser call from."""
    return {"cors_origins": settings.cors_origins}


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
