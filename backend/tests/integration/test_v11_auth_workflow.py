from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import uuid
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select

from alembic import command
from app.auth.models import AuthSession, LocalUser, Role, SocAuditAction, SocAuditEvent
from app.auth.security import keyed_token_digest, verify_password
from app.auth.service import create_local_user
from app.core.config import Settings
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.incidents.models import (
    Incident,
    IncidentAuditEvent,
    IncidentNote,
    IncidentReport,
    IncidentReportRevision,
    IncidentStatus,
    IncidentStatusHistory,
)
from app.incidents.service import qualify_stored_evidence
from app.lab.service import startup_baseline
from app.main import create_app
from tests.incident_helpers import persist_correlation_chain
from tests.integration.test_evidence_persistence import evidence_settings
from tests.integration.test_migrations import alembic_config

_PASSWORD = "Integration-Only-Password-2026!"
_RESET_PASSWORD = "Integration-Only-Reset-Password-2026!"
_BOOTSTRAP_PASSWORD = "Integration-Only-Bootstrap-Password-2026!"
_ROLE_USERS = {
    Role.ADMIN: ("v11-admin", "V11 Integration Administrator"),
    Role.SOC_ANALYST: ("v11-analyst", "V11 Integration Analyst"),
    Role.OT_ENGINEER: ("v11-engineer", "V11 Integration OT Engineer"),
    Role.READ_ONLY: ("v11-readonly", "V11 Integration Read Only"),
}


@dataclass(frozen=True)
class SeedUser:
    user_id: uuid.UUID
    username: str
    display_name: str
    role: Role
    password: str


@dataclass(frozen=True)
class V11AuthState:
    settings: Settings
    users: dict[Role, SeedUser]
    inactive_analyst: SeedUser
    incident_id: uuid.UUID


@dataclass(frozen=True)
class SignedClient:
    client: TestClient
    login_body: dict[str, Any]
    mutation_headers: dict[str, str]
    raw_session_token: str
    set_cookie_headers: tuple[str, ...]


@pytest.fixture(scope="module")
def v11_auth_state() -> Generator[V11AuthState, None, None]:
    settings = evidence_settings().model_copy(update={"scenario_lab_startup_enabled": False})
    command.upgrade(alembic_config(), "head")
    _truncate(settings)

    users: dict[Role, SeedUser] = {}
    with session_scope(settings) as session:
        for role, (username, display_name) in _ROLE_USERS.items():
            model = create_local_user(
                session,
                username=username,
                display_name=display_name,
                role=role,
                password=SecretStr(_PASSWORD),
                request_id=f"seed-{role.value.casefold().replace('_', '-')}",
                actor_user_id=None,
            )
            users[role] = SeedUser(
                user_id=model.user_id,
                username=model.username,
                display_name=model.display_name,
                role=role,
                password=_PASSWORD,
            )
        inactive = create_local_user(
            session,
            username="v11-inactive-analyst",
            display_name="V11 Inactive Integration Analyst",
            role=Role.SOC_ANALYST,
            password=SecretStr(_PASSWORD),
            request_id="seed-inactive-analyst",
            actor_user_id=None,
        )
        inactive.active = False
        inactive.updated_at = datetime.now(UTC)
        inactive_user = SeedUser(
            user_id=inactive.user_id,
            username=inactive.username,
            display_name=inactive.display_name,
            role=Role.SOC_ANALYST,
            password=_PASSWORD,
        )

    with session_scope(settings) as session:
        startup_baseline(settings, session)

    request = persist_correlation_chain("p6b-f008.json", simulation_id="sim-v11-auth-workflow")
    with session_scope(settings) as session:
        qualified = qualify_stored_evidence(session, request)
        assert qualified.incident_id is not None
        incident_id = qualified.incident_id

    yield V11AuthState(
        settings=settings,
        users=users,
        inactive_analyst=inactive_user,
        incident_id=incident_id,
    )
    _truncate(settings)


