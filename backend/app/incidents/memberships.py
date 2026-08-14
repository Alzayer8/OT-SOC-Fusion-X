from __future__ import annotations

import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.context.models import (
    AssetContextEvent,
    CommunicationPolicyFinding,
    PolicyFindingDerivationProvenance,
)
from app.correlation.models import (
    CorrelationDerivationProvenance,
    CyberPhysicalCorrelationFinding,
)
from app.evidence.models import EvidenceRecord
from app.evidence.schemas import OilGasTelemetryPayloadV2
from app.evidence.service import verify_record_integrity
from app.incidents.models import EvidenceSelection, IncidentQualificationRequest
from app.protocols.models import ProtocolSemanticEvent, SyntheticModbusEvent


class IncidentEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedIncidentEvidenceBundle:
    policy_record: EvidenceRecord | None
    policy: CommunicationPolicyFinding | None
    correlation_record: EvidenceRecord | None
    correlation: CyberPhysicalCorrelationFinding | None
    semantic_record: EvidenceRecord | None
    semantic: ProtocolSemanticEvent | None
    context_record: EvidenceRecord | None
    context: AssetContextEvent | None
    raw_record: EvidenceRecord | None
    raw: SyntheticModbusEvent | None
    telemetry_records: tuple[EvidenceRecord, ...]


