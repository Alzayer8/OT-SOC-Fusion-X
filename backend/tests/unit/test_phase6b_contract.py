from __future__ import annotations

import json
import os
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.context.inventory import EXPECTED_INVENTORY_SHA256, load_inventory_profile
from app.context.policy import EXPECTED_POLICY_SHA256, load_policy_profile
from app.correlation.baseline import arithmetic_mean, endpoint_slope
from app.correlation.canonical import (
    canonical_model_bytes,
    canonical_profile_bytes,
    deterministic_correlation_source_event_id,
    sha256_hex,
)
from app.correlation.evaluator import evaluate_correlation
from app.correlation.fixtures import build_fixture_input, load_fixture, verify_fixture_set
from app.correlation.models import (
    CorrelationEvaluationInput,
    CorrelationReasonCode,
    CorrelationStatus,
    EvidenceParentReference,
    ProcessChange,
    TelemetryEvidence,
)
from app.correlation.persistence import (
    CorrelationEvidenceError,
    ParentSelection,
    _verified_selection,
)
from app.correlation.process import classify_delta
from app.correlation.profile import (
    EXPECTED_CORRELATION_PROFILE_SHA256,
    CorrelationProfileError,
    load_correlation_profile,
    parse_correlation_profile_bytes,
)
from app.correlation.temporal import select_window
from app.protocols.decoder import decode_event
from app.protocols.fixtures import load_fixture as load_protocol_fixture
from app.protocols.profile import EXPECTED_PROFILE_SHA256, load_profile
from app.simulation import OilGasTransferSimulator, SimulationConfig

PROJECT_ROOT = Path(os.environ.get("OTSOC_REPOSITORY_ROOT", Path(__file__).resolve().parents[3]))
CORRELATION_ROOT = PROJECT_ROOT / "backend" / "app" / "correlation"


def _request(number: int, *, complete_late: bool = False) -> CorrelationEvaluationInput:
    fixture, _ = load_fixture(f"p6b-f{number:03d}.json")
    profile = load_correlation_profile()
    return build_fixture_input(fixture, profile, complete_late=complete_late)


def _result(number: int, *, complete_late: bool = False):  # type: ignore[no-untyped-def]
    profile = load_correlation_profile()
    return evaluate_correlation(_request(number, complete_late=complete_late), profile)


def _replace_payload(item: TelemetryEvidence, **changes: object) -> TelemetryEvidence:
    return item.model_copy(update={"payload": item.payload.model_copy(update=changes)})


def test_p6b_t001_correlation_profile_load() -> None:
    loaded = load_correlation_profile()
    assert loaded.profile.profile_id == "otsoc.correlation.oil_gas_transfer"
    document = loaded.profile.model_dump(mode="json")
    document["unexpected"] = True
    with pytest.raises(CorrelationProfileError):
        parse_correlation_profile_bytes(json.dumps(document).encode())
    for field, value in (
        ("point_ids", ["unknown_process_point"]),
        (
            "relationships",
            [
                {
                    "source_asset_key": "PLC-01",
                    "relationship_type": "CONTROLS",
                    "target_asset_key": "OTHER",
                }
            ],
        ),
    ):
        changed = loaded.profile.model_dump(mode="json")
        changed["rules"][0][field] = value
        with pytest.raises(CorrelationProfileError):
            parse_correlation_profile_bytes(json.dumps(changed).encode())
    changed = loaded.profile.model_dump(mode="json")
    changed["rules"][0]["thresholds"]["flow_decrease_m3h"] = 0.6
    with pytest.raises(CorrelationProfileError):
        parse_correlation_profile_bytes(json.dumps(changed).encode())


def test_p6b_t002_deterministic_profile_digest() -> None:
    loaded = load_correlation_profile()
    reordered = loaded.profile.model_copy(
        update={
            "statuses": tuple(reversed(loaded.profile.statuses)),
            "rules": tuple(reversed(loaded.profile.rules)),
        }
    )
    assert sha256_hex(canonical_profile_bytes(reordered)) == loaded.sha256
    assert loaded.sha256 == EXPECTED_CORRELATION_PROFILE_SHA256


def test_p6b_t003_s3_cyber_parent_linkage() -> None:
    finding = _result(5).finding
    assert finding.primary_cyber_evidence_id is not None
    assert finding.semantic_evidence_id is not None
    assert finding.asset_context_evidence_id is not None
    assert finding.policy_finding_evidence_id is not None


