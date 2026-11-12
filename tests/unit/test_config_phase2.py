
"""
The Invisible Healer
Phase 02 Configuration Security Tests

Tests:
    - Optional credential handling
    - Storage validation
    - Session secret validation
    - Production security policies
    - Secret masking
    - Secret serialization exclusions
    - Environment isolation
    - Backward compatibility

No network requests or database connections.
"""

import pytest
from pydantic import ValidationError
from app.core.config import Settings, get_settings


TEST_DATABASE_URL = (
    "postgresql+psycopg://"
    "test_user:test_password@localhost:5432/test_db"
)


def build_settings(**overrides) -> Settings:
    """
    Construct isolated application settings.
    The local .env file is not loaded.
    """

    values = {
        "DATABASE_URL": TEST_DATABASE_URL,
        "APP_ENV": "testing",
        "DEBUG": False,
        "STORAGE_ENABLED": False,
        "ADMIN_SESSIONS_ENABLED": False,
        "OPENAI_API_KEY": None,
        "ANTHROPIC_API_KEY": None,
        "SUPABASE_URL": None,
        "SUPABASE_SERVICE_ROLE_KEY": None,
        "SESSION_SECRET": None,
    }

    values.update(overrides)
    return Settings(_env_file=None, **values)


# -----------------------------------------
# Core configuration
# -----------------------------------------

def test_phase2_settings_load():
    settings = build_settings()
    assert settings.APP_NAME == "The Invisible Healer"
    assert settings.APP_ENV == "testing"
    assert settings.is_testing is True


def test_database_url_still_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DATABASE_URL=None)


def test_database_url_still_validated():
    with pytest.raises(ValidationError):
        build_settings(DATABASE_URL="sqlite:///local.db")


# -----------------------------------------
# Optional credentials
# -----------------------------------------

def test_optional_credentials_are_not_required():
    settings = build_settings()

    assert settings.OPENAI_API_KEY is None
    assert settings.ANTHROPIC_API_KEY is None
    assert settings.SUPABASE_SERVICE_ROLE_KEY is None
    assert settings.SESSION_SECRET is None


def test_empty_optional_keys_become_none():
    settings = build_settings(
        OPENAI_API_KEY="",
        ANTHROPIC_API_KEY="  ",
        SESSION_SECRET="",
        SUPABASE_SERVICE_ROLE_KEY="",
    )

    assert settings.OPENAI_API_KEY is None
    assert settings.ANTHROPIC_API_KEY is None
    assert settings.SESSION_SECRET is None
    assert settings.SUPABASE_SERVICE_ROLE_KEY is None


# -----------------------------------------
# Supabase Storage
# -----------------------------------------

def test_storage_disabled_without_credentials():
    settings = build_settings(STORAGE_ENABLED=False)

    assert settings.STORAGE_ENABLED is False
    assert settings.storage_configured is False


def test_storage_enabled_requires_credentials():
    with pytest.raises(ValidationError):
        build_settings(
            STORAGE_ENABLED=True,
            SUPABASE_URL=None,
            SUPABASE_SERVICE_ROLE_KEY=None,
        )


def test_storage_rejects_partial_credentials():
    with pytest.raises(ValidationError):
        build_settings(
            STORAGE_ENABLED=True,
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_SERVICE_ROLE_KEY=None,
        )


def test_storage_accepts_complete_configuration():
    settings = build_settings(
        STORAGE_ENABLED=True,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role-key",
    )

    assert settings.storage_configured is True
    assert settings.STORAGE_ENABLED is True


def test_supabase_rejects_http():
    with pytest.raises(ValidationError):
        build_settings(SUPABASE_URL="http://example.supabase.co")


def test_supabase_rejects_embedded_credentials():
    with pytest.raises(ValidationError):
        build_settings(SUPABASE_URL=("https://user:password@example.supabase.co"))


# -----------------------------------------
# Admin session configuration
# -----------------------------------------

def test_admin_sessions_disabled_without_secret():
    settings = build_settings(ADMIN_SESSIONS_ENABLED=False)
    assert settings.admin_session_configured is False


def test_enabled_sessions_require_secret():
    with pytest.raises(ValidationError):
        build_settings(ADMIN_SESSIONS_ENABLED=True, SESSION_SECRET=None)


def test_short_session_secret_rejected():
    with pytest.raises(ValidationError):
        build_settings(ADMIN_SESSIONS_ENABLED=True, SESSION_SECRET="short-secret")


def test_strong_session_secret_accepted():
    settings = build_settings(ADMIN_SESSIONS_ENABLED=True, SESSION_SECRET="A" * 48)
    assert settings.admin_session_configured is True


def test_samesite_none_requires_secure_cookie():
    with pytest.raises(ValidationError):
        build_settings(
            ADMIN_SESSIONS_ENABLED=True,
            SESSION_SECRET="A" * 48,
            SESSION_COOKIE_SAMESITE="none",
            SESSION_COOKIE_SECURE=False,
        )


# -----------------------------------------
# Production security
# -----------------------------------------

def test_production_debug_rejected():
    with pytest.raises(ValidationError):
        build_settings(APP_ENV="production", DEBUG=True)


def test_production_debug_logging_rejected():
    with pytest.raises(ValidationError):
        build_settings(APP_ENV="production", LOG_LEVEL="DEBUG")


def test_production_insecure_session_cookie_rejected():
    with pytest.raises(ValidationError):
        build_settings(
            APP_ENV="production",
            ADMIN_SESSIONS_ENABLED=True,
            SESSION_SECRET="A" * 48,
            SESSION_COOKIE_SECURE=False,
        )


def test_production_http_only_required():
    with pytest.raises(ValidationError):
        build_settings(
            APP_ENV="production",
            ADMIN_SESSIONS_ENABLED=True,
            SESSION_SECRET="A" * 48,
            SESSION_COOKIE_HTTPONLY=False,
        )


def test_valid_production_configuration():
    settings = build_settings(APP_ENV="production", DEBUG=False, LOG_LEVEL="INFO")
    assert settings.is_production is True


# -----------------------------------------
# Secret representation and serialization
# -----------------------------------------

def test_secrets_are_masked():
    test_key = "TEST_SECRET_DO_NOT_EXPOSE_123"

    settings = build_settings(OPENAI_API_KEY=test_key)
    assert settings.OPENAI_API_KEY is not None
    assert settings.OPENAI_API_KEY.get_secret_value() == test_key
    assert test_key not in repr(settings)
    assert test_key not in str(settings)


def test_secrets_are_excluded_from_model_dump():
    settings = build_settings(
        OPENAI_API_KEY="test-openai-key",
        SESSION_SECRET="test-session-key",
        SUPABASE_SERVICE_ROLE_KEY="test-storage-key",
    )

    serialized = settings.model_dump()

    assert "DATABASE_URL" not in serialized
    assert "OPENAI_API_KEY" not in serialized
    assert "SESSION_SECRET" not in serialized
    assert "SUPABASE_SERVICE_ROLE_KEY" not in serialized


# -----------------------------------------
# Cached settings
# -----------------------------------------

def test_settings_cache_returns_same_instance(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("APP_ENV", "testing")
    get_settings.cache_clear()

    try:
        first = get_settings()
        second = get_settings()
        assert first is second

    finally:
        get_settings.cache_clear()


# -----------------------------------------
# Existing Phase 1 compatibility
# -----------------------------------------

def test_phase1_configuration_remains_compatible():
    settings = build_settings()

    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.DEBUG is False
    assert settings.DATABASE_URL == TEST_DATABASE_URL
    assert settings.is_production is False
    assert settings.is_development is False
