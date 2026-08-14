from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.context.models import (
    AssetContextDerivationProvenance,
    AssetContextEvent,
    AssetContextEvidenceEnvelope,
    CommunicationPolicyFinding,
    PolicyFindingDerivationProvenance,
    PolicyFindingEvidenceEnvelope,
)
from app.correlation.models import (
    CorrelationDerivationProvenance,
    CorrelationEvidenceEnvelope,
    CyberPhysicalCorrelationFinding,
)
from app.protocols.models import CaptureMode, ProtocolSemanticEvent, SyntheticModbusEvent

MAX_EVIDENCE_REQUEST_BYTES = 32_768
MAX_CANONICAL_EVIDENCE_BYTES = 16_384


class StrictEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class HistoricalCoolingTelemetryPayloadV1(StrictEvidenceModel):
    """Read-only compatibility model for accepted historical cooling evidence."""

    simulation_id: str = Field(min_length=5, max_length=80, pattern=r"^[a-zA-Z0-9._:-]+$")
    sequence_number: int = Field(ge=0, le=86_400_000)
    timestamp: AwareDatetime
    simulator_version: str = Field(min_length=1, max_length=24)
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    simulation_time_seconds: int = Field(ge=0, le=86_400_000)
    tank_level_percent: float = Field(ge=5.0, le=95.0)
    pump_command_percent: float = Field(ge=0.0, le=100.0)
    pump_running: bool
    flow_rate_m3h: float = Field(ge=0.0, le=12.0)
    inlet_temperature_c: float = Field(ge=5.0, le=95.0)
    outlet_temperature_c: float = Field(ge=5.0, le=95.0)
    pressure_bar: float = Field(ge=0.0, le=3.0)


class OilGasTelemetryPayloadV2(StrictEvidenceModel):
    domain: Literal["oil_gas_transfer"]
    simulation_id: str = Field(min_length=5, max_length=80, pattern=r"^[a-zA-Z0-9._:-]+$")
    sequence_number: int = Field(ge=0, le=86_400_000)
    timestamp: AwareDatetime
    simulator_version: Literal["3.0.0"]
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    simulation_time_seconds: int = Field(ge=0, le=86_400_000)
    source_tank_level_percent: float = Field(ge=0.0, le=100.0)
    receiving_tank_level_percent: float = Field(ge=0.0, le=100.0)
    transfer_pump_command_percent: float = Field(ge=0.0, le=100.0)
    transfer_pump_running: bool
    control_valve_position_percent: float = Field(ge=0.0, le=100.0)
    pipeline_flow_rate_m3h: float = Field(ge=0.0, le=12.0)
    pipeline_pressure_bar: float = Field(ge=0.0, le=4.0)
    process_temperature_c: float = Field(ge=0.0, le=80.0)


class HistoricalEvidenceProvenanceV1(StrictEvidenceModel):
    producer: Literal["otsoc_simulator"]
    producer_version: str = Field(min_length=1, max_length=24)
    simulation_id: str = Field(min_length=5, max_length=80, pattern=r"^[a-zA-Z0-9._:-]+$")
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceProvenance(StrictEvidenceModel):
    producer: Literal["otsoc_simulator"]
    producer_version: Literal["3.0.0"]
    domain: Literal["oil_gas_transfer"]
    simulation_id: str = Field(min_length=5, max_length=80, pattern=r"^[a-zA-Z0-9._:-]+$")
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    seed: int = Field(ge=0, le=2_147_483_647)


class SyntheticProtocolProvenance(StrictEvidenceModel):
    fixture_set_id: Literal["otsoc.phase4b.synthetic_modbus"]
    fixture_set_version: Literal["1.0.0"]
    generator: Literal["otsoc_static_fixture"]
    generator_version: Literal["1.0.0"]
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    capture_mode: CaptureMode
    educational_only: Literal[True]


class SemanticDerivationProvenance(StrictEvidenceModel):
    derivation_kind: Literal["SEMANTIC_INTERPRETATION"]
    source_evidence_id: uuid.UUID
    source_evidence_integrity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_id: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    profile_version: Literal["1.0.0"]
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decoder_name: Literal["otsoc_offline_modbus_semantics"]
    decoder_version: Literal["1.0.0"]
    canonicalization_version: Literal["otsoc-canonical-json-1"]
    educational_only: Literal[True]


