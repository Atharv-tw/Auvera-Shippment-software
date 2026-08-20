"""Clear order / vendor / tracker data WITHOUT touching users.

Deletes every Order, VendorOrder, their lines, and all reconciled TrackerRows,
leaving the `users` table (logins, roles) intact. Uploaded workbook files under
the upload dir are removed too.

Run: ``uv run python -m app.reset_data``  (add ``--yes`` to skip the prompt)
"""

import shutil
import sys
from pathlib import Path

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import (
    Customer,
    Order,
    OrderLine,
    TrackerRow,
    VendorOrder,
    VendorOrderLine,
)

settings = get_settings()

# child tables first so foreign-key references are cleared before their parents
_MODELS = [TrackerRow, OrderLine, Order, VendorOrderLine, VendorOrder, Customer]


def reset(confirm: bool = True) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        counts = {m.__tablename__: db.query(m).count() for m in _MODELS}
        total = sum(counts.values())
        if total == 0:
            print("Nothing to delete — order/tracker tables are already empty.")
            return
        summary = ", ".join(f"{n} {t}" for t, n in counts.items() if n)
        if confirm:
            reply = input(f"Delete {summary}? Users are kept. [y/N] ").strip().lower()
            if reply not in ("y", "yes"):
                print("Aborted.")
                return
        for m in _MODELS:
            db.query(m).delete()
        db.commit()
        print(f"Deleted: {summary}. Users left untouched.")
    finally:
        db.close()

    # remove uploaded workbook files (users are unaffected)
    upload_dir = Path(settings.upload_dir)
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)
        print(f"Cleared uploads at {upload_dir}/")


if __name__ == "__main__":
    reset(confirm="--yes" not in sys.argv)
