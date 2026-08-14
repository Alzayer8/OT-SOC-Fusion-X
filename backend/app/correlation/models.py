from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

CORRELATION_PROFILE_ID = "otsoc.correlation.oil_gas_transfer"
CORRELATION_PROFILE_VERSION = "1.0.0"
CORRELATION_FINDING_SCHEMA = "otsoc.cyber_physical.correlation_finding"
CORRELATION_FINDING_SCHEMA_VERSION = "1.0.0"
CORRELATION_EVALUATOR_NAME = "otsoc_offline_correlation_evaluator"
CORRELATION_EVALUATOR_VERSION = "1.0.0"
CORRELATION_SOURCE_KEY = "cyber-physical-correlation-evaluator"
CORRELATION_SOURCE_ID = uuid.UUID("21f51f40-c7bb-57a6-993a-416b244185b8")
CORRELATION_EVIDENCE_TYPE = "correlation_finding"
CANONICALIZATION_VERSION = "otsoc-canonical-json-1"

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SemVer = Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
SafeKey = Annotated[
    str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
]
PointId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]


class StrictCorrelationModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
        allow_inf_nan=False,
        frozen=True,
    )


class CorrelationStatus(StrEnum):
    CORRELATED = "CORRELATED"
    NOT_CORRELATED = "NOT_CORRELATED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INDETERMINATE = "INDETERMINATE"


class CorrelationReasonCode(StrEnum):
    PARENT_EVIDENCE_NOT_VERIFIED = "PARENT_EVIDENCE_NOT_VERIFIED"
    PROFILE_VERSION_UNSUPPORTED = "PROFILE_VERSION_UNSUPPORTED"
    PROFILE_DIGEST_MISMATCH = "PROFILE_DIGEST_MISMATCH"
    UNSUPPORTED_CORRELATION_RULE = "UNSUPPORTED_CORRELATION_RULE"
    RUN_ID_MISMATCH = "RUN_ID_MISMATCH"
    CONFIGURATION_MISMATCH = "CONFIGURATION_MISMATCH"
    SIMULATOR_VERSION_MISMATCH = "SIMULATOR_VERSION_MISMATCH"
    CLOCK_SEQUENCE_MISMATCH = "CLOCK_SEQUENCE_MISMATCH"
    ASSET_RELATION_MISMATCH = "ASSET_RELATION_MISMATCH"
    POINT_RELATION_NOT_DEFINED = "POINT_RELATION_NOT_DEFINED"
    WINDOW_NOT_FINALIZED = "WINDOW_NOT_FINALIZED"
    MISSING_TELEMETRY = "MISSING_TELEMETRY"
    INSUFFICIENT_SAMPLES = "INSUFFICIENT_SAMPLES"
    TELEMETRY_GAP_EXCEEDED = "TELEMETRY_GAP_EXCEEDED"
    BASELINE_NOT_STABLE = "BASELINE_NOT_STABLE"
    PROCESS_CHANGE_OUTSIDE_WINDOW = "PROCESS_CHANGE_OUTSIDE_WINDOW"
    PROCESS_EFFECT_DIRECTION_MISMATCH = "PROCESS_EFFECT_DIRECTION_MISMATCH"
    NO_PROCESS_CHANGE = "NO_PROCESS_CHANGE"
    CORRELATION_MATCH = "CORRELATION_MATCH"


REASON_PRECEDENCE = tuple(CorrelationReasonCode)


class ProcessChange(StrEnum):
    INCREASED = "INCREASED"
    DECREASED = "DECREASED"
    UNCHANGED = "UNCHANGED"
    UNAVAILABLE = "UNAVAILABLE"


class ObservationRole(StrEnum):
    REQUIRED = "REQUIRED"
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"


