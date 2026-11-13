"""
The Invisible Healer
Shared Automated Test Fixtures

Phases:
    01 - Application testing
    02 - Isolated configuration
    03 - Isolated database injection

Responsibilities:
    - Testing configuration
    - In-memory database engine
    - Isolated SQLAlchemy session factory
    - FastAPI application factory
    - HTTP TestClient

No live Supabase connection is required
for ordinary API or unit tests.
"""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.main import create_app

TEST_DATABASE_URL = (
    "postgresql+psycopg://test_user:test_password@localhost:5432/test_db"
)


# ============================================
# TEST SETTINGS
# ============================================


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """
    Provide isolated application settings.
    This configuration does not connect
    to the PostgreSQL URL.
    """

    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DEBUG", "false")

    return Settings(
        _env_file=None,
        APP_NAME="The Invisible Healer",
        APP_VERSION="0.1.0",
        APP_ENV="testing",
        DEBUG=False,
        DATABASE_URL=TEST_DATABASE_URL,
        STORAGE_ENABLED=False,
        ADMIN_SESSIONS_ENABLED=False,
        OPENAI_API_KEY=None,
        ANTHROPIC_API_KEY=None,
        DB_ECHO=False,
    )


# ============================================
# ISOLATED TEST DATABASE ENGINE
# ============================================


@pytest.fixture
def test_engine() -> Generator[Engine, None, None]:
    """
    Create an in-memory SQLite engine.
    This engine is only used in tests.
    StaticPool allows multiple test-client
    threads to reuse the same in-memory
    database connection.
    Production still uses PostgreSQL.
    """

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    try:
        yield engine

    finally:
        engine.dispose()


# ============================================
# TEST APPLICATION
# ============================================


@pytest.fixture
def app(test_settings: Settings, test_engine: Engine) -> FastAPI:
    """
    Create an application with an injected
    test database engine.
    """

    return create_app(settings=test_settings, db_engine=test_engine)


# ============================================
# TEST HTTP CLIENT
# ============================================


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """
    Provide an HTTP client with lifespan support.
    """

    with TestClient(app) as test_client:
        yield test_client
