from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.incidents.lifecycle import IncidentLifecycleError, transition_incident_status
from app.incidents.memberships import IncidentEvidenceError
from app.incidents.models import (
    Incident,
    IncidentAuditEvent,
    IncidentEvidenceMembership,
    IncidentQualificationRequest,
    IncidentStatus,
    IncidentStatusHistory,
    IncidentTimelineEntry,
)
from app.incidents.notes import IncidentVersionConflictError, add_analyst_note
from app.incidents.repository import get_incident_detail, list_incidents
from app.incidents.schemas import IncidentListFilters
from app.incidents.service import qualify_stored_evidence
from app.main import create_app
from tests.auth_helpers import create_test_admin, login_test_admin
from tests.incident_helpers import persist_correlation_chain, persist_policy_chain
from tests.integration.test_evidence_persistence import evidence_settings
from tests.integration.test_migrations import alembic_config


@pytest.fixture(autouse=True)
def migrated_clean_incident_database() -> None:
    command.upgrade(alembic_config(), "head")
    with engine_for(evidence_settings()).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)


def _qualify(request: IncidentQualificationRequest):  # type: ignore[no-untyped-def]
    with session_scope(evidence_settings()) as session:
        return qualify_stored_evidence(session, request)


def _policy_request(fixture: str) -> IncidentQualificationRequest:
    return IncidentQualificationRequest(policy_finding=persist_policy_chain(fixture))


@pytest.mark.integration
def test_p7b_t004_qualification_rule_determinism() -> None:
    request = _policy_request("s1_unknown_source_asset.json")
    first = _qualify(request)
    second = _qualify(request)
    assert first.incident_id == second.incident_id
    assert first.incident is not None and second.incident is not None
    assert first.incident.model_dump() == second.incident.model_dump()


@pytest.mark.integration
def test_p7b_t005_s1_qualification() -> None:
    result = _qualify(_policy_request("s1_unknown_source_asset.json"))
    assert result.outcome == "created" and result.incident is not None
    assert (
        result.incident.category.value,
        result.incident.severity.value,
        result.incident.status.value,
    ) == ("ASSET_IDENTITY_ANOMALY", "LOW", "OPEN")


@pytest.mark.integration
def test_p7b_t006_s2_qualification() -> None:
    result = _qualify(_policy_request("s2_it_to_controller.json"))
    assert result.incident is not None
    assert (result.incident.category.value, result.incident.severity.value) == (
        "COMMUNICATION_POLICY_VIOLATION",
        "MEDIUM",
    )


@pytest.mark.integration
def test_p7b_t007_s3_approved_not_correlated() -> None:
    request = persist_correlation_chain(
        "p6b-f002.json", context_fixture="s3_hmi_approved_valve_command.json"
    )
    result = _qualify(request)
    assert result.outcome == "evidence_only" and result.incident_id is None


@pytest.mark.integration
def test_p7b_t008_s3_denied_not_correlated() -> None:
    request = persist_correlation_chain(
        "p6b-f002.json", context_fixture="s3_engineering_denied_valve_command.json"
    )
    result = _qualify(request)
    assert result.incident is not None
    assert (result.incident.category.value, result.incident.severity.value) == (
        "CONTROL_COMMAND_INVESTIGATION",
        "MEDIUM",
    )
    assert result.incident.primary_evidence_id == request.policy_finding.evidence_id  # type: ignore[union-attr]


@pytest.mark.integration
def test_p7b_t009_s3_approved_correlated() -> None:
    request = persist_correlation_chain(
        "p6b-f005.json", context_fixture="s3_hmi_approved_valve_command.json"
    )
    result = _qualify(request)
    assert result.incident is not None
    assert result.incident.severity.value == "MEDIUM"
    assert result.incident.primary_evidence_id == request.correlation_finding.evidence_id  # type: ignore[union-attr]


