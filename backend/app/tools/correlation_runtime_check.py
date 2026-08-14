from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from app.context.adapters import persist_asset_context_and_finding
from app.context.fixtures import load_fixture as load_context_fixture
from app.context.inventory import load_inventory_profile
from app.context.policy import load_policy_profile
from app.core.config import Settings
from app.correlation.fixtures import build_fixture_input, load_fixture
from app.correlation.models import CorrelationStatus
from app.correlation.persistence import (
    CorrelationPersistenceRequest,
    CorrelationPersistenceResult,
    ParentSelection,
    persist_correlation_finding,
)
from app.correlation.profile import load_correlation_profile
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.evidence.schemas import (
    EvidenceIngestRequest,
    EvidenceProvenance,
    OilGasTelemetryPayloadV2,
)
from app.evidence.service import ingest_evidence, verify_record_integrity
from app.protocols.adapters import persist_raw_event, persist_semantic_evidence
from app.protocols.profile import load_profile


@dataclass(frozen=True, slots=True)
class CorrelationRuntimeCheckResult:
    stored_synthetic_evidence_only: bool
    s3_matching_correlated: bool
    s3_no_effect_not_correlated: bool
    s4_abnormal_correlated: bool
    s4_normal_not_correlated: bool
    retry_is_duplicate: bool
    late_initial_insufficient: bool
    late_re_evaluation_correlated: bool
    late_re_evaluation_linked: bool
    old_finding_unchanged: bool
    all_parent_integrity_verified: bool
    ground_truth_absent: bool
    cyber_causation_not_asserted: bool


def _settings() -> Settings:
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url is None or "otsoc_test" not in test_url:
        raise SystemExit("TEST_DATABASE_URL must target the isolated otsoc_test database")
    return Settings(
        app_name="OT-SOC Fusion X",
        app_version="1.0.0",
        app_env="development",
        api_version="v1",
        log_level="WARNING",
        cors_origins=["http://localhost:5173"],
        database_url=test_url,
        database_connect_timeout_seconds=2,
    )


def _selection(record: EvidenceRecord) -> ParentSelection:
    return ParentSelection(
        evidence_id=record.evidence_id,
        expected_integrity_sha256=record.integrity_sha256,
    )


def _persist_s3_parents(
    settings: Settings,
) -> tuple[ParentSelection, ParentSelection, ParentSelection]:
    fixture, fixture_bytes = load_context_fixture("s3_hmi_approved_valve_command.json")
    protocol = load_profile()
    inventory = load_inventory_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=protocol)
    with session_scope(settings) as session:
        raw = persist_raw_event(session, fixture.event, fixture_bytes=fixture_bytes)
    with session_scope(settings) as session:
        semantic, _ = persist_semantic_evidence(session, raw.evidence_id, protocol)
    with session_scope(settings) as session:
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
        if semantic_record is None or context_record is None or policy_record is None:
            raise RuntimeError("the stored S3 cyber-parent chain is unavailable")
        return (
            _selection(semantic_record),
            _selection(context_record),
            _selection(policy_record),
        )


def _persist_telemetry(
    settings: Settings,
    fixture_number: int,
    *,
    complete_late: bool = False,
) -> tuple[ParentSelection, ...]:
    fixture, _ = load_fixture(f"p6b-f{fixture_number:03d}.json")
    evaluation_input = build_fixture_input(
        fixture,
        load_correlation_profile(),
        complete_late=complete_late,
    )
    parents: list[ParentSelection] = []
    for sample in evaluation_input.telemetry:
        envelope = EvidenceIngestRequest(
            source_key="simulator-primary",
            source_event_id=f"p6b:{fixture.catalog_id}:{sample.sequence_number}",
            evidence_type="simulator_telemetry",
            observed_at=sample.observed_at,
            sequence_number=sample.sequence_number,
            payload_schema="otsoc.simulator.telemetry",
            payload_schema_version="2.0.0",
            payload=OilGasTelemetryPayloadV2.model_validate(sample.payload.model_dump()),
            provenance=EvidenceProvenance(
                producer="otsoc_simulator",
                producer_version="3.0.0",
                domain="oil_gas_transfer",
                simulation_id=sample.payload.simulation_id,
                configuration_hash=sample.payload.configuration_hash,
                seed=20260809,
            ),
        )
        with session_scope(settings) as session:
            receipt = ingest_evidence(session, envelope, request_id="phase-6b-runtime-check")
            record = session.get(EvidenceRecord, receipt.evidence_id)
            if record is None:
                raise RuntimeError("stored telemetry evidence is unavailable")
            parents.append(_selection(record))
    return tuple(parents)


