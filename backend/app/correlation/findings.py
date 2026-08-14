from __future__ import annotations

from dataclasses import dataclass

from app.context.canonical import deterministic_asset_id
from app.correlation.canonical import (
    canonical_parent_references,
    deterministic_correlation_source_event_id,
    parent_set_sha256,
)
from app.correlation.models import (
    CANONICALIZATION_VERSION,
    CORRELATION_EVALUATOR_NAME,
    CORRELATION_EVALUATOR_VERSION,
    CORRELATION_EVIDENCE_TYPE,
    CORRELATION_FINDING_SCHEMA,
    CORRELATION_FINDING_SCHEMA_VERSION,
    CORRELATION_SOURCE_ID,
    CorrelationDecision,
    CorrelationDerivationProvenance,
    CorrelationEvaluationInput,
    CyberPhysicalCorrelationFinding,
    EvidenceParentReference,
    ProcessAssetReference,
)
from app.correlation.profile import LoadedCorrelationProfile
from app.evidence.canonical import deterministic_evidence_id_from_fields


@dataclass(frozen=True)
class BuiltCorrelationFinding:
    source_event_id: str
    finding: CyberPhysicalCorrelationFinding
    provenance: CorrelationDerivationProvenance


def build_correlation_finding(
    request: CorrelationEvaluationInput,
    decision: CorrelationDecision,
    loaded_profile: LoadedCorrelationProfile,
) -> BuiltCorrelationFinding:
    cyber = request.cyber_context
    references: list[EvidenceParentReference] = []
    if cyber is not None:
        references.extend((cyber.raw_parent, cyber.semantic_parent, cyber.asset_context_parent))
        if cyber.policy_parent is not None:
            references.append(cyber.policy_parent)
    references.extend(item.parent_reference() for item in request.telemetry)
    if request.reevaluates_parent is not None:
        references.append(request.reevaluates_parent)
    ordered_parents = canonical_parent_references(tuple(references))
    parent_digest = parent_set_sha256(ordered_parents)
    source_event_uuid = deterministic_correlation_source_event_id(
        profile_id=loaded_profile.profile.profile_id,
        profile_version=loaded_profile.profile.profile_version,
        profile_sha256=loaded_profile.sha256,
        rule_id=request.rule_id,
        rule_version=request.rule_version,
        evaluator_version=CORRELATION_EVALUATOR_VERSION,
        simulation_id=decision.simulation_id,
        configuration_hash=decision.configuration_hash,
        anchor_time=decision.anchor_time.isoformat() if decision.anchor_time else None,
        parent_digest=parent_digest,
        finding_schema_version=CORRELATION_FINDING_SCHEMA_VERSION,
    )
    correlation_id = deterministic_evidence_id_from_fields(
        source_id=CORRELATION_SOURCE_ID,
        source_event_id=str(source_event_uuid),
        evidence_type=CORRELATION_EVIDENCE_TYPE,
        payload_schema_version=CORRELATION_FINDING_SCHEMA_VERSION,
    )
    telemetry_parents = canonical_parent_references(
        tuple(item.parent_reference() for item in request.telemetry)
    )
    process_assets = tuple(
        ProcessAssetReference(
            asset_id=deterministic_asset_id(
                inventory_profile_id=loaded_profile.profile.dependencies.inventory_profile_id,
                asset_key=asset_key,
            ),
            asset_key=asset_key,
        )
        for asset_key in decision.process_asset_keys
    )
    finding = CyberPhysicalCorrelationFinding(
        correlation_id=correlation_id,
        finding_schema=CORRELATION_FINDING_SCHEMA,
        finding_schema_version=CORRELATION_FINDING_SCHEMA_VERSION,
        correlation_profile_id=loaded_profile.profile.profile_id,
        correlation_profile_version=loaded_profile.profile.profile_version,
        correlation_profile_sha256=loaded_profile.sha256,
        correlation_rule_id=request.rule_id,
        correlation_rule_version=request.rule_version,
        evaluator_name=CORRELATION_EVALUATOR_NAME,
        evaluator_version=CORRELATION_EVALUATOR_VERSION,
        canonicalization_version=CANONICALIZATION_VERSION,
        primary_cyber_evidence_id=cyber.raw_parent.evidence_id if cyber else None,
        primary_cyber_evidence_integrity_sha256=(
            cyber.raw_parent.integrity_sha256 if cyber else None
        ),
        semantic_evidence_id=cyber.semantic_parent.evidence_id if cyber else None,
        semantic_evidence_integrity_sha256=(
            cyber.semantic_parent.integrity_sha256 if cyber else None
        ),
        asset_context_evidence_id=cyber.asset_context_parent.evidence_id if cyber else None,
        asset_context_evidence_integrity_sha256=(
            cyber.asset_context_parent.integrity_sha256 if cyber else None
        ),
        policy_finding_evidence_id=(
            cyber.policy_parent.evidence_id if cyber and cyber.policy_parent else None
        ),
        policy_finding_evidence_integrity_sha256=(
            cyber.policy_parent.integrity_sha256 if cyber and cyber.policy_parent else None
        ),
        policy_context_status=cyber.policy_context_status if cyber else "UNAVAILABLE",
        telemetry_parents=telemetry_parents,
        reevaluates_finding_id=(
            request.reevaluates_parent.evidence_id if request.reevaluates_parent else None
        ),
        parent_set_sha256=parent_digest,
        simulation_id=decision.simulation_id,
        configuration_hash=decision.configuration_hash,
        simulator_version=decision.simulator_version,
        telemetry_schema_version=decision.telemetry_schema_version,
        domain="oil_gas_transfer",
        process_model_version="3.6",
        timestamp_authority="OBSERVED_AT",
        run_origin=decision.run_origin,
        anchor_time=decision.anchor_time,
        correlation_start_time=decision.correlation_start_time,
        correlation_end_time=decision.correlation_end_time,
        evidence_observed_at=decision.evidence_observed_at,
        baseline_method="FIXED_PRECEDING_WINDOW",
        baseline_sample_count=decision.baseline_sample_count,
        effect_sample_count=decision.effect_sample_count,
        maximum_gap_seconds=decision.maximum_gap_seconds,
        process_assets=process_assets,
        affected_process_points=decision.affected_process_points,
        observations=decision.observations,
        temporal_relation=decision.temporal_relation,
        correlation_status=decision.status,
        reason_code=decision.reason_code,
        matched_minimum_set=decision.matched_minimum_set,
        statement_template_id=decision.statement_template_id,
        analyst_readable_explanation=decision.explanation,
        cyber_cause_asserted=False,
        causality_inferred=False,
        malicious_intent_inferred=False,
        ground_truth_used=False,
        derivation_kind="CYBER_PHYSICAL_CORRELATION",
    )
    dependencies = loaded_profile.profile.dependencies
    provenance = CorrelationDerivationProvenance(
        derivation_kind="CYBER_PHYSICAL_CORRELATION",
        parent_references=ordered_parents,
        parent_set_sha256=parent_digest,
        correlation_profile_id=loaded_profile.profile.profile_id,
        correlation_profile_version=loaded_profile.profile.profile_version,
        correlation_profile_sha256=loaded_profile.sha256,
        correlation_rule_id=request.rule_id,
        correlation_rule_version=request.rule_version,
        evaluator_name=CORRELATION_EVALUATOR_NAME,
        evaluator_version=CORRELATION_EVALUATOR_VERSION,
        inventory_profile_id=dependencies.inventory_profile_id,
        inventory_profile_version=dependencies.inventory_profile_version,
        inventory_profile_sha256=dependencies.inventory_profile_sha256,
        policy_profile_id=dependencies.policy_profile_id,
        policy_profile_version=dependencies.policy_profile_version,
        policy_profile_sha256=dependencies.policy_profile_sha256,
        protocol_profile_id=dependencies.protocol_profile_id,
        protocol_profile_version=dependencies.protocol_profile_version,
        protocol_profile_sha256=dependencies.protocol_profile_sha256,
        simulator_version="3.0.0",
        telemetry_schema="otsoc.simulator.telemetry",
        telemetry_schema_version="2.0.0",
        domain="oil_gas_transfer",
        process_model_version="3.6",
        simulation_id=decision.simulation_id,
        configuration_hash=decision.configuration_hash,
        canonicalization_version=CANONICALIZATION_VERSION,
        educational_only=True,
        ground_truth_used=False,
    )
    return BuiltCorrelationFinding(
        source_event_id=str(source_event_uuid), finding=finding, provenance=provenance
    )
