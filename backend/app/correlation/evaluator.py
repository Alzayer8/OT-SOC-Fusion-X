from __future__ import annotations

from datetime import datetime

from app.correlation.decisions import reason_decision
from app.correlation.findings import BuiltCorrelationFinding, build_correlation_finding
from app.correlation.models import (
    CORRELATION_PROFILE_ID,
    CORRELATION_PROFILE_VERSION,
    CorrelationEvaluationInput,
    CorrelationReasonCode,
)
from app.correlation.profile import LoadedCorrelationProfile
from app.correlation.s3 import evaluate_s3
from app.correlation.s4 import evaluate_s4
from app.correlation.temporal import canonical_telemetry, validate_run_consistency


def evaluate_correlation(
    request: CorrelationEvaluationInput,
    loaded_profile: LoadedCorrelationProfile,
) -> BuiltCorrelationFinding:
    ordered = canonical_telemetry(request.telemetry)
    request = request.model_copy(update={"telemetry": ordered})
    fallback_rule = loaded_profile.profile.rules[0]

    if request.profile_id != CORRELATION_PROFILE_ID or (
        request.profile_version != CORRELATION_PROFILE_VERSION
    ):
        decision = reason_decision(
            CorrelationReasonCode.PROFILE_VERSION_UNSUPPORTED,
            fallback_rule,
            ordered,
            anchor=_request_anchor(request),
        )
        return build_correlation_finding(request, decision, loaded_profile)
    if request.profile_sha256 != loaded_profile.sha256:
        decision = reason_decision(
            CorrelationReasonCode.PROFILE_DIGEST_MISMATCH,
            fallback_rule,
            ordered,
            anchor=_request_anchor(request),
        )
        return build_correlation_finding(request, decision, loaded_profile)
    rule = loaded_profile.rules.get(request.rule_id)
    if rule is None or request.rule_version != "1.0.0":
        decision = reason_decision(
            CorrelationReasonCode.UNSUPPORTED_CORRELATION_RULE,
            fallback_rule,
            ordered,
            anchor=_request_anchor(request),
        )
        return build_correlation_finding(request, decision, loaded_profile)
    if rule.evaluator_branch == "S3" and not _s3_parent_shape_verified(request):
        decision = reason_decision(
            CorrelationReasonCode.PARENT_EVIDENCE_NOT_VERIFIED,
            rule,
            ordered,
            anchor=_request_anchor(request),
        )
        return build_correlation_finding(request, decision, loaded_profile)

    consistency = validate_run_consistency(ordered)
    if consistency.reason is not None:
        decision = reason_decision(
            consistency.reason,
            rule,
            ordered,
            anchor=_request_anchor(request),
            simulation_id=consistency.simulation_id,
            configuration_hash=consistency.configuration_hash,
            simulator_version=consistency.simulator_version,
            run_origin=consistency.run_origin,
        )
        return build_correlation_finding(request, decision, loaded_profile)
    if rule.evaluator_branch == "S3" and not _s3_asset_mapping_valid(request):
        decision = reason_decision(
            CorrelationReasonCode.ASSET_RELATION_MISMATCH,
            rule,
            ordered,
            anchor=_request_anchor(request),
            simulation_id=consistency.simulation_id,
            configuration_hash=consistency.configuration_hash,
            simulator_version=consistency.simulator_version,
            run_origin=consistency.run_origin,
        )
        return build_correlation_finding(request, decision, loaded_profile)
    if rule.evaluator_branch == "S4" and request.cyber_context is not None:
        decision = reason_decision(
            CorrelationReasonCode.ASSET_RELATION_MISMATCH,
            rule,
            ordered,
            simulation_id=consistency.simulation_id,
            configuration_hash=consistency.configuration_hash,
            simulator_version=consistency.simulator_version,
            run_origin=consistency.run_origin,
        )
        return build_correlation_finding(request, decision, loaded_profile)
    allowed_points = set(rule.point_ids)
    supplied_points = set(request.available_point_ids)
    if not supplied_points.issubset(allowed_points):
        decision = reason_decision(
            CorrelationReasonCode.POINT_RELATION_NOT_DEFINED,
            rule,
            ordered,
            anchor=_request_anchor(request),
            simulation_id=consistency.simulation_id,
            configuration_hash=consistency.configuration_hash,
            simulator_version=consistency.simulator_version,
            run_origin=consistency.run_origin,
        )
        return build_correlation_finding(request, decision, loaded_profile)
    if not ordered:
        decision = reason_decision(
            CorrelationReasonCode.MISSING_TELEMETRY,
            rule,
            ordered,
            anchor=_request_anchor(request),
        )
        return build_correlation_finding(request, decision, loaded_profile)
    decision = (
        evaluate_s3(request, rule, consistency)
        if rule.evaluator_branch == "S3"
        else evaluate_s4(request, rule, consistency)
    )
    return build_correlation_finding(request, decision, loaded_profile)


def _request_anchor(request: CorrelationEvaluationInput) -> datetime | None:
    return request.cyber_context.command_observed_at if request.cyber_context else None


def _s3_parent_shape_verified(request: CorrelationEvaluationInput) -> bool:
    cyber = request.cyber_context
    return cyber is not None and (
        cyber.raw_parent.evidence_type == "synthetic_protocol_event"
        and cyber.semantic_parent.evidence_type == "protocol_semantic_event"
        and cyber.asset_context_parent.evidence_type == "asset_context_event"
        and (
            cyber.policy_parent is None
            or cyber.policy_parent.evidence_type == "communication_policy_finding"
        )
    )


def _s3_asset_mapping_valid(request: CorrelationEvaluationInput) -> bool:
    cyber = request.cyber_context
    return cyber is not None and (
        cyber.command_point_id == "control_valve_command_percent"
        and cyber.command_target_asset_key == "CV-101"
        and abs(cyber.command_value_percent - 25.0) <= 1e-12
        and cyber.controller_asset_key == "PLC-01"
        and cyber.relationship_type == "CONTROLS"
        and cyber.relationship_target_asset_key == "CV-101"
    )
