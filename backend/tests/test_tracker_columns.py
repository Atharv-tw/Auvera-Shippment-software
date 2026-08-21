"""The tracker's 56 columns are real columns now - keep the model and the
registry from drifting apart.

`TRACKER_COLUMNS` drives the API schema, the exporter, the paste mapper and the
per-PO field groups. If a key is added there but not to the model (or vice
versa) the mismatch surfaces at runtime as a 500 which, escaping past
CORSMiddleware, is reported by the browser as a CORS error - a failure that has
already cost this project a day once.
"""

from datetime import date, datetime

from sqlalchemy import inspect

from app.models import TrackerRow
from app.services import tracker_map as tm

MODEL_COLUMNS = {c.key for c in inspect(TrackerRow).columns}


def test_every_tracker_key_is_a_real_column():
    missing = set(tm.TRACKER_KEYS) - MODEL_COLUMNS
    assert not missing, f"in TRACKER_COLUMNS but not on the model: {sorted(missing)}"


def test_column_types_match_the_registry():
    """A date key declared as a String would accept junk and break sorting."""
    from sqlalchemy import Date, Float

    cols = {c.key: c for c in inspect(TrackerRow).columns}
    wrong = []
    for key in tm.TRACKER_KEYS:
        expected = tm.TYPE_BY_KEY[key]
        actual = cols[key].type
        if expected == "date" and not isinstance(actual, Date):
            wrong.append((key, "date", str(actual)))
        elif expected == "number" and not isinstance(actual, Float):
            wrong.append((key, "number", str(actual)))
    assert not wrong, f"column type mismatches: {wrong}"


def test_data_property_is_sparse_and_dates_are_iso(db):
    """The wire shape the whole frontend reads: only keys that have a value, and
    dates as strings - both true of the JSON blob this replaced."""
    row = TrackerRow(match_key="X|Y|Z", buyer_po="X", style_no="Y", colour="Z", raw={})
    row.set_tracker_values({"factory_name": "CRIMSON", "etd": "2026-08-12", "order_qty": 300})
    db.add(row)
    db.commit()

    data = row.data
    assert data["factory_name"] == "CRIMSON"
    assert data["etd"] == "2026-08-12", "dates must serialise as ISO strings, not date objects"
    assert data["order_qty"] == 300
    assert "remarks" not in data, "unset keys must be absent, not present-and-null"
    assert isinstance(row.etd, date), "the column itself must hold a real date for SQL sorting"


def test_unmodelled_keys_survive_in_raw(db):
    """The escape hatch: a 57th tracker column can ship as a TRACKER_COLUMNS
    entry alone, with no migration, and still reach the API."""
    row = TrackerRow(match_key="A|B|C", buyer_po="A", style_no="B", colour="C", raw={})
    row.set_tracker_values({"factory_name": "CRIMSON", "not_a_column_yet": "hello"})
    db.add(row)
    db.commit()

    assert row.raw == {"not_a_column_yet": "hello"}
    assert row.data["not_a_column_yet"] == "hello"
    assert row.data["factory_name"] == "CRIMSON"


def test_excel_zero_dates_are_treated_as_blank(db):
    """Excel writes an empty date cell as serial 0, which reads back as early
    1900. The real tracker carries 736 of them. Storing one would put a garbage
    date into sorting, filtering, the overdue rules and the re-export."""
    from app.services.cleaners import clean_date

    for artifact in ("1900-01-07", "1900-01-30", "1900-02-02"):
        assert clean_date(artifact) is None, f"{artifact} should read as blank"
    assert clean_date(datetime(1900, 1, 7)) is None
    # real dates must still survive, in every format the sheets use
    assert clean_date("2026-05-11") == date(2026, 5, 11)
    assert clean_date("06 - Feb - 2026") == date(2026, 2, 6)

    row = TrackerRow(match_key="Z|Z|Z", buyer_po="Z", style_no="Z", colour="Z", raw={})
    row.set_tracker_values({"docs_due_date": "1900-01-07", "etd": "2026-05-11"})
    db.add(row)
    db.commit()
    assert row.docs_due_date is None
    assert "docs_due_date" not in row.data, "a blank date must be absent from the wire shape"
    assert row.data["etd"] == "2026-05-11"
