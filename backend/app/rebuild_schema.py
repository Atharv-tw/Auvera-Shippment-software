"""Drop every table and recreate it from the models. **Destructive.**

``create_all`` only ever *adds* tables - it never alters an existing one. So
when a model gains a column, a database that already has that table keeps the
old shape and every query against it fails. On a deployment that shows up as a
500, and because a 500 escapes before the CORS middleware can touch it, the
browser reports it as a CORS error instead.

While the data is still throwaway this is the fix: drop and rebuild. Once there
is data worth keeping, this script stops being appropriate and the project needs
real migrations (Alembic is already a declared dependency).

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
    print("Dropped all tables.")
    Base.metadata.create_all(bind=engine)
    print(f"Recreated {len(Base.metadata.sorted_tables)} tables from the models.")

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
