from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from app.context.adapters import persist_asset_context_and_finding
from app.context.fixtures import load_fixture as load_context_fixture
from app.context.inventory import load_inventory_profile
from app.context.policy import load_policy_profile
from app.correlation.fixtures import build_fixture_input, load_fixture
from app.correlation.models import CorrelationStatus
from app.correlation.persistence import (
    CorrelationEvidenceError,
    CorrelationPersistenceRequest,
    ParentSelection,
    persist_correlation_finding,
)
from app.correlation.profile import load_correlation_profile
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.evidence.schemas import EvidenceIngestRequest, EvidenceProvenance, OilGasTelemetryPayloadV2
from app.evidence.service import get_evidence, ingest_evidence, verify_record_integrity
from app.protocols.adapters import persist_raw_event, persist_semantic_evidence
from app.protocols.profile import load_profile
from tests.integration.test_evidence_persistence import evidence_settings
from tests.integration.test_migrations import alembic_config


@pytest.fixture(autouse=True)
def migrated_clean_correlation_database() -> None:
    command.upgrade(alembic_config(), "head")
    with engine_for(evidence_settings()).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)


def _selection(record: EvidenceRecord) -> ParentSelection:
    return ParentSelection(
        evidence_id=record.evidence_id,
        expected_integrity_sha256=record.integrity_sha256,
    )


def _persist_telemetry(number: int, *, complete_late: bool = False) -> tuple[ParentSelection, ...]:
    fixture, _ = load_fixture(f"p6b-f{number:03d}.json")
    request = build_fixture_input(fixture, load_correlation_profile(), complete_late=complete_late)
    result: list[ParentSelection] = []
    for item in request.telemetry:
        envelope = EvidenceIngestRequest(
            source_key="simulator-primary",
            source_event_id=f"p6b:{fixture.catalog_id}:{item.sequence_number}",
            evidence_type="simulator_telemetry",
            observed_at=item.observed_at,
            sequence_number=item.sequence_number,
            payload_schema="otsoc.simulator.telemetry",
            payload_schema_version="2.0.0",
            payload=OilGasTelemetryPayloadV2.model_validate(item.payload.model_dump()),
            provenance=EvidenceProvenance(
                producer="otsoc_simulator",
                producer_version="3.0.0",
                domain="oil_gas_transfer",
                simulation_id=item.payload.simulation_id,
                configuration_hash=item.payload.configuration_hash,
                seed=20260809,
            ),
        )
        with session_scope(evidence_settings()) as session:
            receipt = ingest_evidence(session, envelope)
            record = session.get(EvidenceRecord, receipt.evidence_id)
            assert record is not None
            result.append(_selection(record))
    return tuple(result)


def _persist_s3_parents() -> tuple[ParentSelection, ParentSelection, ParentSelection]:
    fixture, fixture_bytes = load_context_fixture("s3_hmi_approved_valve_command.json")
    protocol = load_profile()
    inventory = load_inventory_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=protocol)
    with session_scope(evidence_settings()) as session:
        raw = persist_raw_event(session, fixture.event, fixture_bytes=fixture_bytes)
    with session_scope(evidence_settings()) as session:
        semantic, _ = persist_semantic_evidence(session, raw.evidence_id, protocol)
    with session_scope(evidence_settings()) as session:
        workflow = persist_asset_context_and_finding(
            session,
            semantic.evidence_id,
            inventory,
            policy,
            source_claims=fixture.source_identity_claims,
            destination_claims=fixture.destination_identity_claims,
        )
        semantic_record = session.get(EvidenceRecord, semantic.evidence_id)
        context_record = session.get(EvidenceRecord, workflow.context_receipt.evidence_id)
        policy_record = session.get(EvidenceRecord, workflow.finding_receipt.evidence_id)
        assert (
            semantic_record is not None and context_record is not None and policy_record is not None
        )
        return _selection(semantic_record), _selection(context_record), _selection(policy_record)


def _s3_request(number: int = 5, *, complete_late: bool = False) -> CorrelationPersistenceRequest:
    semantic, context, policy = _persist_s3_parents()
    return CorrelationPersistenceRequest(
        rule_id="CPR-S3-CV-TRANSFER-001",
        semantic_parent=semantic,
        asset_context_parent=context,
        policy_parent=policy,
        telemetry_parents=_persist_telemetry(number, complete_late=complete_late),
    )


