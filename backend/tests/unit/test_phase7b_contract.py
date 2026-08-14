from __future__ import annotations

import json
import os
import re
import socket
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.context.inventory import EXPECTED_INVENTORY_SHA256, load_inventory_profile
from app.context.policy import EXPECTED_POLICY_SHA256, load_policy_profile
from app.correlation.profile import (
    EXPECTED_CORRELATION_PROFILE_SHA256,
    load_correlation_profile,
)
from app.evidence.canonical import (
    canonical_evidence_bytes,
    deterministic_evidence_id,
    integrity_sha256,
)
from app.incidents.canonical import canonical_profile_bytes, sha256_hex
from app.incidents.fixtures import verify_fixture_set
from app.incidents.grouping import grouping_epoch_start
from app.incidents.identity import deterministic_incident_identity
from app.incidents.models import (
    CandidateMembership,
    EvidenceRole,
    IncidentCategory,
    IncidentQualificationRequest,
    IncidentSeverity,
    IncidentStatus,
    QualifiedIncidentCandidate,
)
from app.incidents.profile import (
    EXPECTED_INCIDENT_PROFILE_SHA256,
    IncidentProfileError,
    load_incident_profile,
    parse_incident_profile_bytes,
)
from app.incidents.severity import SEVERITY_RANK
from app.protocols.decoder import decode_event
from app.protocols.fixtures import load_fixture as load_protocol_fixture
from app.protocols.profile import EXPECTED_PROFILE_SHA256, load_profile
from app.simulation import OilGasTransferSimulator, SimulationConfig
from tests.evidence_helpers import sample_evidence_request

PROJECT_ROOT = Path(os.environ.get("OTSOC_REPOSITORY_ROOT", Path(__file__).resolve().parents[3]))
INCIDENT_ROOT = PROJECT_ROOT / "backend" / "app" / "incidents"


def _candidate() -> QualifiedIncidentCandidate:
    observed = datetime(2026, 1, 1, 0, 4, 59, tzinfo=UTC)
    primary = CandidateMembership(
        evidence_id=uuid.UUID("00000000-0000-5000-8000-000000000001"),
        evidence_type="communication_policy_finding",
        evidence_schema="otsoc.communication_policy.finding",
        evidence_schema_version="1.0.0",
        integrity_sha256="1" * 64,
        role=EvidenceRole.PRIMARY,
        observed_at=observed,
        received_at=observed,
    )
    return QualifiedIncidentCandidate(
        qualification_rule_id="IQR-S3-CV-COMMAND-001",
        qualification_rule_version="1.0.0",
        category=IncidentCategory.CONTROL_COMMAND_INVESTIGATION,
        severity=IncidentSeverity.MEDIUM,
        title="CV-101 control-command investigation",
        summary=(
            "A stored CV-101 synthetic command and its verified authorization/process context "
            "warrant analyst review; correlation does not determine cause or malicious intent."
        ),
        primary_membership=primary,
        additional_memberships=(),
        identity_asset_scope=("asset-a", "asset-b"),
        process_asset_scope=("CV-101",),
        target_point_scope=("control_valve_command_percent",),
        source_asset_id=None,
        destination_asset_id=None,
        controller_asset_id=None,
        process_asset_ids=(),
        process_asset_keys=("CV-101",),
        correlation_rule_id="CPR-S3-CV-TRANSFER-001",
        correlation_rule_version="1.0.0",
        run_scope=f"UNBOUND_PROCESS_SCOPE:{primary.evidence_id}",
        configuration_scope="UNBOUND_PROCESS_SCOPE",
        bound_simulation_id=None,
        bound_configuration_hash=None,
        s3_semantic_evidence_id=primary.evidence_id,
        grouping_anchor=observed,
        first_observed_at=observed,
        last_observed_at=observed,
        policy_context="DENIED",
        correlation_context="NOT_CORRELATED",
        evidence_completeness="VERIFIED_S3_CHAIN",
    )


def _identity(candidate: QualifiedIncidentCandidate):  # type: ignore[no-untyped-def]
    loaded = load_incident_profile()
    return deterministic_incident_identity(
        candidate,
        profile_id=loaded.profile.profile_id,
        profile_version=loaded.profile.profile_version,
        profile_sha256=loaded.sha256,
        grouping_epoch=grouping_epoch_start(candidate.grouping_anchor),
    )


def test_p7b_t001_incident_profile_loads_strictly() -> None:
    loaded = load_incident_profile()
    assert (loaded.profile.profile_id, loaded.profile.profile_version) == (
        "otsoc.incident.oil_gas_transfer",
        "1.0.0",
    )
    document = loaded.profile.model_dump(mode="json")
    document["unknown"] = True
    with pytest.raises(IncidentProfileError):
        parse_incident_profile_bytes(json.dumps(document).encode())


