from __future__ import annotations

import uuid
from decimal import Decimal

from app.context.models import PolicyReasonCode, PolicyStatus, ResolutionStatus
from app.correlation.models import CorrelationReasonCode, CorrelationStatus
from app.evidence.models import EvidenceRecord
from app.incidents.grouping import unresolved_source_scope
from app.incidents.memberships import VerifiedIncidentEvidenceBundle
from app.incidents.models import (
    CandidateMembership,
    EvidenceRole,
    IncidentCategory,
    IncidentSeverity,
    QualifiedIncidentCandidate,
)
from app.incidents.profile import LoadedIncidentProfile


class IncidentQualificationError(ValueError):
    pass


def qualify_incident(
    bundle: VerifiedIncidentEvidenceBundle,
    profile: LoadedIncidentProfile,
) -> QualifiedIncidentCandidate | None:
    correlation = bundle.correlation
    if correlation is not None and correlation.correlation_rule_id == "CPR-S4-PUMP-FLOW-001":
        if bundle.policy is not None:
            raise IncidentQualificationError("S4 does not accept policy or cyber evidence.")
        return _qualify_s4(bundle, profile)
    if bundle.policy is None:
        return None
    if _is_s1(bundle):
        return _qualify_s1(bundle, profile)
    if _is_s2(bundle):
        return _qualify_s2(bundle, profile)
    if _is_s3_command(bundle):
        return _qualify_s3(bundle, profile)
    return None


def _qualify_s1(
    bundle: VerifiedIncidentEvidenceBundle,
    profile: LoadedIncidentProfile,
) -> QualifiedIncidentCandidate:
    policy = _required(bundle.policy, "policy finding")
    policy_record = _required(bundle.policy_record, "policy record")
    raw = _required(bundle.raw, "raw event")
    context = _required(bundle.context, "asset context")
    rule = profile.rules["IQR-S1-UNKNOWN-SOURCE-001"]
    primary = _membership(policy_record, EvidenceRole.PRIMARY)
    return QualifiedIncidentCandidate(
        qualification_rule_id=rule.rule_id,
        qualification_rule_version="1.0.0",
        category=IncidentCategory.ASSET_IDENTITY_ANOMALY,
        severity=IncidentSeverity.LOW,
        title=rule.title,
        summary=rule.summary,
        primary_membership=primary,
        additional_memberships=(),
        identity_asset_scope=(
            unresolved_source_scope(raw.source_identity),
            str(policy.destination_asset_id),
        ),
        process_asset_scope=(),
        target_point_scope=tuple(item for item in (policy.target_point,) if item is not None),
        source_asset_id=None,
        destination_asset_id=policy.destination_asset_id,
        controller_asset_id=policy.destination_asset_id,
        process_asset_ids=(),
        process_asset_keys=(),
        correlation_rule_id=None,
        correlation_rule_version=None,
        run_scope="NO_SIMULATION_SCOPE",
        configuration_scope="NO_SIMULATION_SCOPE",
        bound_simulation_id=None,
        bound_configuration_hash=None,
        s3_semantic_evidence_id=None,
        grouping_anchor=context.observed_at,
        first_observed_at=primary.observed_at,
        last_observed_at=primary.observed_at,
        policy_context=policy.policy_status.value,
        correlation_context="UNAVAILABLE",
        evidence_completeness="VERIFIED_POLICY_LINEAGE",
    )


