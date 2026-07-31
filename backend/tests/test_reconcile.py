from app.models import Order, TrackerRow, VendorOrder
from app.services import reconcile
from app.services.order_parser import parse_customer_order, parse_vendor_order

from .conftest import CUSTOMER_FILES, SAMPLES, VENDOR_FILES


def _import_all(db):
    for fn in CUSTOMER_FILES:
        reconcile.import_customer_order(db, parse_customer_order(str(SAMPLES / fn)), fn, 1)
    for fn in VENDOR_FILES:
        reconcile.import_vendor_order(db, parse_vendor_order(str(SAMPLES / fn)), fn, 1)


def test_reconcile_builds_expected_tracker(db):
    _import_all(db)
    assert db.query(Order).count() == 4
    assert db.query(VendorOrder).count() == 2  # ENDOW + CRIMSON blocks
    rows = db.query(TrackerRow).all()
    assert len(rows) == 11

    # TopUp rows stay distinct
    keys = {r.match_key for r in rows}
    assert any("10242608-T1" in k for k in keys)
    assert any(k for k in keys if "10242608" in k and "-T1" not in k)


def test_buyer_and_vendor_sides_merge(db):
    _import_all(db)
    row = db.query(TrackerRow).filter(TrackerRow.style_no == "17088908").first()
    assert row.has_buyer and row.has_vendor
    assert row.data["factory_name"] == "ENDOW EXPORTS"
    assert row.data["buyer_net_price"] == 8.75
    assert row.data["factory_price"] == 8.0
    assert row.data["price_difference"] == 0.75


def test_reimport_preserves_manual_edits(db):
    reconcile.import_customer_order(
        db, parse_customer_order(str(SAMPLES / CUSTOMER_FILES[3])), CUSTOMER_FILES[3], 1
    )
    row = db.query(TrackerRow).filter(TrackerRow.style_no == "17088908").first()
    # simulate a manual edit to an operational column + an imported column
    row.data = {**row.data, "container_no": "ABCD1234567", "buyer_net_price": 99.0}
    row.edited_keys = ["container_no", "buyer_net_price"]
    db.commit()

    # re-import the same customer order + the vendor order
    reconcile.import_customer_order(
        db, parse_customer_order(str(SAMPLES / CUSTOMER_FILES[3])), CUSTOMER_FILES[3], 1
    )
    reconcile.import_vendor_order(
        db, parse_vendor_order(str(SAMPLES / VENDOR_FILES[0])), VENDOR_FILES[0], 1
    )
    db.refresh(row)
    assert row.data["container_no"] == "ABCD1234567"   # operational edit kept
    assert row.data["buyer_net_price"] == 99.0          # edited import column kept
    assert row.data["factory_name"] == "ENDOW EXPORTS"  # new vendor data still applied
