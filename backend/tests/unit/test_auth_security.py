from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import SecretStr, ValidationError
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.auth.audit import AuditPayloadError, append_soc_audit_event
from app.auth.bootstrap import build_parser
from app.auth.dependencies import AuthPrincipal, require_csrf_protection
from app.auth.models import (
    ROLE_PERMISSIONS,
    AuthSession,
    LocalUser,
    Permission,
    Role,
    SocAuditAction,
    SocAuditResult,
)
from app.auth.schemas import LoginRequest, UserPatchRequest
from app.auth.security import (
    IdentityValidationError,
    PasswordPolicyError,
    hash_password,
    keyed_token_digest,
    new_opaque_token,
    normalize_display_name,
    normalize_username,
    safe_token_shape,
    verify_password,
    verify_password_or_dummy,
)
from app.auth.service import IssuedSession, set_auth_cookies
from app.core.config import Settings


def test_password_hash_is_salted_versioned_and_verifiable() -> None:
    password = "Long-local-password-2026!"
    first = hash_password(password)
    second = hash_password(password)

    assert first != second
    assert first.startswith("otsoc-scrypt$1$32768$8$1$32$")
    assert password not in first
    assert verify_password(password, first)
    assert not verify_password("Wrong-local-password-2026!", first)


def test_password_hash_and_unknown_user_paths_fail_closed() -> None:
    assert not verify_password_or_dummy("Any-invalid-password", None)
    assert not verify_password_or_dummy("Any-invalid-password", "malformed")
    assert not verify_password("Any-invalid-password", "otsoc-scrypt$1$bad")
    with pytest.raises(PasswordPolicyError):
        hash_password("too-short")
    with pytest.raises(PasswordPolicyError):
        hash_password("valid-length\npassword")


def test_opaque_tokens_are_keyed_and_never_self_describing() -> None:
    token = new_opaque_token()
    secret = "unit-test-keyed-session-secret-20260811"
    digest = keyed_token_digest(secret, token)

    assert safe_token_shape(token)
    assert len(digest) == 64
    assert token not in digest
    assert keyed_token_digest(secret, token) == digest
    assert keyed_token_digest(f"{secret}-different", token) != digest


def test_role_permission_matrix_is_exact_and_fail_closed() -> None:
    read_permissions = {
        Permission.READ_PRODUCT,
        Permission.READ_INCIDENT,
        Permission.READ_EVIDENCE,
        Permission.READ_REPLAY,
        Permission.READ_REPORTS,
    }
    assert set(Role) == {Role.ADMIN, Role.SOC_ANALYST, Role.OT_ENGINEER, Role.READ_ONLY}
    assert ROLE_PERMISSIONS[Role.READ_ONLY] == read_permissions
    assert ROLE_PERMISSIONS[Role.OT_ENGINEER] == read_permissions | {Permission.WRITE_INCIDENT_NOTE}
    assert Permission.MANAGE_USERS not in ROLE_PERMISSIONS[Role.SOC_ANALYST]
    assert Permission.MANAGE_SCENARIOS not in ROLE_PERMISSIONS[Role.SOC_ANALYST]
    assert Permission.SET_INCIDENT_DISPOSITION in ROLE_PERMISSIONS[Role.SOC_ANALYST]
    assert ROLE_PERMISSIONS[Role.ADMIN] == frozenset(Permission)


def test_identity_and_auth_schemas_are_bounded() -> None:
    assert normalize_username("  Analyst.One ") == "analyst.one"
    assert normalize_display_name("  Local   Analyst  ") == "Local Analyst"
    with pytest.raises(IdentityValidationError):
        normalize_username("unsafe/name")
    with pytest.raises(IdentityValidationError):
        normalize_display_name("unsafe\nname")
    login = LoginRequest(username="analyst.one", password="not-logged-password")
    assert isinstance(login.password, SecretStr)
    assert "not-logged-password" not in repr(login)
    with pytest.raises(ValidationError):
        UserPatchRequest(expected_version=1)
    with pytest.raises(ValidationError):
        LoginRequest.model_validate(
            {"username": "analyst.one", "password": "bounded", "permissions": ["admin"]}
        )


def test_audit_details_reject_sensitive_fields() -> None:
    with Session() as session, pytest.raises(AuditPayloadError):
        append_soc_audit_event(
            session,
            action=SocAuditAction.LOGIN_FAILED,
            result=SocAuditResult.DENIED,
            request_id="request-auth-test",
            details={"nested": {"session_token": "must-not-persist"}},
        )


