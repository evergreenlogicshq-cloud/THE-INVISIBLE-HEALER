"""
The Invisible Healer
Phase 04 - Alembic Migration Tests

Purpose:
    Verify the initial migration infrastructure
    without connecting to live Supabase.

Tests:
    1. Alembic configuration is readable.
    2. Initial revision is registered.
    3. Revision history has one head.
    4. ORM metadata is connected.
    5. Upgrade creates revision tracking.
    6. Schema drift check succeeds.
    7. Downgrade reverses the baseline.

All database writes use a temporary SQLite DB.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from alembic import command
from app.db.base import Base

# ============================================
# PROJECT PATH
# ============================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ============================================
# TEST CONFIGURATION
# ============================================


@pytest.fixture
def migration_config() -> Config:
    """
    Load the project's Alembic configuration.

    This fixture does not establish a
    database connection.
    """

    config_file = PROJECT_ROOT / "alembic.ini"
    assert config_file.is_file()
    return Config(str(config_file))


# ============================================
# ISOLATED DATABASE
# ============================================


@pytest.fixture
def isolated_migration_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """
    Redirect Alembic to a temporary SQLite DB.
    The production migration environment reads
    get_settings().
    This test replaces only that settings getter,
    leaving the actual Alembic execution path
    unchanged.
    """

    database_path = tmp_path / "migration_test.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    settings = SimpleNamespace(DATABASE_URL=database_url, DB_CONNECT_TIMEOUT=5)
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)

    return database_url


# ============================================
# TEST 01 - CONFIGURATION
# ============================================


def test_alembic_configuration(migration_config: Config) -> None:
    """
    Alembic must recognize its script directory.
    """

    script_location = migration_config.get_main_option("script_location")
    assert script_location is not None
    assert Path(script_location).is_dir()


# ============================================
# TEST 02 - INITIAL REVISION
# ============================================


def test_initial_revision_exists(migration_config: Config) -> None:
    """
    Confirm the Phase 04 baseline exists.
    """

    script = ScriptDirectory.from_config(migration_config)
    revision = script.get_revision("0001")
    assert revision is not None
    assert revision.down_revision is None


# ============================================
# TEST 03 - SINGLE HEAD
# ============================================


def test_migration_history_has_single_head(migration_config: Config) -> None:
    """
    The initial history must have one head.
    """

    script = ScriptDirectory.from_config(migration_config)
    assert script.get_heads() == ["0001"]


# ============================================
# TEST 04 - SHARED METADATA
# ============================================


def test_metadata_baseline_is_empty() -> None:
    """
    Phase 04 must not introduce domain tables.
    """

    assert Base.metadata is not None
    assert len(Base.metadata.tables) == 0


# ============================================
# TEST 05 - UPGRADE
# ============================================


def test_initial_upgrade(
    migration_config: Config, isolated_migration_database: str
) -> None:
    """
    Apply the baseline to an isolated database.

    Expected:
        - alembic_version exists
        - revision is 0001
        - no clinical application tables
    """

    command.upgrade(migration_config, "head")
    engine = create_engine(isolated_migration_database)

    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert table_names == ["alembic_version"]

        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert version == "0001"

    finally:
        engine.dispose()


# ============================================
# TEST 06 - SCHEMA DRIFT
# ============================================


def test_no_schema_drift(
    migration_config: Config, isolated_migration_database: str
) -> None:
    """
    Verify Alembic sees no pending model
    changes after applying the baseline.
    This uses the actual Alembic check command.
    """

    command.upgrade(migration_config, "head")
    command.check(migration_config)


# ============================================
# TEST 07 - DOWNGRADE
# ============================================


def test_initial_downgrade(
    migration_config: Config, isolated_migration_database: str
) -> None:
    """
    Verify the baseline downgrade works.
    After returning to base, there must be
    no applied revision.
    """

    command.upgrade(migration_config, "head")
    command.downgrade(migration_config, "base")
    engine = create_engine(isolated_migration_database)

    try:
        table_names = inspect(engine).get_table_names()
        # Alembic may retain an empty version table
        # after downgrading to base.
        assert set(table_names).issubset({"alembic_version"})

        if "alembic_version" in table_names:
            with engine.connect() as connection:
                versions = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).all()

            assert versions == []

    finally:
        engine.dispose()
