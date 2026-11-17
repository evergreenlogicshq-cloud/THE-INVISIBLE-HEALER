from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.admin.auth import (
    SESSION_COOKIE_NAME,
    AuthenticatedAdmin,
    resolve_admin_session,
)

SettingsDependency = Annotated[Settings, Depends(get_settings)]
DatabaseSessionDependency = Annotated[Session, Depends(get_db)]


def require_admin(
    request: Request, db: DatabaseSessionDependency
) -> AuthenticatedAdmin:
    """
    Reusable server-side authentication guard.
    Future Admin APIs must use this dependency.
    Phase 07 will extend it with role checks.
    """

    settings = request.app.state.settings

    if not settings.ADMIN_SESSIONS_ENABLED:
        raise HTTPException(status_code=503, detail="Admin authentication is disabled.")

    authenticated = resolve_admin_session(
        db, request.cookies.get(SESSION_COOKIE_NAME), settings
    )

    if authenticated is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
        )

    return authenticated