def test_p6b_t004_telemetry_parent_linkage() -> None:
    request = _request(1)
    finding = _result(1).finding
    assert {item.evidence_id for item in finding.telemetry_parents} == {
        item.evidence_id for item in request.telemetry
    }
    assert all(item.integrity_sha256 for item in finding.telemetry_parents)


def test_p6b_t005_asset_relationship_validation() -> None:
    request = _request(1)
    assert request.cyber_context is not None
    changed = request.cyber_context.model_copy(update={"controller_asset_key": "OTHER"})
    finding = evaluate_correlation(
        request.model_copy(update={"cyber_context": changed}), load_correlation_profile()
    ).finding
    assert finding.reason_code is CorrelationReasonCode.ASSET_RELATION_MISMATCH


def test_p6b_t006_run_id_consistency() -> None:
    finding = _result(10).finding
    assert (finding.correlation_status, finding.reason_code) == (
        CorrelationStatus.INDETERMINATE,
        CorrelationReasonCode.RUN_ID_MISMATCH,
    )


def test_p6b_t007_configuration_hash_consistency() -> None:
    finding = _result(11).finding
    assert (finding.correlation_status, finding.reason_code) == (
        CorrelationStatus.INDETERMINATE,
        CorrelationReasonCode.CONFIGURATION_MISMATCH,
    )


def test_p6b_t008_deterministic_time_window_selection() -> None:
    canonical = _result(1).finding
    shuffled = _result(12).finding
    assert shuffled.correlation_id == canonical.correlation_id
    assert shuffled.model_dump() == canonical.model_dump()


def test_p6b_t009_boundary_timestamp_inclusion() -> None:
    request = _request(1)
    anchor = request.cyber_context.command_observed_at  # type: ignore[union-attr]
    selection = select_window(
        request.telemetry,
        anchor=anchor,
        baseline_seconds=10,
        effect_seconds=30,
        maximum_gap_seconds=2,
    )
    assert selection.baseline[0].observed_at == anchor - timedelta(seconds=10)
    assert selection.baseline[-1].observed_at == anchor - timedelta(seconds=1)
    assert selection.effect[0].observed_at == anchor
    assert selection.effect[-1].observed_at == anchor + timedelta(seconds=30)


def test_p6b_t010_out_of_window_exclusion() -> None:
    finding = _result(3).finding
    assert finding.reason_code is CorrelationReasonCode.PROCESS_CHANGE_OUTSIDE_WINDOW
    assert finding.correlation_status is CorrelationStatus.NOT_CORRELATED


def test_p6b_t011_deterministic_baseline_calculation() -> None:
    request = _request(1)
    anchor = request.cyber_context.command_observed_at  # type: ignore[union-attr]
    baseline = tuple(item for item in request.telemetry if item.observed_at < anchor)
    assert arithmetic_mean(baseline, lambda item: item.payload.pipeline_flow_rate_m3h) == 4.0
    source_slope = endpoint_slope(baseline, lambda item: item.payload.source_tank_level_percent)
    assert source_slope == pytest.approx(-0.0001)


def test_p6b_t012_flow_decrease_detection() -> None:
    observation = next(
        item
        for item in _result(1).finding.observations
        if item.point_id == "pipeline_flow_rate_m3h"
    )
    assert observation.condition_met is True
    assert observation.observed_direction is ProcessChange.DECREASED
    assert observation.persistence_observed >= 5


def test_p6b_t013_pressure_change_detection() -> None:
    observation = next(
        item for item in _result(1).finding.observations if item.point_id == "pipeline_pressure_bar"
    )
    assert observation.condition_met is True
    assert observation.observed_direction is ProcessChange.INCREASED


def test_p6b_t014_inventory_change_detection() -> None:
    inventory = [
        item
        for item in _result(1).finding.observations
        if item.point_id in {"source_tank_level_percent", "receiving_tank_level_percent"}
    ]
    assert len(inventory) == 2
    assert all(item.condition_met for item in inventory)


def test_p6b_t015_no_change_result() -> None:
    finding = _result(2).finding
    assert (finding.correlation_status, finding.reason_code) == (
        CorrelationStatus.NOT_CORRELATED,
        CorrelationReasonCode.NO_PROCESS_CHANGE,
    )


