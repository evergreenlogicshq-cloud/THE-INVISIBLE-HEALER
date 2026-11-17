"""
The Invisible Healer
Phases 04-06 - Alembic Migration Tests

Purpose:
    Verify migration history and database schema
    without connecting to live Supabase.

Tests:
    - Alembic configuration.
    - Phase 04 baseline revision.
    - Phase 06 authentication revision.
    - Single migration head.
    - ORM metadata registration.
    - Initial baseline upgrade.
    - Phase 06 upgrade.
    - Authentication table structure.
    - Database constraints and indexes.
    - Downgrade to baseline.
    - Full downgrade to base.

All database writes use temporary SQLite.

PostgreSQL-specific schema drift is verified
separately against PostgreSQL using Alembic.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

import app.models  # noqa: F401
from alembic import command
from app.db.base import Base

# ============================================
# PROJECT PATH
# ============================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

AUTH_TABLES = {
    "admin_users",
    "admin_sessions",
    "admin_login_attempts",
}


# ============================================
# ALEMBIC CONFIGURATION
# ============================================


@pytest.fixture
def migration_config() -> Config:
    """
    Load the actual project Alembic configuration.
    """

    config_file = PROJECT_ROOT / "alembic.ini"

    assert config_file.is_file()

    return Config(str(config_file))


# ============================================
# ISOLATED MIGRATION DATABASE
# ============================================


@pytest.fixture
def isolated_migration_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    """
    Redirect Alembic to a temporary SQLite DB.

    Never connects to Supabase or production data.
    """

    database_path = tmp_path / "migration_test.sqlite3"

    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"

    settings = SimpleNamespace(
        DATABASE_URL=database_url,
        DB_CONNECT_TIMEOUT=5,
    )

    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: settings,
    )

    return database_url


# ============================================
# TEST 01 - CONFIGURATION
# ============================================


def test_alembic_configuration(
    migration_config: Config,
) -> None:
    script_location = migration_config.get_main_option("script_location")

    assert script_location is not None
    assert Path(script_location).is_dir()


# ============================================
# TEST 02 - PHASE 04 BASELINE
# ============================================


def test_initial_revision_exists(
    migration_config: Config,
) -> None:
    script = ScriptDirectory.from_config(migration_config)

    revision = script.get_revision("0001")

    assert revision is not None
    assert revision.down_revision is None


# ============================================
# TEST 03 - PHASE 06 REVISION
# ============================================


def test_admin_auth_revision_exists(
    migration_config: Config,
) -> None:
    script = ScriptDirectory.from_config(migration_config)

    revision = script.get_revision("0002")

    assert revision is not None
    assert revision.down_revision == "0001"


# ============================================
# TEST 04 - SINGLE HEAD
# ============================================


def test_migration_history_has_single_head(
    migration_config: Config,
) -> None:
    script = ScriptDirectory.from_config(migration_config)

    assert script.get_heads() == ["0002"]


# ============================================
# TEST 05 - ORM METADATA
# ============================================


def test_metadata_contains_auth_tables() -> None:
    """
    Phase 06 introduces three authentication
    tables without introducing clinical tables.
    """

    assert Base.metadata is not None

    assert set(Base.metadata.tables) == AUTH_TABLES


# ============================================
# TEST 06 - INITIAL BASELINE UPGRADE
# ============================================


def test_initial_upgrade(
    migration_config: Config,
    isolated_migration_database: str,
) -> None:
    """
    Upgrade specifically to 0001.

    The Phase 04 baseline must remain empty
    except for Alembic's revision table.
    """

    command.upgrade(
        migration_config,
        "0001",
    )

    engine = create_engine(isolated_migration_database)

    try:
        inspector = inspect(engine)

        table_names = set(inspector.get_table_names())

        assert table_names == {"alembic_version"}

        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert version == "0001"

    finally:
        engine.dispose()


# ============================================
# TEST 07 - PHASE 06 UPGRADE
# ============================================


def test_phase06_upgrade(
    migration_config: Config,
    isolated_migration_database: str,
) -> None:
    """
    Upgrade through all migrations to 0002.
    """

    command.upgrade(
        migration_config,
        "head",
    )

    engine = create_engine(isolated_migration_database)

    try:
        inspector = inspect(engine)

        table_names = set(inspector.get_table_names())

        expected_tables = AUTH_TABLES | {"alembic_version"}

        assert table_names == expected_tables

        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert version == "0002"

    finally:
        engine.dispose()


# ============================================
# TEST 08 - AUTHENTICATION TABLE STRUCTURE
# ============================================


def test_authentication_table_columns(
    migration_config: Config,
    isolated_migration_database: str,
) -> None:
    """
    Ensure required authentication columns exist.
    """

    command.upgrade(
        migration_config,
        "head",
    )

    engine = create_engine(isolated_migration_database)

    try:
        inspector = inspect(engine)

        user_columns = {
            column["name"] for column in inspector.get_columns("admin_users")
        }

        session_columns = {
            column["name"] for column in inspector.get_columns("admin_sessions")
        }

        attempt_columns = {
            column["name"] for column in inspector.get_columns("admin_login_attempts")
        }

        assert user_columns == {
            "id",
            "email",
            "password_hash",
            "full_name",
            "is_active",
            "created_at",
            "updated_at",
            "last_login_at",
        }

        assert session_columns == {
            "id",
            "user_id",
            "token_hash",
            "csrf_secret",
            "created_at",
            "last_seen_at",
            "expires_at",
            "revoked_at",
        }

        assert attempt_columns == {
            "id",
            "client_key",
            "attempted_at",
        }

    finally:
        engine.dispose()


# ============================================
# TEST 09 - SCHEMA STRUCTURE
# ============================================


def test_no_schema_drift(
    migration_config: Config,
    isolated_migration_database: str,
) -> None:
    """
    Check the structural contract on SQLite.

    SQLite cannot reproduce PostgreSQL-native
    UUID type and server-default comparisons
    exactly, so compare table and column names.

    Strict database-specific drift checking must
    additionally run against PostgreSQL.
    """

    command.upgrade(
        migration_config,
        "head",
    )

    engine = create_engine(isolated_migration_database)

    try:
        inspector = inspect(engine)

        assert (set(inspector.get_table_names()) - {"alembic_version"}) == set(
            Base.metadata.tables
        )

        for table_name, model_table in Base.metadata.tables.items():
            actual_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }

            expected_columns = {column.name for column in model_table.columns}

            assert actual_columns == expected_columns

    finally:
        engine.dispose()


# ============================================
# TEST 10 - FOREIGN KEY AND INDEXES
# ============================================


def test_authentication_constraints(
    migration_config: Config,
    isolated_migration_database: str,
) -> None:
    """
    Confirm session ownership and important
    authentication lookup indexes.
    """

    command.upgrade(
        migration_config,
        "head",
    )

    engine = create_engine(isolated_migration_database)

    try:
        inspector = inspect(engine)

        foreign_keys = inspector.get_foreign_keys("admin_sessions")

        assert any(
            fk["referred_table"] == "admin_users"
            and fk["constrained_columns"] == ["user_id"]
            for fk in foreign_keys
        )

        user_indexes = {index["name"] for index in inspector.get_indexes("admin_users")}

        session_indexes = {
            index["name"] for index in inspector.get_indexes("admin_sessions")
        }

        attempt_indexes = {
            index["name"] for index in inspector.get_indexes("admin_login_attempts")
        }

        assert "ix_admin_users_email" in user_indexes

        assert "ix_admin_sessions_user_id" in session_indexes

        assert "ix_admin_sessions_expires_at" in session_indexes

        assert "ix_admin_login_attempts_key_time" in attempt_indexes

    finally:
        engine.dispose()


# ============================================
# TEST 11 - DOWNGRADE PHASE 06
# ============================================


def test_phase06_downgrade_to_baseline(
    migration_config: Config,
    isolated_migration_database: str,
) -> None:
    """
    Downgrade 0002 -> 0001.

    Authentication tables must be removed,
    while the baseline revision remains.
    """

    command.upgrade(
        migration_config,
        "head",
    )

    command.downgrade(
        migration_config,
        "0001",
    )

    engine = create_engine(isolated_migration_database)

    try:
        inspector = inspect(engine)

        assert set(inspector.get_table_names()) == {"alembic_version"}

        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()

        assert version == "0001"

    finally:
        engine.dispose()


# ============================================
# TEST 12 - FULL DOWNGRADE
# ============================================


def test_initial_downgrade(
    migration_config: Config,
    isolated_migration_database: str,
) -> None:
    """
    Verify all migrations can downgrade
    to an empty baseline in isolated SQLite.
    """

    command.upgrade(
        migration_config,
        "head",
    )

    command.downgrade(
        migration_config,
        "base",
    )

    engine = create_engine(isolated_migration_database)

    try:
        table_names = set(inspect(engine).get_table_names())

        # Alembic may retain an empty
        # revision-tracking table.
        assert table_names.issubset({"alembic_version"})

        if "alembic_version" in table_names:
            with engine.connect() as connection:
                versions = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).all()

            assert versions == []

    finally:
        engine.dispose()
