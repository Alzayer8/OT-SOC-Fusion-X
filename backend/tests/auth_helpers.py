from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.auth.models import Role
from app.auth.service import create_local_user
from app.core.config import Settings
from app.db.session import session_scope

TEST_ADMIN_USERNAME = "integration-admin"
TEST_ADMIN_PASSWORD = "LocalOnly-Test-Password-2026!"


def create_test_admin(settings: Settings) -> None:
    with session_scope(settings) as session:
        create_local_user(
            session,
            username=TEST_ADMIN_USERNAME,
            display_name="Integration Administrator",
            role=Role.ADMIN,
            password=SecretStr(TEST_ADMIN_PASSWORD),
            request_id="integration-bootstrap",
            actor_user_id=None,
        )


def login_test_admin(client: TestClient, settings: Settings) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    csrf_token = response.json()["csrf_token"]
    mutation_headers = {
        "Origin": settings.cors_origin_strings[0],
        "X-CSRF-Token": csrf_token,
    }
    client.headers.update(mutation_headers)
    return mutation_headers