@pytest.mark.integration
def test_p7b_t010_s3_denied_correlated() -> None:
    request = persist_correlation_chain(
        "p6b-f005.json", context_fixture="s3_engineering_denied_valve_command.json"
    )
    result = _qualify(request)
    assert result.incident is not None and result.incident.severity.value == "HIGH"
    with session_scope(evidence_settings()) as session:
        memberships = session.scalars(
            select(IncidentEvidenceMembership).where(
                IncidentEvidenceMembership.incident_id == result.incident_id
            )
        ).all()
    assert sorted(item.role for item in memberships) == ["PRIMARY", "SUPPORTING"]


@pytest.mark.integration
def test_p7b_t011_s4_correlated_qualification() -> None:
    result = _qualify(persist_correlation_chain("p6b-f008.json"))
    assert result.incident is not None
    assert (result.incident.category.value, result.incident.severity.value) == (
        "PROCESS_INCONSISTENCY",
        "HIGH",
    )


@pytest.mark.integration
def test_p7b_t012_s4_has_no_cyber_cause() -> None:
    result = _qualify(persist_correlation_chain("p6b-f008.json"))
    assert result.incident is not None
    assert result.incident.causality_inferred is False
    assert result.incident.policy_context == "UNAVAILABLE"


@pytest.mark.integration
def test_p7b_t013_not_correlated_handling() -> None:
    approved = _qualify(
        persist_correlation_chain(
            "p6b-f002.json", context_fixture="s3_hmi_approved_valve_command.json"
        )
    )
    denied = _qualify(
        persist_correlation_chain(
            "p6b-f002.json", context_fixture="s3_engineering_denied_valve_command.json"
        )
    )
    assert approved.outcome == "evidence_only"
    assert denied.incident is not None and denied.incident.correlation_context == "NOT_CORRELATED"


@pytest.mark.integration
def test_p7b_t014_insufficient_evidence_handling() -> None:
    approved = _qualify(
        persist_correlation_chain(
            "p6b-f014.json", context_fixture="s3_hmi_approved_valve_command.json"
        )
    )
    denied = _qualify(
        persist_correlation_chain(
            "p6b-f014.json", context_fixture="s3_engineering_denied_valve_command.json"
        )
    )
    assert approved.outcome == "evidence_only"
    assert denied.incident is not None
    assert denied.incident.correlation_context == "INSUFFICIENT_EVIDENCE"
    assert denied.incident.severity.value == "MEDIUM"


@pytest.mark.integration
def test_p7b_t015_indeterminate_handling() -> None:
    _qualify(_policy_request("s3_engineering_denied_valve_command.json"))
    mismatched = persist_correlation_chain(
        "p6b-f010.json", context_fixture="s3_engineering_denied_valve_command.json"
    )
    with pytest.raises(IncidentEvidenceError):
        _qualify(mismatched)
    with session_scope(evidence_settings()) as session:
        incident = session.scalar(select(Incident))
        assert incident is not None
        assert incident.severity == "MEDIUM" and incident.malicious_intent_inferred is False
        assert incident.evidence_count == 1


@pytest.mark.integration
def test_p7b_t017_exact_retry_is_idempotent() -> None:
    request = _policy_request("s1_unknown_source_asset.json")
    first = _qualify(request)
    second = _qualify(request)
    assert first.outcome == "created" and second.outcome == "existing"
    assert first.incident_id == second.incident_id
    with session_scope(evidence_settings()) as session:
        assert session.scalar(select(func.count()).select_from(Incident)) == 1
        assert session.scalar(select(func.count()).select_from(IncidentEvidenceMembership)) == 1
        assert session.scalar(select(func.count()).select_from(IncidentTimelineEntry)) == 1


@pytest.mark.integration
def test_p7b_t018_concurrent_duplicate_behavior() -> None:
    request = _policy_request("s1_unknown_source_asset.json")

    def submit() -> str:
        return _qualify(request).outcome

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(lambda _: submit(), range(8)))
    assert outcomes.count("created") == 1
    assert outcomes.count("existing") == 7
    with session_scope(evidence_settings()) as session:
        assert session.scalar(select(func.count()).select_from(Incident)) == 1
        assert session.scalar(select(func.count()).select_from(IncidentTimelineEntry)) == 1
        assert session.scalar(select(func.count()).select_from(IncidentAuditEvent)) == 1


