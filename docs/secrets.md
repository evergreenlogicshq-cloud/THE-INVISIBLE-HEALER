
# The Invisible Healer
## Secrets and Configuration Security Policy

Phase: 02

Status: Engineering baseline

---

## 1. Purpose

This document establishes the minimum requirements
for handling application secrets and environment
configuration.

The Invisible Healer processes medical knowledge
and will eventually process sensitive patient data.

Application credentials must remain server-side
and must never be exposed to users or browsers.

---

## 2. Configuration ownership

The application loads settings using:

    app/core/config.py

Configuration is managed through Pydantic Settings.

Local development uses:

    .env

The committed reference template is:

    .env.example

Production credentials must come from a secure
deployment secret manager or protected environment.

Do not commit production secrets to Git.

---

## 3. Required database configuration

Variable:

    DATABASE_URL

Purpose:

    Connect to Supabase PostgreSQL.

Rules:

- Required for application configuration.
- Must use PostgreSQL URL syntax.
- Must not appear in API responses.
- Must not be printed in application logs.
- Must not be embedded in templates.
- Must not be copied to frontend JavaScript.
- Use encrypted transport to the database.
- Use least-privilege database credentials.

Phase 02 validates the URL format.

Phase 03 implements connectivity and SSL configuration.

---

## 4. Supabase Storage credentials

Variables:

    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    SUPABASE_STORAGE_BUCKET
    STORAGE_ENABLED

The service-role key is privileged.

It must only be used by trusted server-side code.

Never embed it in:

- Jinja templates
- Static JavaScript
- Client-visible HTML
- Public API responses
- Error messages
- Application logs

Storage must remain disabled until its
implementation and authorization checks exist.

When STORAGE_ENABLED is true, both SUPABASE_URL
and SUPABASE_SERVICE_ROLE_KEY are mandatory.

Actual private document upload begins in Phase 18.

---

## 5. Session signing secret

Variables:

    SESSION_SECRET
    ADMIN_SESSIONS_ENABLED

The session secret is used for session security
when Admin authentication is implemented.

Generate a cryptographically random secret.

Example:

    python -c "import secrets; print(secrets.token_urlsafe(48))"

Never use simple or predictable values.

Examples of unacceptable values:

    password123
    change-me
    secret
    admin123

Session cookies must use:

    HttpOnly
    Secure
    SameSite

Session creation, invalidation, CSRF protection,
and login rate limiting belong to Phase 06.

Do not enable Admin sessions before that phase
has been implemented and reviewed.

---

## 6. AI provider credentials

Variables:

    OPENAI_API_KEY
    ANTHROPIC_API_KEY

These credentials are optional in Phase 02.

Do not require them for application startup.

They may only be used inside trusted backend code.

Never pass AI provider keys to browser code.

Never send patient information to an AI provider
without an approved privacy and data-sharing policy.

---

## 7. Environment policies

Development:

- Local .env permitted.
- DEBUG may be enabled.
- Dummy credentials permitted for isolated tests.
- No production patient data.

Testing:

- Use isolated test credentials.
- No production services.
- No real patient data.
- Do not require optional AI credentials.

Production:

- DEBUG must be disabled.
- DEBUG logging must be disabled.
- Secrets must come from protected configuration.
- Database connections must use TLS.
- Privileged credentials must use least privilege.
- Session cookies must be secure and HttpOnly.
- Clinical data handling requires additional controls.

---

## 8. Logging policy

Never log:

- Database passwords
- Complete database connection URLs
- Session secrets
- Supabase service-role keys
- AI provider keys
- Authentication tokens
- Patient data unless explicitly authorized

Allowed:

- Application startup status
- Environment name
- Configuration validation status
- Request correlation identifiers
- Sanitized error categories

Do not serialize the entire Settings object
into application logs.

---

## 9. Secret rotation

When a credential is compromised, exposed,
or scheduled for replacement:

1. Identify the credential and affected service.
2. Restrict access if compromise is suspected.
3. Generate a replacement credential securely.
4. Update the secret manager or protected environment.
5. Restart or redeploy affected applications.
6. Confirm the replacement works.
7. Revoke the old credential.
8. Review access and audit logs.
9. Document the rotation event securely.

Database password rotation:

- Change the password in Supabase.
- Update application configuration.
- Reconnect application processes.
- Verify connectivity.
- Invalidate old credentials.

Supabase service-role key rotation:

- Follow the supported Supabase key rotation process.
- Update trusted backend configuration.
- Verify Storage operations.
- Revoke old keys when safe.

AI provider key rotation:

- Issue a replacement key.
- Update backend environment.
- Verify authorized requests.
- Revoke the previous key.

Session secret rotation:

- Coordinate with the session implementation.
- Decide whether existing sessions must be
  invalidated immediately.
- Rotate the key and verify session behavior.

---

## 10. Exposure response

If secrets appear in a repository, uploaded archive,
support ticket, public log, or shared screenshot:

1. Treat the credential as potentially compromised.
2. Rotate or revoke it.
3. Remove the exposed material from accessible locations.
4. Review service access logs.
5. Investigate unauthorized activity.
6. Document the incident.
7. Correct the process that caused exposure.

Removing a secret from the latest Git commit
does not automatically erase Git history.

---

## 11. Secret scanning

Before committing:

    git status
    git diff --cached

Verify:

- .env is not tracked.
- No real credentials exist in source files.
- No credentials exist in templates or static assets.
- .env.example contains placeholders only.

Use an appropriate secret scanner in CI,
such as Gitleaks, with reviewed configuration.

A local grep search is not a replacement for
dedicated credential scanning.

---

## 12. Future phases

Phase 03:
    Database connection and transport security.

Phase 06:
    Admin authentication and secure sessions.

Phase 18:
    Private Supabase Storage integration.

Phase 33:
    AI provider adapter and controlled key usage.

Phase 46:
    Observability, auditing and incident response.

---

## 13. Phase 02 acceptance criteria

- Typed settings are implemented.
- Missing DATABASE_URL fails validation.
- Invalid DATABASE_URL fails validation.
- Optional credentials are truly optional.
- Enabled Storage requires credentials.
- Enabled Admin sessions require a strong secret.
- Production DEBUG is rejected.
- Secrets are masked in normal representations.
- Sensitive fields are excluded from standard
  settings serialization.
- No live credentials are committed.
- Automated configuration tests pass.

Phase 02 does not authorize clinical deployment.
