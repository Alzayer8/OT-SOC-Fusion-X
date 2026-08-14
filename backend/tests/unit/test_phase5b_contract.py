from __future__ import annotations

import os
import socket
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.context.canonical import (
    canonical_inventory_bytes,
    canonical_policy_bytes,
    deterministic_asset_id,
    deterministic_context_source_event_id,
    deterministic_finding_source_event_id,
    sha256_hex,
)
from app.context.findings import (
    authorization_input_from_semantic,
    build_asset_context_event,
    build_policy_finding,
)
from app.context.fixtures import AssetPolicyFixture, load_fixture, verify_fixture_set
from app.context.identity import resolve_identity
from app.context.inventory import (
    EXPECTED_INVENTORY_SHA256,
    InventoryProfileError,
    load_inventory_profile,
)
from app.context.models import (
    ASSET_CONTEXT_SCHEMA_VERSION,
    EVALUATOR_VERSION,
    POLICY_FINDING_SCHEMA_VERSION,
    RESOLVER_VERSION,
    DimensionStatus,
    IdentifierType,
    IdentityClaim,
    PolicyReasonCode,
    PolicyStatus,
    ResolutionStatus,
    ZoneId,
)
from app.context.policy import (
    EXPECTED_POLICY_SHA256,
    PolicyProfileError,
    evaluate_policy,
    load_policy_profile,
    unsupported_profile_result,
)
from app.main import create_app
from app.protocols.decoder import decode_event
from app.protocols.models import OperationCategory, OperationCompatibility
from app.protocols.profile import EXPECTED_PROFILE_SHA256, load_profile

PROJECT_ROOT = Path(os.environ.get("OTSOC_REPOSITORY_ROOT", Path(__file__).resolve().parents[3]))
CONTEXT_ROOT = PROJECT_ROOT / "backend" / "app" / "context"
SOURCE_HASH = "1" * 64
SEMANTIC_HASH = "2" * 64


def _claims(key: str) -> tuple[IdentityClaim, ...]:
    return (IdentityClaim(identifier_type=IdentifierType.LOGICAL_ID, value=key),)


def _bundle(file_name: str):  # type: ignore[no-untyped-def]
    fixture, _ = load_fixture(file_name)
    protocol = load_profile()
    semantic = decode_event(
        fixture.event,
        protocol,
        semantic_event_id=uuid.uuid5(uuid.NAMESPACE_URL, file_name),
        source_evidence_id=uuid.uuid5(uuid.NAMESPACE_DNS, file_name),
        source_evidence_integrity_sha256=SOURCE_HASH,
        created_at=fixture.event.observed_at,
    )
    inventory = load_inventory_profile()
    context = build_asset_context_event(
        context_event_id=uuid.uuid5(uuid.NAMESPACE_OID, file_name),
        semantic=semantic,
        semantic_integrity_sha256=SEMANTIC_HASH,
        inventory=inventory,
        source_claims=fixture.source_identity_claims,
        destination_claims=fixture.destination_identity_claims,
    )
    auth = authorization_input_from_semantic(semantic, semantic_integrity_sha256=SEMANTIC_HASH)
    policy = load_policy_profile(
        inventory=inventory,
        protocol_profile=protocol,
    )
    result = (
        unsupported_profile_result()
        if fixture.policy_profile_version != "1.0.0"
        else evaluate_policy(auth, context, policy)
    )
    finding = build_policy_finding(
        finding_id=uuid.uuid5(uuid.NAMESPACE_X500, file_name),
        auth=auth,
        context=context,
        result=result,
        policy=policy,
    )
    return fixture, semantic, context, auth, result, finding, inventory, policy


def test_p5b_t001_inventory_profile_loads() -> None:
    loaded = load_inventory_profile()
    assert loaded.profile.profile_version == "1.0.0"
    assert len(loaded.profile.assets) == 11
    assert len(loaded.profile.zones) == 5
    assert len(loaded.profile.relationships) == 9
    with pytest.raises(InventoryProfileError):
        load_inventory_profile(expected_sha256="0" * 64)


def test_p5b_t002_inventory_digest_deterministic() -> None:
    loaded = load_inventory_profile()
    first = canonical_inventory_bytes(loaded.profile)
    assert first == canonical_inventory_bytes(loaded.profile)
    assert sha256_hex(first) == EXPECTED_INVENTORY_SHA256
    assert sha256_hex(first).islower()


def test_p5b_t003_policy_profile_loads() -> None:
    inventory = load_inventory_profile()
    loaded = load_policy_profile(inventory=inventory, protocol_profile=load_profile())
    assert len(loaded.profile.governed_paths) == 3
    assert len(loaded.profile.rules) == 6
    assert all("*" not in rule.point_ids for rule in loaded.profile.rules)
    with pytest.raises(PolicyProfileError):
        load_policy_profile(expected_sha256="0" * 64)