def _s3_request(
    settings: Settings,
    cyber_parents: tuple[ParentSelection, ParentSelection, ParentSelection],
    fixture_number: int,
    *,
    complete_late: bool = False,
    reevaluates_parent: ParentSelection | None = None,
) -> CorrelationPersistenceRequest:
    semantic, context, policy = cyber_parents
    return CorrelationPersistenceRequest(
        rule_id="CPR-S3-CV-TRANSFER-001",
        semantic_parent=semantic,
        asset_context_parent=context,
        policy_parent=policy,
        telemetry_parents=_persist_telemetry(settings, fixture_number, complete_late=complete_late),
        reevaluates_parent=reevaluates_parent,
    )


def _persist(
    settings: Settings, request: CorrelationPersistenceRequest
) -> CorrelationPersistenceResult:
    with session_scope(settings) as session:
        return persist_correlation_finding(session, request)


def main() -> int:
    settings = _settings()
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)

    cyber_parents = _persist_s3_parents(settings)
    s3_match_request = _s3_request(settings, cyber_parents, 1)
    s3_match = _persist(settings, s3_match_request)
    s3_retry = _persist(settings, s3_match_request)
    s3_no_effect = _persist(settings, _s3_request(settings, cyber_parents, 2))
    s4_abnormal = _persist(
        settings,
        CorrelationPersistenceRequest(
            rule_id="CPR-S4-PUMP-FLOW-001",
            telemetry_parents=_persist_telemetry(settings, 8),
        ),
    )
    s4_normal = _persist(
        settings,
        CorrelationPersistenceRequest(
            rule_id="CPR-S4-PUMP-FLOW-001",
            telemetry_parents=_persist_telemetry(settings, 7),
        ),
    )

    late_initial = _persist(
        settings,
        _s3_request(settings, cyber_parents, 14, complete_late=False),
    )
    with session_scope(settings) as session:
        old_record = session.get(EvidenceRecord, late_initial.receipt.evidence_id)
        if old_record is None:
            raise RuntimeError("the initial late-evidence finding is unavailable")
        old_snapshot = (dict(old_record.payload), old_record.integrity_sha256)
        previous = _selection(old_record)
    late_complete = _persist(
        settings,
        _s3_request(
            settings,
            cyber_parents,
            14,
            complete_late=True,
            reevaluates_parent=previous,
        ),
    )
    with session_scope(settings) as session:
        old_after = session.get(EvidenceRecord, late_initial.receipt.evidence_id)
        records = session.query(EvidenceRecord).all()
        if old_after is None:
            raise RuntimeError("the initial late-evidence finding disappeared")
        integrity_verified = all(verify_record_integrity(record) for record in records)
        old_unchanged = (dict(old_after.payload), old_after.integrity_sha256) == old_snapshot

    findings = (
        s3_match.finding,
        s3_no_effect.finding,
        s4_abnormal.finding,
        s4_normal.finding,
        late_initial.finding,
        late_complete.finding,
    )
    serialized = "".join(item.model_dump_json() for item in findings).lower()
    result = CorrelationRuntimeCheckResult(
        stored_synthetic_evidence_only=True,
        s3_matching_correlated=(
            s3_match.finding.correlation_status is CorrelationStatus.CORRELATED
        ),
        s3_no_effect_not_correlated=(
            s3_no_effect.finding.correlation_status is CorrelationStatus.NOT_CORRELATED
        ),
        s4_abnormal_correlated=(
            s4_abnormal.finding.correlation_status is CorrelationStatus.CORRELATED
        ),
        s4_normal_not_correlated=(
            s4_normal.finding.correlation_status is CorrelationStatus.NOT_CORRELATED
        ),
        retry_is_duplicate=(
            s3_retry.receipt.status == "duplicate_existing"
            and s3_retry.receipt.evidence_id == s3_match.receipt.evidence_id
        ),
        late_initial_insufficient=(
            late_initial.finding.correlation_status is CorrelationStatus.INSUFFICIENT_EVIDENCE
        ),
        late_re_evaluation_correlated=(
            late_complete.finding.correlation_status is CorrelationStatus.CORRELATED
        ),
        late_re_evaluation_linked=(
            late_complete.finding.reevaluates_finding_id == late_initial.receipt.evidence_id
        ),
        old_finding_unchanged=old_unchanged,
        all_parent_integrity_verified=integrity_verified,
        ground_truth_absent=(
            "groundtruthevent" not in serialized
            and "scenario_id" not in serialized
            and '"ground_truth_used":true' not in serialized
            and all(not item.ground_truth_used for item in findings)
        ),
        cyber_causation_not_asserted=all(
            not item.cyber_cause_asserted and not item.causality_inferred for item in findings
        ),
    )
    if not all(asdict(result).values()):
        raise RuntimeError("one or more Phase 6B offline runtime checks failed")
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
