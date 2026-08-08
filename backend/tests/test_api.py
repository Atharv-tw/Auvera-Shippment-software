from .conftest import CUSTOMER_FILES, SAMPLES, VENDOR_FILES

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _register(client, email, password="secret123", role="merchant"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": password, "name": email.split("@")[0], "role": role,
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


def test_full_flow(client):
    admin = _register(client, "admin@example.com")  # first user -> admin

    # upload all customer + vendor files at once
    r = client.post("/api/orders/upload", files=_files(CUSTOMER_FILES + VENDOR_FILES),
                    headers=_auth(admin))
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert all(res["status"] == "created" for res in results)
    kinds = {res["filename"]: res["kind"] for res in results}
    assert kinds[SAMPLES.joinpath(VENDOR_FILES[0]).name] == "vendor"

    # tracker populated
    rows = client.get("/api/tracker", headers=_auth(admin)).json()
    assert len(rows) == 11

    # mapping spot-check
    row = next(x for x in rows if x["style_no"] == "17088908")
    assert row["data"]["factory_name"] == "ENDOW EXPORTS"
    assert row["data"]["price_difference"] == 0.75

    # edit a row
    rid = row["id"]
    r = client.patch(f"/api/tracker/{rid}", json={"fields": {"container_no": "XYZ999", "ship_qty": 295}},
                     headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["data"]["container_no"] == "XYZ999"
    assert "container_no" in r.json()["edited_keys"]

    # columns endpoint
    cols = client.get("/api/tracker/columns", headers=_auth(admin)).json()
    assert len(cols) == 56

    # export returns an xlsx
    r = client.get("/api/tracker/export", headers=_auth(admin))
    assert r.status_code == 200
    assert r.headers["content-type"] == XLSX
    assert r.content[:2] == b"PK"  # zip/xlsx magic


def test_non_uploader_cannot_upload(client):
    _register(client, "admin@example.com")                              # first -> admin
    shipping = _register(client, "ship@example.com", role="shipping_manager")
    r = client.post("/api/orders/upload", files=_files(CUSTOMER_FILES[:1]), headers=_auth(shipping))
    assert r.status_code == 403


def test_ceo_can_upload(client):
    _register(client, "admin@example.com")
    ceo = _register(client, "ceo@example.com", role="ceo")
    r = client.post("/api/orders/upload", files=_files(CUSTOMER_FILES[:1]), headers=_auth(ceo))
    assert r.status_code == 200, r.text


def test_merchant_can_upload(client):
    _register(client, "admin@example.com")
    merchant = _register(client, "merchant@example.com", role="merchant")
    r = client.post("/api/orders/upload", files=_files(CUSTOMER_FILES[:1]), headers=_auth(merchant))
    assert r.status_code == 200, r.text


def test_requires_auth(client):
    assert client.get("/api/tracker").status_code == 401