def test_p5b_t004_policy_digest_deterministic() -> None:
    loaded = load_policy_profile()
    first = canonical_policy_bytes(loaded.profile)
    assert first == canonical_policy_bytes(loaded.profile)
    assert sha256_hex(first) == EXPECTED_POLICY_SHA256


def test_p5b_t005_asset_exact_match_resolution() -> None:
    inventory = load_inventory_profile()
    hmi = resolve_identity(_claims("HMI-01"), inventory)
    endpoint = resolve_identity(
        (
            IdentityClaim(
                identifier_type=IdentifierType.PROTOCOL_ENDPOINT_ID, value="OTSOC-MB-UNIT-01"
            ),
        ),
        inventory,
    )
    assert hmi.asset_id == deterministic_asset_id(
        inventory_profile_id=inventory.profile.profile_id, asset_key="HMI-01"
    )
    assert endpoint.asset_key == "PLC-01"


def test_p5b_t006_unknown_asset_remains_unknown() -> None:
    result = resolve_identity(_claims("UNKNOWN-OT-01"), load_inventory_profile())
    assert result.status is ResolutionStatus.UNKNOWN
    assert result.asset_id is None and result.zone_id is None
    assert _bundle("s1_unknown_source_asset.json")[4].policy_status is PolicyStatus.UNKNOWN


def test_p5b_t007_identity_conflict_fails_closed() -> None:
    context = _bundle("identity_conflict.json")[2]
    result = _bundle("identity_conflict.json")[4]
    assert context.source_resolution.status is ResolutionStatus.CONFLICT
    assert (result.policy_status, result.reason_code) == (
        PolicyStatus.UNKNOWN,
        PolicyReasonCode.IDENTITY_CONFLICT,
    )


def test_p5b_t008_zone_resolution() -> None:
    fixture, _, context, *_ = _bundle("s2_it_to_controller.json")
    assert "zone" not in type(fixture.event).model_fields
    assert context.source_resolution.zone_id is ZoneId.IT_ZONE
    assert context.destination_resolution.zone_id is ZoneId.OT_CONTROL_ZONE


def test_p5b_t009_approved_path() -> None:
    result = _bundle("known_hmi_approved_read.json")[4]
    assert (result.policy_status, result.matched_path_id) == (
        PolicyStatus.APPROVED,
        "PATH-HMI-PLC",
    )


def test_p5b_t010_denied_path() -> None:
    result = _bundle("s2_it_to_controller.json")[4]
    assert (result.policy_status, result.reason_code) == (
        PolicyStatus.DENIED,
        PolicyReasonCode.COMMUNICATION_NOT_APPROVED,
    )


def test_p5b_t011_unknown_path() -> None:
    fixture, semantic, context, auth, _, _, _, policy = _bundle("known_hmi_approved_read.json")
    context = build_asset_context_event(
        context_event_id=context.asset_context_event_id,
        semantic=semantic,
        semantic_integrity_sha256=SEMANTIC_HASH,
        inventory=load_inventory_profile(),
        source_claims=_claims("MON-01"),
        destination_claims=fixture.destination_identity_claims,
    )
    result = evaluate_policy(auth, context, policy)
    assert (result.policy_status, result.reason_code) == (
        PolicyStatus.UNKNOWN,
        PolicyReasonCode.POLICY_NOT_CLASSIFIED,
    )


def test_p5b_t012_approved_protocol() -> None:
    result = _bundle("known_hmi_approved_read.json")[4]
    assert result.dimension_results.protocol_approved is DimensionStatus.SATISFIED


def test_p5b_t013_denied_protocol() -> None:
    *_, context, auth, _, _, _, policy = _bundle("known_hmi_approved_read.json")
    result = evaluate_policy(
        auth.model_copy(update={"protocol": "synthetic_other"}), context, policy
    )
    assert (result.policy_status, result.reason_code) == (
        PolicyStatus.DENIED,
        PolicyReasonCode.PROTOCOL_NOT_APPROVED,
    )


def test_p5b_t014_approved_operation() -> None:
    result = _bundle("known_hmi_approved_read.json")[4]
    assert result.dimension_results.operation_approved is DimensionStatus.SATISFIED
    assert result.matched_rule_id == "ACP-001"


def test_p5b_t015_denied_operation() -> None:
    _, _, context, auth, _, _, _, policy = _bundle("known_hmi_approved_read.json")
    result = evaluate_policy(auth.model_copy(update={"function_semantic": None}), context, policy)
    assert (result.policy_status, result.reason_code) == (
        PolicyStatus.DENIED,
        PolicyReasonCode.OPERATION_NOT_APPROVED,
    )