@pytest.mark.integration
def test_real_cookie_login_session_invalid_credentials_expiry_and_logout_revocation(
    v11_auth_state: V11AuthState,
) -> None:
    state = v11_auth_state
    admin = state.users[Role.ADMIN]

    with _signed_client(state, Role.ADMIN) as signed:
        session_response = signed.client.get("/api/v1/auth/session")
        assert session_response.status_code == 200
        assert session_response.json()["user"] == signed.login_body["user"]
        assert session_response.json()["csrf_token"] == signed.login_body["csrf_token"]
        assert signed.login_body["user"]["role"] == Role.ADMIN.value
        rendered_login = json.dumps(signed.login_body).casefold()
        assert "password_hash" not in rendered_login
        assert admin.password.casefold() not in rendered_login

        session_cookie = next(
            item
            for item in signed.set_cookie_headers
            if item.startswith(f"{state.settings.auth_session_cookie_name}=")
        )
        csrf_cookie = next(
            item
            for item in signed.set_cookie_headers
            if item.startswith(f"{state.settings.auth_csrf_cookie_name}=")
        )
        assert "HttpOnly" in session_cookie
        assert "HttpOnly" not in csrf_cookie
        assert "SameSite=strict" in session_cookie and "SameSite=strict" in csrf_cookie
        assert "Domain=" not in session_cookie and "Path=/" in session_cookie

        digest = _session_digest(state.settings, signed.raw_session_token)
        with session_scope(state.settings) as session:
            stored_user = session.get(LocalUser, admin.user_id)
            stored_session = session.scalar(
                select(AuthSession).where(AuthSession.token_digest == digest)
            )
            assert stored_user is not None and stored_session is not None
            assert stored_user.password_hash.startswith("otsoc-scrypt$1$")
            assert verify_password(admin.password, stored_user.password_hash)
            assert admin.password not in stored_user.password_hash
            assert signed.raw_session_token not in stored_session.token_digest
            assert signed.login_body["csrf_token"] not in stored_session.csrf_digest

    with TestClient(create_app(state.settings), raise_server_exceptions=False) as client:
        wrong = client.post(
            "/api/v1/auth/login",
            json={"username": admin.username, "password": "Wrong-Password-Only-2026!"},
        )
        unknown = client.post(
            "/api/v1/auth/login",
            json={"username": "unknown-v11-user", "password": "Wrong-Password-Only-2026!"},
        )
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"]
        assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]
        assert state.settings.auth_session_cookie_name not in wrong.cookies
        assert state.settings.auth_session_cookie_name not in unknown.cookies

    with _signed_client(state, Role.READ_ONLY) as expiring:
        digest = _session_digest(state.settings, expiring.raw_session_token)
        with session_scope(state.settings) as session:
            stored = session.scalar(select(AuthSession).where(AuthSession.token_digest == digest))
            assert stored is not None
            stored.expires_at = stored.created_at + timedelta(microseconds=1)
        expired = expiring.client.get("/api/v1/auth/session")
        assert expired.status_code == 401

    with _signed_client(state, Role.OT_ENGINEER) as logging_out:
        replayed_token = logging_out.raw_session_token
        digest = _session_digest(state.settings, replayed_token)
        logout = logging_out.client.post(
            "/api/v1/auth/logout", headers=logging_out.mutation_headers
        )
        assert logout.status_code == 204
        with session_scope(state.settings) as session:
            stored = session.scalar(select(AuthSession).where(AuthSession.token_digest == digest))
            assert stored is not None and stored.revoked_at is not None

    with TestClient(create_app(state.settings), raise_server_exceptions=False) as replay:
        replay.cookies.set(state.settings.auth_session_cookie_name, replayed_token)
        assert replay.get("/api/v1/auth/session").status_code == 401