class CorrelationTelemetryPayload(StrictCorrelationModel):
    domain: Literal["oil_gas_transfer"]
    simulation_id: str = Field(min_length=5, max_length=80, pattern=r"^[a-zA-Z0-9._:-]+$")
    sequence_number: int = Field(ge=0, le=86_400_000)
    timestamp: AwareDatetime
    simulator_version: str = Field(min_length=1, max_length=24)
    configuration_hash: Sha256
    simulation_time_seconds: int = Field(ge=0, le=86_400_000)
    source_tank_level_percent: float = Field(ge=0.0, le=100.0)
    receiving_tank_level_percent: float = Field(ge=0.0, le=100.0)
    transfer_pump_command_percent: float = Field(ge=0.0, le=100.0)
    transfer_pump_running: bool
    control_valve_position_percent: float = Field(ge=0.0, le=100.0)
    pipeline_flow_rate_m3h: float = Field(ge=0.0, le=12.0)
    pipeline_pressure_bar: float = Field(ge=0.0, le=4.0)
    process_temperature_c: float = Field(ge=0.0, le=80.0)


class EvidenceParentReference(StrictCorrelationModel):
    evidence_id: uuid.UUID
    evidence_type: str = Field(min_length=1, max_length=48)
    integrity_sha256: Sha256
    observed_at: AwareDatetime
    sequence_number: int | None = Field(default=None, ge=0, le=86_400_000)


class TelemetryEvidence(StrictCorrelationModel):
    evidence_id: uuid.UUID
    evidence_type: Literal["simulator_telemetry"]
    integrity_sha256: Sha256
    observed_at: AwareDatetime
    sequence_number: int = Field(ge=0, le=86_400_000)
    payload_schema: Literal["otsoc.simulator.telemetry"]
    payload_schema_version: Literal["2.0.0"]
    payload: CorrelationTelemetryPayload

    @model_validator(mode="after")
    def validate_telemetry_envelope(self) -> TelemetryEvidence:
        if self.observed_at != self.payload.timestamp:
            raise ValueError("telemetry payload timestamp does not match observed_at")
        if self.sequence_number != self.payload.sequence_number:
            raise ValueError("telemetry payload sequence does not match its envelope")
        return self

    def parent_reference(self) -> EvidenceParentReference:
        return EvidenceParentReference(
            evidence_id=self.evidence_id,
            evidence_type=self.evidence_type,
            integrity_sha256=self.integrity_sha256,
            observed_at=self.observed_at,
            sequence_number=self.sequence_number,
        )


class CyberParentContext(StrictCorrelationModel):
    raw_parent: EvidenceParentReference
    semantic_parent: EvidenceParentReference
    asset_context_parent: EvidenceParentReference
    policy_parent: EvidenceParentReference | None
    command_point_id: Literal["control_valve_command_percent"]
    command_target_asset_key: Literal["CV-101"]
    command_value_percent: float = Field(ge=0.0, le=100.0)
    command_observed_at: AwareDatetime
    controller_asset_key: Literal["PLC-01"]
    relationship_type: Literal["CONTROLS"]
    relationship_target_asset_key: Literal["CV-101"]
    policy_context_status: Literal["APPROVED", "DENIED", "UNKNOWN", "UNAVAILABLE"]


class CorrelationEvaluationInput(StrictCorrelationModel):
    profile_id: str = Field(min_length=1, max_length=80)
    profile_version: SemVer
    profile_sha256: Sha256
    rule_id: str = Field(min_length=1, max_length=80)
    rule_version: SemVer
    cyber_context: CyberParentContext | None
    telemetry: tuple[TelemetryEvidence, ...]
    available_point_ids: tuple[PointId, ...]
    reevaluates_parent: EvidenceParentReference | None = None

    @model_validator(mode="after")
    def validate_unique_points(self) -> CorrelationEvaluationInput:
        if len(self.available_point_ids) != len(set(self.available_point_ids)):
            raise ValueError("available process point IDs must be unique")
        return self


class PointObservation(StrictCorrelationModel):
    point_id: PointId
    asset_key: SafeKey
    baseline_value: float | bool | None
    observed_value: float | bool | None
    delta: float | None
    unit: str = Field(min_length=1, max_length=40)
    expected_direction: ProcessChange
    observed_direction: ProcessChange
    threshold: float | None
    persistence_required: int = Field(ge=0, le=100)
    persistence_observed: int = Field(ge=0, le=100)
    role: ObservationRole
    condition_met: bool


