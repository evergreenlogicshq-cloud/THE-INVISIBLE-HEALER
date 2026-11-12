
"""
Phase 01 - Configuration Unit Tests

Acceptance requirements:
    - PostgreSQL URL validation.
    - Required configuration enforcement.
    - Optional AI keys.
    - Production debug restrictions.
    - Configuration profile handling.
"""

import pytest
from pydantic import ValidationError
from app.core.config import Settings


VALID_DATABASE_URL = (
    "postgresql+psycopg://"
    "user:password@localhost:5432/test_db"
)


def build_settings(**overrides):
    """
    Construct settings without reading .env.
    Explicit inputs make test cases deterministic.
    """

    values = {
        "DATABASE_URL": VALID_DATABASE_URL,
        "APP_ENV": "testing",
        "DEBUG": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_configuration():
    """
    Valid settings should load.
    """

    settings = build_settings()
    assert settings.APP_NAME == ("The Invisible Healer")
    assert settings.APP_ENV == "testing"


def test_missing_database_url(monkeypatch):
    """
    Missing required database URL must fail.

    Remove inherited variables first so the
    result is not influenced by the machine.
    """

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DATABASE_URL=None)


def test_invalid_database_scheme():
    """
    SQLite URLs must be rejected.
    """

    with pytest.raises(ValidationError):
        build_settings(
            DATABASE_URL="sqlite:///test.db")


def test_missing_database_name():
    """
    PostgreSQL URLs need a database name.
    """

    with pytest.raises(ValidationError):
        build_settings(DATABASE_URL=("postgresql://localhost:5432/"))


def test_optional_ai_keys():
    """
    Optional model credentials must not
    be required during Phase 01.
    """

    settings = build_settings(OPENAI_API_KEY=None, ANTHROPIC_API_KEY=None)
    assert settings.OPENAI_API_KEY is None
    assert settings.ANTHROPIC_API_KEY is None


def test_production_debug_disabled():
    """
    Production must reject DEBUG=True.
    """

    with pytest.raises(ValidationError):
        build_settings(APP_ENV="production", DEBUG=True)


def test_production_environment():
    """
    Production profile should be recognized.
    """
    settings = build_settings(APP_ENV="production")
    assert settings.is_production is True


def test_api_prefix_validation():
    """
    API prefixes must begin with a slash.
    """

    with pytest.raises(ValidationError):
        build_settings(API_V1_PREFIX="api/v1")
