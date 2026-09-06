"""Round-2 features: richer capture, seasons, per-PO view, paste and reports.

Everything here runs against the real sample workbooks, because the point of
most of it is that we read those sheets faithfully.
"""

import shutil
from datetime import date

import pytest

from app.services.order_parser import detect_kind_detail, parse_customer_order
from app.services.parties import parse_buyer_block
from app.services.seasons import season_for_date

from .conftest import SAMPLES, auth_header, register

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

CUSTOMER_D652 = SAMPLES / "different sheets" / "Customer-Order-D652-18.04.2026.xlsx"
VENDOR_D652 = SAMPLES / "different sheets" / "Vendor-Order-D652-18.04.2026.xlsx"


def _register(client, email, role=None, admin=None):
    return register(client, email, role=role, admin=admin)


def _auth(token):
    return auth_header(token)


def _upload(client, token, *paths):
    files = [("files", (p.name, p.read_bytes(), XLSX)) for p in paths]
    r = client.post("/api/orders/upload", files=files, headers=_auth(token))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def users(client):
    """admin (first user) plus one of every other role, approved by the admin."""
    admin = _register(client, "admin@example.com")
    return {
        "admin": admin,
        "ceo": _register(client, "ceo@example.com", "ceo", admin=admin),
        "shipping": _register(client, "ship@example.com", "shipping_manager", admin=admin),
        "merchant": _register(client, "merchant@example.com", "merchant", admin=admin),
    }


@pytest.fixture()
def loaded(client, users):
    """Both sides of PO D652 imported by the merchant."""
    payload = _upload(client, users["merchant"], CUSTOMER_D652, VENDOR_D652)
    return users, payload


def _rows(client, token):
    r = client.get("/api/tracker", headers=_auth(token))
    assert r.status_code == 200, r.text
    return {(x["style_no"], x["colour"]): x for x in r.json()}


def _ship_in_full(client, token):
    """Set every row's Ship Qty to its order qty. Totals are derived from the
    *shipped* quantity, so a report over freshly imported rows is all zeroes
    until something ships - shipping in full reproduces the sheet's own figures."""
    for row in client.get("/api/tracker", headers=_auth(token)).json():
        qty = (row.get("data") or {}).get("order_qty")
        r = client.patch(f"/api/tracker/{row['id']}",
                         json={"fields": {"ship_qty": qty}}, headers=_auth(token))
        assert r.status_code == 200, r.text


# --- sheet reading -------------------------------------------------------------

def test_sheet_kind_comes_from_layout_not_filename(tmp_path):
    """A buyer sheet named like a vendor sheet must still parse as a buyer sheet."""
    misleading = tmp_path / "Vendor comparison D652.xlsx"
    shutil.copy(CUSTOMER_D652, misleading)
    detected = detect_kind_detail(str(misleading), name_hint=misleading.name)
    assert detected["kind"] == "customer"
    assert detected["confidence"] == "high"


def test_buyer_block_yields_the_real_customer():
    """The sheets' Supplier is us; the customer is the D1 block."""
    parsed = parse_buyer_block(
        "Roman Originals PLC\n"
        "Unit 1, Vantage Point, 5 Wingfoot Close, Birmingham. B24 9JH\n"
        "VAT Number: GB 111 3607 23"
    )
    assert parsed["name"] == "Roman Originals PLC"
    assert parsed["vat_number"] == "GB 111 3607 23"
    assert "Wingfoot" in parsed["address"]


def test_size_ratio_header_is_captured():
    parsed = parse_customer_order(str(CUSTOMER_D652))
    spec = {e["uk_size"]: e for e in parsed["header"]["size_header"]}
    assert spec["24"]["alpha_size"] == "XL"
    assert spec["24"]["range_label"] == "22-24"
    assert spec["6"]["alpha_size"] is None
    # the ratio still adds up to the sheet's own Quantity
    for line in parsed["lines"]:
        assert sum(line["sizes"].values()) == line["quantity"]
    assert sum(line["quantity"] for line in parsed["lines"]) == 900