def test_p5b_t016_read_only_write_rejected() -> None:
    _, _, context, auth, _, _, _, policy = _bundle("known_hmi_approved_read.json")
    changed = auth.model_copy(
        update={
            "operation_category": OperationCategory.WRITE,
            "operation_compatibility": OperationCompatibility.INCOMPATIBLE,
        }
    )
    result = evaluate_policy(changed, context, policy)
    assert result.reason_code is PolicyReasonCode.POINT_WRITE_NOT_APPROVED


def test_p5b_t017_approved_synthetic_write() -> None:
    pump = _bundle("known_hmi_approved_pump_command.json")[4]
    valve = _bundle("s3_hmi_approved_valve_command.json")[4]
    assert {pump.matched_rule_id, valve.matched_rule_id} == {"ACP-002", "ACP-003"}
    assert pump.policy_status is valve.policy_status is PolicyStatus.APPROVED


def test_p5b_t018_command_state_semantics_preserved() -> None:
    semantic = _bundle("s3_hmi_approved_valve_command.json")[1]
    assert semantic.point_id == "control_valve_command_percent"
    assert semantic.point_id != "control_valve_position_percent"
    assert "physical" not in semantic.semantic_statement.lower()


def test_p5b_t019_s1_fixture() -> None:
    result = _bundle("s1_unknown_source_asset.json")[4]
    assert result.reason_code is PolicyReasonCode.SOURCE_UNKNOWN
    assert "compromise" not in result.analyst_readable_statement.lower()


def test_p5b_t020_s2_fixture() -> None:
    result = _bundle("s2_it_to_controller.json")[4]
    assert result.matched_rule_id == "ACP-006"
    assert result.dimension_results.communication_path_approved is DimensionStatus.NOT_SATISFIED


def test_p5b_t021_s3_approved_fixture() -> None:
    _, semantic, _, _, result, *_ = _bundle("s3_hmi_approved_valve_command.json")
    assert semantic.decoded_value == Decimal("25.0")
    assert result.policy_status is PolicyStatus.APPROVED


def test_p5b_t022_s3_denied_fixture() -> None:
    _, semantic, _, _, result, *_ = _bundle("s3_engineering_denied_valve_command.json")
    assert semantic.decoded_value == Decimal("25.0")
    assert result.reason_code is PolicyReasonCode.SOURCE_ROLE_NOT_APPROVED


def test_p5b_t023_no_malicious_intent_inference() -> None:
    prohibited = {"attacker", "compromised", "malicious conclusion"}
    for item in verify_fixture_set().fixtures:
        finding = _bundle(item.file)[5]
        assert finding.malicious_intent_inferred is False
        assert not any(token in finding.analyst_readable_statement.lower() for token in prohibited)


def test_p5b_t024_deterministic_wording() -> None:
    first = _bundle("s2_it_to_controller.json")[5].analyst_readable_statement
    second = _bundle("s2_it_to_controller.json")[5].analyst_readable_statement
    assert first.encode() == second.encode()
    assert "\n" not in first and "\r" not in first


def test_p5b_t025_semantic_evidence_preserved() -> None:
    _, semantic, context, auth, _, _, _, policy = _bundle("known_hmi_approved_read.json")
    before = semantic.model_dump_json()
    evaluate_policy(auth, context, policy)
    assert semantic.model_dump_json() == before


def test_p5b_t026_derivative_context_linkage() -> None:
    _, semantic, context, _, _, finding, *_ = _bundle("known_hmi_approved_read.json")
    assert context.semantic_event_id == semantic.semantic_event_id
    assert context.semantic_evidence_integrity_sha256 == SEMANTIC_HASH
    assert finding.asset_context_event_id == context.asset_context_event_id
    assert sha256_hex(context.model_dump_json().encode()) != sha256_hex(
        finding.model_dump_json().encode()
    )


def test_p5b_t027_profile_version_isolation() -> None:
    with pytest.raises(PolicyProfileError):
        load_policy_profile(profile_version="1.0.1")
    _, _, context, _, result, finding, inventory, policy = _bundle(
        "unsupported_policy_profile_version.json"
    )
    assert result.reason_code is PolicyReasonCode.PROFILE_VERSION_UNSUPPORTED
    assert context.inventory_sha256 == inventory.sha256
    assert finding.policy_sha256 == policy.sha256