def test_p6b_t016_missing_telemetry_result() -> None:
    finding = _result(9).finding
    assert (finding.correlation_status, finding.reason_code) == (
        CorrelationStatus.INSUFFICIENT_EVIDENCE,
        CorrelationReasonCode.MISSING_TELEMETRY,
    )


def test_p6b_t017_insufficient_sample_result() -> None:
    request = _request(1)
    anchor = request.cyber_context.command_observed_at  # type: ignore[union-attr]
    sparse = tuple(
        item for item in request.telemetry if item.observed_at >= anchor - timedelta(seconds=7)
    )
    finding = evaluate_correlation(
        request.model_copy(update={"telemetry": sparse}), load_correlation_profile()
    ).finding
    assert finding.reason_code is CorrelationReasonCode.INSUFFICIENT_SAMPLES
    gapped = tuple(
        item
        for item in request.telemetry
        if item.observed_at not in {anchor + timedelta(seconds=5), anchor + timedelta(seconds=6)}
    )
    gap_finding = evaluate_correlation(
        request.model_copy(update={"telemetry": gapped}), load_correlation_profile()
    ).finding
    assert gap_finding.reason_code is CorrelationReasonCode.TELEMETRY_GAP_EXCEEDED


def test_p6b_t018_s3_correlated_result() -> None:
    finding = _result(1).finding
    assert (finding.correlation_status, finding.reason_code) == (
        CorrelationStatus.CORRELATED,
        CorrelationReasonCode.CORRELATION_MATCH,
    )


def test_p6b_t019_s3_not_correlated_result() -> None:
    assert _result(2).finding.correlation_status is CorrelationStatus.NOT_CORRELATED


def test_p6b_t020_s3_insufficient_result() -> None:
    assert _result(9).finding.correlation_status is CorrelationStatus.INSUFFICIENT_EVIDENCE


def test_p6b_t021_s4_pump_running_zero_flow_result() -> None:
    finding = _result(6).finding
    assert finding.reason_code is CorrelationReasonCode.MISSING_TELEMETRY


def test_p6b_t022_s4_normal_flow_negative_result() -> None:
    finding = _result(7).finding
    assert (finding.correlation_status, finding.reason_code) == (
        CorrelationStatus.NOT_CORRELATED,
        CorrelationReasonCode.NO_PROCESS_CHANGE,
    )


def test_p6b_t023_s4_pressure_consistency() -> None:
    request = _request(8)
    changed = tuple(
        _replace_payload(item, pipeline_pressure_bar=1.2)
        if item.observed_at >= request.telemetry[10].observed_at
        else item
        for item in request.telemetry
    )
    finding = evaluate_correlation(
        request.model_copy(update={"telemetry": changed}), load_correlation_profile()
    ).finding
    assert finding.reason_code is CorrelationReasonCode.PROCESS_EFFECT_DIRECTION_MISMATCH


def test_p6b_t024_s4_inventory_consistency() -> None:
    request = _request(8)
    anchor = request.telemetry[10].observed_at
    changed = tuple(
        _replace_payload(
            item,
            source_tank_level_percent=72.0 - (item.observed_at - anchor).total_seconds() * 0.001,
            receiving_tank_level_percent=18.0 + (item.observed_at - anchor).total_seconds() * 0.001,
        )
        if item.observed_at >= anchor
        else item
        for item in request.telemetry
    )
    finding = evaluate_correlation(
        request.model_copy(update={"telemetry": changed}), load_correlation_profile()
    ).finding
    assert finding.reason_code is CorrelationReasonCode.PROCESS_EFFECT_DIRECTION_MISMATCH


def test_p6b_t025_no_cyber_cause_invention_for_s4() -> None:
    finding = _result(8).finding
    assert finding.primary_cyber_evidence_id is None
    assert finding.policy_finding_evidence_id is None
    assert finding.cyber_cause_asserted is False


def test_p6b_t026_policy_context_retained() -> None:
    assert _result(4).finding.policy_context_status == "DENIED"
    assert _result(5).finding.policy_context_status == "APPROVED"
    assert _result(1).finding.policy_context_status == "UNAVAILABLE"


def test_p6b_t027_approved_policy_does_not_suppress_physical_effect() -> None:
    assert _result(5).finding.correlation_status is CorrelationStatus.CORRELATED