def test_every_cell_of_a_line_is_kept():
    line = parse_customer_order(str(CUSTOMER_D652))["lines"][0]
    assert line["raw"]["AB"] == {"header": "Packing method", "value": "Boxed into w/h"}
    assert line["order_date"] == "13 - Apr - 2026"
    assert line["order_date_d"] == date(2026, 4, 13)


def test_payment_terms_reach_the_tracker_verbatim(client, loaded):
    """The '100%' prefix is part of the term and must survive the import."""
    users, _ = loaded
    rows = _rows(client, users["admin"])
    crimson = rows[("20273308", "Black")]["data"]
    endow = rows[("17088908", "Black")]["data"]

    assert crimson["factory_name"] == "CRIMSON"
    assert crimson["factory_payment_terms_status"] == "100%TT 30 DAYS"
    assert endow["factory_name"] == "ENDOW EXPORTS"
    assert endow["factory_payment_terms_status"] == "100%TT"
    # the buyer's own terms come off the buyer sheet
    assert crimson["buyer_payment_terms_status"] == "100%TT"


def test_customer_name_comes_from_the_sheet(client, loaded):
    users, _ = loaded
    rows = _rows(client, users["admin"])
    assert rows[("17088908", "Black")]["data"]["customer_name"] == "Roman Originals PLC"


def test_container_size_column_is_relabelled(client, users):
    cols = client.get("/api/tracker/columns", headers=_auth(users["admin"])).json()
    by_key = {c["key"]: c for c in cols}
    assert by_key["container_size"]["label"] == "Container Size"
    assert by_key["container_size"]["col"] == "AY"
    assert by_key["buyer_net_price"]["is_price"] is True
    assert by_key["buyer_po"]["is_identity"] is True
    assert by_key["price_difference"]["is_derived"] is True


def test_masters_populate_themselves_from_uploads(client, loaded):
    users, _ = loaded
    customers = client.get("/api/customers", headers=_auth(users["admin"])).json()
    assert "Roman Originals PLC" in [c["name"] for c in customers]

    vendors = client.get("/api/vendors", headers=_auth(users["admin"])).json()
    by_name = {v["name"]: v for v in vendors}
    assert set(by_name) >= {"CRIMSON", "ENDOW EXPORTS"}
    assert by_name["CRIMSON"]["payment_terms"] == "100%TT 30 DAYS"
    assert by_name["CRIMSON"]["port_of_loading"] == "Nhava Sheva"


def test_only_admin_manages_vendors(client, loaded):
    users, _ = loaded
    body = {"name": "NEW FACTORY"}
    assert client.post("/api/vendors", json=body, headers=_auth(users["ceo"])).status_code == 403
    assert client.post("/api/vendors", json=body, headers=_auth(users["admin"])).status_code == 201


# --- roles ---------------------------------------------------------------------

def test_merchant_has_pos_but_no_tracker(client, loaded):
    users, _ = loaded
    r = client.get("/api/pos", headers=_auth(users["merchant"]))
    assert r.status_code == 200, r.text
    assert [p["buyer_po"] for p in r.json()] == ["D652"]


def test_merchant_reads_tracker_rows_but_cannot_touch_them(client, loaded):
    """The dashboard panel needs the rows; nothing else about the tracker opens up."""
    users, _ = loaded
    m = _auth(users["merchant"])

    rows = client.get("/api/tracker", headers=m)
    assert rows.status_code == 200, rows.text
    row_id = rows.json()[0]["id"]

    # read-only: every write, the export and the column list stay shut
    assert client.patch(f"/api/tracker/{row_id}", json={"fields": {"lot_no": "9"}},
                        headers=m).status_code == 403
    assert client.patch("/api/tracker/lines", json={"updates": {}}, headers=m).status_code == 403
    assert client.post("/api/tracker", json={"fields": {}}, headers=m).status_code == 403
    assert client.get("/api/tracker/export", headers=m).status_code == 403
    assert client.get("/api/tracker/columns", headers=m).status_code == 403