class ProcessAssetReference(StrictCorrelationModel):
    asset_id: uuid.UUID
    asset_key: SafeKey


class CorrelationDecision(StrictCorrelationModel):
    status: CorrelationStatus
    reason_code: CorrelationReasonCode
    anchor_time: AwareDatetime | None
    correlation_start_time: AwareDatetime | None
    correlation_end_time: AwareDatetime | None
    evidence_observed_at: AwareDatetime
    temporal_relation: Literal[
        "FOLLOWED_WITHIN_WINDOW",
        "PROCESS_ONLY_WITHIN_WINDOW",
        "NO_MATCHING_CHANGE",
        "UNAVAILABLE",
    ]
    simulation_id: str | None
    configuration_hash: Sha256 | None
    simulator_version: str | None
    telemetry_schema_version: str | None
    run_origin: AwareDatetime | None
    baseline_sample_count: int = Field(ge=0)
    effect_sample_count: int = Field(ge=0)
    maximum_gap_seconds: float | None = Field(default=None, ge=0.0)
    matched_minimum_set: str | None
    process_asset_keys: tuple[SafeKey, ...]
    affected_process_points: tuple[PointId, ...]
    observations: tuple[PointObservation, ...]
    statement_template_id: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=600)


class CyberPhysicalCorrelationFinding(StrictCorrelationModel):
    correlation_id: uuid.UUID
    finding_schema: Literal["otsoc.cyber_physical.correlation_finding"]
    finding_schema_version: Literal["1.0.0"]
    correlation_profile_id: Literal["otsoc.correlation.oil_gas_transfer"]
    correlation_profile_version: SemVer
    correlation_profile_sha256: Sha256
    correlation_rule_id: str = Field(min_length=1, max_length=80)
    correlation_rule_version: SemVer
    evaluator_name: Literal["otsoc_offline_correlation_evaluator"]
    evaluator_version: SemVer
    canonicalization_version: Literal["otsoc-canonical-json-1"]
    primary_cyber_evidence_id: uuid.UUID | None
    primary_cyber_evidence_integrity_sha256: Sha256 | None
    semantic_evidence_id: uuid.UUID | None
    semantic_evidence_integrity_sha256: Sha256 | None
    asset_context_evidence_id: uuid.UUID | None
    asset_context_evidence_integrity_sha256: Sha256 | None
    policy_finding_evidence_id: uuid.UUID | None
    policy_finding_evidence_integrity_sha256: Sha256 | None
    policy_context_status: Literal["APPROVED", "DENIED", "UNKNOWN", "UNAVAILABLE"]
    telemetry_parents: tuple[EvidenceParentReference, ...]
    reevaluates_finding_id: uuid.UUID | None
    parent_set_sha256: Sha256
    simulation_id: str | None
    configuration_hash: Sha256 | None
    simulator_version: str | None
    telemetry_schema_version: str | None
    domain: Literal["oil_gas_transfer"]
    process_model_version: Literal["3.6"]
    timestamp_authority: Literal["OBSERVED_AT"]
    run_origin: AwareDatetime | None
    anchor_time: AwareDatetime | None
    correlation_start_time: AwareDatetime | None
    correlation_end_time: AwareDatetime | None
    evidence_observed_at: AwareDatetime
    baseline_method: Literal["FIXED_PRECEDING_WINDOW"]
    baseline_sample_count: int = Field(ge=0)
    effect_sample_count: int = Field(ge=0)
    maximum_gap_seconds: float | None = Field(default=None, ge=0.0)
    process_assets: tuple[ProcessAssetReference, ...]
    affected_process_points: tuple[PointId, ...]
    observations: tuple[PointObservation, ...]
    temporal_relation: str = Field(min_length=1, max_length=48)
    correlation_status: CorrelationStatus
    reason_code: CorrelationReasonCode
    matched_minimum_set: str | None
    statement_template_id: str = Field(min_length=1, max_length=80)
    analyst_readable_explanation: str = Field(min_length=1, max_length=600)
    cyber_cause_asserted: Literal[False]
    causality_inferred: Literal[False]
    malicious_intent_inferred: Literal[False]
    ground_truth_used: Literal[False]
    derivation_kind: Literal["CYBER_PHYSICAL_CORRELATION"]

    @field_validator("analyst_readable_explanation")
    @classmethod
    def prohibit_overclaiming(cls, value: str) -> str:
        prohibited = {"caused", "attack", "attacker", "malicious", "compromised", "incident"}
        words = {word.strip(".,:;!?()[]").lower() for word in value.split()}
        if words & prohibited:
            raise ValueError(
                "correlation explanation contains a prohibited causal or incident term"
            )
        return value

    @model_validator(mode="after")
    def validate_cyber_boundary(self) -> CyberPhysicalCorrelationFinding:
        if self.correlation_rule_id == "CPR-S4-PUMP-FLOW-001" and any(
            value is not None
            for value in (
                self.primary_cyber_evidence_id,
                self.semantic_evidence_id,
                self.asset_context_evidence_id,
                self.policy_finding_evidence_id,
            )
        ):
            raise ValueError("S4 must not contain a cyber, context, or policy parent")
        return self


