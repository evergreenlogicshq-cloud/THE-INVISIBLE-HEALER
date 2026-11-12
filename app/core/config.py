
"""
The Invisible Healer
Core Configuration Module

Phase 02 - Secrets and Configuration Hygiene

Responsibilities:
    - Load typed application configuration.
    - Validate required environment variables.
    - Keep sensitive credentials out of repr output.
    - Validate PostgreSQL configuration.
    - Configure optional Supabase Storage credentials.
    - Prepare secure Admin session configuration.
    - Validate production security requirements.
    - Support dependency injection and isolated testing.

Important:
    Phase 02 performs no database or storage connections.
    Database connectivity begins in Phase 03.
"""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


EnvironmentType = Literal["development", "testing", "production"]


class Settings(BaseSettings):
    """
    Central application configuration.
    Environment variables override local .env values.
    Sensitive fields are excluded from serialization
    and object representations where appropriate.
    """

    # -----------------------------------------
    # Application settings
    # -----------------------------------------

    APP_NAME: str = "The Invisible Healer"
    APP_VERSION: str = "0.1.0"
    APP_ENV: EnvironmentType = "development"
    DEBUG: bool = False
    # -----------------------------------------
    # API configuration
    # -----------------------------------------
    API_V1_PREFIX: str = "/api/v1"
    # -----------------------------------------
    # Database configuration
    # -----------------------------------------
    DATABASE_URL: str = Field(..., min_length=1, repr=False, exclude=True)
    # -----------------------------------------
    # Supabase Storage configuration
    # -----------------------------------------
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: SecretStr | None = Field(default=None, repr=False, exclude=True)
    SUPABASE_STORAGE_BUCKET: str = "clinical-documents"
    STORAGE_ENABLED: bool = False
    # -----------------------------------------
    # Admin session configuration
    #
    # Session authentication is implemented
    # in Phase 06, not Phase 02.
    # -----------------------------------------
    SESSION_SECRET: SecretStr | None = Field(default=None, repr=False, exclude=True)
    ADMIN_SESSIONS_ENABLED: bool = False
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: Literal[ "lax", "strict", "none"] = "lax"
    SESSION_MAX_AGE_SECONDS: int = Field(default=3600, ge=300, le=86400)
    # -----------------------------------------
    # Optional AI provider credentials
    # -----------------------------------------
    OPENAI_API_KEY: SecretStr | None = Field(default=None, repr=False, exclude=True)
    ANTHROPIC_API_KEY: SecretStr | None = Field(default=None, repr=False, exclude=True)
    # -----------------------------------------
    # Logging configuration
    # -----------------------------------------
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    # -----------------------------------------
    # Pydantic settings configuration
    # -----------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
        hide_input_in_errors=True,
    )
    # -----------------------------------------
    # Normalize optional secrets
    # -----------------------------------------
    @field_validator(
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SESSION_SECRET",
        mode="before",
    )
    @classmethod
    def normalize_optional_secrets(cls, value):
        """
        Treat absent and blank credentials as None.
        Do not expose supplied secret values in
        validation error messages.
        """

        if value is None:
            return None

        if isinstance(value, SecretStr):
            if not value.get_secret_value().strip():
                return None
            return value

        if isinstance(value, str):
            if not value.strip():
                return None

            return value.strip()

        raise ValueError("Invalid secret configuration type.")

    # -----------------------------------------
    # Validate database URL
    # -----------------------------------------

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """
        Validate PostgreSQL URL syntax.
        Accepted schemes:
            postgresql://
            postgresql+psycopg://
        Connection establishment belongs
        to Phase 03.
        """

        try:
            parsed = urlsplit(value)
            allowed_schemes = {"postgresql", "postgresql+psycopg"}

            if parsed.scheme not in allowed_schemes:
                raise ValueError("Unsupported database scheme.")

            if not parsed.hostname:
                raise ValueError("Missing database hostname.")

            if not parsed.path.strip("/"):
                raise ValueError("Missing database name.")

            port = parsed.port

            if port is not None and not 1 <= port <= 65535:
                raise ValueError("Invalid database port.")

            if parsed.fragment:
                raise ValueError("Database URL fragment is not allowed.")

        except (ValueError, TypeError):
            raise ValueError(
                "Invalid DATABASE_URL. "
                "Check the PostgreSQL connection format."
            ) from None

        return value

    # -----------------------------------------
    # Validate API prefix
    # -----------------------------------------

    @field_validator("API_V1_PREFIX")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """
        Keep API prefixes consistent.
        """

        if not value.startswith("/"):
            raise ValueError("API_V1_PREFIX must begin with '/'.")

        if value == "/" or value.endswith("/"):
            raise ValueError(
                "API_V1_PREFIX must be a non-root "
                "path without a trailing slash."
            )

        return value

    # -----------------------------------------
    # Validate Supabase URL
    # -----------------------------------------

    @field_validator("SUPABASE_URL")
    @classmethod
    def validate_supabase_url(cls, value: str | None) -> str | None:
        """
        Validate the project API URL.
        The privileged service-role key must
        never be included in this URL.
        """

        if value is None or not value.strip():
            return None

        value = value.strip()

        try:
            parsed = urlsplit(value)

            if parsed.scheme != "https":
                raise ValueError("HTTPS is required.")

            if not parsed.hostname:
                raise ValueError("Missing hostname.")

            if parsed.username or parsed.password:
                raise ValueError("Embedded credentials are forbidden.")

            if parsed.query or parsed.fragment:
                raise ValueError("Query and fragment are forbidden.")

            if parsed.path not in ("", "/"):
                raise ValueError("Unexpected URL path.")

        except ValueError:
            raise ValueError("SUPABASE_URL must be a valid HTTPS project URL.") from None

        return value.rstrip("/")

    # -----------------------------------------
    # Validate complete environment
    # -----------------------------------------

    @model_validator(mode="after")
    def validate_environment(self):
        """
        Apply feature-dependent security rules.

        Future features can be configured now
        without requiring their credentials
        before those features are enabled.
        """

        if self.APP_ENV == "production" and self.DEBUG:
            raise ValueError("DEBUG cannot be enabled in production.")

        if self.APP_ENV == "production":
            if self.LOG_LEVEL == "DEBUG":
                raise ValueError("DEBUG logging is disabled in production.")

        # Storage must have both required values
        # before it can be activated.

        if self.STORAGE_ENABLED:
            if (
                self.SUPABASE_URL is None
                or self.SUPABASE_SERVICE_ROLE_KEY is None
            ):
                raise ValueError(
                    "Storage is enabled but Supabase "
                    "credentials are incomplete."
                )

        # Check the session secret only when
        # Admin sessions are enabled.

        if self.ADMIN_SESSIONS_ENABLED:
            if self.SESSION_SECRET is None:
                raise ValueError(
                    "SESSION_SECRET is required when "
                    "Admin sessions are enabled."
                )

            secret = self.SESSION_SECRET.get_secret_value()

            if len(secret) < 32:
                raise ValueError(
                    "SESSION_SECRET must contain "
                    "at least 32 characters."
                )

            if (
                self.SESSION_COOKIE_SAMESITE == "none"
                and not self.SESSION_COOKIE_SECURE
            ):
                raise ValueError("SameSite=None requires Secure cookies.")

            if self.APP_ENV == "production":
                if not self.SESSION_COOKIE_SECURE:
                    raise ValueError(
                        "Secure session cookies are "
                        "required in production."
                    )

                if not self.SESSION_COOKIE_HTTPONLY:
                    raise ValueError(
                        "HttpOnly session cookies are "
                        "required in production."
                    )

        return self

    # -----------------------------------------
    # Environment helpers
    # -----------------------------------------

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_testing(self) -> bool:
        return self.APP_ENV == "testing"

    @property
    def storage_configured(self) -> bool:
        """
        Report configuration completeness,
        not actual storage connectivity.
        """

        return (
            self.SUPABASE_URL is not None
            and self.SUPABASE_SERVICE_ROLE_KEY is not None
        )

    @property
    def admin_session_configured(self) -> bool:
        """
        Report whether a session signing key exists.
        """

        return self.SESSION_SECRET is not None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings.
    Calling modules must not log or serialize
    the complete settings object.
    """

    return Settings()