@pytest.mark.integration
def test_csrf_and_origin_are_enforced_before_an_authenticated_mutation(
    v11_auth_state: V11AuthState,
) -> None:
    state = v11_auth_state
    with _signed_client(state, Role.SOC_ANALYST) as signed:
        payload = {
            "content": "CSRF integration validation note.",
            "expected_version": _incident_version(state),
        }
        missing_origin = signed.client.post(
            f"/api/v1/incidents/{state.incident_id}/notes", json=payload
        )
        assert missing_origin.status_code == 403

        bad_origin = signed.client.post(
            f"/api/v1/incidents/{state.incident_id}/notes",
            json=payload,
            headers={
                "Origin": "http://unapproved.invalid",
                "X-CSRF-Token": signed.login_body["csrf_token"],
            },
        )
        assert bad_origin.status_code == 403

        mismatched_token = signed.client.post(
            f"/api/v1/incidents/{state.incident_id}/notes",
            json=payload,
            headers={
                "Origin": state.settings.cors_origin_strings[0],
                "X-CSRF-Token": "x" * 43,
            },
        )
        assert mismatched_token.status_code == 403

        accepted = signed.client.post(
            f"/api/v1/incidents/{state.incident_id}/notes",
            json=payload,
            headers=signed.mutation_headers,
        )
        assert accepted.status_code == 200
        assert accepted.json()["operation"] == "note_added"


@pytest.mark.integration
def test_exact_role_boundaries_are_enforced_by_real_server_sessions(
    v11_auth_state: V11AuthState,
) -> None:
    state = v11_auth_state
    incident_path = f"/api/v1/incidents/{state.incident_id}"

    for role in Role:
        with _signed_client(state, role) as signed:
            assert signed.client.get(incident_path).status_code == 200

    with _signed_client(state, Role.READ_ONLY) as read_only:
        version = _incident_version(state)
        read_only_denied = (
            read_only.client.post(
                f"{incident_path}/notes",
                json={"content": "Not authorized.", "expected_version": version},
                headers=read_only.mutation_headers,
            ),
            read_only.client.patch(
                f"{incident_path}/assignment",
                json={"assignee_user_id": None, "expected_version": version},
                headers=read_only.mutation_headers,
            ),
            read_only.client.patch(
                f"{incident_path}/disposition",
                json={
                    "disposition": "TRUE_POSITIVE",
                    "reason": "Not authorized.",
                    "expected_version": version,
                },
                headers=read_only.mutation_headers,
            ),
            read_only.client.patch(
                f"{incident_path}/status",
                json={"new_status": "INVESTIGATING", "expected_version": version},
                headers=read_only.mutation_headers,
            ),
            read_only.client.put(
                f"{incident_path}/report",
                json={"investigation_summary": "Not authorized.", "expected_version": 0},
                headers=read_only.mutation_headers,
            ),
            read_only.client.post("/api/v1/lab/reset", headers=read_only.mutation_headers),
            read_only.client.get("/api/v1/users"),
            read_only.client.get("/api/v1/incident-assignees"),
        )
        assert {response.status_code for response in read_only_denied} == {403}

    with _signed_client(state, Role.OT_ENGINEER) as engineer:
        note = engineer.client.post(
            f"{incident_path}/notes",
            json={
                "content": "Approved OT engineer process-context note.",
                "expected_version": _incident_version(state),
            },
            headers=engineer.mutation_headers,
        )
        assert note.status_code == 200
        version = _incident_version(state)
        engineer_denied = (
            engineer.client.patch(
                f"{incident_path}/assignment",
                json={"assignee_user_id": None, "expected_version": version},
                headers=engineer.mutation_headers,
            ),
            engineer.client.patch(
                f"{incident_path}/disposition",
                json={
                    "disposition": "TRUE_POSITIVE",
                    "reason": "Not authorized.",
                    "expected_version": version,
                },
                headers=engineer.mutation_headers,
            ),
            engineer.client.patch(
                f"{incident_path}/status",
                json={"new_status": "INVESTIGATING", "expected_version": version},
                headers=engineer.mutation_headers,
            ),
            engineer.client.put(
                f"{incident_path}/report",
                json={"investigation_summary": "Not authorized.", "expected_version": 0},
                headers=engineer.mutation_headers,
            ),
            engineer.client.post("/api/v1/lab/reset", headers=engineer.mutation_headers),
            engineer.client.get("/api/v1/users"),
            engineer.client.get("/api/v1/incident-assignees"),
        )
        assert {response.status_code for response in engineer_denied} == {403}

    with _signed_client(state, Role.SOC_ANALYST) as analyst:
        assert analyst.client.get("/api/v1/incident-assignees").status_code == 200
        assert analyst.client.get("/api/v1/users").status_code == 403
        assert (
            analyst.client.post("/api/v1/lab/reset", headers=analyst.mutation_headers).status_code
            == 403
        )

    with _signed_client(state, Role.ADMIN) as admin:
        assert admin.client.get("/api/v1/users").status_code == 200
        assert admin.client.get("/api/v1/incident-assignees").status_code == 200
        admin_note = admin.client.post(
            f"{incident_path}/notes",
            json={
                "content": "Approved administrator investigation note.",
                "expected_version": _incident_version(state),
            },
            headers=admin.mutation_headers,
        )
        assert admin_note.status_code == 200
        reset = admin.client.post("/api/v1/lab/reset", headers=admin.mutation_headers)
        assert reset.status_code == 200, reset.text
        assert reset.json()["active_run"]["scenario_id"] == "BASELINE"