def _qualify_s2(
    bundle: VerifiedIncidentEvidenceBundle,
    profile: LoadedIncidentProfile,
) -> QualifiedIncidentCandidate:
    policy = _required(bundle.policy, "policy finding")
    policy_record = _required(bundle.policy_record, "policy record")
    semantic = _required(bundle.semantic, "semantic event")
    rule = profile.rules["IQR-S2-IT-PLC-POLICY-001"]
    primary = _membership(policy_record, EvidenceRole.PRIMARY)
    return QualifiedIncidentCandidate(
        qualification_rule_id=rule.rule_id,
        qualification_rule_version="1.0.0",
        category=IncidentCategory.COMMUNICATION_POLICY_VIOLATION,
        severity=IncidentSeverity.MEDIUM,
        title=rule.title,
        summary=rule.summary,
        primary_membership=primary,
        additional_memberships=(),
        identity_asset_scope=(str(policy.source_asset_id), str(policy.destination_asset_id)),
        process_asset_scope=(),
        target_point_scope=("pipeline_flow_rate_m3h",),
        source_asset_id=policy.source_asset_id,
        destination_asset_id=policy.destination_asset_id,
        controller_asset_id=policy.destination_asset_id,
        process_asset_ids=(),
        process_asset_keys=(),
        correlation_rule_id=None,
        correlation_rule_version=None,
        run_scope="NO_SIMULATION_SCOPE",
        configuration_scope="NO_SIMULATION_SCOPE",
        bound_simulation_id=None,
        bound_configuration_hash=None,
        s3_semantic_evidence_id=None,
        grouping_anchor=semantic.observed_at,
        first_observed_at=primary.observed_at,
        last_observed_at=primary.observed_at,
        policy_context=policy.policy_status.value,
        correlation_context="UNAVAILABLE",
        evidence_completeness="VERIFIED_POLICY_LINEAGE",
    )


def _qualify_s3(
    bundle: VerifiedIncidentEvidenceBundle,
    profile: LoadedIncidentProfile,
) -> QualifiedIncidentCandidate | None:
    policy = _required(bundle.policy, "policy finding")
    policy_record = _required(bundle.policy_record, "policy record")
    semantic = _required(bundle.semantic, "semantic event")
    context = _required(bundle.context, "asset context")
    correlation = bundle.correlation
    correlation_record = bundle.correlation_record
    correlated = bool(
        correlation is not None
        and correlation.correlation_rule_id == "CPR-S3-CV-TRANSFER-001"
        and correlation.correlation_rule_version == "1.0.0"
        and correlation.correlation_status is CorrelationStatus.CORRELATED
        and correlation.reason_code is CorrelationReasonCode.CORRELATION_MATCH
    )
    if policy.policy_status is PolicyStatus.APPROVED and not correlated:
        return None
    if policy.policy_status not in {PolicyStatus.APPROVED, PolicyStatus.DENIED}:
        return None
    if correlation is not None and correlation.correlation_rule_id != "CPR-S3-CV-TRANSFER-001":
        raise IncidentQualificationError("The selected correlation is unrelated to S3.")

    rule = profile.rules["IQR-S3-CV-COMMAND-001"]
    if policy.policy_status is PolicyStatus.DENIED:
        primary = _membership(policy_record, EvidenceRole.PRIMARY)
        additional = (
            (
                _membership(
                    _required(correlation_record, "correlation record"),
                    EvidenceRole.SUPPORTING if correlated else EvidenceRole.CONTEXT,
                ),
            )
            if correlation_record is not None
            else ()
        )
        severity = IncidentSeverity.HIGH if correlated else IncidentSeverity.MEDIUM
        run_scope = f"UNBOUND_PROCESS_SCOPE:{semantic.semantic_event_id}"
        configuration_scope = "UNBOUND_PROCESS_SCOPE"
    else:
        approved_correlation = _required(correlation, "correlation finding")
        primary = _membership(
            _required(correlation_record, "correlation record"), EvidenceRole.PRIMARY
        )
        additional = (_membership(policy_record, EvidenceRole.CONTEXT),)
        severity = IncidentSeverity.MEDIUM
        run_scope = _required(approved_correlation.simulation_id, "S3 simulation ID")
        configuration_scope = _required(
            approved_correlation.configuration_hash, "S3 configuration hash"
        )

    memberships = (primary, *additional)
    bound_simulation_id = (
        correlation.simulation_id
        if correlation is not None
        and correlation.simulation_id is not None
        and correlation.configuration_hash is not None
        else None
    )
    bound_configuration_hash = (
        correlation.configuration_hash
        if correlation is not None and bound_simulation_id is not None
        else None
    )
    process_ids: tuple[uuid.UUID, ...]
    process_keys: tuple[str, ...]
    if correlation is not None:
        process_pairs = sorted(
            ((item.asset_key, item.asset_id) for item in correlation.process_assets),
            key=lambda item: item[0],
        )
        process_keys = tuple(key for key, _ in process_pairs)
        process_ids = tuple(asset_id for _, asset_id in process_pairs)
    else:
        target = _required(context.target_process_asset, "S3 target process asset")
        process_keys = (_required(target.asset_key, "S3 process asset key"),)
        process_ids = (_required(target.asset_id, "S3 process asset ID"),)
    return QualifiedIncidentCandidate(
        qualification_rule_id=rule.rule_id,
        qualification_rule_version="1.0.0",
        category=IncidentCategory.CONTROL_COMMAND_INVESTIGATION,
        severity=severity,
        title=rule.title,
        summary=rule.summary,
        primary_membership=primary,
        additional_memberships=additional,
        identity_asset_scope=tuple(
            value
            for value in (str(policy.source_asset_id), str(policy.destination_asset_id))
            if value != "None"
        ),
        process_asset_scope=("CV-101",),
        target_point_scope=("control_valve_command_percent",),
        source_asset_id=policy.source_asset_id,
        destination_asset_id=policy.destination_asset_id,
        controller_asset_id=policy.destination_asset_id,
        process_asset_ids=process_ids,
        process_asset_keys=process_keys,
        correlation_rule_id="CPR-S3-CV-TRANSFER-001",
        correlation_rule_version="1.0.0",
        run_scope=run_scope,
        configuration_scope=configuration_scope,
        bound_simulation_id=bound_simulation_id,
        bound_configuration_hash=bound_configuration_hash,
        s3_semantic_evidence_id=semantic.semantic_event_id,
        grouping_anchor=semantic.observed_at,
        first_observed_at=min(item.observed_at for item in memberships),
        last_observed_at=max(item.observed_at for item in memberships),
        policy_context=policy.policy_status.value,
        correlation_context=(
            correlation.correlation_status.value if correlation else "UNAVAILABLE"
        ),
        evidence_completeness="VERIFIED_S3_CHAIN",
    )


