"""Alembic environment.

The database URL comes from ``app.config`` (i.e. the ``DATABASE_URL`` env var),
never from ``alembic.ini`` - one source of truth, and no credentials in the repo.
The engine is built directly rather than through ``engine_from_config`` so that a
password containing ``%`` cannot trip configparser's interpolation.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

# every model must be imported before ``Base.metadata`` is read, or autogenerate
# will cheerfully decide the missing tables should be dropped
import app.models  # noqa: F401
from app.config import get_settings
from app.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    # An explicit override wins, so callers (tests, rebuild_schema) can target a
    # database without depending on get_settings() being re-read - it is cached.
    override = config.attributes.get("database_url")
    if override:
        return str(override)
    return get_settings().database_url


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    url = _url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        # SQLite cannot ALTER most things; batch mode recreates the table instead.
        # Without this, dev migrations fail while Postgres ones pass.
        render_as_batch=_is_sqlite(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _url()
    connect_args = {"check_same_thread": False} if _is_sqlite(url) else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=_is_sqlite(url),
        )
        with context.begin_transaction():
            context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
