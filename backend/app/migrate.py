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
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.config import get_settings

# app/migrate.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"

VERSION_TABLE = "alembic_version"


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    if database_url is not None:
        # env.py normally reads app.config; tests point it elsewhere
        cfg.attributes["database_url"] = database_url
    return cfg


def _base_revision(cfg: Config) -> str:
    """The first migration in the history, found rather than hard-coded so
    renaming or regenerating the baseline cannot silently break adoption."""
    script = ScriptDirectory.from_config(cfg)
    bases = script.get_bases()
    if len(bases) != 1:
        raise RuntimeError(f"expected exactly one base revision, found {bases}")
    return bases[0]


def _baseline_tables(cfg: Config) -> set[str]:
    """The tables the baseline migration creates.

    Derived by running the baseline into a throwaway database rather than
    hard-coded, so it cannot rot as migrations are added.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        url = f"sqlite:///{Path(tmp) / 'baseline.db'}"
        command.upgrade(alembic_config(url), _base_revision(cfg))
        engine = create_engine(url)
        try:
            return set(inspect(engine).get_table_names()) - {VERSION_TABLE}
        finally:
            engine.dispose()


def _adopt_pre_alembic_database(cfg: Config, database_url: str | None) -> None:
    """Bring a database that predates Alembic under version control.

    This project ran on ``create_all`` before migrations existed, so deployed
    databases have every table but no ``alembic_version``. Alembic reads that as
    an empty database and tries to run the baseline, which fails on the first
    ``CREATE TABLE`` with "relation already exists" - a boot crash, not a
    warning.

    The fix is to *stamp* the baseline rather than run it: the tables are
    already there, so the baseline has effectively been applied. Only the
    migrations after it need to run.

    Deliberately narrow. It stamps only when the tables already present cover
    everything the baseline creates. Anything else is a schema this code does
    not recognise, and guessing at that is how you get a half-migrated database.
    """
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    try:
        existing = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    if VERSION_TABLE in existing:
        return  # already under Alembic; nothing to adopt
    if not existing:
        return  # genuinely empty; the migrations will build it

    # Compared against what the BASELINE creates, not against today's models.
    # A pre-Alembic database has the tables create_all made at the time it was
    # last deployed - it cannot have tables that only a later migration adds, so
    # measuring it against the current models would condemn every legacy
    # database the moment any migration introduces a table.
    expected = _baseline_tables(cfg)
    if not expected:
        raise RuntimeError("the baseline migration created no tables; cannot identify this schema")
    missing = expected - existing
    if missing:
        raise RuntimeError(
            "This database has tables but no alembic_version, and does not match "
            "the baseline schema. Missing: " + ", ".join(sorted(missing)) + ".\n"
            "Refusing to stamp a schema I cannot identify. Either migrate it by "
            "hand, or - if the data is expendable - redeploy once with "
            "REBUILD_SCHEMA=true to drop and rebuild from the migrations."
        )

    base = _base_revision(cfg)
    print(
        f"Database predates Alembic ({len(existing)} tables, no {VERSION_TABLE}). "
        f"Stamping baseline {base} and applying everything after it."
    )
    command.stamp(cfg, base)


def upgrade_head(database_url: str | None = None) -> None:
    cfg = alembic_config(database_url)
    _adopt_pre_alembic_database(cfg, database_url)
    command.upgrade(cfg, "head")


def stamp_head(database_url: str | None = None) -> None:
    command.stamp(alembic_config(database_url), "head")
