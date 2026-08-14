from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.correlation.canonical import canonical_document_bytes, sha256_hex
from app.correlation.models import (
    CORRELATION_PROFILE_ID,
    CORRELATION_PROFILE_VERSION,
    CorrelationEvaluationInput,
    CorrelationReasonCode,
    CorrelationStatus,
    CorrelationTelemetryPayload,
    CyberParentContext,
    EvidenceParentReference,
    TelemetryEvidence,
)
from app.correlation.profile import LoadedCorrelationProfile

MAX_FIXTURE_BYTES = 8_192
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = PROJECT_ROOT / "fixtures" / "events" / "phase-6b-correlation"
FIXTURE_FILES = frozenset(f"p6b-f{number:03d}.json" for number in range(1, 16))


class CorrelationFixtureError(ValueError):
    pass


class StrictFixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, frozen=True)


class CorrelationFixture(StrictFixtureModel):
    fixture_set_id: Literal["otsoc.phase6b.correlation"]
    fixture_set_version: Literal["1.0.0"]
    catalog_id: str = Field(pattern=r"^P6B-F0(?:0[1-9]|1[0-5])$")
    rule_id: Literal["CPR-S3-CV-TRANSFER-001", "CPR-S4-PUMP-FLOW-001"]
    anchor_time: AwareDatetime
    pattern: Literal[
        "S3_MATCH",
        "S3_NO_CHANGE",
        "S3_OUTSIDE",
        "S4_ZERO_PARTIAL",
        "S4_NORMAL",
        "S4_MATCH",
        "S3_MISSING",
        "S3_WRONG_RUN",
        "S3_WRONG_CONFIG",
        "S3_OUT_OF_ORDER",
        "S3_DUPLICATE",
        "S3_LATE",
        "UNRELATED_POINT",
    ]
    policy_context_status: Literal["APPROVED", "DENIED", "UNKNOWN", "UNAVAILABLE"]
    available_point_ids: tuple[str, ...]
    parent_seed: str = Field(min_length=1, max_length=40)
    expected_status: CorrelationStatus
    expected_reason: CorrelationReasonCode
    contains_ground_truth: Literal[False]


class FixtureManifestEntry(StrictFixtureModel):
    catalog_id: str = Field(pattern=r"^P6B-F0(?:0[1-9]|1[0-5])$")
    file: str
    bytes: int = Field(gt=0, le=MAX_FIXTURE_BYTES)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FixtureManifest(StrictFixtureModel):
    fixture_set_id: Literal["otsoc.phase6b.correlation"]
    fixture_set_version: Literal["1.0.0"]
    profile_id: Literal["otsoc.correlation.oil_gas_transfer"]
    profile_version: Literal["1.0.0"]
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    educational_only: Literal[True]
    contains_ground_truth: Literal[False]
    fixtures: tuple[FixtureManifestEntry, ...] = Field(min_length=15, max_length=15)

    @model_validator(mode="after")
    def validate_fixture_catalog(self) -> FixtureManifest:
        files = [item.file for item in self.fixtures]
        ids = [item.catalog_id for item in self.fixtures]
        if set(files) != FIXTURE_FILES or len(files) != len(set(files)):
            raise ValueError("fixture file catalog is incomplete or duplicated")
        if set(ids) != {f"P6B-F{number:03d}" for number in range(1, 16)}:
            raise ValueError("fixture ID catalog is incomplete")
        return self


def load_fixture(file_name: str) -> tuple[CorrelationFixture, bytes]:
    if file_name not in FIXTURE_FILES:
        raise CorrelationFixtureError("The requested correlation fixture is not allowlisted.")
    path = FIXTURE_ROOT / file_name
    if path.is_symlink() or path.resolve().parent != FIXTURE_ROOT.resolve():
        raise CorrelationFixtureError("The approved correlation fixture path is unsafe.")
    content = path.read_bytes()
    if not content or len(content) > MAX_FIXTURE_BYTES:
        raise CorrelationFixtureError("The correlation fixture exceeds the size bound.")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        fixture = CorrelationFixture.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorrelationFixtureError("The correlation fixture is invalid.") from exc
    return fixture, content


def verify_fixture_set(loaded_profile: LoadedCorrelationProfile) -> FixtureManifest:
    path = FIXTURE_ROOT / "manifest.json"
    try:
        document = json.loads(path.read_text("utf-8"), object_pairs_hook=_unique_object)
        manifest = FixtureManifest.model_validate(document)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorrelationFixtureError("The correlation fixture manifest is invalid.") from exc
    if manifest.profile_sha256 != loaded_profile.sha256:
        raise CorrelationFixtureError("The fixture profile digest is not approved.")
    for entry in manifest.fixtures:
        fixture, content = load_fixture(entry.file)
        if fixture.catalog_id != entry.catalog_id:
            raise CorrelationFixtureError("A fixture ID differs from its manifest entry.")
        if len(content) != entry.bytes or sha256_hex(content) != entry.sha256:
            raise CorrelationFixtureError("A fixture byte length or digest does not match.")
    return manifest


def build_fixture_input(
    fixture: CorrelationFixture,
    loaded_profile: LoadedCorrelationProfile,
    *,
    complete_late: bool = False,
    reevaluates_parent: EvidenceParentReference | None = None,
) -> CorrelationEvaluationInput:
    telemetry = _telemetry_for(fixture, complete_late=complete_late)
    cyber = _cyber_for(fixture) if fixture.rule_id.startswith("CPR-S3") else None
    return CorrelationEvaluationInput(
        profile_id=CORRELATION_PROFILE_ID,
        profile_version=CORRELATION_PROFILE_VERSION,
        profile_sha256=loaded_profile.sha256,
        rule_id=fixture.rule_id,
        rule_version="1.0.0",
        cyber_context=cyber,
        telemetry=telemetry,
        available_point_ids=fixture.available_point_ids,
        reevaluates_parent=reevaluates_parent,
    )