@pytest.mark.integration
def test_p7b_t022_different_run_isolation() -> None:
    first = _qualify(persist_correlation_chain("p6b-f008.json"))
    second = _qualify(
        persist_correlation_chain("p6b-f008.json", simulation_id="sim-phase7b-second-run")
    )
    assert first.incident_id != second.incident_id
    assert first.incident is not None and second.incident is not None
    assert first.incident.run_scope != second.incident.run_scope


@pytest.mark.integration
def test_p7b_t023_different_configuration_isolation() -> None:
    first = _qualify(persist_correlation_chain("p6b-f008.json"))
    second = _qualify(persist_correlation_chain("p6b-f008.json", configuration_hash="c" * 64))
    assert first.incident_id != second.incident_id
    assert first.incident is not None and second.incident is not None
    assert first.incident.configuration_scope != second.incident.configuration_scope


@pytest.mark.integration
def test_p7b_t024_late_evidence_enrichment() -> None:
    policy_request = _policy_request("s3_engineering_denied_valve_command.json")
    initial = _qualify(policy_request)
    correlated_request = persist_correlation_chain(
        "p6b-f005.json", context_fixture="s3_engineering_denied_valve_command.json"
    )
    later = _qualify(correlated_request)
    assert initial.incident_id == later.incident_id
    assert later.outcome == "enriched" and later.incident is not None
    assert later.incident.severity.value == "HIGH"
    assert later.incident.version == 2


@pytest.mark.integration
def test_p7b_t025_primary_evidence_is_immutable() -> None:
    initial = _qualify(_policy_request("s3_engineering_denied_valve_command.json"))
    assert initial.incident is not None
    before = (
        initial.incident.primary_evidence_id,
        initial.incident.primary_evidence_type,
        initial.incident.primary_evidence_integrity_sha256,
    )
    later = _qualify(
        persist_correlation_chain(
            "p6b-f005.json", context_fixture="s3_engineering_denied_valve_command.json"
        )
    )
    assert later.incident is not None
    assert (
        later.incident.primary_evidence_id,
        later.incident.primary_evidence_type,
        later.incident.primary_evidence_integrity_sha256,
    ) == before


@pytest.mark.integration
def test_p7b_t026_membership_integrity_reload() -> None:
    result = _qualify(persist_correlation_chain("p6b-f008.json"))
    with session_scope(evidence_settings()) as session:
        memberships = session.scalars(
            select(IncidentEvidenceMembership).where(
                IncidentEvidenceMembership.incident_id == result.incident_id
            )
        ).all()
        for membership in memberships:
            record = session.get(EvidenceRecord, membership.evidence_id)
            assert record is not None
            assert membership.integrity_sha256 == record.integrity_sha256
            assert membership.evidence_schema == record.payload_schema


@pytest.mark.integration
def test_p7b_t027_hash_substitution_rejected_atomically() -> None:
    selection = persist_policy_chain("s1_unknown_source_asset.json")
    changed = selection.model_copy(update={"expected_integrity_sha256": "0" * 64})
    with pytest.raises(IncidentEvidenceError), session_scope(evidence_settings()) as session:
        qualify_stored_evidence(session, IncidentQualificationRequest(policy_finding=changed))
    with session_scope(evidence_settings()) as session:
        assert session.scalar(select(func.count()).select_from(Incident)) == 0


@pytest.mark.integration
def test_p7b_t028_timeline_uses_evidence_observed_at() -> None:
    initial = _qualify(_policy_request("s3_engineering_denied_valve_command.json"))
    later = _qualify(
        persist_correlation_chain(
            "p6b-f005.json", context_fixture="s3_engineering_denied_valve_command.json"
        )
    )
    assert initial.incident_id == later.incident_id
    with session_scope(evidence_settings()) as session:
        detail = get_incident_detail(session, later.incident_id)  # type: ignore[arg-type]
    assert detail is not None
    assert [item.observed_at for item in detail.timeline] == sorted(
        item.observed_at for item in detail.timeline
    )