def test_merchant_edits_a_po_but_not_its_prices(client, loaded):
    users, _ = loaded
    detail = client.get("/api/pos/D652", headers=_auth(users["merchant"])).json()
    row_id = detail["lines"][0]["tracker_row_id"]

    # an operational column: allowed
    r = client.patch(f"/api/pos/D652/rows/{row_id}",
                     json={"tracker_fields": {"remarks": "checked"}},
                     headers=_auth(users["merchant"]))
    assert r.status_code == 200, r.text
    assert r.json()["tracker"]["remarks"] == "checked"

    # an order-sheet product field: allowed, and written to the order line
    r = client.patch(f"/api/pos/D652/rows/{row_id}",
                     json={"line_fields": {"composition": "95% Polyester, 5% Elastane"}},
                     headers=_auth(users["merchant"]))
    assert r.status_code == 200, r.text
    assert r.json()["line"]["composition"] == "95% Polyester, 5% Elastane"

    # money: refused
    r = client.patch(f"/api/pos/D652/rows/{row_id}",
                     json={"tracker_fields": {"buyer_net_price": 1}},
                     headers=_auth(users["merchant"]))
    assert r.status_code == 403
    assert "Buyer Net Price" in r.json()["detail"]


def test_ceo_may_set_prices_from_the_po_view(client, loaded):
    users, _ = loaded
    detail = client.get("/api/pos/D652", headers=_auth(users["ceo"])).json()
    row_id = detail["lines"][0]["tracker_row_id"]
    r = client.patch(f"/api/pos/D652/rows/{row_id}",
                     json={"tracker_fields": {"buyer_net_price": 6.5}},
                     headers=_auth(users["ceo"]))
    assert r.status_code == 200, r.text
    assert r.json()["tracker"]["buyer_net_price"] == 6.5


def test_po_detail_carries_the_size_ratio(client, loaded):
    users, _ = loaded
    detail = client.get("/api/pos/D652", headers=_auth(users["merchant"])).json()
    assert detail["customer_name"] == "Roman Originals PLC"
    assert len(detail["lines"]) == 3
    assert detail["totals"]["order_qty"] == 900
    line = detail["lines"][0]
    assert sum(line["sizes"].values()) == 300
    assert any(e["alpha_size"] == "XL" for e in line["size_header"])


def test_po_schema_groups_every_field(client, users):
    schema = client.get("/api/pos/schema", headers=_auth(users["merchant"])).json()
    assert [g["key"] for g in schema["groups"]] == ["buyer", "vendor", "product", "shipping"]
    by_key = {f["key"]: f for f in schema["fields"]}
    assert by_key["buyer_net_price"]["group"] == "buyer"
    assert by_key["factory_price"]["group"] == "vendor"
    assert by_key["container_no"]["group"] == "shipping"
    assert by_key["composition"]["group"] == "product"
    assert by_key["composition"]["origin"] == "order_line"


# --- seasons -------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (date(2026, 2, 28), ("AW", 2025)),
    (date(2026, 3, 1), ("SS", 2026)),
    (date(2026, 8, 31), ("SS", 2026)),
    (date(2026, 9, 1), ("AW", 2026)),
    (date(2027, 1, 15), ("AW", 2026)),
])
def test_season_boundaries(value, expected):
    assert season_for_date(value) == expected


def test_upload_suggests_a_season_per_po(client, loaded):
    _users, payload = loaded
    assert len(payload["seasons"]) == 1
    suggestion = payload["seasons"][0]
    # earliest buyer delivery on D652 is 13-Jul-26 -> Spring/Summer 2026
    assert suggestion["buyer_po"] == "D652"
    assert (suggestion["season_type"], suggestion["season_year"]) == ("SS", 2026)
    assert suggestion["confirmed"] is False
    assert suggestion["basis"] == "buyer delivery date"


def test_merchant_confirms_a_season(client, loaded):
    users, _ = loaded
    r = client.post("/api/seasons/assign", headers=_auth(users["merchant"]), json={
        "assignments": [{"buyer_po": "D652", "season_type": "AW", "season_year": 2026}],
    })
    assert r.status_code == 200, r.text
    assert r.json()[0]["label"] == "Autumn-Winter '26"

    assert client.get("/api/seasons/pending", headers=_auth(users["merchant"])).json() == []
    detail = client.get("/api/pos/D652", headers=_auth(users["merchant"])).json()
    assert detail["season"]["code"] == "AW26"