def _qualify_s4(
    bundle: VerifiedIncidentEvidenceBundle,
    profile: LoadedIncidentProfile,
) -> QualifiedIncidentCandidate | None:
    correlation = _required(bundle.correlation, "correlation finding")
    if not (
        correlation.correlation_rule_id == "CPR-S4-PUMP-FLOW-001"
        and correlation.correlation_rule_version == "1.0.0"
        and correlation.correlation_status is CorrelationStatus.CORRELATED
        and correlation.reason_code is CorrelationReasonCode.CORRELATION_MATCH
        and correlation.primary_cyber_evidence_id is None
        and correlation.semantic_evidence_id is None
        and correlation.asset_context_evidence_id is None
        and correlation.policy_finding_evidence_id is None
        and correlation.cyber_cause_asserted is False
        and correlation.causality_inferred is False
        and correlation.ground_truth_used is False
    ):
        return None
    expected_assets = {"P-101", "PL-101", "TK-101", "TK-102"}
    if {item.asset_key for item in correlation.process_assets} != expected_assets:
        return None
    correlation_record = _required(bundle.correlation_record, "correlation record")
    primary = _membership(correlation_record, EvidenceRole.PRIMARY)
    process_pairs = sorted(
        ((item.asset_key, item.asset_id) for item in correlation.process_assets),
        key=lambda item: item[0],
    )
    rule = profile.rules["IQR-S4-PUMP-FLOW-001"]
    simulation_id = _required(correlation.simulation_id, "S4 simulation ID")
    configuration_hash = _required(correlation.configuration_hash, "S4 configuration hash")
    return QualifiedIncidentCandidate(
        qualification_rule_id=rule.rule_id,
        qualification_rule_version="1.0.0",
        category=IncidentCategory.PROCESS_INCONSISTENCY,
        severity=IncidentSeverity.HIGH,
        title=rule.title,
        summary=rule.summary,
        primary_membership=primary,
        additional_memberships=(),
        identity_asset_scope=(),
        process_asset_scope=tuple(key for key, _ in process_pairs),
        target_point_scope=tuple(sorted(correlation.affected_process_points)),
        source_asset_id=None,
        destination_asset_id=None,
        controller_asset_id=None,
        process_asset_ids=tuple(asset_id for _, asset_id in process_pairs),
        process_asset_keys=tuple(key for key, _ in process_pairs),
        correlation_rule_id="CPR-S4-PUMP-FLOW-001",
        correlation_rule_version="1.0.0",
        run_scope=simulation_id,
        configuration_scope=configuration_hash,
        bound_simulation_id=simulation_id,
        bound_configuration_hash=configuration_hash,
        s3_semantic_evidence_id=None,
        grouping_anchor=_required(correlation.anchor_time, "S4 anchor time"),
        first_observed_at=primary.observed_at,
        last_observed_at=primary.observed_at,
        policy_context="UNAVAILABLE",
        correlation_context=correlation.correlation_status.value,
        evidence_completeness="VERIFIED_S4_CORRELATION",
    )


