"""The calculated tracker columns.

Each is a subtraction over two columns, a date offset (a base date plus fixed
days), or a total (shipped quantity times price), and each must go **empty**
when an input is missing. The
source spreadsheet cannot express that: Excel treats a blank date as day zero,
so the real tracker carries -46221 in Delay Shipment and -7 in Day of Delayed
Received docs on every row that has not shipped yet. Those are not data, they
are the formula misfiring.
"""

from datetime import date

import pytest

from app.models import TrackerRow
from app.services import tracker_map as tm


def test_every_derived_column_is_declared():
    assert tm.DERIVED_KEYS == {
        "price_difference",
        "short_extra_qty",
        "delay_shipment",
        "docs_delay_days",
        "docs_due_date",
        "factory_payment_due_date",
        "buyer_payment_due_date",
        "buyer_total_value",
        "vendor_total_value",
    }


@pytest.mark.parametrize(
    "key, values, expected",
    [
        # the figures from row 3 of the real tracker
        ("price_difference", {"buyer_net_price": 9.5, "factory_price": 8.3}, 1.2),
        ("short_extra_qty", {"ship_qty": 56, "order_qty": 500}, -444),
        (
            "delay_shipment",
            {"etd": "2026-04-24", "factory_delivery_date": "2026-01-31"},
            83,
        ),
        # docs_due_date is itself derived (ETD + 7), so it is supplied here via
        # the ETD it comes from, not typed in directly.
        (
            "docs_delay_days",
            {"etd": "2026-04-24", "docs_received": "2026-05-08"},  # due 2026-05-01
            7,
        ),
        # the date offsets: base date plus a fixed number of days
        ("docs_due_date", {"etd": "2026-04-24"}, "2026-05-01"),
        ("factory_payment_due_date", {"docs_received": "2026-04-20"}, "2026-05-23"),
        ("buyer_payment_due_date", {"docs_shared_date": "2026-04-25"}, "2026-05-25"),
        # totals: shipped quantity times unit price (not the order qty)
        ("buyer_total_value", {"ship_qty": 296, "buyer_net_price": 9.5}, 2812.0),
        ("vendor_total_value", {"ship_qty": 296, "factory_price": 8.3}, 2456.8),
        # negative and zero are legitimate values, not errors: a shipment can be
        # short or over, and docs can arrive early
        ("short_extra_qty", {"ship_qty": 300, "order_qty": 300}, 0),
        ("short_extra_qty", {"ship_qty": 343, "order_qty": 300}, 43),
        (
            "docs_delay_days",
            {"etd": "2026-05-09", "docs_received": "2026-05-14"},  # due 2026-05-16
            -2,
        ),
    ],
)
def test_formulas_match_the_source_spreadsheet(key, values, expected):
    assert tm.compute_derived(dict(values))[key] == expected


@pytest.mark.parametrize(
    "key, values",
    [
        ("delay_shipment", {"etd": None, "factory_delivery_date": "2026-07-18"}),
        ("delay_shipment", {"etd": "2026-07-18", "factory_delivery_date": None}),
        ("docs_delay_days", {"docs_received": None, "etd": "2026-04-24"}),
        ("docs_delay_days", {"docs_received": "2026-05-08", "etd": None}),
        ("price_difference", {"buyer_net_price": 9.5, "factory_price": None}),
        ("short_extra_qty", {"ship_qty": None, "order_qty": 300}),
        # a missing base date empties the offset columns too
        ("docs_due_date", {"etd": None}),
        ("factory_payment_due_date", {"docs_received": None}),
        ("buyer_payment_due_date", {"docs_shared_date": None}),
        # no shipped quantity yet -> no total (the sheet multiplies by Ship Qty)
        ("buyer_total_value", {"ship_qty": None, "buyer_net_price": 9.5}),
        ("vendor_total_value", {"ship_qty": 296, "factory_price": None}),
    ],
)
def test_a_missing_input_empties_the_result(key, values):
    assert tm.compute_derived(dict(values))[key] is None


def test_excel_zero_date_does_not_become_a_huge_delay():
    """The exact shape of the -46221 bug: a blank ETD against a real factory
    delivery date. Excel reads the blank as day zero and subtracts 126 years."""
    out = tm.compute_derived(
        {"etd": None, "factory_delivery_date": "2026-07-18",
         "docs_received": None, "docs_due_date": "1900-01-07"}
    )
    assert out["delay_shipment"] is None
    assert out["docs_delay_days"] is None


def test_a_stale_derived_value_is_cleared_not_kept(db):
    """If an input is removed, the old figure must go. A stale delay is worse
    than a blank one, because it still reads as a fact."""
    row = TrackerRow(match_key="D|1|Red", buyer_po="D", style_no="1", colour="Red", raw={})
    row.set_tracker_values({"etd": "2026-04-20", "factory_delivery_date": "2026-04-01"})
    db.add(row)
    db.commit()

    values = row.data
    tm.compute_derived(values)
    row.set_tracker_values(values)
    db.commit()
    assert row.delay_shipment == 19

    values = row.data
    values["etd"] = None
    tm.compute_derived(values)
    row.set_tracker_values(values)
    db.commit()
    assert row.delay_shipment is None, "clearing an input must clear the result"


def test_derived_columns_are_not_editable_by_anyone(client):
    """Not even an admin: these are formulas, so a hand-typed figure would be
    silently overwritten on the next edit anyway."""
    from app import permissions

    for role in ("admin", "ceo", "shipping_manager", "merchant"):
        editable = permissions.editable_tracker_keys(role)
        assert not (editable & tm.DERIVED_KEYS), f"{role} can edit a derived column"


def test_each_derived_column_can_name_its_inputs():
    """The UI tells you which fields to change instead of just refusing."""
    assert tm.derived_from_labels("delay_shipment") == [
        "Actual Vessel Sailing date (ETD)",
        "Factory Delivery dtd",
    ]
    assert tm.derived_from_labels("short_extra_qty") == ["Ship Qty ( pcs )", "Order qty"]
    # a date offset names its single base column
    assert tm.derived_from_labels("docs_due_date") == ["Actual Vessel Sailing date (ETD)"]
    # a total names its quantity and price
    assert tm.derived_from_labels("buyer_total_value") == ["Ship Qty ( pcs )", "Buyer Net Price"]
    assert tm.derived_from_labels("buyer_po") == [], "only derived columns have inputs"


def test_dates_are_whole_days_not_fractions():
    out = tm.compute_derived({"etd": date(2026, 4, 20), "factory_delivery_date": date(2026, 4, 1)})
    assert out["delay_shipment"] == 19
    assert isinstance(out["delay_shipment"], int)
