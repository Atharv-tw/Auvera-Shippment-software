"""The main Shipment Tracker column definitions and the sheet -> tracker mapping.

The tracker (tab ``Shipment-01-04-2026``) has 56 columns A..BD. Uploaded
Customer-Order sheets fill the buyer-side columns, Vendor-Order sheets fill the
factory-side columns, a few are constant/derived, one is computed, and the rest
are operational (blank on import, edited in-app).
"""

from __future__ import annotations

from typing import Any

from app.services.parties import parse_buyer_block

# type: "text" | "number" | "date"
# source: "buyer" | "vendor" | "const" | "calc" | "operational"
# Each entry: (excel_col, key, label, type, source)
TRACKER_COLUMNS: list[dict[str, str]] = [
    dict(col="A", key="company_code", label="Company code", type="text", source="const"),
    dict(col="B", key="customer_name", label="Customer Name", type="text", source="buyer"),
    dict(col="C", key="factory_name", label="Factory's Name", type="text", source="vendor"),
    dict(col="D", key="division", label="Division", type="text", source="const"),
    dict(col="E", key="buyer_po", label="Buyer PO#", type="text", source="buyer"),
    dict(col="F", key="colour", label="Colour", type="text", source="buyer"),
    dict(col="G", key="style_no", label="Style No.", type="text", source="buyer"),
    dict(col="H", key="buyer_po_delivery_date", label="Buyer PO Delivery dtd", type="date", source="buyer"),
    dict(col="I", key="factory_delivery_date", label="Factory Delivery dtd", type="date", source="vendor"),
    dict(col="J", key="mode", label="Mode", type="text", source="operational"),
    dict(col="K", key="fob_or_cf", label="FOB or C&F", type="text", source="buyer"),
    dict(col="L", key="order_qty", label="Order qty", type="number", source="buyer"),
    dict(col="M", key="ship_qty", label="Ship Qty ( pcs )", type="number", source="operational"),
    dict(col="N", key="pkgs_ctns", label="Pkgs / Ctns", type="number", source="operational"),
    dict(col="O", key="buyer_currency", label="Buyer Currency", type="text", source="buyer"),
    dict(col="P", key="buyer_net_price", label="Buyer Net Price", type="number", source="buyer"),
    dict(col="Q", key="buyer_total_value", label="Buyer Total Value", type="number", source="buyer"),
    dict(col="R", key="vendor_terms", label="Vendor Terms", type="text", source="vendor"),
    dict(col="S", key="factory_price", label="Factory Unit Price", type="number", source="vendor"),
    dict(col="T", key="vendor_total_value", label="Vendor Total Value", type="number", source="vendor"),
    dict(col="U", key="price_difference", label="Price Difference", type="number", source="calc"),
    dict(col="V", key="factory_inv_no", label="Factory Inv No.", type="text", source="operational"),
    dict(col="W", key="factory_inv_date", label="Factory Inv/ Date", type="date", source="operational"),
    dict(col="X", key="auvera_inv_no", label="Auvera Inv No.", type="text", source="operational"),
    dict(col="Y", key="etd", label="Actual Vessel Sailing date (ETD)", type="date", source="operational"),
    dict(col="Z", key="eta", label="Shipment ETA (Confirm by forwarder)", type="date", source="operational"),
    dict(col="AA", key="bl_no", label="BL/AWB/FCR No.", type="text", source="operational"),
    dict(col="AB", key="bl_date", label="BL/AWB/FCR Date", type="date", source="operational"),
    dict(col="AC", key="docs_received", label="Post shipping / Docs received from  vendor ", type="date", source="operational"),
    dict(col="AD", key="docs_due_date", label="Docs Due Date", type="date", source="operational"),
    dict(col="AE", key="docs_delay_days", label="Day of Delayed Received docs", type="number", source="operational"),
    dict(col="AF", key="forwarder", label="FORWARDER", type="text", source="operational"),
    dict(col="AG", key="item", label="Item", type="text", source="buyer"),
    dict(col="AH", key="short_extra_qty", label="Short / Extra Ship Qnty (+/-)", type="number", source="operational"),
    dict(col="AI", key="factory_payment_due_date", label="Factory Pyament Due Date", type="date", source="operational"),
    dict(col="AJ", key="shipment_status", label="Shipment Status ", type="text", source="operational"),
    dict(col="AK", key="delay_shipment", label="Delay Shipment", type="number", source="operational"),
    dict(col="AL", key="buyer_payment_due_date", label="Buyer Payment Due Date", type="date", source="operational"),
    dict(col="AM", key="remarks", label="Remarks", type="text", source="operational"),
    dict(col="AN", key="factory_payment_terms_status", label="Factory Payment Terms (LC/TT/DA/DP) Status", type="text", source="operational"),
    dict(col="AO", key="buyer_payment_terms_status", label="Buyer Payment Terms (LC/TT/DA/DP) Status", type="text", source="operational"),
    dict(col="AP", key="final_inspection_date", label="Final inspection date", type="date", source="operational"),
    dict(col="AQ", key="pod", label="POD", type="text", source="operational"),
    dict(col="AR", key="preship_docs_sent", label="Pre-shipping docs sending to buyer for approval", type="date", source="operational"),
    dict(col="AS", key="buyer_approved", label="Buyer Approved", type="date", source="operational"),
    dict(col="AT", key="booking_no", label="Booking No.", type="text", source="operational"),
    dict(col="AU", key="booking_date", label="Booking date", type="date", source="operational"),
    dict(col="AV", key="approval_carting_do_date", label="Approval, Carting, DO date", type="date", source="operational"),
    dict(col="AW", key="actual_ho_date", label="Actual H/o date/FCR date", type="date", source="operational"),
    dict(col="AX", key="container_no", label="Container No.", type="text", source="operational"),
    dict(col="AY", key="container_size", label="Container Size", type="text", source="operational"),
    dict(col="AZ", key="lcl_fcl", label="LCL/FCL", type="text", source="operational"),
    dict(col="BA", key="vessel", label="Vessel", type="text", source="operational"),
    dict(col="BB", key="voyage", label="Voyage", type="text", source="operational"),
    dict(col="BC", key="docs_shared_customer", label="Post shipping Docs share to the customer via mail", type="text", source="operational"),
    dict(col="BD", key="docs_shared_date", label="date", type="date", source="operational"),
]