class CorrelationDerivationProvenance(StrictCorrelationModel):
    derivation_kind: Literal["CYBER_PHYSICAL_CORRELATION"]
    parent_references: tuple[EvidenceParentReference, ...]
    parent_set_sha256: Sha256
    correlation_profile_id: Literal["otsoc.correlation.oil_gas_transfer"]
    correlation_profile_version: SemVer
    correlation_profile_sha256: Sha256
    correlation_rule_id: str
    correlation_rule_version: SemVer
    evaluator_name: Literal["otsoc_offline_correlation_evaluator"]
    evaluator_version: SemVer
    inventory_profile_id: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    inventory_profile_version: Literal["1.0.0"]
    inventory_profile_sha256: Sha256
    policy_profile_id: Literal["otsoc.communication_policy.oil_gas_transfer"]
    policy_profile_version: Literal["1.0.0"]
    policy_profile_sha256: Sha256
    protocol_profile_id: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    protocol_profile_version: Literal["1.0.0"]
    protocol_profile_sha256: Sha256
    simulator_version: Literal["3.0.0"]
    telemetry_schema: Literal["otsoc.simulator.telemetry"]
    telemetry_schema_version: Literal["2.0.0"]
    domain: Literal["oil_gas_transfer"]
    process_model_version: Literal["3.6"]
    simulation_id: str | None
    configuration_hash: Sha256 | None
    canonicalization_version: Literal["otsoc-canonical-json-1"]
    educational_only: Literal[True]
    ground_truth_used: Literal[False]


class CorrelationEvidenceEnvelope(StrictCorrelationModel):
    source_key: Literal["cyber-physical-correlation-evaluator"]
    source_event_id: Annotated[str, Field(pattern=r"^[a-f0-9-]{36}$")]
    evidence_type: Literal["correlation_finding"]
    observed_at: AwareDatetime
    sequence_number: int = Field(ge=0, le=86_400_000)
    payload_schema: Literal["otsoc.cyber_physical.correlation_finding"]
    payload_schema_version: Literal["1.0.0"]
    payload: CyberPhysicalCorrelationFinding
    provenance: CorrelationDerivationProvenance

    @model_validator(mode="after")
    def validate_correlation_envelope(self) -> CorrelationEvidenceEnvelope:
        if self.payload.evidence_observed_at != self.observed_at:
            raise ValueError("correlation finding timestamp does not match observed_at")
        if self.payload.parent_set_sha256 != self.provenance.parent_set_sha256:
            raise ValueError("correlation parent-set digest does not match provenance")
        if self.payload.correlation_profile_sha256 != self.provenance.correlation_profile_sha256:
            raise ValueError("correlation profile digest does not match provenance")
        return self
