"""Shared fixtures for API integration tests."""

import re
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.services.admin.auth import create_admin_user

EMAIL = "concept-doctor@example.com"
PASSWORD = "Concept-Doctor-Password-2026!"


def extract_csrf_token(html: str) -> str:
    match = re.search(
        r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']',
        html,
    )
    assert match is not None, "CSRF token not found in HTML."
    return match.group(1)


@pytest.fixture
def doctor_client(
    app: FastAPI, test_engine: Engine, test_settings: Settings
) -> Generator[TestClient, None, None]:
    test_settings.ADMIN_SESSIONS_ENABLED = True
    test_settings.SESSION_SECRET = SecretStr(
        "concept-test-session-secret-at-least-32-characters"
    )
    test_settings.SESSION_COOKIE_SECURE = False
    test_settings.SESSION_MAX_AGE_SECONDS = 3600
    test_settings.SESSION_IDLE_TIMEOUT_SECONDS = 900

    registered_routes = set(app.openapi().get("paths", {}))
    assert "/admin/concepts" in registered_routes, (
        "Phase 09 admin router is not registered in the test application."
    )
    assert "/api/admin/concepts" in registered_routes, (
        "Phase 09 API router is not registered in the test application."
    )

    Base.metadata.create_all(test_engine)

    try:
        with Session(test_engine) as db:
            create_admin_user(
                db,
                email=EMAIL,
                full_name="Concept Test Doctor",
                password=PASSWORD,
            )
            db.commit()

        with TestClient(app) as client:
            login_page = client.get("/admin/login")
            assert login_page.status_code == 200

            csrf_token = extract_csrf_token(login_page.text)

            response = client.post(
                "/admin/login",
                data={
                    "email": EMAIL,
                    "password": PASSWORD,
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )
            assert response.status_code == 303
            admin_page = client.get("/admin/concepts")
            assert admin_page.status_code == 200
            csrf_token = extract_csrf_token(admin_page.text)
            client.headers.update({"X-CSRF-Token": csrf_token})

            yield client

    finally:
        Base.metadata.drop_all(test_engine)
