"""
Phase 06 - Authentication service.

Security decisions:
- Argon2id passwords.
- Random, independently generated session tokens.
- Only session token hashes stored in PostgreSQL.
- Signed cookies with expiration.
- Absolute and idle session expiry.
- CSRF tokens bound to the authenticated session.
- Generic login failures to prevent account enumeration.
- Database-backed failed-login throttling.
"""

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pwdlib import PasswordHash
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.admin.admin_user import AdminLoginAttempt, AdminSession, AdminUser

password_hasher = PasswordHash.recommended()

LOGIN_WINDOW_SECONDS = 900
MAX_FAILED_ATTEMPTS = 5
SESSION_COOKIE_NAME = "ih_admin_session"
LOGIN_CSRF_COOKIE_NAME = "ih_login_csrf"


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalized_email(email: str) -> str:
    return email.strip().casefold()


def validate_password(password: str) -> None:
    """
    Apply a length-based password policy.

    Length is checked in bytes because it affects
    storage and hash-processing limits.
    """

    if not isinstance(password, str):
        raise TypeError("Password must be text")

    size = len(password.encode("utf-8"))

    if size < 12 or size > 1024:
        raise ValueError("Password must contain 12-1024 UTF-8 bytes")


def hash_password(password: str) -> str:
    validate_password(password)
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return password_hasher.verify(password, stored_hash)
    except (ValueError, TypeError):
        return False


# A real Argon2 hash is used when the email does not exist.
# This reduces timing differences between known and unknown users.
DUMMY_PASSWORD_HASH = password_hasher.hash("Dummy-not-a-real-admin-password-2026")


def get_signer(settings: Settings) -> URLSafeTimedSerializer:
    if settings.SESSION_SECRET is None:
        raise RuntimeError("Admin session secret is not configured.")

    return URLSafeTimedSerializer(
        secret_key=settings.SESSION_SECRET.get_secret_value(),
        salt="invisible-healer-admin-v1",
    )


def issue_login_csrf(settings: Settings) -> str:
    return get_signer(settings).dumps(
        {"purpose": "login", "nonce": secrets.token_urlsafe(24)}
    )


def verify_login_csrf(
    form_token: str,
    cookie_token: str | None,
    settings: Settings,
) -> bool:

    if not cookie_token or not form_token:
        return False

    if not secrets.compare_digest(form_token, cookie_token):
        return False

    try:
        payload = get_signer(settings).loads(cookie_token, max_age=LOGIN_WINDOW_SECONDS)
    except (BadSignature, SignatureExpired):
        return False

    return isinstance(payload, dict) and payload.get("purpose") == "login"


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def client_rate_key(ip_address: str, settings: Settings) -> str:
    """
    Generate a privacy-preserving identifier
    from a trusted client address.
    Never trust an unvalidated X-Forwarded-For
    header from a public internet client.
    """
    secret = settings.SESSION_SECRET.get_secret_value()

    return hmac.new(
        secret.encode("utf-8"),
        ip_address.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def too_many_attempts(db: Session, client_key: str, now: datetime) -> bool:
    window_start = now - timedelta(seconds=LOGIN_WINDOW_SECONDS)
    count = db.scalar(
        select(func.count(AdminLoginAttempt.id)).where(
            AdminLoginAttempt.client_key == client_key,
            AdminLoginAttempt.attempted_at >= window_start,
        )
    )

    return int(count or 0) >= MAX_FAILED_ATTEMPTS


def record_failed_attempt(db: Session, client_key: str, now: datetime) -> None:
    db.add(AdminLoginAttempt(client_key=client_key, attempted_at=now))

    db.flush()


def authenticate_admin(db: Session, email: str, password: str) -> AdminUser | None:
    """
    Return an active Admin user only after
    successful password verification.
    """

    # Avoid expensive Argon2 work on unreasonably
    # large input while preserving generic failures.
    if len(password.encode("utf-8")) > 1024:
        return None

    normalized = normalized_email(email)

    if len(normalized) > 254:
        return None

    user = db.scalar(select(AdminUser).where(AdminUser.email == normalized))
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    valid = verify_password(password, stored_hash)

    if user is None or not valid or not user.is_active:
        return None

    return user


@dataclass(frozen=True)
class CreatedSession:
    cookie_value: str
    record: AdminSession


def create_admin_session(
    db: Session, user: AdminUser, settings: Settings
) -> CreatedSession:
    """
    Generate a fresh bearer token on each login.
    Previous tokens are never reused.
    """
    now = utc_now()
    raw_token = secrets.token_urlsafe(48)

    record = AdminSession(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        csrf_secret=secrets.token_hex(32),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS),
    )

    db.add(record)
    db.flush()
    user.last_login_at = now
    cookie_value = get_signer(settings).dumps({"sid": raw_token})

    return CreatedSession(cookie_value=cookie_value, record=record)