def test_shipping_cannot_assign_seasons(client, loaded):
    users, _ = loaded
    r = client.post("/api/seasons/assign", headers=_auth(users["shipping"]), json={
        "assignments": [{"buyer_po": "D652", "season_type": "SS", "season_year": 2026}],
    })
    assert r.status_code == 403


# --- paste ---------------------------------------------------------------------

PASTE_ONE_PO = (
    "Style\tColour\tContainer No\tVessel\tBL No\tETD\n"
    "20273308\tBlack\tMSMU8156172\tMAERSK KOWLOON\tBL-9931\t12-Aug-26\n"
)

PASTE_MULTI = (
    "PO No.\tStyle\tColour\tBooking No\tForwarder\n"
    "D652\t17088908\tBlack\tBK-771\tDSV\n"
    "D999\t11111111\tBlack\tBK-772\tDSV\n"
)


def test_paste_is_shipping_only(client, loaded):
    users, _ = loaded
    body = {"text": PASTE_ONE_PO, "buyer_po": "D652"}
    assert client.post("/api/paste/preview", json=body,
                       headers=_auth(users["merchant"])).status_code == 403
    assert client.post("/api/paste/preview", json=body,
                       headers=_auth(users["ceo"])).status_code == 403
    assert client.post("/api/paste/preview", json=body,
                       headers=_auth(users["shipping"])).status_code == 200


def test_paste_maps_email_headers_onto_tracker_columns(client, loaded):
    users, _ = loaded
    r = client.post("/api/paste/preview", json={"text": PASTE_ONE_PO, "buyer_po": "D652"},
                    headers=_auth(users["shipping"]))
    assert r.status_code == 200, r.text
    preview = r.json()
    mapped = {c["excel_header"]: c["matched_field_key"] for c in preview["columns"]}
    assert mapped["Container No"] == "container_no"
    assert mapped["Vessel"] == "vessel"
    assert mapped["BL No"] == "bl_no"
    assert mapped["ETD"] == "etd"
    assert preview["matched_row_count"] == 1
    assert preview["rows"][0]["mapped"]["etd"] == "2026-08-12"


def test_paste_applies_to_one_po(client, loaded):
    users, _ = loaded
    r = client.post("/api/paste/apply", json={"text": PASTE_ONE_PO, "buyer_po": "D652"},
                    headers=_auth(users["shipping"]))
    assert r.status_code == 200, r.text
    assert r.json()["updated_rows"] == 1

    data = _rows(client, users["admin"])[("20273308", "Black")]["data"]
    assert data["container_no"] == "MSMU8156172"
    assert data["vessel"] == "MAERSK KOWLOON"
    assert data["etd"] == "2026-08-12"


def test_paste_spanning_pos_reports_the_ones_we_do_not_have(client, loaded):
    users, _ = loaded
    r = client.post("/api/paste/apply", json={"text": PASTE_MULTI},
                    headers=_auth(users["shipping"]))
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["updated_rows"] == 1
    assert result["unmatched_pos"] == ["D999"]

    data = _rows(client, users["admin"])[("17088908", "Black")]["data"]
    assert data["booking_no"] == "BK-771"
    assert data["forwarder"] == "DSV"


def test_paste_refuses_an_ambiguous_row(client, loaded):
    """D652 has three lines; without a style or colour we must not guess."""
    users, _ = loaded
    text = "PO No.\tBooking No\nD652\tBK-800\n"
    r = client.post("/api/paste/preview", json={"text": text},
                    headers=_auth(users["shipping"]))
    assert r.status_code == 200, r.text
    preview = r.json()
    assert preview["matched_row_count"] == 0
    assert "3 lines" in preview["rows"][0]["error"]


def test_paste_cannot_smuggle_in_a_price(client, loaded):
    users, _ = loaded
    text = "Style\tColour\tBuyer Net Price\nB20273308\tBlack\t99\n".replace("B2027", "2027")
    r = client.post("/api/paste/preview", json={"text": text, "buyer_po": "D652"},
                    headers=_auth(users["shipping"]))
    assert r.status_code == 200, r.text
    price_col = next(c for c in r.json()["columns"] if c["excel_header"] == "Buyer Net Price")
    assert price_col["matched_field_key"] == "buyer_net_price"
    assert price_col["will_import"] is False
    assert "cannot edit" in price_col["blocked_reason"]

    client.post("/api/paste/apply", json={"text": text, "buyer_po": "D652"},
                headers=_auth(users["shipping"]))
    data = _rows(client, users["admin"])[("20273308", "Black")]["data"]
    assert data["buyer_net_price"] == 5.45  # untouched