@pytest.mark.integration
def test_bootstrap_admin_create_password_reset_disable_and_final_admin_guard(
    v11_auth_state: V11AuthState,
) -> None:
    state = v11_auth_state
    backend_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "development",
            "DATABASE_URL": state.settings.database_url_string,
            "AUTH_SESSION_SECRET": state.settings.auth_session_secret.get_secret_value(),
            "SCENARIO_LAB_STARTUP_ENABLED": "false",
            "PYTHONPATH": str(backend_root),
        }
    )
    bootstrap = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.auth.bootstrap",
            "--username",
            "v11-bootstrap-readonly",
            "--display-name",
            "V11 Bootstrap Read Only",
            "--role",
            "READ_ONLY",
            "--password-stdin",
        ],
        cwd=backend_root,
        env=environment,
        input=f"{_BOOTSTRAP_PASSWORD}\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr
    assert _BOOTSTRAP_PASSWORD not in bootstrap.stdout + bootstrap.stderr
    with session_scope(state.settings) as session:
        bootstrapped = session.scalar(
            select(LocalUser).where(LocalUser.username == "v11-bootstrap-readonly")
        )
        assert bootstrapped is not None
        assert bootstrapped.role == Role.READ_ONLY.value
        assert verify_password(_BOOTSTRAP_PASSWORD, bootstrapped.password_hash)

    with _signed_client(state, Role.ADMIN) as admin:
        created = admin.client.post(
            "/api/v1/users",
            json={
                "username": "v11-managed-user",
                "display_name": "V11 Managed User",
                "role": "READ_ONLY",
                "password": _PASSWORD,
            },
            headers=admin.mutation_headers,
        )
        assert created.status_code == 201, created.text
        created_body = created.json()["user"]
        managed_user_id = uuid.UUID(created_body["user_id"])
        rendered_user = json.dumps(created.json()).casefold()
        assert "password_hash" not in rendered_user
        assert _PASSWORD.casefold() not in rendered_user

        with TestClient(create_app(state.settings), raise_server_exceptions=False) as managed:
            old_login = managed.post(
                "/api/v1/auth/login",
                json={"username": "v11-managed-user", "password": _PASSWORD},
            )
            assert old_login.status_code == 200
            old_token = managed.cookies.get(state.settings.auth_session_cookie_name)
            assert old_token is not None

        reset = admin.client.post(
            f"/api/v1/users/{managed_user_id}/password-reset",
            json={"password": _RESET_PASSWORD, "expected_version": created_body["version"]},
            headers=admin.mutation_headers,
        )
        assert reset.status_code == 200
        reset_body = reset.json()["user"]
        assert reset_body["version"] == created_body["version"] + 1

        with TestClient(create_app(state.settings), raise_server_exceptions=False) as replay:
            replay.cookies.set(state.settings.auth_session_cookie_name, old_token)
            assert replay.get("/api/v1/auth/session").status_code == 401
            assert (
                replay.post(
                    "/api/v1/auth/login",
                    json={"username": "v11-managed-user", "password": _PASSWORD},
                ).status_code
                == 401
            )
            assert (
                replay.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "v11-managed-user",
                        "password": _RESET_PASSWORD,
                    },
                ).status_code
                == 200
            )

        disabled = admin.client.patch(
            f"/api/v1/users/{managed_user_id}",
            json={"active": False, "expected_version": reset_body["version"]},
            headers=admin.mutation_headers,
        )
        assert disabled.status_code == 200
        assert disabled.json()["user"]["active"] is False
        with TestClient(create_app(state.settings), raise_server_exceptions=False) as disabled_user:
            assert (
                disabled_user.post(
                    "/api/v1/auth/login",
                    json={
                        "username": "v11-managed-user",
                        "password": _RESET_PASSWORD,
                    },
                ).status_code
                == 401
            )

        primary_admin = state.users[Role.ADMIN]
        final_admin = admin.client.patch(
            f"/api/v1/users/{primary_admin.user_id}",
            json={
                "active": False,
                "expected_version": _user_version(state, primary_admin.user_id),
            },
            headers=admin.mutation_headers,
        )
        assert final_admin.status_code == 422
        with session_scope(state.settings) as session:
            still_active = session.get(LocalUser, primary_admin.user_id)
            assert still_active is not None and still_active.active is True


