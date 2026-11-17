"""
Phase 06 - Admin Authentication Unit Tests.

Tests:
- Argon2 password hashing
- Password verification
- Invalid password rejection
- Password length validation
- Email normalization
- Session token hashing
"""

import pytest

from app.services.admin.auth import (
    hash_password,
    hash_session_token,
    normalized_email,
    validate_password,
    verify_password,
)


def test_password_is_hashed() -> None:
    password = "A-long-secure-test-password-123"
    hashed = hash_password(password)
    assert hashed != password
    assert hashed.startswith("$argon2")


def test_valid_password_verifies() -> None:
    password = "Another-secure-password-123"
    hashed = hash_password(password)
    assert verify_password(password, hashed)


def test_invalid_password_is_rejected() -> None:
    hashed = hash_password("correct-password-12345")
    assert not verify_password("Incorrect-password-12345", hashed)


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_password("short")


def test_email_is_normalized() -> None:
    assert normalized_email("ADMIN@EXAMPLE.COM") == "admin@example.com"


def test_session_token_is_hashed() -> None:
    raw_token = "a-random-session-token"
    digest = hash_session_token(raw_token)

    assert digest != raw_token
    assert len(digest) == 64
    assert digest == hash_session_token(raw_token)