def _is_s1(bundle: VerifiedIncidentEvidenceBundle) -> bool:
    policy = bundle.policy
    context = bundle.context
    return bool(
        policy is not None
        and context is not None
        and policy.policy_status is PolicyStatus.UNKNOWN
        and policy.reason_code is PolicyReasonCode.SOURCE_UNKNOWN
        and policy.source_resolution is ResolutionStatus.UNKNOWN
        and policy.source_asset_id is None
        and policy.source_asset_key is None
        and policy.source_role is None
        and policy.source_zone is None
        and policy.destination_resolution is ResolutionStatus.RESOLVED
        and policy.destination_asset_key == "PLC-01"
        and policy.destination_zone is not None
        and policy.destination_zone.value == "OT_CONTROL_ZONE"
        and context.source_resolution.status is ResolutionStatus.UNKNOWN
        and context.destination_resolution.status is ResolutionStatus.RESOLVED
        and context.destination_resolution.asset_key == "PLC-01"
    )


def _is_s2(bundle: VerifiedIncidentEvidenceBundle) -> bool:
    policy = bundle.policy
    return bool(
        policy is not None
        and policy.source_asset_key == "IT-WS-01"
        and policy.source_zone is not None
        and policy.source_zone.value == "IT_ZONE"
        and policy.destination_asset_key == "PLC-01"
        and policy.destination_zone is not None
        and policy.destination_zone.value == "OT_CONTROL_ZONE"
        and policy.protocol == "modbus_tcp"
        and policy.operation_category.value == "READ"
        and policy.function_semantic is not None
        and policy.function_semantic.value == "READ_INPUT_REGISTERS"
        and policy.function_code == 4
        and policy.target_point == "pipeline_flow_rate_m3h"
        and policy.point_access_class is not None
        and policy.point_access_class.value == "READ_ONLY"
        and policy.policy_status is PolicyStatus.DENIED
        and policy.reason_code is PolicyReasonCode.COMMUNICATION_NOT_APPROVED
        and policy.matched_rule_id == "ACP-006"
    )


def _is_s3_command(bundle: VerifiedIncidentEvidenceBundle) -> bool:
    semantic = bundle.semantic
    context = bundle.context
    if semantic is None or context is None:
        return False
    relationship = any(
        item.relationship_type.value == "CONTROLS"
        and item.source_asset_key == "PLC-01"
        and item.target_ref == "CV-101"
        for item in context.relevant_relationships
    )
    return bool(
        semantic.operation_category.value == "WRITE"
        and semantic.function_semantic is not None
        and semantic.function_semantic.value == "WRITE_SINGLE_REGISTER"
        and semantic.operation_compatibility.value == "COMPATIBLE"
        and semantic.point_id == "control_valve_command_percent"
        and semantic.fictional_target_component == "CV-101"
        and isinstance(semantic.decoded_value, Decimal)
        and semantic.decoded_value == Decimal("25.0")
        and context.destination_resolution.asset_key == "PLC-01"
        and context.target_process_asset is not None
        and context.target_process_asset.asset_key == "CV-101"
        and relationship
    )


def _membership(record: EvidenceRecord, role: EvidenceRole) -> CandidateMembership:
    return CandidateMembership(
        evidence_id=record.evidence_id,
        evidence_type=record.evidence_type,
        evidence_schema=record.payload_schema,
        evidence_schema_version=record.payload_schema_version,
        integrity_sha256=record.integrity_sha256,
        role=role,
        observed_at=record.observed_at,
        received_at=record.received_at,
    )


def _required[T](value: T | None, label: str) -> T:
    if value is None:
        raise IncidentQualificationError(f"The verified {label} is required.")
    return value