@pytest.mark.integration
def test_assignment_allowlist_and_all_dispositions_preserve_evidence(
    v11_auth_state: V11AuthState,
) -> None:
    state = v11_auth_state
    analyst = state.users[Role.SOC_ANALYST]
    engineer = state.users[Role.OT_ENGINEER]
    before_evidence = _evidence_snapshot(state)

    with _signed_client(state, Role.SOC_ANALYST) as signed:
        assignees = signed.client.get("/api/v1/incident-assignees")
        assert assignees.status_code == 200
        listed_ids = {uuid.UUID(item["user_id"]) for item in assignees.json()["items"]}
        assert analyst.user_id in listed_ids
        assert state.users[Role.ADMIN].user_id in listed_ids
        assert engineer.user_id not in listed_ids
        assert state.inactive_analyst.user_id not in listed_ids

        assigned = signed.client.patch(
            f"/api/v1/incidents/{state.incident_id}/assignment",
            json={
                "assignee_user_id": str(analyst.user_id),
                "expected_version": _incident_version(state),
            },
            headers=signed.mutation_headers,
        )
        assert assigned.status_code == 200
        assert assigned.json()["incident"]["assignee_user_id"] == str(analyst.user_id)
        assert assigned.json()["incident"]["assignee_display_name"] == analyst.display_name
        detail = signed.client.get(f"/api/v1/incidents/{state.incident_id}")
        assert detail.status_code == 200
        assert detail.json()["incident"]["assignee_user_id"] == str(analyst.user_id)
        assert detail.json()["incident"]["assignee_display_name"] == analyst.display_name

        for invalid_user_id in (
            engineer.user_id,
            state.inactive_analyst.user_id,
            uuid.UUID("00000000-0000-4000-8000-000000000099"),
        ):
            rejected = signed.client.patch(
                f"/api/v1/incidents/{state.incident_id}/assignment",
                json={
                    "assignee_user_id": str(invalid_user_id),
                    "expected_version": _incident_version(state),
                },
                headers=signed.mutation_headers,
            )
            assert rejected.status_code == 422

        missing_rationale = signed.client.patch(
            f"/api/v1/incidents/{state.incident_id}/disposition",
            json={
                "disposition": "TRUE_POSITIVE",
                "reason": "",
                "expected_version": _incident_version(state),
            },
            headers=signed.mutation_headers,
        )
        assert missing_rationale.status_code == 422

        for disposition, reason in (
            (
                "TRUE_POSITIVE",
                "The defined synthetic condition was correctly identified; "
                "no actor intent is inferred.",
            ),
            (
                "FALSE_POSITIVE",
                "The qualification did not represent the condition as initially interpreted.",
            ),
            (
                "UNREVIEWED",
                "Further authenticated analyst review is required before final disposition.",
            ),
        ):
            changed = signed.client.patch(
                f"/api/v1/incidents/{state.incident_id}/disposition",
                json={
                    "disposition": disposition,
                    "reason": reason,
                    "expected_version": _incident_version(state),
                },
                headers=signed.mutation_headers,
            )
            assert changed.status_code == 200, changed.text
            incident = changed.json()["incident"]
            assert incident["disposition"] == disposition
            assert incident["disposition_reason"] == reason
            assert incident["disposition_set_by_user_id"] == str(analyst.user_id)

    assert _evidence_snapshot(state) == before_evidence