def test_session_cookie_is_httponly_and_csrf_cookie_is_separate(
    unit_settings: Settings,
) -> None:
    now = datetime.now(UTC)
    user = LocalUser(
        user_id=uuid.uuid4(),
        username="analyst.one",
        display_name="Local Analyst",
        role=Role.SOC_ANALYST.value,
        password_hash="not-returned",
        active=True,
        version=1,
        created_at=now,
        updated_at=now,
        password_changed_at=now,
    )
    auth_session = AuthSession(
        session_id=uuid.uuid4(),
        user_id=user.user_id,
        token_digest="a" * 64,
        csrf_digest="b" * 64,
        created_at=now,
        expires_at=now + timedelta(hours=1),
        last_seen_at=now,
        revoked_at=None,
    )
    issued = IssuedSession(
        user=user,
        auth_session=auth_session,
        raw_session_token="s" * 43,
        raw_csrf_token="c" * 43,
    )
    response = Response()
    set_auth_cookies(response, issued, unit_settings)
    cookies = [
        value.decode("latin-1")
        for key, value in response.raw_headers
        if key.lower() == b"set-cookie"
    ]

    session_cookie = next(value for value in cookies if value.startswith("otsoc_session="))
    csrf_cookie = next(value for value in cookies if value.startswith("otsoc_csrf="))
    assert "HttpOnly" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=strict" in session_cookie and "SameSite=strict" in csrf_cookie
    assert issued.raw_session_token not in auth_session.token_digest
    assert issued.raw_csrf_token not in auth_session.csrf_digest
    assert issued.raw_session_token not in repr(issued)
    assert issued.raw_csrf_token not in repr(issued)


def test_bootstrap_accepts_no_password_argument() -> None:
    options = {option for action in build_parser()._actions for option in action.option_strings}
    assert "--password" not in options
    assert "--password-stdin" in options


def test_csrf_requires_matching_cookie_header_digest_and_origin(
    unit_settings: Settings,
) -> None:
    now = datetime.now(UTC)
    user = LocalUser(
        user_id=uuid.uuid4(),
        username="analyst.one",
        display_name="Local Analyst",
        role=Role.SOC_ANALYST.value,
        password_hash="not-returned",
        active=True,
        version=1,
        created_at=now,
        updated_at=now,
        password_changed_at=now,
    )
    csrf_token = "c" * 43
    auth_session = AuthSession(
        session_id=uuid.uuid4(),
        user_id=user.user_id,
        token_digest="a" * 64,
        csrf_digest=keyed_token_digest(
            unit_settings.auth_session_secret.get_secret_value(), csrf_token
        ),
        created_at=now,
        expires_at=now + timedelta(hours=1),
        last_seen_at=now,
        revoked_at=None,
    )
    principal = AuthPrincipal(
        user=user,
        session=auth_session,
        role=Role.SOC_ANALYST,
        permissions=ROLE_PERMISSIONS[Role.SOC_ANALYST],
    )

    accepted = _request(
        method="PATCH",
        origin="http://localhost:5173",
        csrf_header=csrf_token,
        csrf_cookie=csrf_token,
    )
    assert require_csrf_protection(accepted, principal, unit_settings) is principal

    rejected = _request(
        method="PATCH",
        origin="http://unapproved.example",
        csrf_header=csrf_token,
        csrf_cookie=csrf_token,
    )
    with pytest.raises(HTTPException) as failure:
        require_csrf_protection(rejected, principal, unit_settings)
    assert failure.value.status_code == 403


def test_auth_openapi_exposes_only_bounded_local_workflows() -> None:
    app = FastAPI()
    app.include_router(auth_router)
    schema = app.openapi()
    assert set(schema["paths"]) == {
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/session",
        "/api/v1/users",
        "/api/v1/users/{user_id}",
        "/api/v1/users/{user_id}/password-reset",
        "/api/v1/incident-assignees",
    }
    contract = json.dumps(schema, sort_keys=True).casefold()
    assert schema["components"]["securitySchemes"] == {
        "OTSOCSessionCookie": {
            "type": "apiKey",
            "description": (
                "Opaque HttpOnly local session cookie. The configured runtime name may differ."
            ),
            "in": "cookie",
            "name": "otsoc_session",
        }
    }
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]
    assert schema["paths"]["/api/v1/auth/session"]["get"]["security"] == [
        {"OTSOCSessionCookie": []}
    ]
    assert "password_hash" not in contract
    assert "x-otsoc-actor-id" not in contract
    assert "x-otsoc-permissions" not in contract
    assert all("delete" not in operations for operations in schema["paths"].values())


def _request(*, method: str, origin: str, csrf_header: str, csrf_cookie: str) -> Request:
    headers = [
        (b"origin", origin.encode("ascii")),
        (b"x-csrf-token", csrf_header.encode("ascii")),
        (b"cookie", f"otsoc_csrf={csrf_cookie}".encode("ascii")),
    ]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": "/api/v1/incidents/example",
            "raw_path": b"/api/v1/incidents/example",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("127.0.0.1", 8000),
        }
    )