def test_p7b_t002_profile_digest_is_deterministic() -> None:
    loaded = load_incident_profile()
    reordered = loaded.profile.model_copy(
        update={
            "categories": tuple(reversed(loaded.profile.categories)),
            "severities": tuple(reversed(loaded.profile.severities)),
            "statuses": tuple(reversed(loaded.profile.statuses)),
            "evidence_roles": tuple(reversed(loaded.profile.evidence_roles)),
            "timeline_entry_types": tuple(reversed(loaded.profile.timeline_entry_types)),
            "evidence_schemas": tuple(reversed(loaded.profile.evidence_schemas)),
            "rules": tuple(reversed(loaded.profile.rules)),
        }
    )
    assert sha256_hex(canonical_profile_bytes(reordered)) == loaded.sha256
    assert loaded.sha256 == EXPECTED_INCIDENT_PROFILE_SHA256


def test_p7b_t003_profile_tampering_fails_closed() -> None:
    document = load_incident_profile().profile.model_dump(mode="json")
    changes = (
        ("category", "UNSUPPORTED"),
        ("initial_severity", "CRITICAL"),
        ("rule_version", "1.0.1"),
        ("title", "Confirmed cyberattack"),
    )
    for field, value in changes:
        changed = json.loads(json.dumps(document))
        changed["rules"][0][field] = value
        with pytest.raises(IncidentProfileError):
            parse_incident_profile_bytes(json.dumps(changed).encode())
    changed = json.loads(json.dumps(document))
    changed["grouping"]["window_seconds"] = 301
    with pytest.raises(IncidentProfileError):
        parse_incident_profile_bytes(json.dumps(changed).encode())


def test_p7b_t016_incident_uuid_and_key_are_deterministic() -> None:
    first = _identity(_candidate())
    second = _identity(_candidate())
    assert first == second
    assert first.incident_id.version == 5 and len(first.grouping_key_sha256) == 64


def test_p7b_t019_five_minute_epoch_boundaries() -> None:
    before = datetime(2026, 1, 1, 0, 4, 59, 999999, tzinfo=UTC)
    boundary = datetime(2026, 1, 1, 0, 5, 0, tzinfo=UTC)
    assert grouping_epoch_start(before) == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert grouping_epoch_start(boundary) == boundary


def test_p7b_t020_asset_scope_prevents_over_grouping() -> None:
    original = _identity(_candidate())
    changed = _identity(_candidate().model_copy(update={"identity_asset_scope": ("other",)}))
    assert original.incident_id != changed.incident_id


def test_p7b_t021_process_scope_and_point_prevent_over_grouping() -> None:
    original = _identity(_candidate())
    changed_asset = _identity(_candidate().model_copy(update={"process_asset_scope": ("P-101",)}))
    changed_point = _identity(
        _candidate().model_copy(update={"target_point_scope": ("pipeline_flow_rate_m3h",)})
    )
    assert len({original.incident_id, changed_asset.incident_id, changed_point.incident_id}) == 3


def test_p7b_t031_category_mapping_is_exact() -> None:
    profile = load_incident_profile().profile
    assert set(profile.categories) == set(IncidentCategory)
    assert {rule.category for rule in profile.rules} == set(IncidentCategory)


def test_p7b_t032_titles_are_controlled_and_deterministic() -> None:
    rules = load_incident_profile().rules
    assert {rule.title for rule in rules.values()} == {
        "Unknown synthetic source identity",
        "Unapproved synthetic IT-to-controller communication",
        "CV-101 control-command investigation",
        "P-101/PL-101 process inconsistency",
    }


def test_p7b_t033_summaries_are_neutral_and_deterministic() -> None:
    summaries = [rule.summary for rule in load_incident_profile().rules.values()]
    assert all("analyst review" in summary for summary in summaries)
    assert all("confirmed" not in summary.lower() for summary in summaries)


def test_p7b_t034_templates_reject_maliciousness_and_causality_overclaim() -> None:
    document = load_incident_profile().profile.model_dump(mode="json")
    for statement in (
        "Attacker compromised the PLC.",
        "Confirmed cyberattack.",
        "Sabotage caused the valve failure.",
        "The command definitely caused the process effect.",
    ):
        changed = json.loads(json.dumps(document))
        changed["rules"][0]["summary"] = statement
        with pytest.raises(IncidentProfileError):
            parse_incident_profile_bytes(json.dumps(changed).encode())


def test_p7b_t035_severity_precedence_is_frozen() -> None:
    assert set(IncidentSeverity) == {
        IncidentSeverity.LOW,
        IncidentSeverity.MEDIUM,
        IncidentSeverity.HIGH,
    }
    assert SEVERITY_RANK == {
        IncidentSeverity.LOW: 1,
        IncidentSeverity.MEDIUM: 2,
        IncidentSeverity.HIGH: 3,
    }


def test_p7b_t036_initial_status_is_open() -> None:
    profile = load_incident_profile().profile
    assert profile.initial_status is IncidentStatus.OPEN
    assert set(profile.statuses) == set(IncidentStatus)


