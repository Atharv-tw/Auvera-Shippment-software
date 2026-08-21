"""One registry of every field the per-PO detail view shows.

The Shipment Tracker is the shipping team's fixed 56-column table. The per-PO
view is a different thing: it shows a purchase order the way the *business*
sees it, so it unions the tracker columns with the order-sheet detail the
tracker has no room for (article, garment spec, size ratio...).

Fields are grouped into four sections - **buyer**, **vendor**, **product**,
**shipping** - and the grouping lives here alone so the API and the UI can
never drift apart.

``origin`` says where a field is stored and therefore where an edit is written:
``tracker`` -> ``TrackerRow.data``, ``order_line`` -> the ``OrderLine`` /
``VendorOrderLine`` record behind the row.
"""

from __future__ import annotations

from app.services import tracker_map as tm

GROUPS: list[dict[str, str]] = [
    {"key": "buyer", "label": "Buyer details"},
    {"key": "vendor", "label": "Vendor details"},
    {"key": "product", "label": "Product details"},
    {"key": "shipping", "label": "Shipping details"},
]

# a tracker column's section follows the column's own source
_GROUP_BY_SOURCE = {
    "buyer": "buyer",
    "const": "buyer",
    "vendor": "vendor",
    "calc": "vendor",
    "operational": "shipping",
}

# Order-sheet line fields the tracker has no column for. Quantity, price, total
# and the delivery date are deliberately absent: the tracker already carries
# them (order_qty / buyer_net_price / buyer_total_value / buyer_po_delivery_date)
# and showing both would invite editing the wrong one.
LINE_FIELDS: list[dict] = [
    dict(key="order_date", label="Order Date", type="text", group="buyer"),
    dict(key="article", label="Article (supplier ref)", type="text", group="product"),
    dict(key="description", label="Description", type="text", group="product"),
    dict(key="garment_code", label="Garment Code", type="text", group="product"),
    dict(key="lot", label="LOT#", type="text", group="product"),
    dict(key="topup", label="TopUp", type="text", group="product"),
    dict(key="packing_method", label="Packing method", type="text", group="product"),
    dict(key="sleeve_length", label="Sleeve Length", type="text", group="product"),
    dict(key="shoulder_pad", label="Shoulder pad", type="text", group="product"),
    dict(key="hanger_foam", label="Hanger foam", type="text", group="product"),
    dict(key="composition", label="Composition", type="text", group="product"),
    dict(key="lining", label="Lining", type="text", group="product"),
    dict(key="brand", label="Brand", type="text", group="product"),
    dict(key="swing_ticket_type", label="Swing ticket type", type="text", group="product"),
    dict(key="label_extra", label="Label extra", type="text", group="product"),
    dict(key="factory", label="Factory (sheet)", type="text", group="product"),
    dict(key="store", label="Store", type="text", group="product"),
]

LINE_KEYS: frozenset[str] = frozenset(f["key"] for f in LINE_FIELDS)

# money on an order line - gated exactly like the tracker's price columns
LINE_PRICE_KEYS: frozenset[str] = frozenset({"price", "total_spent", "quantity"})

# PO-level context shown in the header card, read-only (it comes off the sheet
# header and is re-derived on every re-import).
HEADER_FIELDS: list[dict] = [
    dict(key="supplier", label="Supplier"),
    dict(key="code", label="Code"),
    dict(key="country_of_payment", label="Country of Payment"),
    dict(key="payment_terms", label="Payment Terms"),
    dict(key="currency", label="Currency"),
    dict(key="terms_of_delivery", label="Terms of Delivery"),
    dict(key="factory_town", label="Factory Town"),
    dict(key="port_of_loading", label="Port of Loading"),
    dict(key="source_filename", label="Source file"),
]


def tracker_field_specs() -> list[dict]:
    """The 56 tracker columns, tagged with their per-PO section."""
    return [
        {
            "key": c["key"],
            "label": c["label"],
            "type": c["type"],
            "group": _GROUP_BY_SOURCE.get(c["source"], "shipping"),
            "origin": "tracker",
            "is_price": c["key"] in tm.PRICE_KEYS,
            "is_identity": c["key"] in tm.IDENTITY_KEYS,
            "is_derived": c["key"] in tm.DERIVED_KEYS,
        }
        for c in tm.TRACKER_COLUMNS
    ]


def line_field_specs() -> list[dict]:
    """The order-sheet fields the tracker has no column for."""
    return [
        {
            "key": f["key"],
            "label": f["label"],
            "type": f["type"],
            "group": f["group"],
            "origin": "order_line",
            "is_price": f["key"] in LINE_PRICE_KEYS,
            "is_identity": False,
            "is_derived": False,
        }
        for f in LINE_FIELDS
    ]


def po_field_specs() -> list[dict]:
    """Every field on the per-PO view, tracker and order-sheet alike."""
    return tracker_field_specs() + line_field_specs()
