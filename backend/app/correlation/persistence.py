from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.context.inventory import load_inventory_profile
from app.context.models import AssetContextEvent, CommunicationPolicyFinding
from app.context.policy import load_policy_profile
from app.correlation.evaluator import evaluate_correlation
from app.correlation.models import (
    CORRELATION_EVIDENCE_TYPE,
    CORRELATION_FINDING_SCHEMA,
    CORRELATION_FINDING_SCHEMA_VERSION,
    CORRELATION_SOURCE_KEY,
    CorrelationEvaluationInput,
    CorrelationEvidenceEnvelope,
    CorrelationTelemetryPayload,
    CyberParentContext,
    CyberPhysicalCorrelationFinding,
    EvidenceParentReference,
    StrictCorrelationModel,
    TelemetryEvidence,
)
from app.correlation.profile import load_correlation_profile
from app.evidence.models import EvidenceRecord
from app.evidence.schemas import EvidenceIngestionReceipt
from app.evidence.service import ingest_internal_evidence, verify_record_integrity
from app.protocols.models import (
    FunctionSemantic,
    OperationCategory,
    OperationCompatibility,
    ProtocolSemanticEvent,
)
from app.protocols.profile import load_profile as load_protocol_profile


class CorrelationEvidenceError(ValueError):
    pass


class ParentSelection(StrictCorrelationModel):
    evidence_id: uuid.UUID
    expected_integrity_sha256: str


class CorrelationPersistenceRequest(StrictCorrelationModel):
    rule_id: str
    semantic_parent: ParentSelection | None = None
    asset_context_parent: ParentSelection | None = None
    policy_parent: ParentSelection | None = None
    telemetry_parents: tuple[ParentSelection, ...]
    reevaluates_parent: ParentSelection | None = None


@dataclass(frozen=True)
class CorrelationPersistenceResult:
    receipt: EvidenceIngestionReceipt
    finding: CyberPhysicalCorrelationFinding


def persist_correlation_finding(
    session: Session,
    request: CorrelationPersistenceRequest,
    *,
    receipt_timestamp: datetime | None = None,
) -> CorrelationPersistenceResult:
    inventory = load_inventory_profile()
    protocol = load_protocol_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=protocol)
    profile = load_correlation_profile(
        inventory=inventory,
        policy=policy,
        protocol_profile=protocol,
    )
    rule = profile.rules.get(request.rule_id)
    if rule is None:
        raise CorrelationEvidenceError("The requested correlation rule is unsupported.")
    telemetry = tuple(
        _telemetry_from_record(_verified_selection(session, item, "simulator_telemetry"))
        for item in request.telemetry_parents
    )
    cyber: CyberParentContext | None
    if rule.evaluator_branch == "S3":
        cyber = _s3_cyber_context(session, request)
    else:
        _validate_s4_parent_boundary(request)
        cyber = None
    reevaluates = None
    if request.reevaluates_parent is not None:
        previous = _verified_selection(
            session, request.reevaluates_parent, CORRELATION_EVIDENCE_TYPE
        )
        try:
            previous_finding = CyberPhysicalCorrelationFinding.model_validate(previous.payload)
        except ValidationError as exc:
            raise CorrelationEvidenceError(
                "The prior correlation finding payload is invalid."
            ) from exc
        if (
            previous_finding.correlation_profile_id != profile.profile.profile_id
            or previous_finding.correlation_profile_version != profile.profile.profile_version
            or previous_finding.correlation_profile_sha256 != profile.sha256
            or previous_finding.correlation_rule_id != rule.rule_id
            or previous_finding.correlation_rule_version != rule.rule_version
        ):
            raise CorrelationEvidenceError(
                "The prior finding is not compatible with this re-evaluation."
            )
        reevaluates = _reference(previous)
    evaluation_input = CorrelationEvaluationInput(
        profile_id=profile.profile.profile_id,
        profile_version=profile.profile.profile_version,
        profile_sha256=profile.sha256,
        rule_id=rule.rule_id,
        rule_version=rule.rule_version,
        cyber_context=cyber,
        telemetry=telemetry,
        available_point_ids=rule.point_ids,
        reevaluates_parent=reevaluates,
    )
    built = evaluate_correlation(evaluation_input, profile)
    sequence_number = max((item.sequence_number for item in telemetry), default=0)
    envelope = CorrelationEvidenceEnvelope(
        source_key=CORRELATION_SOURCE_KEY,
        source_event_id=built.source_event_id,
        evidence_type=CORRELATION_EVIDENCE_TYPE,
        observed_at=built.finding.evidence_observed_at,
        sequence_number=sequence_number,
        payload_schema=CORRELATION_FINDING_SCHEMA,
        payload_schema_version=CORRELATION_FINDING_SCHEMA_VERSION,
        payload=built.finding,
        provenance=built.provenance,
    )
    receipt = ingest_internal_evidence(
        session,
        envelope,
        receipt_timestamp=receipt_timestamp,
        request_id="offline-cyber-physical-correlation",
    )
    if receipt.evidence_id != built.finding.correlation_id:
        raise CorrelationEvidenceError("The correlation evidence identity is inconsistent.")
    return CorrelationPersistenceResult(receipt=receipt, finding=built.finding)