class HistoricalEvidenceEnvelopeV1(StrictEvidenceModel):
    """Historical verification/read model; never accepted by the write API."""

    source_key: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    source_event_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:-]+$")
    evidence_type: Literal["simulator_telemetry"]
    observed_at: AwareDatetime
    sequence_number: int = Field(ge=0, le=86_400_000)
    payload_schema: Literal["otsoc.simulator.telemetry"]
    payload_schema_version: Literal["1.0.0"]
    payload: HistoricalCoolingTelemetryPayloadV1
    provenance: HistoricalEvidenceProvenanceV1

    @model_validator(mode="after")
    def validate_envelope_consistency(self) -> HistoricalEvidenceEnvelopeV1:
        _validate_common_consistency(self)
        return self


class EvidenceIngestRequest(StrictEvidenceModel):
    source_key: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    source_event_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:-]+$")
    evidence_type: Literal["simulator_telemetry"]
    observed_at: AwareDatetime
    sequence_number: int = Field(ge=0, le=86_400_000)
    payload_schema: Literal["otsoc.simulator.telemetry"]
    payload_schema_version: Literal["2.0.0"]
    payload: OilGasTelemetryPayloadV2
    provenance: EvidenceProvenance

    @model_validator(mode="after")
    def validate_envelope_consistency(self) -> EvidenceIngestRequest:
        _validate_common_consistency(self)
        if self.payload.domain != self.provenance.domain:
            raise ValueError("payload domain does not match provenance")
        return self


class SyntheticProtocolEvidenceEnvelope(StrictEvidenceModel):
    source_key: Literal["synthetic-modbus-fixture-primary"]
    source_event_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._:-]+$")
    evidence_type: Literal["synthetic_protocol_event"]
    observed_at: AwareDatetime
    sequence_number: int = Field(ge=0, le=86_400_000)
    payload_schema: Literal["otsoc.synthetic_modbus.event"]
    payload_schema_version: Literal["1.0.0"]
    payload: SyntheticModbusEvent
    provenance: SyntheticProtocolProvenance

    @model_validator(mode="after")
    def validate_protocol_envelope_consistency(self) -> SyntheticProtocolEvidenceEnvelope:
        if self.payload.observed_at != self.observed_at:
            raise ValueError("protocol payload timestamp does not match observed_at")
        if self.payload.capture_mode is not self.provenance.capture_mode:
            raise ValueError("protocol capture mode does not match provenance")
        if self.payload.fixture_id != self.source_event_id:
            raise ValueError("protocol fixture ID does not match source event ID")
        return self


class SemanticEvidenceEnvelope(StrictEvidenceModel):
    source_key: Literal["protocol-semantics-decoder"]
    source_event_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-f0-9-]{36}$")
    evidence_type: Literal["protocol_semantic_event"]
    observed_at: AwareDatetime
    sequence_number: int = Field(ge=0, le=86_400_000)
    payload_schema: Literal["otsoc.protocol.semantic_event"]
    payload_schema_version: Literal["1.0.0"]
    payload: ProtocolSemanticEvent
    provenance: SemanticDerivationProvenance

    @model_validator(mode="after")
    def validate_semantic_envelope_consistency(self) -> SemanticEvidenceEnvelope:
        if self.payload.observed_at != self.observed_at:
            raise ValueError("semantic payload timestamp does not match observed_at")
        if str(self.payload.semantic_event_id) == str(self.payload.source_evidence_id):
            raise ValueError("semantic evidence must not reuse the raw evidence ID")
        if self.payload.source_evidence_id != self.provenance.source_evidence_id:
            raise ValueError("semantic source evidence ID does not match provenance")
        if (
            self.payload.source_evidence_integrity_sha256
            != self.provenance.source_evidence_integrity_sha256
        ):
            raise ValueError("semantic source integrity hash does not match provenance")
        if self.payload.profile_sha256 != self.provenance.profile_sha256:
            raise ValueError("semantic profile digest does not match provenance")
        if self.payload.decoder_version != self.provenance.decoder_version:
            raise ValueError("semantic decoder version does not match provenance")
        return self


class EvidenceIngestionReceipt(StrictEvidenceModel):
    status: Literal["accepted", "duplicate_existing"]
    evidence_id: uuid.UUID
    source_key: str
    receipt_timestamp: datetime
    schema_version: Literal["1.0.0"] = "1.0.0"