@pytest.mark.integration
def test_seven_field_report_create_update_conflict_and_plain_text_xss_inertness(
    v11_auth_state: V11AuthState,
) -> None:
    state = v11_auth_state
    analyst = state.users[Role.SOC_ANALYST]
    endpoint = f"/api/v1/incidents/{state.incident_id}/report"
    xss_text = '<script>alert("v11-report")</script>'
    fields = {
        "investigation_summary": xss_text,
        "analyst_assessment": "Synthetic condition assessed without asserting malicious intent.",
        "evidence_assessment": "Stored immutable evidence and lineage were reviewed.",
        "process_impact_assessment": "Synthetic transfer behavior requires academic review.",
        "disposition_rationale": "Disposition remains a separate analyst interpretation.",
        "recommended_follow_up": "Continue offline advisory review only.",
        "final_conclusion": "Initial bounded plain-text conclusion.",
    }

    with _signed_client(state, Role.SOC_ANALYST) as signed:
        empty = signed.client.get(endpoint)
        assert empty.status_code == 200 and empty.json()["version"] == 0
        created = signed.client.put(
            endpoint,
            json={**fields, "expected_version": 0},
            headers=signed.mutation_headers,
        )
        assert created.status_code == 200, created.text
        assert created.headers["content-type"].startswith("application/json")
        created_body = created.json()
        assert created_body["version"] == 1
        assert created_body["fields_filled"] == created_body["fields_total"] == 7
        assert created_body["investigation_summary"] == xss_text
        assert created_body["created_by_user_id"] == str(analyst.user_id)
        assert created_body["updated_by_user_id"] == str(analyst.user_id)

        updated_fields = {
            **fields,
            "final_conclusion": "Updated deterministic analyst conclusion.",
        }
        updated = signed.client.put(
            endpoint,
            json={**updated_fields, "expected_version": 1},
            headers=signed.mutation_headers,
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        assert updated.json()["final_conclusion"] == updated_fields["final_conclusion"]

        stale = signed.client.put(
            endpoint,
            json={**fields, "expected_version": 1},
            headers=signed.mutation_headers,
        )
        assert stale.status_code == 409
        unsafe_control = signed.client.put(
            endpoint,
            json={
                **updated_fields,
                "investigation_summary": "unsafe\u0000text",
                "expected_version": 2,
            },
            headers=signed.mutation_headers,
        )
        assert unsafe_control.status_code == 422

    with session_scope(state.settings) as session:
        report = session.get(IncidentReport, state.incident_id)
        assert report is not None
        assert report.version == 2
        assert report.investigation_summary == xss_text
        assert report.final_conclusion == "Updated deterministic analyst conclusion."
        revisions = session.scalars(
            select(IncidentReportRevision)
            .where(IncidentReportRevision.incident_id == state.incident_id)
            .order_by(IncidentReportRevision.version)
        ).all()
        assert [revision.version for revision in revisions] == [1, 2]
        assert all(revision.saved_by_user_id == analyst.user_id for revision in revisions)


@pytest.mark.integration
def test_analyst_note_html_is_returned_as_inert_plain_text(
    v11_auth_state: V11AuthState,
) -> None:
    state = v11_auth_state
    xss_text = '<script>alert("v11-note")</script><img src=x onerror=alert(1)>'

    with _signed_client(state, Role.SOC_ANALYST) as signed:
        response = signed.client.post(
            f"/api/v1/incidents/{state.incident_id}/notes",
            json={"content": xss_text, "expected_version": _incident_version(state)},
            headers=signed.mutation_headers,
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("application/json")
        detail = signed.client.get(f"/api/v1/incidents/{state.incident_id}")
        assert detail.status_code == 200, detail.text
        notes = detail.json()["notes"]
        assert notes[-1]["content"] == html.escape(xss_text, quote=True)
        assert "<script>" not in notes[-1]["content"]
        assert "onerror=" in notes[-1]["content"]

    with session_scope(state.settings) as session:
        stored = session.scalar(
            select(IncidentNote).where(
                IncidentNote.incident_id == state.incident_id,
                IncidentNote.content == xss_text,
            )
        )
        assert stored is not None
        assert stored.content == xss_text


@pytest.mark.integration
def test_incident_and_global_audit_events_preserve_authenticated_identity(
    v11_auth_state: V11AuthState,
) -> None:
    state = v11_auth_state
    analyst = state.users[Role.SOC_ANALYST]
    request_id = "v11-audit-identity-note"

    with _signed_client(state, Role.SOC_ANALYST) as signed:
        note = signed.client.post(
            f"/api/v1/incidents/{state.incident_id}/notes",
            json={
                "content": "Authenticated audit identity integration note.",
                "expected_version": _incident_version(state),
            },
            headers={**signed.mutation_headers, "X-Request-ID": request_id},
        )
        assert note.status_code == 200
        incident_audit = signed.client.get(f"/api/v1/incidents/{state.incident_id}/audit")
        assert incident_audit.status_code == 200
        matching = [
            event for event in incident_audit.json()["items"] if event["request_id"] == request_id
        ]
        assert len(matching) == 1
        assert matching[0]["action"] == "ANALYST_NOTE_ADDED"
        assert matching[0]["actor_user_id"] == str(analyst.user_id)
        assert matching[0]["actor_display_name"] == analyst.display_name
        logout = signed.client.post("/api/v1/auth/logout", headers=signed.mutation_headers)
        assert logout.status_code == 204

    with session_scope(state.settings) as session:
        incident_event = session.scalar(
            select(IncidentAuditEvent).where(
                IncidentAuditEvent.request_id == request_id,
                IncidentAuditEvent.action == "ANALYST_NOTE_ADDED",
            )
        )
        assert incident_event is not None
        assert incident_event.actor_user_id == analyst.user_id
        global_note = session.scalar(
            select(SocAuditEvent).where(
                SocAuditEvent.request_id == request_id,
                SocAuditEvent.action == SocAuditAction.INCIDENT_NOTE_ADDED.value,
            )
        )
        assert global_note is not None and global_note.actor_user_id == analyst.user_id
        actions = set(
            session.scalars(
                select(SocAuditEvent.action).where(SocAuditEvent.actor_user_id == analyst.user_id)
            ).all()
        )
        assert SocAuditAction.LOGIN_SUCCEEDED.value in actions
        assert SocAuditAction.LOGOUT.value in actions


@pytest.mark.integration
def test_resolution_readiness_warning_is_preserved_without_replacing_phase7b_lifecycle(
    v11_auth_state: V11AuthState,
) -> None:
    state = v11_auth_state
    analyst = state.users[Role.SOC_ANALYST]
    endpoint = f"/api/v1/incidents/{state.incident_id}"
    with _signed_client(state, Role.SOC_ANALYST) as signed:
        current_status = _incident_status(state)
        if current_status is IncidentStatus.RESOLVED:
            reopened = signed.client.patch(
                f"{endpoint}/status",
                json={
                    "new_status": "INVESTIGATING",
                    "expected_version": _incident_version(state),
                    "reason": "Reopen for resolution-warning integration coverage.",
                },
                headers=signed.mutation_headers,
            )
            assert reopened.status_code == 200

        unreviewed = signed.client.patch(
            f"{endpoint}/disposition",
            json={
                "disposition": "UNREVIEWED",
                "reason": "Deliberately pending review to exercise the advisory warning.",
                "expected_version": _incident_version(state),
            },
            headers=signed.mutation_headers,
        )
        assert unreviewed.status_code == 200

        no_reason = signed.client.patch(
            f"{endpoint}/status",
            json={
                "new_status": "RESOLVED",
                "expected_version": _incident_version(state),
            },
            headers=signed.mutation_headers,
        )
        assert no_reason.status_code == 422

        resolved = signed.client.patch(
            f"{endpoint}/status",
            json={
                "new_status": "RESOLVED",
                "expected_version": _incident_version(state),
                "reason": "Phase 7B lifecycle resolution remains authoritative.",
            },
            headers=signed.mutation_headers,
        )
        assert resolved.status_code == 200, resolved.text
        body = resolved.json()
        assert body["incident"]["status"] == "RESOLVED"
        assert len(body["warnings"]) == 1
        assert "Resolution readiness warning" in body["warnings"][0]
        assert "reviewed analyst disposition" in body["warnings"][0]
        assert "Phase 7B lifecycle remains authoritative" in body["warnings"][0]

    with session_scope(state.settings) as session:
        history = session.scalar(
            select(IncidentStatusHistory)
            .where(
                IncidentStatusHistory.incident_id == state.incident_id,
                IncidentStatusHistory.new_status == IncidentStatus.RESOLVED.value,
            )
            .order_by(IncidentStatusHistory.changed_at.desc())
        )
        assert history is not None
        assert history.actor_user_id == analyst.user_id
        assert history.reason == "Phase 7B lifecycle resolution remains authoritative."


@contextmanager
def _signed_client(state: V11AuthState, role: Role) -> Iterator[SignedClient]:
    user = state.users[role]
    with TestClient(create_app(state.settings), raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": user.username, "password": user.password},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        raw_session_token = client.cookies.get(state.settings.auth_session_cookie_name)
        assert raw_session_token is not None
        yield SignedClient(
            client=client,
            login_body=body,
            mutation_headers={
                "Origin": state.settings.cors_origin_strings[0],
                "X-CSRF-Token": body["csrf_token"],
            },
            raw_session_token=raw_session_token,
            set_cookie_headers=tuple(response.headers.get_list("set-cookie")),
        )


def _session_digest(settings: Settings, raw_token: str) -> str:
    return keyed_token_digest(settings.auth_session_secret.get_secret_value(), raw_token)


def _incident_version(state: V11AuthState) -> int:
    with session_scope(state.settings) as session:
        version = session.scalar(
            select(Incident.version).where(Incident.incident_id == state.incident_id)
        )
        assert version is not None
        return version


def _incident_status(state: V11AuthState) -> IncidentStatus:
    with session_scope(state.settings) as session:
        value = session.scalar(
            select(Incident.status).where(Incident.incident_id == state.incident_id)
        )
        assert value is not None
        return IncidentStatus(value)


def _user_version(state: V11AuthState, user_id: uuid.UUID) -> int:
    with session_scope(state.settings) as session:
        version = session.scalar(select(LocalUser.version).where(LocalUser.user_id == user_id))
        assert version is not None
        return version


def _evidence_snapshot(state: V11AuthState) -> tuple[tuple[str, str, str], ...]:
    with session_scope(state.settings) as session:
        rows = session.execute(
            select(
                EvidenceRecord.evidence_id,
                EvidenceRecord.integrity_sha256,
                EvidenceRecord.payload,
            ).order_by(EvidenceRecord.evidence_id)
        ).all()
        return tuple(
            (
                str(evidence_id),
                integrity_sha256,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            )
            for evidence_id, integrity_sha256, payload in rows
        )


def _truncate(settings: Settings) -> None:
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
    with session_scope(settings) as session:
        assert session.scalar(select(func.count()).select_from(LocalUser)) == 0
