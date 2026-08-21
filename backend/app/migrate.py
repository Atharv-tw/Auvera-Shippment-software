"""Programmatic Alembic entry points.

Used by prestart (on deploy), by rebuild_schema (dev reset) and by the tests.
Driving Alembic through its Python API rather than shelling out keeps this
working regardless of the current working directory or whether the ``alembic``
console script is on PATH inside the container.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

# app/migrate.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    if database_url is not None:
        # env.py normally reads app.config; tests point it elsewhere
        cfg.attributes["database_url"] = database_url
    return cfg


def upgrade_head(database_url: str | None = None) -> None:
    command.upgrade(alembic_config(database_url), "head")


def stamp_head(database_url: str | None = None) -> None:
    command.stamp(alembic_config(database_url), "head")