# --- pasting a plain-text table with gaps ---------------------------------------
# An e-mail table is held together by alignment, not tabs. Splitting it on runs
# of spaces loses every empty cell, which shifts the rest of the row a column
# left and writes values into the wrong tracker fields.

PASTE_ALIGNED_WITH_GAPS = (
    "PO No.    Style       Colour   Mode   Forwarder   BL No.        Vessel\n"
    "D652      17088908    Black                       177116010974  KLEVEN\n"
)


def test_paste_keeps_columns_aligned_across_empty_cells(client, loaded):
    users, _ = loaded
    r = client.post("/api/paste/preview", json={"text": PASTE_ALIGNED_WITH_GAPS},
                    headers=_auth(users["shipping"]))
    assert r.status_code == 200, r.text
    mapped = r.json()["rows"][0]["mapped"]
    assert mapped["bl_no"] == "177116010974"   # not shifted into Mode
    assert mapped["vessel"] == "KLEVEN"        # not shifted into Forwarder
    assert "mode" not in mapped and "forwarder" not in mapped


def test_paste_applies_an_aligned_table_with_gaps(client, loaded):
    users, _ = loaded
    r = client.post("/api/paste/apply", json={"text": PASTE_ALIGNED_WITH_GAPS},
                    headers=_auth(users["shipping"]))
    assert r.status_code == 200, r.text
    assert r.json()["updated_rows"] == 1

    data = _rows(client, users["admin"])[("17088908", "Black")]["data"]
    assert data["bl_no"] == "177116010974"
    assert data["vessel"] == "KLEVEN"
    assert data.get("mode") is None

# --- reports -------------------------------------------------------------------

def test_reports_are_ceo_and_admin_only(client, loaded):
    users, _ = loaded
    assert client.get("/api/reports/summary", headers=_auth(users["merchant"])).status_code == 403
    assert client.get("/api/reports/summary", headers=_auth(users["shipping"])).status_code == 403
    assert client.get("/api/reports/summary", headers=_auth(users["ceo"])).status_code == 200


def test_report_by_season_totals_match_the_sheets(client, loaded):
    users, _ = loaded
    _ship_in_full(client, users["ceo"])
    client.post("/api/seasons/assign", headers=_auth(users["merchant"]), json={
        "assignments": [{"buyer_po": "D652", "season_type": "SS", "season_year": 2026}],
    })
    report = client.get("/api/reports/summary?group_by=season",
                        headers=_auth(users["ceo"])).json()
    assert [b["key"] for b in report["buckets"]] == ["SS26"]
    bucket = report["buckets"][0]
    assert bucket["label"] == "Spring-Summer '26"
    assert bucket["po_count"] == 1
    assert bucket["line_count"] == 3
    assert bucket["order_qty"] == 900
    # buyer totals off the customer sheet: 1635 + 2625 + 2775
    assert bucket["buyer_value"] == 7035
    # vendor totals: CRIMSON 300 x 3.75, ENDOW 300 x 8 twice
    assert bucket["vendor_value"] == 1125 + 2400 + 2400
    assert bucket["margin"] == round(7035 - 5925, 2)


def test_report_by_vendor_splits_the_factories(client, loaded):
    users, _ = loaded
    _ship_in_full(client, users["ceo"])
    report = client.get("/api/reports/summary?group_by=vendor",
                        headers=_auth(users["ceo"])).json()
    by_key = {b["key"]: b for b in report["buckets"]}
    assert set(by_key) == {"CRIMSON", "ENDOW EXPORTS"}
    assert by_key["ENDOW EXPORTS"]["line_count"] == 2
    assert by_key["CRIMSON"]["vendor_value"] == 1125
    assert report["totals"]["line_count"] == 3