def verify_qualification_evidence(
    session: Session,
    request: IncidentQualificationRequest,
) -> VerifiedIncidentEvidenceBundle:
    policy_record = None
    policy = None
    correlation_record = None
    correlation = None
    semantic_record = None
    semantic = None
    context_record = None
    context = None
    raw_record = None
    raw = None
    telemetry_records: tuple[EvidenceRecord, ...] = ()

    if request.policy_finding is not None:
        policy_record = _verified_selection(
            session,
            request.policy_finding,
            evidence_type="communication_policy_finding",
            schema="otsoc.communication_policy.finding",
            version="1.0.0",
        )
        policy = _validate_model(
            CommunicationPolicyFinding,
            policy_record.payload,
            "The stored communication-policy finding is invalid.",
        )

    if request.correlation_finding is not None:
        correlation_record = _verified_selection(
            session,
            request.correlation_finding,
            evidence_type="correlation_finding",
            schema="otsoc.cyber_physical.correlation_finding",
            version="1.0.0",
        )
        correlation = _validate_model(
            CyberPhysicalCorrelationFinding,
            correlation_record.payload,
            "The stored cyber-physical correlation finding is invalid.",
        )
        correlation_provenance = _validate_model(
            CorrelationDerivationProvenance,
            correlation_record.provenance,
            "The stored correlation provenance is invalid.",
        )
        if correlation.correlation_id != correlation_record.evidence_id:
            raise IncidentEvidenceError("The correlation identity does not match its record.")
        if correlation.parent_set_sha256 != correlation_provenance.parent_set_sha256:
            raise IncidentEvidenceError("The correlation parent-set digest is inconsistent.")
        telemetry_records = tuple(
            _verified_reference(
                session,
                item.evidence_id,
                item.integrity_sha256,
                evidence_type="simulator_telemetry",
                schema="otsoc.simulator.telemetry",
                version="2.0.0",
            )
            for item in correlation.telemetry_parents
        )
        _validate_correlation_telemetry_scope(correlation, telemetry_records)
        if correlation.policy_finding_evidence_id is not None:
            correlated_policy_record = _verified_reference(
                session,
                correlation.policy_finding_evidence_id,
                _required_hash(
                    correlation.policy_finding_evidence_integrity_sha256,
                    "correlation policy parent",
                ),
                evidence_type="communication_policy_finding",
                schema="otsoc.communication_policy.finding",
                version="1.0.0",
            )
            if (
                policy_record is not None
                and correlated_policy_record.evidence_id != policy_record.evidence_id
            ):
                raise IncidentEvidenceError("The selected policy and correlation lineage differ.")
            policy_record = correlated_policy_record
            policy = _validate_model(
                CommunicationPolicyFinding,
                policy_record.payload,
                "The correlated policy finding is invalid.",
            )

    if policy_record is not None and policy is not None:
        (
            semantic_record,
            semantic,
            context_record,
            context,
            raw_record,
            raw,
        ) = _verify_policy_lineage(session, policy_record, policy)

    if correlation is not None and correlation.correlation_rule_id == "CPR-S3-CV-TRANSFER-001":
        if any(
            value is None
            for value in (
                correlation.semantic_evidence_id,
                correlation.semantic_evidence_integrity_sha256,
                correlation.asset_context_evidence_id,
                correlation.asset_context_evidence_integrity_sha256,
            )
        ):
            raise IncidentEvidenceError("An S3 correlation is missing required cyber lineage.")
        correlated_semantic = _verified_reference(
            session,
            _required_uuid(correlation.semantic_evidence_id, "semantic parent"),
            _required_hash(
                correlation.semantic_evidence_integrity_sha256,
                "semantic parent",
            ),
            evidence_type="protocol_semantic_event",
            schema="otsoc.protocol.semantic_event",
            version="1.0.0",
        )
        correlated_context = _verified_reference(
            session,
            _required_uuid(correlation.asset_context_evidence_id, "asset-context parent"),
            _required_hash(
                correlation.asset_context_evidence_integrity_sha256,
                "asset-context parent",
            ),
            evidence_type="asset_context_event",
            schema="otsoc.asset.context_event",
            version="1.0.0",
        )
        if (
            semantic_record is not None
            and semantic_record.evidence_id != correlated_semantic.evidence_id
        ):
            raise IncidentEvidenceError("The correlation semantic lineage does not match policy.")
        if (
            context_record is not None
            and context_record.evidence_id != correlated_context.evidence_id
        ):
            raise IncidentEvidenceError("The correlation asset lineage does not match policy.")
        semantic_record = correlated_semantic
        context_record = correlated_context
        semantic = _validate_model(
            ProtocolSemanticEvent,
            semantic_record.payload,
            "The correlated semantic event is invalid.",
        )
        context = _validate_model(
            AssetContextEvent,
            context_record.payload,
            "The correlated asset-context event is invalid.",
        )
        raw_record = _verified_reference(
            session,
            semantic.source_evidence_id,
            semantic.source_evidence_integrity_sha256,
            evidence_type="synthetic_protocol_event",
            schema="otsoc.synthetic_modbus.event",
            version="1.0.0",
        )
        raw = _validate_model(
            SyntheticModbusEvent,
            raw_record.payload,
            "The correlated raw protocol event is invalid.",
        )

    return VerifiedIncidentEvidenceBundle(
        policy_record=policy_record,
        policy=policy,
        correlation_record=correlation_record,
        correlation=correlation,
        semantic_record=semantic_record,
        semantic=semantic,
        context_record=context_record,
        context=context,
        raw_record=raw_record,
        raw=raw,
        telemetry_records=telemetry_records,
    )


