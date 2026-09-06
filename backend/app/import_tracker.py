"""Feed the DB from the master Shipment Tracker workbook.

The order sheets only carry the buyer/factory columns; the client's tracker file
also has the operational ones (invoices, BL, container, booking, docs dates) and
rows for POs whose paperwork was never uploaded. This merges that file in,
preserving anything edited in the app.

Run: ``uv run python -m app.import_tracker "../Shipment Tracker - 01-04-2026.xlsx"``
     add ``--dry-run`` to report what it would change without writing,
     ``--sheet NAME`` to pick a tab other than the first ``Shipment*`` one.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.services.tracker_import import import_tracker_workbook

_DEFAULT = Path(__file__).resolve().parents[2] / "Shipment Tracker - 01-04-2026.xlsx"


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    dry_run = "--dry-run" in argv
    sheet = None
    if "--sheet" in argv:
        sheet = argv[argv.index("--sheet") + 1]
        args = [a for a in args if a != sheet]
    path = Path(args[0]) if args else _DEFAULT
    if not path.exists():
        print(f"No such workbook: {path}")
        return 1

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = import_tracker_workbook(db, path, sheet=sheet, dry_run=dry_run)
    finally:
        db.close()

    print(f"{path.name} — tab {result['sheet']!r}, header on row {result['header_row']}")
    for label in ("created", "updated", "unchanged"):
        keys = result[label]
        print(f"  {label:>9}: {len(keys)}" + (f"  {', '.join(keys)}" if keys else ""))
    for line in result["overwritten"]:
        print(f"  changed  {line}")
    for line in result["skipped_edits"]:
        print(f"  kept     {line}")
    if dry_run:
        print("Dry run — nothing written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