def _s3_cyber_context(
    session: Session, request: CorrelationPersistenceRequest
) -> CyberParentContext:
    if request.semantic_parent is None or request.asset_context_parent is None:
        raise CorrelationEvidenceError("S3 requires semantic and asset-context parents.")
    semantic_record = _verified_selection(
        session, request.semantic_parent, "protocol_semantic_event"
    )
    context_record = _verified_selection(
        session, request.asset_context_parent, "asset_context_event"
    )
    try:
        semantic = ProtocolSemanticEvent.model_validate(semantic_record.payload)
        context = AssetContextEvent.model_validate(context_record.payload)
    except ValidationError as exc:
        raise CorrelationEvidenceError("An S3 parent payload is invalid.") from exc
    if semantic.semantic_event_id != semantic_record.evidence_id:
        raise CorrelationEvidenceError("The semantic payload identity does not match its record.")
    raw_record = _verified_record(session, semantic.source_evidence_id, "synthetic_protocol_event")
    if raw_record.integrity_sha256 != semantic.source_evidence_integrity_sha256:
        raise CorrelationEvidenceError("The semantic event references a substituted raw parent.")
    decoded_value = semantic.decoded_value
    if (
        semantic.operation_category is not OperationCategory.WRITE
        or semantic.function_semantic is not FunctionSemantic.WRITE_SINGLE_REGISTER
        or semantic.operation_compatibility is not OperationCompatibility.COMPATIBLE
        or semantic.point_id != "control_valve_command_percent"
        or semantic.fictional_target_component != "CV-101"
        or not isinstance(decoded_value, Decimal)
        or float(decoded_value) != 25.0
    ):
        raise CorrelationEvidenceError(
            "The semantic parent does not match the S3 command contract."
        )
    relationship_ok = any(
        item.relationship_type.value == "CONTROLS"
        and item.source_asset_key == "PLC-01"
        and item.target_ref == "CV-101"
        for item in context.relevant_relationships
    )
    if (
        context.semantic_event_id != semantic_record.evidence_id
        or context.semantic_evidence_integrity_sha256 != semantic_record.integrity_sha256
        or context.destination_resolution.asset_key != "PLC-01"
        or context.target_process_asset is None
        or context.target_process_asset.asset_key != "CV-101"
        or not relationship_ok
    ):
        raise CorrelationEvidenceError("The asset context does not match the S3 relationship.")
    policy_reference = None
    policy_status = "UNAVAILABLE"
    if request.policy_parent is not None:
        policy_record = _verified_selection(
            session, request.policy_parent, "communication_policy_finding"
        )
        try:
            finding = CommunicationPolicyFinding.model_validate(policy_record.payload)
        except ValidationError as exc:
            raise CorrelationEvidenceError("The policy parent payload is invalid.") from exc
        if (
            finding.semantic_event_id != semantic_record.evidence_id
            or finding.asset_context_event_id != context_record.evidence_id
            or finding.semantic_evidence_integrity_sha256 != semantic_record.integrity_sha256
        ):
            raise CorrelationEvidenceError("The policy finding does not match the S3 lineage.")
        policy_reference = _reference(policy_record)
        policy_status = finding.policy_status.value
    return CyberParentContext(
        raw_parent=_reference(raw_record),
        semantic_parent=_reference(semantic_record),
        asset_context_parent=_reference(context_record),
        policy_parent=policy_reference,
        command_point_id="control_valve_command_percent",
        command_target_asset_key="CV-101",
        command_value_percent=float(decoded_value),
        command_observed_at=semantic.observed_at,
        controller_asset_key="PLC-01",
        relationship_type="CONTROLS",
        relationship_target_asset_key="CV-101",
        policy_context_status=policy_status,
    )


def _validate_s4_parent_boundary(
    request: CorrelationPersistenceRequest,
) -> None:
    if any(
        item is not None
        for item in (
            request.semantic_parent,
            request.asset_context_parent,
            request.policy_parent,
        )
    ):
        raise CorrelationEvidenceError("S4 does not accept cyber, context, or policy parents.")
    return None


def _telemetry_from_record(record: EvidenceRecord) -> TelemetryEvidence:
    try:
        payload = CorrelationTelemetryPayload.model_validate(record.payload)
    except ValidationError as exc:
        raise CorrelationEvidenceError("A stored telemetry payload is invalid.") from exc
    return TelemetryEvidence(
        evidence_id=record.evidence_id,
        evidence_type="simulator_telemetry",
        integrity_sha256=record.integrity_sha256,
        observed_at=record.observed_at,
        sequence_number=record.sequence_number or 0,
        payload_schema="otsoc.simulator.telemetry",
        payload_schema_version="2.0.0",
        payload=payload,
    )


def _verified_selection(
    session: Session, selection: ParentSelection, expected_type: str
) -> EvidenceRecord:
    record = _verified_record(session, selection.evidence_id, expected_type)
    if record.integrity_sha256 != selection.expected_integrity_sha256:
        raise CorrelationEvidenceError("A supplied parent digest does not match stored evidence.")
    return record


def _verified_record(
    session: Session, evidence_id: uuid.UUID, expected_type: str
) -> EvidenceRecord:
    record = session.scalar(
        select(EvidenceRecord)
        .options(joinedload(EvidenceRecord.source))
        .where(EvidenceRecord.evidence_id == evidence_id)
    )
    if record is None or record.evidence_type != expected_type:
        raise CorrelationEvidenceError("A required stored parent was not found.")
    if not verify_record_integrity(record):
        raise CorrelationEvidenceError("A stored parent integrity check failed.")
    return record


def _reference(record: EvidenceRecord) -> EvidenceParentReference:
    return EvidenceParentReference(
        evidence_id=record.evidence_id,
        evidence_type=record.evidence_type,
        integrity_sha256=record.integrity_sha256,
        observed_at=record.observed_at,
        sequence_number=record.sequence_number,
    )