class EvidenceRecordResponse(StrictEvidenceModel):
    evidence_id: uuid.UUID
    evidence_version: int
    source_key: str
    source_event_id: str
    evidence_type: str
    observed_at: datetime
    received_at: datetime
    sequence_number: int | None
    payload_schema: str
    payload_schema_version: Literal["1.0.0", "2.0.0"]
    payload: (
        HistoricalCoolingTelemetryPayloadV1
        | OilGasTelemetryPayloadV2
        | SyntheticModbusEvent
        | ProtocolSemanticEvent
        | AssetContextEvent
        | CommunicationPolicyFinding
        | CyberPhysicalCorrelationFinding
    )
    provenance: (
        HistoricalEvidenceProvenanceV1
        | EvidenceProvenance
        | SyntheticProtocolProvenance
        | SemanticDerivationProvenance
        | AssetContextDerivationProvenance
        | PolicyFindingDerivationProvenance
        | CorrelationDerivationProvenance
    )
    integrity_sha256: str
    canonical_byte_length: int

    @model_validator(mode="after")
    def validate_payload_version(self) -> EvidenceRecordResponse:
        expected: tuple[type[BaseModel], type[BaseModel]]
        if self.evidence_type == "simulator_telemetry" and self.payload_schema_version == "1.0.0":
            expected = (HistoricalCoolingTelemetryPayloadV1, HistoricalEvidenceProvenanceV1)
        elif self.evidence_type == "simulator_telemetry" and self.payload_schema_version == "2.0.0":
            expected = (OilGasTelemetryPayloadV2, EvidenceProvenance)
        elif (
            self.evidence_type == "synthetic_protocol_event"
            and self.payload_schema == "otsoc.synthetic_modbus.event"
            and self.payload_schema_version == "1.0.0"
        ):
            expected = (SyntheticModbusEvent, SyntheticProtocolProvenance)
        elif (
            self.evidence_type == "protocol_semantic_event"
            and self.payload_schema == "otsoc.protocol.semantic_event"
            and self.payload_schema_version == "1.0.0"
        ):
            expected = (ProtocolSemanticEvent, SemanticDerivationProvenance)
        elif (
            self.evidence_type == "asset_context_event"
            and self.payload_schema == "otsoc.asset.context_event"
            and self.payload_schema_version == "1.0.0"
        ):
            expected = (AssetContextEvent, AssetContextDerivationProvenance)
        elif (
            self.evidence_type == "communication_policy_finding"
            and self.payload_schema == "otsoc.communication_policy.finding"
            and self.payload_schema_version == "1.0.0"
        ):
            expected = (CommunicationPolicyFinding, PolicyFindingDerivationProvenance)
        elif (
            self.evidence_type == "correlation_finding"
            and self.payload_schema == "otsoc.cyber_physical.correlation_finding"
            and self.payload_schema_version == "1.0.0"
        ):
            expected = (CyberPhysicalCorrelationFinding, CorrelationDerivationProvenance)
        else:
            raise ValueError("unsupported evidence type/schema/version combination")
        if not isinstance(self.payload, expected[0]) or not isinstance(
            self.provenance, expected[1]
        ):
            raise ValueError("evidence payload or provenance does not match its typed contract")
        return self


class EvidenceListResponse(StrictEvidenceModel):
    items: list[EvidenceRecordResponse]
    limit: int
    offset: int
    next_cursor: str | None = None
    evidence_type: str | None = None
    source_key: str | None = None
    observed_from: datetime | None = None
    observed_to: datetime | None = None


def _validate_common_consistency(
    envelope: HistoricalEvidenceEnvelopeV1 | EvidenceIngestRequest,
) -> None:
    if envelope.payload.sequence_number != envelope.sequence_number:
        raise ValueError("payload sequence does not match envelope sequence")
    if envelope.payload.timestamp != envelope.observed_at:
        raise ValueError("payload timestamp does not match observed_at")
    if envelope.payload.simulation_id != envelope.provenance.simulation_id:
        raise ValueError("payload simulation_id does not match provenance")
    if envelope.payload.configuration_hash != envelope.provenance.configuration_hash:
        raise ValueError("payload configuration hash does not match provenance")
    if envelope.payload.simulator_version != envelope.provenance.producer_version:
        raise ValueError("payload simulator version does not match provenance")


InternalEvidenceEnvelope = (
    SyntheticProtocolEvidenceEnvelope
    | SemanticEvidenceEnvelope
    | AssetContextEvidenceEnvelope
    | PolicyFindingEvidenceEnvelope
    | CorrelationEvidenceEnvelope
)
VerifiableEvidenceEnvelope = (
    HistoricalEvidenceEnvelopeV1 | EvidenceIngestRequest | InternalEvidenceEnvelope
)