def test_p6b_t028_denied_policy_does_not_manufacture_physical_effect() -> None:
    request = _request(2)
    denied = _request(4).cyber_context
    finding = evaluate_correlation(
        request.model_copy(update={"cyber_context": denied}), load_correlation_profile()
    ).finding
    assert finding.correlation_status is CorrelationStatus.NOT_CORRELATED


def test_p6b_t029_ground_truth_not_used() -> None:
    document = _request(1).model_dump(mode="json")
    document["ground_truth"] = "contradictory"
    with pytest.raises(ValidationError):
        CorrelationEvaluationInput.model_validate(document)
    source = "\n".join(path.read_text("utf-8") for path in CORRELATION_ROOT.glob("*.py"))
    assert "GroundTruthEvent" not in source and "scenario_id" not in source
    assert _result(1).finding.ground_truth_used is False


def test_p6b_t030_wording_avoids_causality_overclaim() -> None:
    prohibited = {"caused", "attack", "attacker", "malicious", "compromised"}
    for number in (1, 8):
        statement = _result(number).finding.analyst_readable_explanation.lower().split()
        words = {word.strip(".,:;!?()[]") for word in statement}
        assert not words & prohibited


def test_p6b_t031_deterministic_reason_code_precedence() -> None:
    request = _request(10)
    changed = tuple(
        _replace_payload(item, configuration_hash="c" * 64) if index % 2 else item
        for index, item in enumerate(request.telemetry)
    )
    finding = evaluate_correlation(
        request.model_copy(update={"telemetry": changed}), load_correlation_profile()
    ).finding
    assert finding.reason_code is CorrelationReasonCode.RUN_ID_MISMATCH


def test_p6b_t032_deterministic_derivative_identity() -> None:
    assert _result(1).finding.correlation_id == _result(1).finding.correlation_id


def test_p6b_t033_canonical_parent_ordering() -> None:
    assert _result(12).finding.parent_set_sha256 == _result(1).finding.parent_set_sha256


def test_p6b_t034_duplicate_idempotency() -> None:
    assert _result(13).finding.correlation_id == _result(1).finding.correlation_id


def test_p6b_t035_concurrent_duplicate_behavior() -> None:
    with ThreadPoolExecutor(max_workers=8) as executor:
        identities = list(executor.map(lambda _: _result(1).finding.correlation_id, range(8)))
    assert len(set(identities)) == 1


def test_p6b_t036_late_evidence_re_evaluation() -> None:
    profile = load_correlation_profile()
    initial = _result(14)
    parent = EvidenceParentReference(
        evidence_id=initial.finding.correlation_id,
        evidence_type="correlation_finding",
        integrity_sha256=sha256_hex(canonical_model_bytes(initial.finding)),
        observed_at=initial.finding.evidence_observed_at,
        sequence_number=110,
    )
    fixture, _ = load_fixture("p6b-f014.json")
    complete = build_fixture_input(fixture, profile, complete_late=True, reevaluates_parent=parent)
    later = evaluate_correlation(complete, profile).finding
    assert initial.finding.correlation_status is CorrelationStatus.INSUFFICIENT_EVIDENCE
    assert later.correlation_status is CorrelationStatus.CORRELATED
    assert later.reevaluates_finding_id == initial.finding.correlation_id


def test_p6b_t037_prior_finding_remains_immutable() -> None:
    initial = _result(14)
    before = initial.finding.model_dump_json()
    test_p6b_t036_late_evidence_re_evaluation()
    assert initial.finding.model_dump_json() == before


def test_p6b_t038_profile_version_isolation() -> None:
    values = {
        "profile_id": "otsoc.correlation.oil_gas_transfer",
        "profile_sha256": EXPECTED_CORRELATION_PROFILE_SHA256,
        "rule_id": "CPR-S3-CV-TRANSFER-001",
        "rule_version": "1.0.0",
        "evaluator_version": "1.0.0",
        "simulation_id": "sim-phase6b-primary",
        "configuration_hash": "a" * 64,
        "anchor_time": "2026-01-01T01:04:00+00:00",
        "parent_digest": "b" * 64,
        "finding_schema_version": "1.0.0",
    }
    old = deterministic_correlation_source_event_id(**values, profile_version="1.0.0")
    new = deterministic_correlation_source_event_id(**values, profile_version="1.0.1")
    assert old != new