@pytest.mark.integration
def test_correlation_insert_parent_link_and_read_union() -> None:
    request = _s3_request()
    with session_scope(evidence_settings()) as session:
        result = persist_correlation_finding(session, request)
        record = session.get(EvidenceRecord, result.receipt.evidence_id)
        assert record is not None and verify_record_integrity(record) is True
        assert result.finding.correlation_status is CorrelationStatus.CORRELATED
        response = get_evidence(session, result.receipt.evidence_id)
        assert response is not None and response.evidence_type == "correlation_finding"
        assert len(result.finding.telemetry_parents) == len(request.telemetry_parents)


@pytest.mark.integration
def test_correlation_retry_idempotency() -> None:
    request = _s3_request()
    with session_scope(evidence_settings()) as session:
        first = persist_correlation_finding(session, request)
    with session_scope(evidence_settings()) as session:
        second = persist_correlation_finding(session, request)
    assert first.receipt.status == "accepted"
    assert second.receipt.status == "duplicate_existing"
    assert first.receipt.evidence_id == second.receipt.evidence_id


@pytest.mark.integration
def test_correlation_concurrent_duplicates() -> None:
    request = _s3_request()

    def submit() -> str:
        with session_scope(evidence_settings()) as session:
            return persist_correlation_finding(session, request).receipt.status

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(lambda _: submit(), range(8)))
    assert statuses.count("accepted") == 1
    assert statuses.count("duplicate_existing") == 7
    with session_scope(evidence_settings()) as session:
        count = session.scalar(
            select(func.count())
            .select_from(EvidenceRecord)
            .where(EvidenceRecord.evidence_type == "correlation_finding")
        )
        assert count == 1


@pytest.mark.integration
def test_correlation_parent_hash_substitution_fails_closed() -> None:
    request = _s3_request()
    assert request.semantic_parent is not None
    changed = request.model_copy(
        update={
            "semantic_parent": request.semantic_parent.model_copy(
                update={"expected_integrity_sha256": "0" * 64}
            )
        }
    )
    with pytest.raises(CorrelationEvidenceError), session_scope(evidence_settings()) as session:
        persist_correlation_finding(session, changed)


@pytest.mark.integration
def test_correlation_evidence_is_append_only() -> None:
    request = _s3_request()
    with session_scope(evidence_settings()) as session:
        result = persist_correlation_finding(session, request)
    with pytest.raises(DBAPIError), session_scope(evidence_settings()) as session:
        session.execute(
            text("UPDATE evidence_records SET source_event_id='changed' WHERE evidence_id=:id"),
            {"id": result.receipt.evidence_id},
        )


@pytest.mark.integration
def test_late_re_evaluation_preserves_prior_finding() -> None:
    initial_request = _s3_request(14, complete_late=False)
    with session_scope(evidence_settings()) as session:
        initial = persist_correlation_finding(session, initial_request)
    assert initial.finding.correlation_status is CorrelationStatus.INSUFFICIENT_EVIDENCE
    with session_scope(evidence_settings()) as session:
        initial_record = session.get(EvidenceRecord, initial.receipt.evidence_id)
        assert initial_record is not None
        before = (dict(initial_record.payload), initial_record.integrity_sha256)
        previous = _selection(initial_record)
    complete_request = _s3_request(14, complete_late=True).model_copy(
        update={"reevaluates_parent": previous}
    )
    with session_scope(evidence_settings()) as session:
        later = persist_correlation_finding(session, complete_request)
        old = session.get(EvidenceRecord, initial.receipt.evidence_id)
        assert old is not None
        assert (dict(old.payload), old.integrity_sha256) == before
    assert later.finding.correlation_status is CorrelationStatus.CORRELATED
    assert later.finding.reevaluates_finding_id == initial.receipt.evidence_id


@pytest.mark.integration
def test_s4_persists_without_cyber_parent() -> None:
    request = CorrelationPersistenceRequest(
        rule_id="CPR-S4-PUMP-FLOW-001",
        telemetry_parents=_persist_telemetry(8),
    )
    with session_scope(evidence_settings()) as session:
        result = persist_correlation_finding(session, request)
    assert result.finding.correlation_status is CorrelationStatus.CORRELATED
    assert result.finding.primary_cyber_evidence_id is None
    assert result.finding.cyber_cause_asserted is False
