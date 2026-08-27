"""No phone may reach the API, whatever it does to the frontend JS.

The client gate can be bypassed; this cannot. Tablets and desktops are let
through, and health/uptime probes stay open so monitoring never trips on it.
"""

import pytest

from app.mobile_guard import is_phone

_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
_ANDROID_PHONE = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
)
_IPAD = (
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/604.1"
)
_ANDROID_TABLET = (
    "Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


@pytest.mark.parametrize("ua", [_IPHONE, _ANDROID_PHONE])
def test_phone_user_agents_are_detected(ua):
    assert is_phone(ua) is True


@pytest.mark.parametrize("ua", [_IPAD, _ANDROID_TABLET, _DESKTOP, "", None])
def test_tablets_and_desktops_are_not_phones(ua):
    assert is_phone(ua) is False


def test_a_phone_is_refused_before_it_reaches_auth(client):
    # login is public; the phone is turned away before the credentials matter
    r = client.post(
        "/api/auth/login",
        json={"email": "someone@example.com", "password": "whatever"},
        headers={"User-Agent": _IPHONE},
    )
    assert r.status_code == 403
    assert "phone" in r.json()["detail"].lower()


def test_a_desktop_reaches_the_endpoint(client):
    # same call from a desktop is not phone-blocked - it fails auth instead
    r = client.post(
        "/api/auth/login",
        json={"email": "someone@example.com", "password": "whatever"},
        headers={"User-Agent": _DESKTOP},
    )
    assert r.status_code != 403


def test_health_stays_open_to_phones(client):
    # uptime probes must answer regardless of the user-agent they carry
    for path in ("/ping", "/api/health"):
        r = client.get(path, headers={"User-Agent": _IPHONE})
        assert r.status_code == 200, path
