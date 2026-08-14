from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from alembic import command
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.main import create_app
from tests.auth_helpers import create_test_admin, login_test_admin
from tests.evidence_helpers import sample_evidence_request
from tests.integration.test_evidence_persistence import evidence_settings
from tests.integration.test_migrations import alembic_config


@pytest.fixture
def evidence_client() -> Generator[TestClient, None, None]:
    command.upgrade(alembic_config(), "head")
    settings = evidence_settings()
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
    create_test_admin(settings)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        login_test_admin(client, settings)
        yield client


@pytest.mark.integration
def test_post_read_and_bounded_list_evidence(evidence_client: TestClient) -> None:
    payload = sample_evidence_request(source_event_id="api-1").model_dump(mode="json")
    accepted = evidence_client.post("/api/v1/evidence", json=payload)
    assert accepted.status_code == 201
    receipt = accepted.json()
    assert receipt["status"] == "accepted"

    duplicate = evidence_client.post("/api/v1/evidence", json=payload)
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "duplicate_existing"
    assert duplicate.json()["evidence_id"] == receipt["evidence_id"]

    read = evidence_client.get(f"/api/v1/evidence/{receipt['evidence_id']}")
    assert read.status_code == 200
    assert read.json()["source_event_id"] == "api-1"
    assert "ground_truth" not in read.text.lower()
    assert "scenario_id" not in read.text.lower()

    listed = evidence_client.get("/api/v1/evidence?scope=ALL_HISTORY&limit=1&offset=0")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1


@pytest.mark.integration
@pytest.mark.parametrize(
    ("mutation", "expected_status"),
    [
        ({"source_key": "unknown-source"}, 404),
        ({"evidence_type": "modbus_packet"}, 422),
        ({"payload_schema_version": "9.0.0"}, 422),
        ({"observed_at": "not-a-time"}, 422),
    ],
)
def test_invalid_api_evidence_fails_safely_without_partial_state(
    evidence_client: TestClient,
    mutation: dict[str, object],
    expected_status: int,
) -> None:
    payload = sample_evidence_request().model_dump(mode="json")
    payload.update(mutation)
    response = evidence_client.post("/api/v1/evidence", json=payload)
    assert response.status_code == expected_status
    assert "traceback" not in response.text.lower()
    assert "postgresql" not in response.text.lower()

    with session_scope(evidence_settings()) as session:
        assert session.scalar(select(func.count()).select_from(EvidenceRecord)) == 0


@pytest.mark.integration
def test_api_rejects_malformed_payload_unknown_fields_and_oversized_request(
    evidence_client: TestClient,
) -> None:
    payload = sample_evidence_request().model_dump(mode="json")
    payload["payload"]["unexpected"] = "not allowed"
    malformed = evidence_client.post("/api/v1/evidence", json=payload)
    assert malformed.status_code == 422

    normal = sample_evidence_request().model_dump(mode="json")
    oversized = evidence_client.post(
        "/api/v1/evidence",
        json=normal,
        headers={"Content-Length": "32769"},
    )
    assert oversized.status_code == 413
    assert "traceback" not in oversized.text.lower()

    actually_oversized = evidence_client.post(
        "/api/v1/evidence",
        content=b"{" + (b" " * 32_768) + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert actually_oversized.status_code == 413
    assert actually_oversized.json()["error"]["code"] == "request_size_error"

    with session_scope(evidence_settings()) as session:
        assert session.scalar(select(func.count()).select_from(EvidenceRecord)) == 0


@pytest.mark.integration
def test_api_pagination_bounds_and_missing_id_are_safe(evidence_client: TestClient) -> None:
    assert evidence_client.get("/api/v1/evidence?limit=101").status_code == 422
    assert evidence_client.get("/api/v1/evidence?offset=10001").status_code == 422
    missing = evidence_client.get("/api/v1/evidence/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404
    assert "traceback" not in missing.text.lower()
