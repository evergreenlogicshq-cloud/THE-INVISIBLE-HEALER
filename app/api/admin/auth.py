"""
Phase 06 - Admin login/logout routes.

Endpoints:
    GET  /admin/login
    POST /admin/login
    POST /admin/logout

Authentication is database-backed.
Registration is intentionally not public.
"""

from fastapi import (
    APIRouter,
    Form,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.admin.dashboard import templates
from app.api.dependencies import DatabaseSessionDependency
from app.services.admin.auth import (
    LOGIN_CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    authenticate_admin,
    client_rate_key,
    create_admin_session,
    issue_login_csrf,
    record_failed_attempt,
    resolve_admin_session,
    revoke_session,
    too_many_attempts,
    utc_now,
    verify_login_csrf,
    verify_session_csrf,
)

router = APIRouter(prefix="/admin", tags=["Admin Authentication"])


def require_feature(request: Request):
    settings = request.app.state.settings

    if not settings.ADMIN_SESSIONS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not enabled.",
        )

    return settings


def render_login(
    request: Request,
    *,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """
    Render a login form with a fresh signed CSRF token.
    """

    settings = require_feature(request)
    csrf_token = issue_login_csrf(settings)

    response = templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={
            "page_title": "Admin Login",
            "app_name": settings.APP_NAME,
            "environment": settings.APP_ENV,
            "error": error,
            "csrf_token": csrf_token,
        },
        status_code=status_code,
    )

    response.set_cookie(
        key=LOGIN_CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=900,
        path="/admin",
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response


@router.get("/login", response_class=HTMLResponse, name="admin_login_page")
def login_page(request: Request, db: DatabaseSessionDependency):
    settings = require_feature(request)
    existing = resolve_admin_session(
        db,
        request.cookies.get(SESSION_COOKIE_NAME),
        settings,
    )

    if existing is not None:
        return RedirectResponse("/admin", status_code=status.HTTP_303_SEE_OTHER)

    return render_login(request)


@router.post("/login", name="admin_login")
def login(
    request: Request,
    db: DatabaseSessionDependency,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    settings = require_feature(request)

    if not verify_login_csrf(
        csrf_token,
        request.cookies.get(LOGIN_CSRF_COOKIE_NAME),
        settings,
    ):
        return render_login(
            request,
            error="Your form expired. Please try again.",
            status_code=403,
        )

    # Starlette's request.client is supplied by the
    # ASGI server. Use trusted proxy configuration
    # at the deployment boundary.
    client_ip = request.client.host if request.client is not None else "unknown"

    rate_key = client_rate_key(client_ip, settings)
    now = utc_now()

    if too_many_attempts(db, rate_key, now):
        return render_login(
            request,
            error="Too many attempts. Try again later.",
            status_code=429,
        )

    user = authenticate_admin(db, email, password)

    if user is None:
        record_failed_attempt(db, rate_key, now)

        # Generic error: don't identify which
        # part of the credentials was incorrect.
        return render_login(
            request,
            error="Invalid email or password.",
            status_code=401,
        )

    created = create_admin_session(db, user, settings)
    # Commit authentication state before emitting
    # a session cookie to the browser.
    db.commit()

    response = RedirectResponse(
        "/admin?notice=welcome", status_code=status.HTTP_303_SEE_OTHER
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=created.cookie_value,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        path="/admin",
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

    response.delete_cookie(LOGIN_CSRF_COOKIE_NAME, path="/admin")
    response.headers["Cache-Control"] = "no-store"

    return response


@router.post("/logout", name="admin_logout")
def logout(
    request: Request,
    db: DatabaseSessionDependency,
    csrf_token: str = Form(...),
):
    settings = require_feature(request)

    authenticated = resolve_admin_session(
        db,
        request.cookies.get(SESSION_COOKIE_NAME),
        settings,
    )

    if authenticated is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    if not verify_session_csrf(authenticated.session, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")

    revoke_session(db, authenticated.session)
    db.commit()
    response = RedirectResponse("/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/admin")

    response.headers["Cache-Control"] = "no-store"

    return response