def _verify_policy_lineage(
    session: Session,
    policy_record: EvidenceRecord,
    policy: CommunicationPolicyFinding,
) -> tuple[
    EvidenceRecord,
    ProtocolSemanticEvent,
    EvidenceRecord,
    AssetContextEvent,
    EvidenceRecord,
    SyntheticModbusEvent,
]:
    provenance = _validate_model(
        PolicyFindingDerivationProvenance,
        policy_record.provenance,
        "The stored policy provenance is invalid.",
    )
    semantic_record = _verified_reference(
        session,
        policy.semantic_event_id,
        policy.semantic_evidence_integrity_sha256,
        evidence_type="protocol_semantic_event",
        schema="otsoc.protocol.semantic_event",
        version="1.0.0",
    )
    context_record = _verified_reference(
        session,
        policy.asset_context_event_id,
        provenance.asset_context_integrity_sha256,
        evidence_type="asset_context_event",
        schema="otsoc.asset.context_event",
        version="1.0.0",
    )
    raw_record = _verified_reference(
        session,
        policy.source_evidence_id,
        policy.source_evidence_integrity_sha256,
        evidence_type="synthetic_protocol_event",
        schema="otsoc.synthetic_modbus.event",
        version="1.0.0",
    )
    semantic = _validate_model(
        ProtocolSemanticEvent,
        semantic_record.payload,
        "The stored semantic event is invalid.",
    )
    context = _validate_model(
        AssetContextEvent,
        context_record.payload,
        "The stored asset-context event is invalid.",
    )
    raw = _validate_model(
        SyntheticModbusEvent,
        raw_record.payload,
        "The stored raw protocol event is invalid.",
    )
    if (
        semantic.semantic_event_id != semantic_record.evidence_id
        or semantic.source_evidence_id != raw_record.evidence_id
        or context.asset_context_event_id != context_record.evidence_id
        or context.semantic_event_id != semantic_record.evidence_id
        or context.source_evidence_id != raw_record.evidence_id
        or policy.finding_id != policy_record.evidence_id
        or policy.semantic_event_id != semantic_record.evidence_id
        or policy.asset_context_event_id != context_record.evidence_id
    ):
        raise IncidentEvidenceError("The policy evidence lineage is inconsistent.")
    return semantic_record, semantic, context_record, context, raw_record, raw


def _verified_selection(
    session: Session,
    selection: EvidenceSelection,
    *,
    evidence_type: str,
    schema: str,
    version: str,
) -> EvidenceRecord:
    return _verified_reference(
        session,
        selection.evidence_id,
        selection.expected_integrity_sha256,
        evidence_type=evidence_type,
        schema=schema,
        version=version,
    )


def _verified_reference(
    session: Session,
    evidence_id: uuid.UUID,
    expected_integrity_sha256: str,
    *,
    evidence_type: str,
    schema: str,
    version: str,
) -> EvidenceRecord:
    record = session.scalar(
        select(EvidenceRecord)
        .options(joinedload(EvidenceRecord.source))
        .where(EvidenceRecord.evidence_id == evidence_id)
    )
    if record is None:
        raise IncidentEvidenceError("A required stored evidence record was not found.")
    if (
        record.evidence_type != evidence_type
        or record.payload_schema != schema
        or record.payload_schema_version != version
    ):
        raise IncidentEvidenceError("A stored evidence type/schema/version is not allowed.")
    if record.integrity_sha256 != expected_integrity_sha256:
        raise IncidentEvidenceError("A supplied evidence digest does not match stored evidence.")
    if not verify_record_integrity(record):
        raise IncidentEvidenceError("A stored evidence integrity check failed.")
    return record


def _validate_correlation_telemetry_scope(
    correlation: CyberPhysicalCorrelationFinding,
    records: tuple[EvidenceRecord, ...],
) -> None:
    for record in records:
        payload = _validate_model(
            OilGasTelemetryPayloadV2,
            record.payload,
            "A correlation telemetry parent is invalid.",
        )
        if (
            payload.simulation_id != correlation.simulation_id
            or payload.configuration_hash != correlation.configuration_hash
        ):
            raise IncidentEvidenceError("Correlation telemetry run/configuration is incompatible.")


def _validate_model[BaseModelType: BaseModel](
    model: type[BaseModelType], value: object, message: str
) -> BaseModelType:
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise IncidentEvidenceError(message) from exc


def _required_hash(value: str | None, label: str) -> str:
    if value is None:
        raise IncidentEvidenceError(f"The {label} integrity digest is missing.")
    return value


def _required_uuid(value: uuid.UUID | None, label: str) -> uuid.UUID:
    if value is None:
        raise IncidentEvidenceError(f"The {label} identity is missing.")
    return value