def _telemetry_for(
    fixture: CorrelationFixture, *, complete_late: bool
) -> tuple[TelemetryEvidence, ...]:
    is_s4 = fixture.rule_id.startswith("CPR-S4")
    end = 60 if is_s4 else 30
    if fixture.pattern == "S3_OUTSIDE":
        end = 40
    if fixture.pattern == "S3_LATE" and not complete_late:
        end = 10
    relative_seconds = list(range(-10, end + 1))
    result: list[TelemetryEvidence] = []
    for relative in relative_seconds:
        values = _values(fixture.pattern, relative)
        simulation_id = "sim-phase6b-primary"
        configuration_hash = "a" * 64
        if fixture.pattern == "S3_WRONG_RUN" and relative >= 0:
            simulation_id = "sim-phase6b-other"
        if fixture.pattern == "S3_WRONG_CONFIG" and relative >= 0:
            configuration_hash = "c" * 64
        simulation_time = 100 + relative
        observed_at = fixture.anchor_time + timedelta(seconds=relative)
        payload = CorrelationTelemetryPayload(
            domain="oil_gas_transfer",
            simulation_id=simulation_id,
            sequence_number=simulation_time,
            timestamp=observed_at,
            simulator_version="3.0.0",
            configuration_hash=configuration_hash,
            simulation_time_seconds=simulation_time,
            source_tank_level_percent=values[0],
            receiving_tank_level_percent=values[1],
            transfer_pump_command_percent=55.0,
            transfer_pump_running=True,
            control_valve_position_percent=values[2],
            pipeline_flow_rate_m3h=values[3],
            pipeline_pressure_bar=values[4],
            process_temperature_c=values[5],
        )
        identity = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"urn:otsoc:phase6b:{fixture.parent_seed}:telemetry:{relative}",
        )
        digest = hashlib.sha256(
            canonical_document_bytes(payload.model_dump(mode="json"))
        ).hexdigest()
        result.append(
            TelemetryEvidence(
                evidence_id=identity,
                evidence_type="simulator_telemetry",
                integrity_sha256=digest,
                observed_at=observed_at,
                sequence_number=simulation_time,
                payload_schema="otsoc.simulator.telemetry",
                payload_schema_version="2.0.0",
                payload=payload,
            )
        )
    if fixture.pattern == "S3_OUT_OF_ORDER":
        result.reverse()
    return tuple(result)


def _values(pattern: str, relative: int) -> tuple[float, float, float, float, float, float]:
    baseline_source = 72.0 - (relative + 10) * 0.0001
    baseline_receiving = 18.0 + (relative + 10) * 0.0001
    if relative < 0:
        return baseline_source, baseline_receiving, 70.0, 4.0, 1.0, 26.0
    s3_match = pattern in {
        "S3_MATCH",
        "S3_WRONG_RUN",
        "S3_WRONG_CONFIG",
        "S3_OUT_OF_ORDER",
        "S3_DUPLICATE",
        "S3_LATE",
    }
    if pattern == "S3_OUTSIDE":
        s3_match = relative > 30
    if s3_match:
        source = 71.999 - relative * 0.00005
        receiving = 18.001 + relative * 0.00005
        return source, receiving, 25.0, 3.0, 1.2, 26.0
    if pattern in {"S4_MATCH", "S4_ZERO_PARTIAL"}:
        return 71.999, 18.001, 70.0, 0.0, 1.6, 26.0
    if pattern == "UNRELATED_POINT":
        return baseline_source, baseline_receiving, 70.0, 4.0, 1.0, 30.0
    return baseline_source, baseline_receiving, 70.0, 4.0, 1.0, 26.0


def _cyber_for(fixture: CorrelationFixture) -> CyberParentContext:
    seed = fixture.parent_seed
    raw = _parent(seed, "raw", "synthetic_protocol_event", fixture.anchor_time, 500)
    semantic = _parent(seed, "semantic", "protocol_semantic_event", fixture.anchor_time, 500)
    context = _parent(seed, "context", "asset_context_event", fixture.anchor_time, 500)
    policy = (
        None
        if fixture.policy_context_status == "UNAVAILABLE"
        else _parent(seed, "policy", "communication_policy_finding", fixture.anchor_time, 500)
    )
    return CyberParentContext(
        raw_parent=raw,
        semantic_parent=semantic,
        asset_context_parent=context,
        policy_parent=policy,
        command_point_id="control_valve_command_percent",
        command_target_asset_key="CV-101",
        command_value_percent=25.0,
        command_observed_at=fixture.anchor_time,
        controller_asset_key="PLC-01",
        relationship_type="CONTROLS",
        relationship_target_asset_key="CV-101",
        policy_context_status=fixture.policy_context_status,
    )


def _parent(
    seed: str, kind: str, evidence_type: str, observed_at: Any, sequence_number: int
) -> EvidenceParentReference:
    evidence_id = uuid.uuid5(uuid.NAMESPACE_URL, f"urn:otsoc:phase6b:{seed}:{kind}")
    digest = hashlib.sha256(f"{seed}|{kind}".encode()).hexdigest()
    return EvidenceParentReference(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        integrity_sha256=digest,
        observed_at=observed_at,
        sequence_number=sequence_number,
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CorrelationFixtureError("A correlation fixture contains a duplicate JSON key.")
        result[key] = value
    return result
