"""The waitlist and the admin user-management panel.

New accounts arrive with no role and can do nothing until an admin approves
them. Only an admin may list users or change a role, and the admin cannot lock
themselves - or the whole system - out.
"""

from .conftest import auth_header, register


def _me(client, token):
    return client.get("/api/auth/me", headers=auth_header(token)).json()


def test_first_user_is_admin_the_rest_are_pending(client):
    admin = register(client, "admin@example.com")
    assert _me(client, admin)["role"] == "admin"

    r = client.post("/api/auth/register", json={
        "email": "newbie@example.com", "password": "secret123", "name": "New",
    })
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "pending"


def test_pending_user_is_locked_out_of_features_but_can_see_itself(client):
    register(client, "admin@example.com")  # first -> admin
    pending = register(client, "wait@example.com")  # no role

    # can read its own account (the waitlist page needs this)...
    assert client.get("/api/auth/me", headers=auth_header(pending)).status_code == 200
    # ...but every feature endpoint is shut
    assert client.get("/api/tracker", headers=auth_header(pending)).status_code == 403
    assert client.get("/api/pos", headers=auth_header(pending)).status_code == 403


def test_only_admin_may_list_or_change_users(client):
    admin = register(client, "admin@example.com")
    ceo = register(client, "ceo@example.com", role="ceo", admin=admin)

    assert client.get("/api/admin/users", headers=auth_header(admin)).status_code == 200
    assert client.get("/api/admin/users", headers=auth_header(ceo)).status_code == 403
    # a non-admin cannot promote anyone
    uid = _me(client, ceo)["id"]
    r = client.patch(f"/api/admin/users/{uid}", json={"role": "admin"}, headers=auth_header(ceo))
    assert r.status_code == 403


def test_assigning_a_role_clears_the_waitlist(client):
    admin = register(client, "admin@example.com")
    pending = register(client, "wait@example.com")
    uid = _me(client, pending)["id"]

    # blocked before approval
    assert client.get("/api/pos", headers=auth_header(pending)).status_code == 403

    r = client.patch(f"/api/admin/users/{uid}", json={"role": "merchant"},
                     headers=auth_header(admin))
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "merchant"

    # the same token now works - the role is read from the DB, not the token
    assert client.get("/api/pos", headers=auth_header(pending)).status_code == 200


def test_users_list_puts_pending_first(client):
    admin = register(client, "admin@example.com")
    register(client, "ceo@example.com", role="ceo", admin=admin)
    register(client, "wait@example.com")  # pending

    rows = client.get("/api/admin/users", headers=auth_header(admin)).json()
    assert rows[0]["role"] == "pending"
    # the payload carries what the panel shows
    assert {"is_active", "created_at", "email", "name"} <= set(rows[0])


def test_admin_cannot_demote_or_disable_themselves(client):
    admin = register(client, "admin@example.com")
    uid = _me(client, admin)["id"]

    assert client.patch(f"/api/admin/users/{uid}", json={"role": "merchant"},
                        headers=auth_header(admin)).status_code == 400
    assert client.patch(f"/api/admin/users/{uid}", json={"is_active": False},
                        headers=auth_header(admin)).status_code == 400


def test_a_second_admin_can_be_demoted_and_disabled(client):
    """With more than one admin, removing one is allowed - the guards only bite
    on self-removal and on the last admin, so a spare admin is fully editable."""
    admin = register(client, "admin@example.com")
    other = register(client, "other@example.com", role="admin", admin=admin)
    other_uid = _me(client, other)["id"]

    assert client.patch(f"/api/admin/users/{other_uid}", json={"is_active": False},
                        headers=auth_header(admin)).status_code == 200
    assert client.patch(f"/api/admin/users/{other_uid}", json={"role": "ceo", "is_active": True},
                        headers=auth_header(admin)).status_code == 200

    # an active admin always remains
    rows = client.get("/api/admin/users", headers=auth_header(admin)).json()
    assert any(u["role"] == "admin" and u["is_active"] for u in rows)
