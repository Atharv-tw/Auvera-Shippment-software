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
    jwt_expire_minutes: int = 60 * 24

    cors_origins: list[str] = ["http://localhost:3000"]

    upload_dir: str = "uploads"
    max_upload_bytes: int = 20 * 1024 * 1024  # 20 MB


@lru_cache
def get_settings() -> Settings:
    return Settings()