@dataclass(frozen=True)
class AuthenticatedAdmin:
    user: AdminUser
    session: AdminSession


def resolve_admin_session(
    db: Session, cookie_value: str | None, settings: Settings
) -> AuthenticatedAdmin | None:
    """
    Validate cookie signature, database state,
    absolute expiry and inactivity timeout.
    """

    if not cookie_value:
        return None

    try:
        payload = get_signer(settings).loads(
            cookie_value,
            max_age=settings.SESSION_MAX_AGE_SECONDS,
        )
    except (BadSignature, SignatureExpired):
        return None

    if not isinstance(payload, dict):
        return None

    raw_token = payload.get("sid")

    if not isinstance(raw_token, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{32,128}", raw_token
    ):
        return None

    token_hash = hash_session_token(raw_token)

    record = db.scalar(
        select(AdminSession).where(AdminSession.token_hash == token_hash)
    )

    if record is None:
        return None

    now = utc_now()

    if record.revoked_at is not None:
        return None

    # SQLite tests may return naive datetimes.
    # Production PostgreSQL stores timezone-aware values.
    def aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    if aware(record.expires_at) <= now:
        record.revoked_at = now
        db.flush()
        return None

    idle_limit = timedelta(seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS)

    if aware(record.last_seen_at) + idle_limit <= now:
        record.revoked_at = now
        db.flush()
        return None

    user = db.get(AdminUser, record.user_id)

    if user is None or not user.is_active:
        record.revoked_at = now
        db.flush()
        return None

    # Throttle activity writes so frequent page loads
    # do not generate constant UPDATE statements.
    if now - aware(record.last_seen_at) >= timedelta(seconds=30):
        record.last_seen_at = now
        db.flush()

    return AuthenticatedAdmin(user=user, session=record)


def session_csrf_token(record: AdminSession) -> str:
    return hmac.new(
        record.csrf_secret.encode("utf-8"),
        b"admin-form-csrf-v1",
        hashlib.sha256,
    ).hexdigest()


def verify_session_csrf(record: AdminSession, supplied_token: str) -> bool:
    return secrets.compare_digest(session_csrf_token(record), supplied_token)


def revoke_session(db: Session, record: AdminSession) -> None:
    record.revoked_at = utc_now()
    db.flush()


def create_admin_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
) -> AdminUser:
    """
    Trusted server-side account provisioning.
    There is intentionally no public registration API.
    """

    email = normalized_email(email)
    full_name = full_name.strip()

    if (
        not email
        or len(email) > 254
        or "@" not in email
        or any(char.isspace() for char in email)
    ):
        raise ValueError("A valid email is required.")

    if not 2 <= len(full_name) <= 150:
        raise ValueError("Full name must contain 2-150 characters.")

    existing = db.scalar(select(AdminUser).where(AdminUser.email == email))

    if existing is not None:
        raise ValueError("An Admin user already exists.")

    user = AdminUser(
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=True,
    )

    db.add(user)
    db.flush()
    return user
