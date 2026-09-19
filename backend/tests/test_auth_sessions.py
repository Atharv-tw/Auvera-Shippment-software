"""Sign-in sessions, the company-domain gate, lockout, and merchant creation.

Deliberately free of workbook fixtures, so it runs in a bare clone where the
sample spreadsheets (gitignored) are absent.
"""

from datetime import timedelta

import pytest

from app.config import get_settings
from app.models import User, UserSession, utcnow
from app.services import sessions as session_service

from .conftest import auth_header, register

PASSWORD = "secret123456"


@pytest.fixture(autouse=True)
def _reset_settings():
    """Settings are lru_cached; tests that tweak them must not leak into others."""
    yield
    get_settings.cache_clear()


def _session_of(db, refresh_token):
    """The session row a refresh token names.

    Not ``.first()``: registering already opened a session, so the earliest row
    is never the one a later sign-in created.
    """
    db.expire_all()
    return db.get(UserSession, int(refresh_token.partition(".")[0]))


def _tokens(client, email=PASSWORD and "admin@example.com", password=PASSWORD):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


# --- the company-domain gate --------------------------------------------------

def test_no_allowlist_means_no_restriction(client):
    """The default the test suite and local development run with."""
    r = client.post("/api/auth/register", json={
        "email": "anyone@gmail.com", "password": PASSWORD, "name": "Any"})
    assert r.status_code == 201, r.text


def test_off_domain_cannot_register_or_sign_in(client, monkeypatch):
    admin = register(client, "admin@example.com")
    assert admin  # first user, so there is something to lock out of

    settings = get_settings()
    monkeypatch.setattr(settings, "allowed_email_domains", ["auverastudio.com"])
    monkeypatch.setattr(settings, "admin_email", "vasanti@auverastudio.com")

    r = client.post("/api/auth/register", json={
        "email": "outsider@gmail.com", "password": PASSWORD, "name": "Out"})
    assert r.status_code == 403
    assert "auverastudio.com" in r.json()["detail"]

    # an account that already exists is shut out at sign-in too - the whole
    # point of checking on login and not only on registration
    r = client.post("/api/auth/login", json={
        "email": "admin@example.com", "password": PASSWORD})
    assert r.status_code == 403


def test_on_domain_is_admitted(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "allowed_email_domains", ["auverastudio.com"])
    r = client.post("/api/auth/register", json={
        "email": "vasanti@auverastudio.com", "password": PASSWORD, "name": "Vasanti"})
    assert r.status_code == 201, r.text


def test_the_configured_admin_is_never_locked_out(client, monkeypatch):
    """A typo in the domain list must not cost you the only administrator."""
    register(client, "admin@example.com")
    settings = get_settings()
    monkeypatch.setattr(settings, "allowed_email_domains", ["auverastudio.com"])
    monkeypatch.setattr(settings, "admin_email", "admin@example.com")

    r = client.post("/api/auth/login", json={
        "email": "admin@example.com", "password": PASSWORD})
    assert r.status_code == 200, r.text


def test_domain_match_is_exact_not_a_suffix(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "allowed_email_domains", ["auverastudio.com"])
    for email in ("x@evil-auverastudio.com", "x@mail.auverastudio.com"):
        r = client.post("/api/auth/register", json={
            "email": email, "password": PASSWORD, "name": "X"})
        assert r.status_code == 403, f"{email} should not pass: {r.text}"


# --- passwords and lockout ----------------------------------------------------

def test_password_must_be_twelve_characters(client):
    r = client.post("/api/auth/register", json={
        "email": "short@example.com", "password": "elevenchars", "name": "S"})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={
        "email": "long@example.com", "password": "twelvechars!", "name": "L"})
    assert r.status_code == 201, r.text


def test_an_obvious_password_is_refused(client):
    r = client.post("/api/auth/register", json={
        "email": "weak@example.com", "password": "passwordpassword", "name": "W"})
    assert r.status_code == 422


def test_repeated_failures_lock_the_account(client):
    register(client, "admin@example.com")
    settings = get_settings()

    for _ in range(settings.max_failed_logins):
        r = client.post("/api/auth/login", json={
            "email": "admin@example.com", "password": "wrongwrongwrong"})
        assert r.status_code == 401

    # the right password now too - the lock is on the account, not the guess
    r = client.post("/api/auth/login", json={
        "email": "admin@example.com", "password": PASSWORD})
    assert r.status_code == 429


