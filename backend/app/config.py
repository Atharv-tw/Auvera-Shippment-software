from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Shipping Z API"
    debug: bool = False

    # sqlite for local dev; postgres in production via DATABASE_URL
    database_url: str = "sqlite:///./shipping_z.db"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    # Short, because a stolen access token can no longer be revoked any other
    # way and the frontend now refreshes transparently.
    jwt_expire_minutes: int = 15
    refresh_expire_days: int = 14
    # Accept pre-session tokens (no `sid` claim) issued before session control
    # shipped. They are all expired within 24h of that deploy; unset then.
    allow_sessionless_tokens: bool = True

    # The /admin database browser signs its own cookie. Sharing jwt_secret
    # means one leak opens both surfaces; empty falls back with a warning.
    admin_session_secret: str = ""

    # Empty = no restriction (local dev and the test suite). In production set
    # ALLOWED_EMAIL_DOMAINS=auverastudio.com
    allowed_email_domains: list[str] = []
    # Read here as well as in seed.py: the domain gate always lets the
    # configured admin in, so a typo cannot lock out the last administrator.
    admin_email: str = "admin@example.com"

    cors_origins: list[str] = ["http://localhost:3000"]

    upload_dir: str = "uploads"
    max_upload_bytes: int = 20 * 1024 * 1024  # 20 MB

    # Failed logins before the account is held shut, and for how long.
    max_failed_logins: int = 5
    lockout_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
