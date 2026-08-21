"""Role-based permissions and the field-level audit trail."""

from .conftest import CUSTOMER_FILES, SAMPLES

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _register(client, email, role):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": email.split("@")[0], "role": role,
    })
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _files(names):
    out = []
    for n in names:
        path = SAMPLES / n
        out.append(("files", (path.name, path.read_bytes(), XLSX)))
    return out


def _bootstrap(client):
    """admin (first user) + one user of every role; returns tokens + first row id."""
    admin = _register(client, "admin@example.com", role="admin")  # first -> admin regardless
    ceo = _register(client, "ceo@example.com", role="ceo")
    shipping = _register(client, "ship@example.com", role="shipping_manager")
    merchant = _register(client, "merchant@example.com", role="merchant")
    # populate the tracker via an upload (admin is an allowed uploader)
    r = client.post("/api/orders/upload", files=_files(CUSTOMER_FILES[:1]), headers=_auth(admin))
    assert r.status_code == 200, r.text
    rows = client.get("/api/tracker", headers=_auth(admin)).json()
    return admin, ceo, shipping, merchant, rows[0]["id"]


def test_admin_role_forced_for_first_user(client):
    admin = _register(client, "admin@example.com", role="merchant")  # asked merchant...
    me = client.get("/api/auth/me", headers=_auth(admin)).json()
    assert me["role"] == "admin"  # ...but first user is always admin


def test_cannot_self_register_admin(client):
    _register(client, "admin@example.com", role="admin")  # first user
    r = client.post("/api/auth/register", json={
        "email": "sneaky@example.com", "password": "secret123", "name": "x", "role": "admin",
    })
    assert r.status_code == 403


def test_merchant_cannot_view_tracker(client):
    _, _, _, merchant, _ = _bootstrap(client)
    assert client.get("/api/tracker", headers=_auth(merchant)).status_code == 403
    # ...but can view order details
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
    assert str(r.json()["data"]["order_qty"]) == "123"
    # operational is no longer off-limits to the CEO
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"container_no": "X"}},
                     headers=_auth(ceo))
    assert r.status_code == 200, r.text
    # and money is theirs
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"buyer_net_price": 12.5}},
                     headers=_auth(ceo))
    assert r.status_code == 200, r.text
    assert float(r.json()["data"]["buyer_net_price"]) == 12.5


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