COL_BY_KEY: dict[str, str] = {c["key"]: c["col"] for c in TRACKER_COLUMNS}
TYPE_BY_KEY: dict[str, str] = {c["key"]: c["type"] for c in TRACKER_COLUMNS}
SOURCE_BY_KEY: dict[str, str] = {c["key"]: c["source"] for c in TRACKER_COLUMNS}
LABEL_BY_KEY: dict[str, str] = {c["key"]: c["label"] for c in TRACKER_COLUMNS}
TRACKER_KEYS: list[str] = [c["key"] for c in TRACKER_COLUMNS]

# --- field classes -------------------------------------------------------------
# "order_detail" columns come from the order paperwork (buyer/vendor) plus the
# constants/derived values tied to them; "operational" columns are the tracker's
# own shipment/docs/booking data, blank on import and filled in-app.
ORDER_DETAIL_SOURCES: frozenset[str] = frozenset({"buyer", "vendor", "const", "calc"})
OPERATIONAL_SOURCES: frozenset[str] = frozenset({"operational"})

ORDER_DETAIL_KEYS: frozenset[str] = frozenset(
    c["key"] for c in TRACKER_COLUMNS if c["source"] in ORDER_DETAIL_SOURCES
)
OPERATIONAL_KEYS: frozenset[str] = frozenset(
    c["key"] for c in TRACKER_COLUMNS if c["source"] in OPERATIONAL_SOURCES
)


# --- edit gates ----------------------------------------------------------------
# Money columns. Only the CEO and admin may hand-edit these; a sheet upload
# still writes them for everyone, since that is the sheet's own figure.
PRICE_KEYS: frozenset[str] = frozenset({
    "buyer_net_price", "buyer_total_value",
    "factory_price", "vendor_total_value",
    "price_difference",
})