def test_a_good_sign_in_clears_the_counter(client, db):
    register(client, "admin@example.com")
    client.post("/api/auth/login", json={
        "email": "admin@example.com", "password": "wrongwrongwrong"})
    client.post("/api/auth/login", json={
        "email": "admin@example.com", "password": PASSWORD})
    user = db.query(User).filter(User.email == "admin@example.com").first()
    assert user.failed_login_count == 0
    assert user.locked_until is None


# --- sessions -----------------------------------------------------------------

def test_login_issues_a_refresh_token_and_records_the_event(client):
    register(client, "admin@example.com")
    data = _tokens(client)
    assert data["refresh_token"]
    assert data["expires_in"] > 0

    feed = client.get("/api/auth/activity", headers=auth_header(data["access_token"]))
    assert feed.status_code == 200, feed.text
    assert [e["event"] for e in feed.json()].count("login") >= 1


def test_logout_ends_the_session_and_the_token_stops_working(client):
    register(client, "admin@example.com")
    data = _tokens(client)
    headers = auth_header(data["access_token"])

    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", json={}, headers=headers).status_code == 204
    # the same token, moments later, is no longer anybody
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_logout_works_after_the_access_token_has_expired(client, db):
    """Sign-out takes the refresh token in the body for exactly this case."""
    register(client, "admin@example.com")
    data = _tokens(client)

    r = client.post("/api/auth/logout", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 204
    session = _session_of(db, data["refresh_token"])
    assert session.revoked_at is not None
    assert session.revoked_reason == "logout"


def test_logout_is_idempotent(client):
    register(client, "admin@example.com")
    data = _tokens(client)
    body = {"refresh_token": data["refresh_token"]}
    assert client.post("/api/auth/logout", json=body).status_code == 204
    assert client.post("/api/auth/logout", json=body).status_code == 204
    assert client.post("/api/auth/logout", json={"refresh_token": "nonsense"}).status_code == 204


def test_refresh_mints_a_new_access_token(client):
    register(client, "admin@example.com")
    data = _tokens(client)
    r = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 200, r.text
    assert client.get("/api/auth/me", headers=auth_header(r.json()["access_token"])).status_code == 200


def test_a_revoked_session_cannot_refresh(client):
    register(client, "admin@example.com")
    data = _tokens(client)
    client.post("/api/auth/logout", json={"refresh_token": data["refresh_token"]})
    r = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 401


def test_a_tampered_refresh_token_is_refused(client):
    register(client, "admin@example.com")
    data = _tokens(client)
    session_id, _, _secret = data["refresh_token"].partition(".")
    r = client.post("/api/auth/refresh", json={"refresh_token": f"{session_id}.forged"})
    assert r.status_code == 401


def test_an_expired_session_is_refused_after_a_round_trip(client, db):
    """The timezone trap: utcnow() is aware, the column is naive.

    Committing and then expiring the object forces the value to be re-read from
    the database, which is where a naive/aware comparison blows up. An assertion
    on the in-memory object would pass and prove nothing.
    """
    register(client, "admin@example.com")
    data = _tokens(client)

    session = _session_of(db, data["refresh_token"])
    session.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    db.expire_all()

    assert client.get("/api/auth/me", headers=auth_header(data["access_token"])).status_code == 401
    assert client.post("/api/auth/refresh",
                       json={"refresh_token": data["refresh_token"]}).status_code == 401


def test_logout_everywhere_kills_every_session_but_logs_one_line(client, db):
    register(client, "admin@example.com")
    first = _tokens(client)
    second = _tokens(client)
    third = _tokens(client)

    r = client.post("/api/auth/logout-all", headers=auth_header(third["access_token"]))
    assert r.status_code == 200, r.text
    # four, not three: registering opened a session before these three sign-ins
    assert r.json()["revoked"] == 4

    for data in (first, second, third):
        assert client.get("/api/auth/me",
                          headers=auth_header(data["access_token"])).status_code == 401

    # one click, one line of history - the reason the sessions and the record
    # are two tables rather than one
    fresh = _tokens(client)
    events = client.get("/api/auth/activity", headers=auth_header(fresh["access_token"])).json()
    assert [e["event"] for e in events].count("logout_all") == 1


def test_disabling_an_account_ends_its_sessions(client, db):
    admin = register(client, "admin@example.com")
    victim = register(client, "victim@example.com", role="merchant", admin=admin)
    assert client.get("/api/auth/me", headers=auth_header(victim)).status_code == 200

    uid = db.query(User).filter(User.email == "victim@example.com").first().id
    r = client.patch(f"/api/admin/users/{uid}", json={"is_active": False},
                     headers=auth_header(admin))
    assert r.status_code == 200, r.text
    assert client.get("/api/auth/me", headers=auth_header(victim)).status_code == 401


def test_assigning_a_role_does_not_sign_the_person_out(client):
    """Approval off the waitlist must not bounce them to the login screen."""
    admin = register(client, "admin@example.com")
    newcomer = register(client, "new@example.com", role="merchant", admin=admin)
    me = client.get("/api/auth/me", headers=auth_header(newcomer))
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "merchant"


# --- who may read the feed ----------------------------------------------------

def test_activity_is_ceo_and_admin_only(client):
    admin = register(client, "admin@example.com")
    ceo = register(client, "ceo@example.com", role="ceo", admin=admin)
    shipping = register(client, "ship@example.com", role="shipping_manager", admin=admin)
    merchant = register(client, "merchant@example.com", role="merchant", admin=admin)

    assert client.get("/api/auth/activity", headers=auth_header(admin)).status_code == 200
    assert client.get("/api/auth/activity", headers=auth_header(ceo)).status_code == 200
    assert client.get("/api/auth/activity", headers=auth_header(shipping)).status_code == 403
    assert client.get("/api/auth/activity", headers=auth_header(merchant)).status_code == 403


def test_activity_pages_and_counts(client):
    admin = register(client, "admin@example.com")
    for _ in range(3):
        _tokens(client)

    r = client.get("/api/auth/activity?limit=2", headers=auth_header(admin))
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert int(r.headers["X-Total-Count"]) >= 4  # 1 register + 3 logins


# --- merchant manual entry ----------------------------------------------------

def _new_row(client, token, po="D900", style="S1", colour="Red"):
    return client.post(
        "/api/tracker",
        json={"fields": {"buyer_po": po, "style_no": style, "colour": colour}},
        headers=auth_header(token),
    )


def test_merchant_creates_a_row_but_cannot_rekey_it_afterwards(client):
    """The whole design in one test: identity is settable once, at creation."""
    admin = register(client, "admin@example.com")
    merchant = register(client, "merchant@example.com", role="merchant", admin=admin)

    r = _new_row(client, merchant)
    assert r.status_code == 201, r.text
    row_id = r.json()["id"]

    # ...and never again
    r = client.patch(f"/api/tracker/{row_id}", json={"fields": {"buyer_po": "D901"}},
                     headers=auth_header(merchant))
    assert r.status_code == 403


def test_shipping_manager_edits_rows_but_does_not_originate_them(client):
    admin = register(client, "admin@example.com")
    shipping = register(client, "ship@example.com", role="shipping_manager", admin=admin)
    assert _new_row(client, shipping).status_code == 403


def test_ceo_and_admin_still_create(client):
    admin = register(client, "admin@example.com")
    ceo = register(client, "ceo@example.com", role="ceo", admin=admin)
    assert _new_row(client, admin, po="D901").status_code == 201
    assert _new_row(client, ceo, po="D902").status_code == 201


def test_a_merchant_cannot_smuggle_a_price_in_at_creation(client):
    """Creation widens identity only - prices stay CEO and admin."""
    admin = register(client, "admin@example.com")
    merchant = register(client, "merchant@example.com", role="merchant", admin=admin)
    r = client.post(
        "/api/tracker",
        json={"fields": {"buyer_po": "D903", "style_no": "S1", "colour": "Red",
                         "buyer_net_price": "9.99"}},
        headers=auth_header(merchant),
    )
    assert r.status_code == 403


def test_create_mode_columns_advertise_what_the_create_gate_accepts(client):
    """Advertising one set and enforcing another is the bug this prevents."""
    admin = register(client, "admin@example.com")
    merchant = register(client, "merchant@example.com", role="merchant", admin=admin)
    h = auth_header(merchant)

    edit = {c["key"] for c in client.get("/api/tracker/columns", headers=h).json() if c["editable"]}
    create = {c["key"] for c in
              client.get("/api/tracker/columns?mode=create", headers=h).json() if c["editable"]}

    assert {"buyer_po", "style_no", "colour"} <= create
    assert not ({"buyer_po", "style_no", "colour"} & edit)
    assert edit < create


def test_duplicate_identity_is_still_refused(client):
    admin = register(client, "admin@example.com")
    merchant = register(client, "merchant@example.com", role="merchant", admin=admin)
    assert _new_row(client, merchant, po="D904").status_code == 201
    assert _new_row(client, merchant, po="D904").status_code == 409
