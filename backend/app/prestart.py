"""Container pre-start: wait for the database, then seed.

Kept in Python (not a shell script) so it runs identically on any host and
sidesteps CRLF / exec-bit issues when building images from Windows.
"""

import sys
import time

from sqlalchemy import create_engine

from app.config import get_settings


def wait_for_db(attempts: int = 60, delay: float = 2.0) -> None:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        return  # nothing to wait for
    last_error: Exception | None = None
    for i in range(attempts):
        try:
            create_engine(url).connect().close()
            print("Database is ready.")
            return
        except Exception as exc:  # noqa: BLE001 - retry any connection error
            last_error = exc
            print(f"  waiting for database ({i + 1}/{attempts})…")
            time.sleep(delay)
    print(f"Database did not become ready: {last_error}")
    sys.exit(1)


def main() -> None:
    wait_for_db()

    # A model that gained a column needs the table rebuilt - create_all cannot
    # alter one. Set REBUILD_SCHEMA=true for a single deploy to do that, then
    # unset it. Destructive: it drops every table, users included.
    from app.rebuild_schema import rebuild_if_env_set

    if rebuild_if_env_set():
        return  # rebuild seeds as its last step

    from app import seed

    seed.main()


if __name__ == "__main__":
    main()
