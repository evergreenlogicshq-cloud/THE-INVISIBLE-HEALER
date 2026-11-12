
"""
The Invisible Healer
Shared Test Fixtures

Phase 01

Responsibilities:
    - Isolated application settings
    - FastAPI test application factory
    - HTTP TestClient
    - No live database dependency
"""

import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from fastapi import FastAPI


TEST_DATABASE_URL = (
    "postgresql+psycopg://"
    "test_user:test_password@localhost:5432/test_db"
)


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch,) -> Settings:
    """Create isolated settings for API tests."""

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
        OPENAI_API_KEY=None,
        ANTHROPIC_API_KEY=None,
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    """Create an isolated FastAPI application."""

    from app.main import create_app
    return create_app(settings=test_settings)


@pytest.fixture
def client(app: FastAPI):
    """Provide a test client with lifespan support."""

    with TestClient(app) as test_client:
        yield test_client
