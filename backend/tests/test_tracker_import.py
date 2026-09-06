"""Importing the client's own Shipment Tracker workbook back into the DB."""

from app.models import TrackerRow
from app.services import reconcile
from app.services.order_parser import parse_customer_order
from app.services.tracker_import import import_tracker_workbook

from .conftest import CUSTOMER_FILES, SAMPLES

TRACKER = SAMPLES / "Shipment Tracker - 01-04-2026.xlsx"


def test_imports_every_data_row(db):
    result = import_tracker_workbook(db, TRACKER)
    # 12 real rows; the sheet's hundreds of blank template rows carry a stray
    # Mode/FOB default and must not become tracker rows
    assert len(result["created"]) == 12
    assert db.query(TrackerRow).count() == 12
    assert result["sheet"] == "Shipment-01-04-2026"


def test_fills_the_operational_columns(db):
    import_tracker_workbook(db, TRACKER)
    row = db.query(TrackerRow).filter(TrackerRow.style_no == "14936708").one()
    assert row.container_no == "MSMU8156172"
    assert row.container_size == "40HC"       # AY "Size" is the container size
    assert row.vessel == "MSC SINDY"
    assert row.forwarder == "Cargo Consolidators"
    # derived, not taken from the sheet: this row has a BL number and an ETD
    assert row.shipment_status == "Shipped"


def test_derived_columns_are_recomputed_not_copied(db):
    import_tracker_workbook(db, TRACKER)
    row = db.query(TrackerRow).filter(TrackerRow.style_no == "14893608").one()
    assert row.ship_qty == 56 and row.order_qty == 500
    assert row.short_extra_qty == -444          # ship - order
    assert row.docs_due_date.isoformat() == "2026-05-01"  # ETD + 7
    assert row.docs_delay_days == 7
    # the sheet's own Buyer Payment Due Date is Excel day zero (1900-01-30)
    # because its base date is blank; it must not be persisted
    assert row.buyer_payment_due_date is None


def test_merges_onto_rows_from_order_sheets(db):
    fn = CUSTOMER_FILES[3]  # D652
    reconcile.import_customer_order(db, parse_customer_order(str(SAMPLES / fn)), fn, 1)
    before = db.query(TrackerRow).count()
    result = import_tracker_workbook(db, TRACKER)

    assert len(result["updated"]) == before      # every existing row gained data
    assert db.query(TrackerRow).count() == 12    # and the rest were created
    row = db.query(TrackerRow).filter(TrackerRow.style_no == "17088908").one()
    assert row.buyer_net_price == 8.75           # kept from the buyer sheet
    assert row.bl_no is None                     # blank in the tracker too
    assert row.factory_inv_no == "EE/2026-27/02"


def test_never_overwrites_an_in_app_edit(db):
    fn = CUSTOMER_FILES[3]
    reconcile.import_customer_order(db, parse_customer_order(str(SAMPLES / fn)), fn, 1)
    row = db.query(TrackerRow).filter(TrackerRow.style_no == "17088908").one()
    row.factory_delivery_date = None
    row.set_tracker_values({"factory_delivery_date": "2026-01-01"})
    row.edited_keys = ["factory_delivery_date"]
    db.commit()

    import_tracker_workbook(db, TRACKER)
    db.refresh(row)
    assert row.factory_delivery_date.isoformat() == "2026-01-01"


def test_reimport_is_idempotent(db):
    import_tracker_workbook(db, TRACKER)
    again = import_tracker_workbook(db, TRACKER)
    assert again["created"] == [] and again["updated"] == []
    assert len(again["unchanged"]) == 12


def test_dry_run_writes_nothing(db):
    result = import_tracker_workbook(db, TRACKER, dry_run=True)
    assert len(result["created"]) == 12
    assert db.query(TrackerRow).count() == 0
