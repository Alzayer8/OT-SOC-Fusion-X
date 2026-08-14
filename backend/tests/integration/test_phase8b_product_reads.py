from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from alembic import command
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.incidents.models import Incident
from app.lab.service import startup_baseline
from app.main import create_app
from tests.auth_helpers import create_test_admin, login_test_admin
from tests.integration.test_evidence_persistence import evidence_settings
from tests.integration.test_migrations import alembic_config


@pytest.fixture(scope="module")
def phase8b_stack() -> Generator[tuple[TestClient, uuid.UUID, uuid.UUID], None, None]:
    command.upgrade(alembic_config(), "head")
    settings = evidence_settings()
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
    with session_scope(settings) as session:
        startup_baseline(settings, session)
    create_test_admin(settings)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        login_test_admin(client, settings)
        s3_response = client.post("/api/v1/lab/start", json={"scenario_id": "S3"})
        s4_response = client.post("/api/v1/lab/start", json={"scenario_id": "S4"})
        assert s3_response.status_code == 200 and s4_response.status_code == 200
        s3_id = uuid.UUID(s3_response.json()["active_run"]["incident_ids"][0])
        s4_id = uuid.UUID(s4_response.json()["active_run"]["incident_ids"][0])
        yield client, s3_id, s4_id


@pytest.mark.integration
def test_phase8b_overview_and_asset_reads_are_exact(
    phase8b_stack: tuple[TestClient, uuid.UUID, uuid.UUID],
) -> None:
    client, _, _ = phase8b_stack

    overview = client.get("/api/v1/overview/summary")
    catalog = client.get("/api/v1/assets")
    valve = client.get("/api/v1/assets/CV-101")
    missing = client.get("/api/v1/assets/NOT-AN-ASSET")

    assert overview.status_code == 200
    summary = overview.json()
    assert summary["active_run"]["scenario_id"] == "S4"
    assert summary["incidents"]["total"] == 1
    assert summary["incidents"]["high"] == 1
    assert summary["assets"] == {"total": 11, "enabled": 11, "cyber": 6, "process": 5}
    assert summary["process_snapshot_status"] == "COMPLETE"
    assert summary["process_snapshot"]["payload"]["simulation_id"]
    assert catalog.status_code == 200
    assert [item["definition"]["asset_key"] for item in catalog.json()["assets"]] == [
        "PLC-01",
        "HMI-01",
        "ENG-WS-01",
        "IT-WS-01",
        "MON-01",
        "SOC-01",
        "TK-101",
        "P-101",
        "PL-101",
        "CV-101",
        "TK-102",
    ]
    assert len(catalog.json()["zones"]) == 5
    assert len(catalog.json()["relationships"]) == 9
    assert valve.status_code == 200 and valve.json()["asset"]["definition"]["asset_key"] == "CV-101"
    assert missing.status_code == 404


@pytest.mark.integration
def test_phase8b_filtered_cursor_evidence_read_is_bounded_and_stable(
    phase8b_stack: tuple[TestClient, uuid.UUID, uuid.UUID],
) -> None:
    client, _, _ = phase8b_stack
    first = client.get(
        "/api/v1/evidence",
        params={"evidence_type": "simulator_telemetry", "limit": 1},
    )
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["items"]) == 1 and first_body["next_cursor"]
    second = client.get(
        "/api/v1/evidence",
        params={
            "evidence_type": "simulator_telemetry",
            "limit": 1,
            "cursor": first_body["next_cursor"],
        },
    )
    assert second.status_code == 200
    assert second.json()["items"][0]["evidence_id"] != first_body["items"][0]["evidence_id"]
    assert (
        client.get("/api/v1/evidence", params={"observed_from": "2026-01-01T00:00:00Z"}).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/evidence",
            params={
                "observed_from": "2026-01-01T00:00:00Z",
                "observed_to": "2026-02-02T00:00:00Z",
            },
        ).status_code
        == 422
    )
    assert client.get("/api/v1/evidence", params={"cursor": "invalid"}).status_code == 422


