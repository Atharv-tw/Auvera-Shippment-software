"""Who is allowed to hold an account at all, by email domain.

Roles answer "what may this person do"; this answers "may this person be here".
The gate runs on registration *and* on login, because turning it on has to shut
out accounts that already exist, not merely stop new ones being made.

Empty ``ALLOWED_EMAIL_DOMAINS`` means no restriction, which is what local
development and the test suite run with.
"""

from __future__ import annotations

from app.config import get_settings


def allowed_domains() -> set[str]:
    return {d.strip().lower() for d in get_settings().allowed_email_domains if d.strip()}


def is_allowed_login_email(email: str) -> bool:
    domains = allowed_domains()
    if not domains:
        return True

    email = (email or "").strip().lower()

    # The configured admin is always allowed. Without this, a typo in
    # ALLOWED_EMAIL_DOMAINS locks the only administrator out of the one account
    # that could fix it.
    if email and email == get_settings().admin_email.strip().lower():
        return True

    # Exact match on the domain, never a suffix test: "evil-auverastudio.com"
    # and "mail.auverastudio.com" are different companies as far as this is
    # concerned, and must be listed to get in.
    return email.rpartition("@")[2] in domains


def refusal_message() -> str:
    domains = sorted(allowed_domains())
    if len(domains) == 1:
        return f"Only {domains[0]} accounts may sign in."
    return "Only company accounts may sign in: " + ", ".join(domains)