@pytest.mark.integration
def test_p7b_t029_equal_timestamp_timeline_tie_break() -> None:
    created = _qualify(_policy_request("s1_unknown_source_asset.json"))
    assert created.incident is not None and created.incident_id is not None
    same_time = created.incident.first_observed_at
    with session_scope(evidence_settings()) as session:
        transition_incident_status(
            session,
            created.incident_id,
            new_status=IncidentStatus.INVESTIGATING,
            expected_version=1,
            actor_context="analyst-1",
            reason=None,
            request_id="tie-status",
            changed_at=same_time,
        )
    with session_scope(evidence_settings()) as session:
        add_analyst_note(
            session,
            created.incident_id,
            content="Timeline tie test.",
            expected_version=2,
            actor_context="analyst-1",
            request_id="tie-note",
            created_at=same_time,
        )
    with session_scope(evidence_settings()) as session:
        detail = get_incident_detail(session, created.incident_id)
    assert detail is not None
    assert [item.entry_type.value for item in detail.timeline] == [
        "INCIDENT_CREATED",
        "STATUS_CHANGED",
        "ANALYST_NOTE_ADDED",
    ]


@pytest.mark.integration
def test_p7b_t030_received_at_is_not_semantic_order() -> None:
    initial = _qualify(_policy_request("s3_engineering_denied_valve_command.json"))
    result = _qualify(
        persist_correlation_chain(
            "p6b-f002.json",
            context_fixture="s3_engineering_denied_valve_command.json",
        )
    )
    assert initial.incident_id == result.incident_id
    with session_scope(evidence_settings()) as session:
        detail = get_incident_detail(session, result.incident_id)  # type: ignore[arg-type]
    assert detail is not None
    ordered = tuple(
        sorted(
            detail.timeline,
            key=lambda item: (item.observed_at, item.entry_type.value, str(item.reference_id)),
        )
    )
    assert {item.timeline_entry_id for item in ordered} == {
        item.timeline_entry_id for item in detail.timeline
    }
    assert any(
        item.received_at is not None and item.received_at != item.observed_at
        for item in detail.timeline
        if item.evidence_id is not None
    )


@pytest.mark.integration
def test_p7b_t037_valid_status_transitions() -> None:
    created = _qualify(_policy_request("s1_unknown_source_asset.json"))
    assert created.incident_id is not None
    with session_scope(evidence_settings()) as session:
        investigating = transition_incident_status(
            session,
            created.incident_id,
            new_status=IncidentStatus.INVESTIGATING,
            expected_version=1,
            actor_context="analyst-1",
            reason="Review started.",
            request_id="status-1",
        )
        assert investigating.status == "INVESTIGATING"
    with session_scope(evidence_settings()) as session:
        resolved = transition_incident_status(
            session,
            created.incident_id,
            new_status=IncidentStatus.RESOLVED,
            expected_version=2,
            actor_context="analyst-1",
            reason="Stored evidence reviewed.",
            request_id="status-2",
        )
        assert resolved.status == "RESOLVED"


@pytest.mark.integration
def test_p7b_t038_invalid_stale_and_unauthorized_transitions() -> None:
    created = _qualify(_policy_request("s1_unknown_source_asset.json"))
    assert created.incident_id is not None
    with pytest.raises(IncidentLifecycleError), session_scope(evidence_settings()) as session:
        transition_incident_status(
            session,
            created.incident_id,
            new_status=IncidentStatus.OPEN,
            expected_version=1,
            actor_context="analyst-1",
            reason=None,
            request_id="invalid",
        )
    with pytest.raises(IncidentVersionConflictError), session_scope(evidence_settings()) as session:
        transition_incident_status(
            session,
            created.incident_id,
            new_status=IncidentStatus.INVESTIGATING,
            expected_version=9,
            actor_context="analyst-1",
            reason=None,
            request_id="stale",
        )
    with TestClient(create_app(evidence_settings()), raise_server_exceptions=False) as client:
        response = client.patch(
            f"/api/v1/incidents/{created.incident_id}/status",
            json={"new_status": "INVESTIGATING", "expected_version": 1},
        )
        create_test_admin(evidence_settings())
        login_test_admin(client, evidence_settings())
        unsafe_reason = client.patch(
            f"/api/v1/incidents/{created.incident_id}/status",
            json={
                "new_status": "RESOLVED",
                "expected_version": 1,
                "reason": "unsafe\u0000reason",
            },
        )
    assert response.status_code == 401 and unsafe_reason.status_code == 422


