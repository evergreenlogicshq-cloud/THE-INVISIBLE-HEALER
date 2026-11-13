"""
The Invisible Healer
PostgreSQL Integration Tests

Phase 03

Purpose:
    Verify real PostgreSQL connectivity
    using SQLAlchemy and Psycopg 3.

Important:
    - These tests do not create tables.
    - These tests do not write patient data.
    - These tests do not modify schemas.
    - Real DB tests are opt-in.
    - TEST_DATABASE_URL should refer to
      an isolated testing database/project.

Enable with:
    RUN_DB_INTEGRATION_TESTS=true

Requires:
    TEST_DATABASE_URL
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.db.session import check_database_connection, create_session_factory


def get_integration_database_url():
    """
    Obtain the dedicated integration
    testing database URL.

    Never log the returned value.
    """

    enabled = (
        os.getenv(
            "RUN_DB_INTEGRATION_TESTS",
            "false",
        ).lower()
        == "true"
    )

    if not enabled:
        pytest.skip("Real database integration tests disabled.")

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.fail("TEST_DATABASE_URL is required for database integration tests.")

    return database_url


# ============================================
# POSTGRESQL CONNECTION TEST
# ============================================


def test_postgresql_connection():
    """
    Verify real PostgreSQL connectivity.
    """

    database_url = get_integration_database_url()
    parsed = make_url(database_url)
    assert parsed.get_backend_name() == "postgresql"

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            **({"prepare_threshold": None} if parsed.port == 6543 else {}),
        },
    )

    try:
        assert check_database_connection(engine) is True

    finally:
        engine.dispose()


# ============================================
# POSTGRESQL SESSION TEST
# ============================================


def test_postgresql_session_factory():
    """
    Verify that a SQLAlchemy Session
    can execute a read-only PostgreSQL query.
    """

    database_url = get_integration_database_url()
    parsed = make_url(database_url)
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            **({"prepare_threshold": None} if parsed.port == 6543 else {}),
        },
    )

    try:
        factory = create_session_factory(engine)
        from sqlalchemy import text

        with factory() as session:
            result = session.execute(text("SELECT 1")).scalar_one()

        assert result == 1

    finally:
        engine.dispose()
