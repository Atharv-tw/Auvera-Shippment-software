"""Role-based permissions and the field-level audit trail."""

from .conftest import CUSTOMER_FILES, SAMPLES, auth_header, register

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _register(client, email, role=None, admin=None):
    return register(client, email, role=role, admin=admin)


def _auth(token):
    return auth_header(token)


def _files(names):
    out = []
    for n in names:
        path = SAMPLES / n
        out.append(("files", (path.name, path.read_bytes(), XLSX)))
    return out


def _bootstrap(client):
    """admin (first user) + one user of every role; returns tokens + first row id."""
    admin = _register(client, "admin@example.com")  # first user -> admin regardless
    ceo = _register(client, "ceo@example.com", role="ceo", admin=admin)
    shipping = _register(client, "ship@example.com", role="shipping_manager", admin=admin)
    merchant = _register(client, "merchant@example.com", role="merchant", admin=admin)
    # populate the tracker via an upload (admin is an allowed uploader)
    r = client.post("/api/orders/upload", files=_files(CUSTOMER_FILES[:1]), headers=_auth(admin))
    assert r.status_code == 200, r.text
    rows = client.get("/api/tracker", headers=_auth(admin)).json()
    return admin, ceo, shipping, merchant, rows[0]["id"]


def test_admin_role_forced_for_first_user(client):
    admin = _register(client, "admin@example.com")
    me = client.get("/api/auth/me", headers=_auth(admin)).json()
    assert me["role"] == "admin"  # first user is always admin


def test_new_users_land_on_the_waitlist_with_no_role(client):
    _register(client, "admin@example.com")  # first user -> admin
    # a role in the body is ignored: registration never grants access now
    r = client.post("/api/auth/register", json={
        "email": "sneaky@example.com", "password": "secret123", "name": "x", "role": "admin",
    })
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "pending"


def test_merchant_reads_tracker_rows_but_gets_no_tracker_page(client):
    _, _, _, merchant, rid = _bootstrap(client)
    # the dashboard's Shipment Tracker panel reads the rows...
    assert client.get("/api/tracker", headers=_auth(merchant)).status_code == 200
    # ...but the tracker page's own endpoints, and every write, stay shut
    assert client.get("/api/tracker/columns", headers=_auth(merchant)).status_code == 403
    assert client.patch(f"/api/tracker/{rid}", json={"fields": {"container_no": "C1"}},
                        headers=_auth(merchant)).status_code == 403
    # ...and order details were always fine
    assert client.get("/api/orders", headers=_auth(merchant)).status_code == 200


def test_shipping_manager_edits_everything_except_price(client):
    _, _, shipping, _, rid = _bootstrap(client)
    # operational field: allowed
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"container_no": "C1"}},
                     headers=_auth(shipping))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["container_no"] == "C1"
    # order detail that is not money: allowed too, unlike the old lane model
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"order_qty": 999}},
                     headers=_auth(shipping))
    assert r.status_code == 200, r.text
    # money: forbidden
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"buyer_net_price": 1.5}},
                     headers=_auth(shipping))
    assert r.status_code == 403
    # the row's identity is CEO/admin only - changing it would re-key the row
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"buyer_po": "NOPE"}},
                     headers=_auth(shipping))
    assert r.status_code == 403


def test_ceo_edits_everything_including_price(client):
    _, ceo, _, _, rid = _bootstrap(client)
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"order_qty": 123}},
                     headers=_auth(ceo))
    assert r.status_code == 200, r.text
    # compare the value, not its Python repr: order_qty is a Float column now, so
    # it comes back as 123.0. JSON numbers are IEEE doubles, so the browser parses
    # 123 and 123.0 to the same value - the string form was never the contract.
    assert r.json()["data"]["order_qty"] == 123
    # operational is no longer off-limits to the CEO
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"container_no": "X"}},
                     headers=_auth(ceo))
    assert r.status_code == 200, r.text
    # and money is theirs
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"buyer_net_price": 12.5}},
                     headers=_auth(ceo))
    assert r.status_code == 200, r.text
    assert float(r.json()["data"]["buyer_net_price"]) == 12.5



def test_shipment_status_follows_bl_and_sailing_date(client):
    """Two values, neither typed: evidence of sailing makes a line Shipped."""
    admin, _, _, _, rid = _bootstrap(client)
    row = client.get(f"/api/tracker/{rid}", headers=_auth(admin)).json()
    assert row["data"]["shipment_status"] == "Planned"

    # nobody hand-edits it, not even an admin
    assert client.patch(f"/api/tracker/{rid}", json={
        "fields": {"shipment_status": "Shipped"}},
        headers=_auth(admin)).status_code == 403

    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"bl_no": "177116010974"}},
                     headers=_auth(admin))
    assert r.json()["data"]["shipment_status"] == "Shipped"

    # clearing the evidence puts it back
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"bl_no": None}},
                     headers=_auth(admin))
    assert r.json()["data"]["shipment_status"] == "Planned"

    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"etd": "2026-08-29"}},
                     headers=_auth(admin))
    assert r.json()["data"]["shipment_status"] == "Shipped"