@pytest.mark.integration
def test_p7b_t039_status_history_preserved() -> None:
    created = _qualify(_policy_request("s1_unknown_source_asset.json"))
    assert created.incident_id is not None
    with session_scope(evidence_settings()) as session:
        transition_incident_status(
            session,
            created.incident_id,
            new_status=IncidentStatus.RESOLVED,
            expected_version=1,
            actor_context="analyst-2",
            reason="Review completed.",
            request_id="history",
        )
    with session_scope(evidence_settings()) as session:
        rows = session.scalars(
            select(IncidentStatusHistory)
            .where(IncidentStatusHistory.incident_id == created.incident_id)
            .order_by(IncidentStatusHistory.version_after)
        ).all()
    assert [(row.previous_status, row.new_status) for row in rows] == [
        (None, "OPEN"),
        ("OPEN", "RESOLVED"),
    ]
    assert rows[-1].actor_context == "analyst-2" and rows[-1].reason == "Review completed."


@pytest.mark.integration
def test_p7b_t040_note_authorization_and_qualification_isolation() -> None:
    created = _qualify(_policy_request("s1_unknown_source_asset.json"))
    assert created.incident is not None and created.incident_id is not None
    before = (
        created.incident.category,
        created.incident.title,
        created.incident.severity,
        created.incident.status,
    )
    create_test_admin(evidence_settings())
    with TestClient(create_app(evidence_settings()), raise_server_exceptions=False) as client:
        denied = client.post(
            f"/api/v1/incidents/{created.incident_id}/notes",
            json={"content": "Confirmed attack wording is inert.", "expected_version": 1},
        )
        login_test_admin(client, evidence_settings())
        nul_rejected = client.post(
            f"/api/v1/incidents/{created.incident_id}/notes",
            json={"content": "unsafe\u0000note", "expected_version": 1},
        )
        control_rejected = client.post(
            f"/api/v1/incidents/{created.incident_id}/notes",
            json={"content": "safe\rforged", "expected_version": 1},
        )
        accepted = client.post(
            f"/api/v1/incidents/{created.incident_id}/notes",
            json={"content": "Confirmed attack wording is inert.", "expected_version": 1},
        )
    assert (
        denied.status_code,
        nul_rejected.status_code,
        control_rejected.status_code,
        accepted.status_code,
    ) == (401, 422, 422, 200)
    incident = accepted.json()["incident"]
    assert (
        incident["category"],
        incident["title"],
        incident["severity"],
        incident["status"],
    ) == tuple(value.value if hasattr(value, "value") else value for value in before)


@pytest.mark.integration
def test_p7b_t041_note_does_not_modify_evidence() -> None:
    request = _policy_request("s1_unknown_source_asset.json")
    created = _qualify(request)
    assert created.incident_id is not None and request.policy_finding is not None
    with session_scope(evidence_settings()) as session:
        before = session.get(EvidenceRecord, request.policy_finding.evidence_id)
        assert before is not None
        frozen = (dict(before.payload), before.integrity_sha256)
        add_analyst_note(
            session,
            created.incident_id,
            content="Analyst context only.",
            expected_version=1,
            actor_context="analyst-1",
            request_id="note-isolation",
        )
    with session_scope(evidence_settings()) as session:
        after = session.get(EvidenceRecord, request.policy_finding.evidence_id)
        assert after is not None
        assert (dict(after.payload), after.integrity_sha256) == frozen