def test_p5b_t028_policy_version_re_evaluation() -> None:
    _, semantic, context, *_ = _bundle("known_hmi_approved_read.json")
    common = {
        "semantic_event_id": semantic.semantic_event_id,
        "asset_context_event_id": context.asset_context_event_id,
        "inventory_profile": context.inventory_profile,
        "inventory_version": context.inventory_version,
        "inventory_sha256": context.inventory_sha256,
        "policy_profile": "otsoc.communication_policy.oil_gas_transfer",
        "evaluator_version": EVALUATOR_VERSION,
        "finding_schema_version": POLICY_FINDING_SCHEMA_VERSION,
    }
    old = deterministic_finding_source_event_id(
        **common, policy_version="1.0.0", policy_sha256=EXPECTED_POLICY_SHA256
    )
    new = deterministic_finding_source_event_id(
        **common, policy_version="1.0.1", policy_sha256="3" * 64
    )
    assert old != new


def test_p5b_t029_idempotency() -> None:
    semantic = _bundle("known_hmi_approved_read.json")[1]
    values = {
        "semantic_event_id": semantic.semantic_event_id,
        "inventory_profile": "otsoc.asset_inventory.oil_gas_transfer",
        "inventory_version": "1.0.0",
        "inventory_sha256": EXPECTED_INVENTORY_SHA256,
        "resolver_version": RESOLVER_VERSION,
        "context_schema_version": ASSET_CONTEXT_SCHEMA_VERSION,
    }
    assert deterministic_context_source_event_id(**values) == deterministic_context_source_event_id(
        **values
    )


def test_p5b_t030_concurrent_duplicate_behavior() -> None:
    semantic = _bundle("duplicate_policy_evaluation.json")[1]
    identities = {
        deterministic_context_source_event_id(
            semantic_event_id=semantic.semantic_event_id,
            inventory_profile="otsoc.asset_inventory.oil_gas_transfer",
            inventory_version="1.0.0",
            inventory_sha256=EXPECTED_INVENTORY_SHA256,
            resolver_version=RESOLVER_VERSION,
            context_schema_version=ASSET_CONTEXT_SCHEMA_VERSION,
        )
        for _ in range(8)
    }
    assert len(identities) == 1


def test_p5b_t031_ground_truth_non_leakage() -> None:
    fixture, _ = load_fixture("s1_unknown_source_asset.json")
    document = fixture.model_dump(mode="json")
    document["ground_truth"] = "S1"
    with pytest.raises(ValidationError):
        AssetPolicyFixture.model_validate(document)
    sources = "\n".join(path.read_text("utf-8") for path in CONTEXT_ROOT.glob("*.py"))
    assert "GroundTruthEvent" not in sources


def test_p5b_t032_no_socket_network_capability(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def blocked_socket(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("Phase 5B attempted socket creation")

    monkeypatch.setattr(socket, "socket", blocked_socket)
    assert _bundle("known_hmi_approved_read.json")[4].policy_status is PolicyStatus.APPROVED
    sources = "\n".join(path.read_text("utf-8").lower() for path in CONTEXT_ROOT.glob("*.py"))
    for token in (
        "import socket",
        "import scapy",
        "import pymodbus",
        "import requests",
        "import subprocess",
        "import snmp",
    ):
        assert token not in sources
    assert calls == 0


def test_p5b_t033_phase4_decoder_unchanged() -> None:
    semantic = _bundle("s3_hmi_approved_valve_command.json")[1]
    assert (
        EXPECTED_PROFILE_SHA256
        == "b3ade7b3ae5dd7e5955c54b5a3345dc6f79b5bfa7bf78a2f1a82df3a5f4016ff"
    )
    assert semantic.decoded_value == Decimal("25.0")
    assert "policy_status" not in type(semantic).model_fields


def test_p5b_t034_simulator_remains_independent() -> None:
    root = PROJECT_ROOT / "backend" / "app" / "simulation"
    before = {path: path.read_bytes() for path in root.glob("*.py")}
    _bundle("known_hmi_approved_read.json")
    assert before == {path: path.read_bytes() for path in root.glob("*.py")}
    text = "\n".join(value.decode() for value in before.values()).lower()
    assert "app.context" not in text and "app.protocols" not in text


def test_p5b_t035_no_incident_creation() -> None:
    text = "\n".join(path.read_text("utf-8").lower() for path in CONTEXT_ROOT.rglob("*.py"))
    assert "create_incident" not in text
    assert "/policy/evaluate" not in text and "/assets/discover" not in text
    paths = create_app().openapi()["paths"]
    assert "post" not in paths["/api/v1/incidents"]
    assert all("qualif" not in path for path in paths)
    finding = _bundle("known_hmi_approved_read.json")[5]
    assert "incident" not in type(finding).model_fields
    assert "severity" not in type(finding).model_fields