def test_price_difference_is_never_hand_edited(client):
    admin, _, _, _, rid = _bootstrap(client)
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"price_difference": 99}},
                     headers=_auth(admin))
    assert r.status_code == 403


def test_audit_trail_records_upload_and_edit(client):
    admin, ceo, _, merchant, rid = _bootstrap(client)
    # the upload should have recorded who entered the order-detail columns
    trail = client.get(f"/api/tracker/{rid}/audit?field=order_qty", headers=_auth(ceo)).json()
    assert len(trail) >= 1
    assert trail[0]["action"] == "import"
    assert trail[0]["user_name"]  # uploader captured

    # a CEO edit appends a newer entry (newest first)
    client.patch(f"/api/tracker/{rid}", json={"fields": {"order_qty": 500}}, headers=_auth(ceo))
    trail = client.get(f"/api/tracker/{rid}/audit?field=order_qty", headers=_auth(ceo)).json()
    assert trail[0]["action"] == "edit"
    assert trail[0]["new_value"] == "500"

    # merchant cannot read the audit trail
    assert client.get(f"/api/tracker/{rid}/audit", headers=_auth(merchant)).status_code == 403


# --- "who may edit this field?" is answered once, by the API --------------------

def _editable_columns(client, token):
    cols = client.get("/api/tracker/columns", headers=_auth(token)).json()
    return {c["key"] for c in cols if c["editable"]}


def test_columns_carry_the_edit_answer(client):
    """The column list tells the caller which columns it may write, so the UI
    reads the answer instead of re-deriving the rule."""
    admin, ceo, shipping, _, _ = _bootstrap(client)

    ceo_keys = _editable_columns(client, ceo)
    shipping_keys = _editable_columns(client, shipping)

    assert {"buyer_net_price", "buyer_po", "container_no"} <= ceo_keys
    assert "buyer_net_price" not in shipping_keys  # money is CEO/admin
    assert "buyer_po" not in shipping_keys  # identity re-keys the row
    assert "container_no" in shipping_keys  # everything else is theirs
    # derived columns are nobody's to type, admin included
    assert "price_difference" not in _editable_columns(client, admin)


def test_advertised_edit_rights_match_what_the_write_gate_accepts(client):
    """The guard against the two halves drifting apart.

    Every column, both editing roles: what ``/columns`` says about editing has
    to be what ``PATCH`` actually does. If they ever disagree, the UI either
    offers an edit that will 403 on save, or hides one it was allowed to make.
    """
    _, ceo, shipping, _, rid = _bootstrap(client)
    for token in (ceo, shipping):
        for col in client.get("/api/tracker/columns", headers=_auth(token)).json():
            # None means "clear this cell" and is valid for every column type,
            # so the permission gate is the only thing under test here
            r = client.patch(f"/api/tracker/{rid}", json={"fields": {col["key"]: None}},
                             headers=_auth(token))
            assert r.status_code in (200, 403), r.text
            assert (r.status_code != 403) is col["editable"], (
                f"{col['key']}: editable={col['editable']} but PATCH said {r.status_code}"
            )


def test_po_schema_carries_the_edit_answer_per_origin(client):
    """A PO field is stored either on the tracker row or on the order line, and
    the two are gated separately - so each is answered against its own origin."""
    _, _, _, merchant, _ = _bootstrap(client)
    schema = client.get("/api/pos/schema", headers=_auth(merchant)).json()
    by_key = {f["key"]: f for f in schema["fields"]}

    assert by_key["remarks"]["editable"] is True  # tracker, operational
    assert by_key["composition"]["editable"] is True  # order-sheet detail
    assert by_key["buyer_net_price"]["editable"] is False  # money
    assert by_key["buyer_po"]["editable"] is False  # identity
    assert by_key["price_difference"]["editable"] is False  # derived


def test_po_schema_matches_what_the_po_write_gate_accepts(client):
    """The same no-drift check on the per-PO view, which a merchant reaches
    without any tracker access at all."""
    _, _, _, merchant, _ = _bootstrap(client)
    m = _auth(merchant)
    buyer_po = client.get("/api/pos", headers=m).json()[0]["buyer_po"]
    row_id = client.get(f"/api/pos/{buyer_po}", headers=m).json()["lines"][0]["tracker_row_id"]

    for field in client.get("/api/pos/schema", headers=m).json()["fields"]:
        side = "tracker_fields" if field["origin"] == "tracker" else "line_fields"
        r = client.patch(f"/api/pos/{buyer_po}/rows/{row_id}",
                         json={side: {field["key"]: None}}, headers=m)
        assert r.status_code in (200, 403), r.text
        assert (r.status_code != 403) is field["editable"], (
            f"{field['key']} ({field['origin']}): editable={field['editable']} "
            f"but PATCH said {r.status_code}"
        )