@pytest.mark.integration
def test_p7b_t042_authorized_bounded_list_contract() -> None:
    first = _qualify(_policy_request("s1_unknown_source_asset.json"))
    _qualify(_policy_request("s2_it_to_controller.json"))
    assert first.incident is not None
    create_test_admin(evidence_settings())
    with TestClient(create_app(evidence_settings()), raise_server_exceptions=False) as client:
        assert client.get("/api/v1/incidents").status_code == 401
        login_test_admin(client, evidence_settings())
        page = client.get("/api/v1/incidents?scope=ALL_HISTORY&limit=1&severity=MEDIUM")
        unbounded = client.get("/api/v1/incidents?scope=ALL_HISTORY&limit=101")
        bad_cursor = client.get("/api/v1/incidents?scope=ALL_HISTORY&cursor=%%%")
        overlong_time_range = client.get(
            "/api/v1/incidents",
            params={
                "observed_from": first.incident.last_observed_at.isoformat(),
                "observed_to": (
                    first.incident.last_observed_at + timedelta(days=31, seconds=1)
                ).isoformat(),
            },
        )
    assert page.status_code == 200 and len(page.json()["items"]) == 1
    assert (
        unbounded.status_code,
        bad_cursor.status_code,
        overlong_time_range.status_code,
    ) == (422, 422, 422)


@pytest.mark.integration
def test_p7b_t043_deterministic_list_order_and_cursor() -> None:
    _qualify(_policy_request("s1_unknown_source_asset.json"))
    _qualify(_policy_request("s2_it_to_controller.json"))
    with session_scope(evidence_settings()) as session:
        full = list_incidents(
            session,
            filters=IncidentListFilters(),
            limit=100,
            cursor=None,
            scope="ALL_HISTORY",
        )
        first = list_incidents(
            session,
            filters=IncidentListFilters(),
            limit=1,
            cursor=None,
            scope="ALL_HISTORY",
        )
        second = list_incidents(
            session,
            filters=IncidentListFilters(),
            limit=1,
            cursor=first.next_cursor,
            scope="ALL_HISTORY",
        )
    assert len(full.items) == 2 and first.next_cursor is not None
    assert [first.items[0].incident_id, second.items[0].incident_id] == [
        item.incident_id for item in full.items
    ]
    assert full.items[0].last_observed_at >= full.items[1].last_observed_at


@pytest.mark.integration
def test_p7b_t044_incident_detail_completeness() -> None:
    created = _qualify(
        persist_correlation_chain(
            "p6b-f005.json", context_fixture="s3_engineering_denied_valve_command.json"
        )
    )
    with session_scope(evidence_settings()) as session:
        detail = get_incident_detail(session, created.incident_id)  # type: ignore[arg-type]
    assert detail is not None
    assert detail.incident.incident_id == created.incident_id
    assert detail.evidence_memberships and detail.timeline
    assert detail.status_history and detail.severity_history
    assert detail.context.policy == "DENIED" and detail.context.correlation == "CORRELATED"


@pytest.mark.integration
def test_p7b_t045_detail_reconstructs_evidence_lineage() -> None:
    created = _qualify(
        persist_correlation_chain(
            "p6b-f005.json", context_fixture="s3_engineering_denied_valve_command.json"
        )
    )
    with session_scope(evidence_settings()) as session:
        detail = get_incident_detail(session, created.incident_id)  # type: ignore[arg-type]
    assert detail is not None
    types = {item.evidence_type for item in detail.lineage_references}
    assert {
        "synthetic_protocol_event",
        "protocol_semantic_event",
        "asset_context_event",
        "communication_policy_finding",
        "correlation_finding",
        "simulator_telemetry",
    }.issubset(types)


@pytest.mark.integration
def test_p7b_t047_incident_operations_cannot_delete_evidence() -> None:
    request = _policy_request("s1_unknown_source_asset.json")
    _qualify(request)
    assert request.policy_finding is not None
    with pytest.raises(DBAPIError), session_scope(evidence_settings()) as session:
        session.execute(
            text("DELETE FROM evidence_records WHERE evidence_id=:id"),
            {"id": request.policy_finding.evidence_id},
        )