def test_p7b_t046_ground_truth_fields_are_rejected() -> None:
    request = {
        "policy_finding": {
            "evidence_id": "00000000-0000-5000-8000-000000000001",
            "expected_integrity_sha256": "1" * 64,
        },
        "scenario_id": "hidden",
    }
    with pytest.raises(ValidationError):
        IncidentQualificationRequest.model_validate(request)
    source = "\n".join(path.read_text("utf-8") for path in INCIDENT_ROOT.glob("*.py"))
    assert "GroundTruthEvent" not in source
    assert _candidate().ground_truth_used is False


def test_p7b_t048_no_containment_or_playbook_executor_exists() -> None:
    names = {path.name for path in INCIDENT_ROOT.glob("*.py")}
    assert not names & {
        "containment.py",
        "response.py",
        "playbooks.py",
        "firewall.py",
        "quarantine.py",
    }
    route_source = (PROJECT_ROOT / "backend" / "app" / "api" / "incidents.py").read_text("utf-8")
    assert "@router.delete" not in route_source and "playbook" not in route_source.lower()


def test_p7b_t049_incident_engine_has_no_network_or_control_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def blocked_socket(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("incident engine attempted socket creation")

    monkeypatch.setattr(socket, "socket", blocked_socket)
    assert load_incident_profile().sha256 == EXPECTED_INCIDENT_PROFILE_SHA256
    source = "\n".join(path.read_text("utf-8").lower() for path in INCIDENT_ROOT.glob("*.py"))
    assert "import socket" not in source and "import requests" not in source
    assert "subprocess" not in source and calls == 0


def test_p7b_t050_phase6b_regression_contract() -> None:
    profile = load_correlation_profile()
    assert profile.sha256 == EXPECTED_CORRELATION_PROFILE_SHA256
    assert set(profile.rules) == {"CPR-S3-CV-TRANSFER-001", "CPR-S4-PUMP-FLOW-001"}
    correlation_root = PROJECT_ROOT / "backend" / "app" / "correlation"
    source = "\n".join(path.read_text("utf-8") for path in correlation_root.glob("*.py"))
    assert "app.incidents" not in source


def test_p7b_t051_phase5b_regression_contract() -> None:
    inventory = load_inventory_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=load_profile())
    assert inventory.sha256 == EXPECTED_INVENTORY_SHA256
    assert policy.sha256 == EXPECTED_POLICY_SHA256
    assert len(inventory.profile.assets) == 11
    assert len(inventory.profile.zones) == 5
    assert len(policy.profile.rules) == 6


def test_p7b_t052_phase4b_regression_contract() -> None:
    profile = load_profile()
    event, _ = load_protocol_fixture("p4b-s3-valve-command-25.json")
    semantic = decode_event(
        event,
        profile,
        semantic_event_id=uuid.uuid4(),
        source_evidence_id=uuid.uuid4(),
        source_evidence_integrity_sha256="1" * 64,
        created_at=event.observed_at,
    )
    assert profile.sha256 == EXPECTED_PROFILE_SHA256 and len(profile.profile.points) == 9
    assert str(semantic.decoded_value) == "25.0" and semantic.ground_truth_used is False


def test_p7b_t053_phase36_simulator_regression_contract() -> None:
    config = SimulationConfig(duration_seconds=5)
    simulator = OilGasTransferSimulator(config)
    first = tuple(simulator.step().telemetry for _ in range(3))
    simulator.reset()
    assert tuple(simulator.step().telemetry for _ in range(3)) == first
    assert all(item.domain == "oil_gas_transfer" for item in first)
    assert all(
        0.0 <= item.source_tank_level_percent <= 100.0
        and 0.0 <= item.receiving_tank_level_percent <= 100.0
        for item in first
    )


def test_p7b_t054_phase3_evidence_regression_contract() -> None:
    request = sample_evidence_request(source_event_id="phase7b-regression")
    source_id = uuid.UUID("143c438b-ca4d-5094-ae31-7794ca91d8f9")
    first = canonical_evidence_bytes(source_id, request)
    second = canonical_evidence_bytes(source_id, request)
    assert first == second and integrity_sha256(first) == integrity_sha256(second)
    assert deterministic_evidence_id(source_id, request) == deterministic_evidence_id(
        source_id, request
    )
    migration = (
        PROJECT_ROOT / "backend" / "alembic" / "versions" / "0002_phase_3_evidence_foundation.py"
    ).read_text("utf-8")
    assert "evidence_records_append_only" in migration


def test_p7b_t055_three_service_compose_invariant_and_fixture_catalog() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text("utf-8")
    services_block = compose.split("services:", 1)[1].split("\nvolumes:", 1)[0]
    services = set(re.findall(r"^  ([a-z][a-z0-9_-]*):$", services_block, re.MULTILINE))
    assert services == {"db", "backend", "frontend"}
    fixtures = verify_fixture_set()
    assert len(fixtures.fixtures) == 20
    assert [item.catalog_id for item in fixtures.fixtures] == [
        f"P7B-F{number:03d}" for number in range(1, 21)
    ]
