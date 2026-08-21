"""Drop every table and replay the migrations from scratch. **Destructive.**

This is a **dev reset and a break-glass tool, not the normal path.** Schema
changes ship as Alembic migrations now:

    uv run alembic revision --autogenerate -m "what changed"
    uv run alembic upgrade head

Reach for this script only to wipe a throwaway dev database back to a clean
seeded state, or on a deployment whose schema has drifted beyond what a
migration can reconcile. It drops every table, users included, then rebuilds by
running ``alembic upgrade head`` - so the result is exactly what the migration
path produces, never a create_all shortcut that could diverge from it.

Run::

    uv run python -m app.rebuild_schema --yes

or, where there is no shell (Render, Fly), set ``REBUILD_SCHEMA=true`` in the
environment and redeploy - ``prestart`` picks it up on boot. **Unset it again
straight afterwards**, or every future deploy will wipe the database.
"""

import os
import shutil
import sys
from pathlib import Path

from sqlalchemy import text

from app.config import get_settings
from app.database import Base, engine

settings = get_settings()


def _safe_url() -> str:
    """The database URL with any password removed, for printing."""
    url = settings.database_url
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def rebuild(confirm: bool = True) -> None:
    from app import models  # noqa: F401 - register every table on Base

    print(f"Target: {_safe_url()}")
    if confirm:
        reply = input(
            "This DROPS every table, including users, and recreates them empty. "
            "Continue? [y/N] "
        ).strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted.")
            return

    Base.metadata.drop_all(bind=engine)
    # ...including Alembic's own bookkeeping, so the rebuild replays every
    # migration from zero rather than starting from a stale version marker.
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    print("Dropped all tables.")

    from app.migrate import upgrade_head

    upgrade_head()
    print(f"Recreated {len(Base.metadata.sorted_tables)} tables by replaying migrations.")

    upload_dir = Path(settings.upload_dir)
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)
        print(f"Cleared uploads at {upload_dir}/")

    from app import seed

    seed.main()


def rebuild_if_env_set() -> bool:
    """Called from prestart. Returns True if it rebuilt."""
    if os.getenv("REBUILD_SCHEMA", "").strip().lower() not in ("1", "true", "yes"):
        return False
    print("REBUILD_SCHEMA is set - dropping and recreating the schema.")
    rebuild(confirm=False)
    print(
        "Schema rebuilt. UNSET REBUILD_SCHEMA now, or the next deploy wipes the "
        "database again."
    )
    return True


if __name__ == "__main__":
    rebuild(confirm="--yes" not in sys.argv)