@pytest.mark.integration
def test_phase8b_s3_replay_is_verified_ordered_and_read_only(
    phase8b_stack: tuple[TestClient, uuid.UUID, uuid.UUID],
) -> None:
    client, s3_id, _ = phase8b_stack
    with session_scope(evidence_settings()) as session:
        before = (
            session.scalar(select(func.count()).select_from(EvidenceRecord)),
            session.scalar(select(func.count()).select_from(Incident)),
        )

    with TestClient(create_app(evidence_settings()), raise_server_exceptions=False) as anonymous:
        denied = anonymous.get("/api/v1/replay", params={"incident_id": str(s3_id)})
    response = client.get(
        "/api/v1/replay",
        params={"incident_id": str(s3_id)},
    )

    assert denied.status_code == 401 and response.status_code == 200
    bundle = response.json()
    assert bundle["source_kind"] == "INCIDENT"
    assert bundle["completeness"] == "COMPLETE" and bundle["truncated"] is False
    assert len({bundle["simulation_id"]}) == 1 and len({bundle["configuration_hash"]}) == 1
    tuples = [
        (item["observed_at"], item["sort_rank"], item["event_id"]) for item in bundle["events"]
    ]
    assert tuples == sorted(tuples)
    types = {
        item["evidence"]["evidence_type"]
        for item in bundle["events"]
        if item["evidence"] is not None
    }
    assert {
        "synthetic_protocol_event",
        "protocol_semantic_event",
        "asset_context_event",
        "communication_policy_finding",
        "simulator_telemetry",
        "correlation_finding",
    }.issubset(types)
    raw = next(
        item["evidence"]
        for item in bundle["events"]
        if item["evidence"] is not None
        and item["evidence"]["evidence_type"] == "synthetic_protocol_event"
    )
    semantic = next(
        item["evidence"]
        for item in bundle["events"]
        if item["evidence"] is not None
        and item["evidence"]["evidence_type"] == "protocol_semantic_event"
    )
    assert raw["payload"]["raw_value"] == 250
    assert semantic["payload"]["decoded_value"] == "25.0"
    with session_scope(evidence_settings()) as session:
        after = (
            session.scalar(select(func.count()).select_from(EvidenceRecord)),
            session.scalar(select(func.count()).select_from(Incident)),
        )
    assert after == before


@pytest.mark.integration
def test_phase8b_s4_replay_remains_process_only(
    phase8b_stack: tuple[TestClient, uuid.UUID, uuid.UUID],
) -> None:
    client, _, s4_id = phase8b_stack
    response = client.get(
        "/api/v1/replay",
        params={"incident_id": str(s4_id)},
    )

    assert response.status_code == 200
    bundle = response.json()
    assert bundle["incident"]["category"] == "PROCESS_INCONSISTENCY"
    evidence_types = {
        item["evidence"]["evidence_type"]
        for item in bundle["events"]
        if item["evidence"] is not None
    }
    assert evidence_types == {"simulator_telemetry", "correlation_finding"}
    summaries = " ".join(item["summary"] for item in bundle["events"]).lower()
    assert "no cyber cause is asserted" in summaries
    assert "cyber caused" not in summaries and "caused by attack" not in summaries


@pytest.mark.integration
def test_phase8b_replay_source_and_window_validation_is_fail_closed(
    phase8b_stack: tuple[TestClient, uuid.UUID, uuid.UUID],
) -> None:
    client, s3_id, _ = phase8b_stack
    detail = client.get(f"/api/v1/incidents/{s3_id}").json()
    start = detail["incident"]["first_observed_at"]
    bad_multiple = client.get(
        "/api/v1/replay",
        params={"incident_id": str(s3_id), "correlation_evidence_id": str(uuid.uuid4())},
    )
    bad_window = client.get(
        "/api/v1/replay",
        params={
            "simulation_id": detail["incident"]["bound_simulation_id"],
            "configuration_hash": detail["incident"]["bound_configuration_hash"],
            "observed_from": start,
            "observed_to": (datetime.fromisoformat(start) + timedelta(minutes=16)).isoformat(),
            "evidence_type": "simulator_telemetry",
        },
    )

    assert bad_multiple.status_code == 422
    assert bad_window.status_code == 422