def test_report_filters_by_vendor(client, loaded):
    users, _ = loaded
    report = client.get("/api/reports/summary?group_by=customer&vendor=CRIMSON",
                        headers=_auth(users["ceo"])).json()
    assert report["totals"]["line_count"] == 1
    assert report["buckets"][0]["key"] == "Roman Originals PLC"


def test_report_export_is_a_workbook(client, loaded):
    users, _ = loaded
    r = client.get("/api/reports/export?group_by=vendor", headers=_auth(users["ceo"]))
    assert r.status_code == 200, r.text
    assert r.content[:2] == b"PK"  # xlsx is a zip
    assert "attachment" in r.headers["content-disposition"]


# --- change trail on the PO view ----------------------------------------------

def test_po_audit_covers_tracker_and_order_sheet_fields(client, loaded):
    """The 'who changed this' trail has to reach both records behind a line.

    A PO line spans a tracker row and the order line under it, and an edit to
    either is worth the same question. Regression guard: the order-line half was
    written but unreadable for a while, so the trail simply vanished for product
    fields.
    """
    users, _ = loaded
    detail = client.get("/api/pos/D652", headers=_auth(users["ceo"])).json()
    row_id = detail["lines"][0]["tracker_row_id"]

    client.patch(f"/api/pos/D652/rows/{row_id}",
                 json={"tracker_fields": {"remarks": "checked by CEO"}},
                 headers=_auth(users["ceo"]))
    client.patch(f"/api/pos/D652/rows/{row_id}",
                 json={"line_fields": {"composition": "92% Polyester, 8% Elastane"}},
                 headers=_auth(users["ceo"]))

    tracker_trail = client.get(
        f"/api/pos/D652/rows/{row_id}/audit?origin=tracker&field=remarks",
        headers=_auth(users["ceo"]),
    ).json()
    assert [e["new_value"] for e in tracker_trail] == ["checked by CEO"]
    assert tracker_trail[0]["user_name"]
    assert tracker_trail[0]["created_at"]

    line_trail = client.get(
        f"/api/pos/D652/rows/{row_id}/audit?origin=order_line&field=composition",
        headers=_auth(users["ceo"]),
    ).json()
    assert len(line_trail) == 1
    assert line_trail[0]["old_value"] == "100% Polyester"
    assert line_trail[0]["new_value"] == "92% Polyester, 8% Elastane"


def test_po_audit_keeps_the_whole_history(client, loaded):
    """An upload is part of the trail, not just later hand edits."""
    users, _ = loaded
    detail = client.get("/api/pos/D652", headers=_auth(users["ceo"])).json()
    row_id = detail["lines"][0]["tracker_row_id"]

    client.patch(f"/api/pos/D652/rows/{row_id}",
                 json={"tracker_fields": {"buyer_net_price": 9.99}},
                 headers=_auth(users["ceo"]))
    trail = client.get(
        f"/api/pos/D652/rows/{row_id}/audit?origin=tracker&field=buyer_net_price",
        headers=_auth(users["ceo"]),
    ).json()
    # newest first: the CEO's edit, then the merchant's upload that set it
    assert [e["action"] for e in trail] == ["edit", "import"]
    assert trail[0]["old_value"] == trail[1]["new_value"]


def test_po_audit_is_ceo_and_admin_only(client, loaded):
    users, _ = loaded
    detail = client.get("/api/pos/D652", headers=_auth(users["merchant"])).json()
    row_id = detail["lines"][0]["tracker_row_id"]
    for role in ("merchant", "shipping"):
        r = client.get(f"/api/pos/D652/rows/{row_id}/audit", headers=_auth(users[role]))
        assert r.status_code == 403, role
    assert client.get(f"/api/pos/D652/rows/{row_id}/audit",
                      headers=_auth(users["admin"])).status_code == 200


def test_po_audit_rejects_a_row_from_another_po(client, loaded):
    """A real row id under the wrong PO must not leak that row's history."""
    users, _ = loaded
    detail = client.get("/api/pos/D652", headers=_auth(users["ceo"])).json()
    row_id = detail["lines"][0]["tracker_row_id"]
    r = client.get(f"/api/pos/D999/rows/{row_id}/audit", headers=_auth(users["ceo"]))
    assert r.status_code == 404