# The row's identity. Editing any of these re-keys ``match_key``, which would
# silently orphan the row from future re-imports - CEO/admin only.
IDENTITY_KEYS: frozenset[str] = frozenset({"buyer_po", "style_no", "colour"})

# Derived, never hand-edited by anyone.
DERIVED_KEYS: frozenset[str] = frozenset({"price_difference"})


def field_class(key: str) -> str:
    """'order_detail' or 'operational' for a tracker column key."""
    return "operational" if key in OPERATIONAL_KEYS else "order_detail"

# Constants for this operation (Auvera Studio Limited / Roman Originals).
COMPANY_CODE = "ASL"
DEFAULT_CUSTOMER = "ROMAN ORIGINAL PLC"
DEFAULT_DIVISION = "Apparels"


def style_with_topup(style_no: Any, topup: Any) -> str | None:
    """Tracker Style No. encodes a TopUp as a ``-T1`` suffix (e.g. 20271008-T1)."""
    if style_no is None or str(style_no).strip() == "":
        return None
    style = str(style_no).strip()
    if topup and str(topup).strip():
        return f"{style}-{str(topup).strip()}"
    return style


def _fob_or_cf(terms_of_delivery: Any) -> str | None:
    if not terms_of_delivery:
        return None
    t = str(terms_of_delivery).upper()
    if "C&F" in t or "CNF" in t or "CFR" in t:
        return "C&F"
    if "FOB" in t:
        return "FOB"
    return None


def match_key(buyer_po: Any, style_no: Any, colour: Any) -> str:
    """Identity of a tracker row: Buyer PO# + Style No.(+TopUp) + Colour."""
    return "|".join(
        str(x).strip().upper() if x is not None else ""
        for x in (buyer_po, style_no, colour)
    )


def buyer_fields(header: dict, line: dict) -> dict[str, Any]:
    """Map a Customer-Order header + line to buyer-side tracker fields."""
    style = style_with_topup(line.get("style_no"), line.get("topup"))
    qty = line.get("quantity")
    price = line.get("price")
    total = line.get("total_spent")
    if total is None and qty is not None and price is not None:
        total = round(qty * price, 2)
    # the sheet's "Supplier" is us; the customer is the D1 block
    customer = parse_buyer_block(header.get("buyer_block"))["name"]
    return {
        "company_code": COMPANY_CODE,
        "customer_name": customer or DEFAULT_CUSTOMER,
        "division": DEFAULT_DIVISION,
        "buyer_po": header.get("order_number"),
        "colour": line.get("colour"),
        "style_no": style,
        "buyer_po_delivery_date": line.get("etd"),
        "fob_or_cf": _fob_or_cf(header.get("terms_of_delivery")),
        "order_qty": qty,
        "buyer_currency": header.get("currency"),
        "buyer_net_price": price,
        "buyer_total_value": total,
        "item": line.get("description"),
        # what the buyer pays us, taken verbatim from the buyer sheet ("100%TT")
        "buyer_payment_terms_status": header.get("payment_terms"),
        # provenance / traceability (not tracker columns, carried in metadata)
        "_article": line.get("article"),
    }


def vendor_fields(header: dict, line: dict) -> dict[str, Any]:
    """Map a Vendor-Order block header + line to factory-side tracker fields."""
    qty = line.get("quantity")
    price = line.get("price")
    total = round(qty * price, 2) if qty is not None and price is not None else None
    return {
        "factory_name": header.get("supplier"),
        "factory_delivery_date": line.get("etd"),
        "vendor_terms": header.get("terms_of_delivery"),
        "factory_price": price,
        "vendor_total_value": total,
        # what we pay this factory, verbatim from its own block header - the
        # "100%" prefix is part of the term and is kept ("100%TT 30 DAYS")
        "factory_payment_terms_status": header.get("payment_terms"),
        "_article": line.get("article"),
    }


def compute_derived(fields: dict[str, Any]) -> dict[str, Any]:
    """Fill computed columns (Price Difference) from whatever is present."""
    buyer = fields.get("buyer_net_price")
    factory = fields.get("factory_price")
    if buyer is not None and factory is not None:
        fields["price_difference"] = round(buyer - factory, 4)
    return fields