def test_p6b_t039_process_point_mismatch() -> None:
    assert _result(15).finding.reason_code is CorrelationReasonCode.POINT_RELATION_NOT_DEFINED


def test_p6b_t040_unsupported_correlation_rule() -> None:
    request = _request(1).model_copy(update={"rule_id": "CPR-UNKNOWN-001"})
    finding = evaluate_correlation(request, load_correlation_profile()).finding
    assert finding.reason_code is CorrelationReasonCode.UNSUPPORTED_CORRELATION_RULE


def test_p6b_t041_evidence_hash_substitution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = SimpleNamespace(
        evidence_id=uuid.uuid4(),
        evidence_type="asset_context_event",
        integrity_sha256="1" * 64,
    )
    session = SimpleNamespace(scalar=lambda statement: record)
    monkeypatch.setattr("app.correlation.persistence.verify_record_integrity", lambda item: True)
    selection = ParentSelection(evidence_id=record.evidence_id, expected_integrity_sha256="0" * 64)
    with pytest.raises(CorrelationEvidenceError):
        _verified_selection(session, selection, "asset_context_event")  # type: ignore[arg-type]


def test_p6b_t042_semantic_parent_substitution_failure() -> None:
    source = (CORRELATION_ROOT / "persistence.py").read_text("utf-8")
    assert "context.semantic_event_id != semantic_record.evidence_id" in source
    assert "semantic.source_evidence_integrity_sha256" in source


def test_p6b_t043_telemetry_parent_substitution_failure() -> None:
    source = (CORRELATION_ROOT / "persistence.py").read_text("utf-8")
    assert '_verified_selection(session, item, "simulator_telemetry")' in source
    assert "record.integrity_sha256 != selection.expected_integrity_sha256" in source


def test_p6b_t044_no_simulator_coupling() -> None:
    source = "\n".join(path.read_text("utf-8") for path in CORRELATION_ROOT.glob("*.py"))
    assert "app.simulation" not in source
    assert "OilGasTransferSimulator" not in source


def test_p6b_t045_no_networking(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def blocked_socket(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("correlation attempted socket creation")

    monkeypatch.setattr(socket, "socket", blocked_socket)
    assert _result(1).finding.correlation_status is CorrelationStatus.CORRELATED
    source = "\n".join(path.read_text("utf-8").lower() for path in CORRELATION_ROOT.glob("*.py"))
    assert "import socket" not in source and "import requests" not in source
    assert calls == 0


def test_p6b_t046_no_incident_creation() -> None:
    fields = type(_result(1).finding).model_fields
    assert "incident_id" not in fields and "severity" not in fields
    assert "assignee" not in fields and "containment" not in fields


def test_p6b_t047_no_risk_scoring() -> None:
    fields = type(_result(1).finding).model_fields
    assert "risk_score" not in fields and "confidence" not in fields


def test_p6b_t048_phase5_regression() -> None:
    inventory = load_inventory_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=load_profile())
    assert inventory.sha256 == EXPECTED_INVENTORY_SHA256
    assert policy.sha256 == EXPECTED_POLICY_SHA256
    assert len(inventory.profile.assets) == 11 and len(inventory.profile.zones) == 5


def test_p6b_t049_phase4_regression() -> None:
    protocol = load_profile()
    event, _ = load_protocol_fixture("p4b-s3-valve-command-25.json")
    semantic = decode_event(
        event,
        protocol,
        semantic_event_id=uuid.uuid4(),
        source_evidence_id=uuid.uuid4(),
        source_evidence_integrity_sha256="1" * 64,
        created_at=event.observed_at,
    )
    assert protocol.sha256 == EXPECTED_PROFILE_SHA256
    assert len(protocol.profile.points) == 9
    assert str(semantic.decoded_value) == "25.0"


def test_p6b_t050_phase36_simulator_regression() -> None:
    simulator = OilGasTransferSimulator(SimulationConfig(duration_seconds=2))
    first = simulator.step().telemetry
    simulator.reset()
    assert simulator.step().telemetry == first
    assert (
        classify_delta(-1.0, deadband=0.1, increase_threshold=0.5, decrease_threshold=0.5)
        is ProcessChange.DECREASED
    )
    assert len(verify_fixture_set(load_correlation_profile()).fixtures) == 15
