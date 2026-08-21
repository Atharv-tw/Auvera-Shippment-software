"""Listing behaviour of GET /api/tracker: search, sort and opt-in paging.

The dashboard panel pages through this endpoint; the tracker grid asks for
everything at once. Both share one query, so both are covered here.
"""

from .conftest import CUSTOMER_FILES, SAMPLES

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client):
    r = client.post("/api/auth/register", json={
        "email": "admin@example.com", "password": "secret123", "name": "admin", "role": "admin",
    })
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    path = SAMPLES / CUSTOMER_FILES[0]
    files = [("files", (path.name, path.read_bytes(), XLSX))]
    assert client.post("/api/orders/upload", files=files, headers=_auth(token)).status_code == 200
    return token


def test_no_limit_returns_every_row_and_a_total(client):
    """The tracker grid depends on getting the whole set - paging is opt-in."""
    token = _admin(client)
    r = client.get("/api/tracker", headers=_auth(token))
    assert r.status_code == 200
    assert len(r.json()) == int(r.headers["X-Total-Count"])


def test_limit_and_offset_page_without_losing_the_total(client):
    token = _admin(client)
    everything = client.get("/api/tracker", headers=_auth(token)).json()
    assert len(everything) >= 2, "sample upload should yield several rows"

    first = client.get("/api/tracker?limit=1&sort=buyer_po", headers=_auth(token))
    second = client.get("/api/tracker?limit=1&offset=1&sort=buyer_po", headers=_auth(token))

    assert len(first.json()) == 1 and len(second.json()) == 1
    assert first.json()[0]["id"] != second.json()[0]["id"]
    # the count is of matching rows, not of the page
    assert int(first.headers["X-Total-Count"]) == len(everything)


def test_search_reaches_factory_name(client):
    """The dashboard used to filter client-side purely because the query could
    not see factory_name. It is a real column now, so the server can."""
    token = _admin(client)
    rows = client.get("/api/tracker", headers=_auth(token)).json()
    factory = next((r["data"].get("factory_name") for r in rows if r["data"].get("factory_name")), None)
    if factory is None:
        # buyer-only upload: assert the column is at least searchable, not 500
        assert client.get("/api/tracker?search=anything", headers=_auth(token)).status_code == 200
        return
    hits = client.get(f"/api/tracker?search={factory[:5]}", headers=_auth(token)).json()
    assert hits and all(factory[:5].lower() in str(h["data"].get("factory_name", "")).lower() for h in hits)


def test_sort_desc_reverses_and_unknown_sort_is_rejected(client):
    token = _admin(client)
    asc = client.get("/api/tracker?sort=buyer_po&order=asc", headers=_auth(token)).json()
    desc = client.get("/api/tracker?sort=buyer_po&order=desc", headers=_auth(token)).json()
    assert [r["id"] for r in asc] == list(reversed([r["id"] for r in desc]))

    bad = client.get("/api/tracker?sort=remarks", headers=_auth(token))
    assert bad.status_code == 400, "sort must be an allow-list, not any column name"
