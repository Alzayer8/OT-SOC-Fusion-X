from __future__ import annotations

import uuid

from app.context.canonical import CANONICALIZATION_VERSION
from app.context.identity import resolve_identity
from app.context.inventory import LoadedInventory
from app.context.models import (
    ASSET_CONTEXT_SCHEMA,
    ASSET_CONTEXT_SCHEMA_VERSION,
    EVALUATOR_NAME,
    EVALUATOR_VERSION,
    POLICY_FINDING_SCHEMA,
    POLICY_FINDING_SCHEMA_VERSION,
    RESOLVER_NAME,
    RESOLVER_VERSION,
    AssetContextEvent,
    AssetResolution,
    AuthorizationInput,
    CommunicationPolicyFinding,
    IdentifierType,
    IdentityClaim,
    PolicyEvaluationResult,
    PolicyFindingDerivationProvenance,
    ResolutionStatus,
    ResolvedRelationship,
)
from app.context.policy import LoadedPolicy
from app.protocols.models import ProtocolSemanticEvent


def default_identity_claims(
    semantic: ProtocolSemanticEvent,
) -> tuple[tuple[IdentityClaim, ...], tuple[IdentityClaim, ...]]:
    return (
        (
            IdentityClaim(
                identifier_type=IdentifierType.LOGICAL_ID,
                value=semantic.source_identity,
            ),
        ),
        (
            IdentityClaim(
                identifier_type=IdentifierType.PROTOCOL_ENDPOINT_ID,
                value=semantic.destination_identity,
            ),
        ),
    )


def build_asset_context_event(
    *,
    context_event_id: uuid.UUID,
    semantic: ProtocolSemanticEvent,
    semantic_integrity_sha256: str,
    inventory: LoadedInventory,
    source_claims: tuple[IdentityClaim, ...] | None = None,
    destination_claims: tuple[IdentityClaim, ...] | None = None,
) -> AssetContextEvent:
    default_source, default_destination = default_identity_claims(semantic)
    source_claims = source_claims or default_source
    destination_claims = destination_claims or default_destination
    source = resolve_identity(source_claims, inventory)
    destination = resolve_identity(destination_claims, inventory)
    target = _target_resolution(semantic, inventory)
    relevant = _relevant_relationships(semantic, destination, target, inventory)
    return AssetContextEvent(
        asset_context_event_id=context_event_id,
        asset_context_schema=ASSET_CONTEXT_SCHEMA,
        asset_context_schema_version=ASSET_CONTEXT_SCHEMA_VERSION,
        source_evidence_id=semantic.source_evidence_id,
        source_evidence_integrity_sha256=semantic.source_evidence_integrity_sha256,
        semantic_event_id=semantic.semantic_event_id,
        semantic_evidence_integrity_sha256=semantic_integrity_sha256,
        inventory_profile=inventory.profile.profile_id,
        inventory_version=inventory.profile.profile_version,
        inventory_sha256=inventory.sha256,
        resolver_name=RESOLVER_NAME,
        resolver_version=RESOLVER_VERSION,
        canonicalization_version=CANONICALIZATION_VERSION,
        observed_at=semantic.observed_at,
        source_identity_claims=source_claims,
        destination_identity_claims=destination_claims,
        source_resolution=source,
        destination_resolution=destination,
        relevant_relationships=relevant,
        target_process_asset=target,
        derivation_kind="ASSET_CONTEXT_RESOLUTION",
        derived_from=semantic.semantic_event_id,
        ground_truth_used=False,
    )


def authorization_input_from_semantic(
    semantic: ProtocolSemanticEvent,
    *,
    semantic_integrity_sha256: str,
    source_evidence_verified: bool = True,
    semantic_evidence_verified: bool = True,
) -> AuthorizationInput:
    return AuthorizationInput(
        source_evidence_verified=source_evidence_verified,
        semantic_evidence_verified=semantic_evidence_verified,
        source_evidence_id=semantic.source_evidence_id,
        source_evidence_integrity_sha256=semantic.source_evidence_integrity_sha256,
        semantic_event_id=semantic.semantic_event_id,
        semantic_evidence_integrity_sha256=semantic_integrity_sha256,
        observed_at=semantic.observed_at,
        protocol_profile=semantic.profile_id,
        protocol_profile_version=semantic.profile_version,
        protocol_profile_sha256=semantic.profile_sha256,
        protocol=semantic.protocol,
        operation_category=semantic.operation_category,
        function_semantic=semantic.function_semantic,
        function_code=semantic.function_code,
        target_point=semantic.point_id,
        point_access_class=semantic.point_access_class,
        fictional_target_component=semantic.fictional_target_component,
        operation_compatibility=semantic.operation_compatibility,
    )


def build_policy_finding(
    *,
    finding_id: uuid.UUID,
    auth: AuthorizationInput,
    context: AssetContextEvent,
    result: PolicyEvaluationResult,
    policy: LoadedPolicy,
) -> CommunicationPolicyFinding:
    source = context.source_resolution
    destination = context.destination_resolution
    statement = _contextual_statement(auth, context, result, policy.profile.profile_version)
    return CommunicationPolicyFinding(
        finding_id=finding_id,
        finding_schema=POLICY_FINDING_SCHEMA,
        finding_schema_version=POLICY_FINDING_SCHEMA_VERSION,
        source_evidence_id=auth.source_evidence_id,
        source_evidence_integrity_sha256=auth.source_evidence_integrity_sha256,
        semantic_event_id=auth.semantic_event_id,
        semantic_evidence_integrity_sha256=auth.semantic_evidence_integrity_sha256,
        asset_context_event_id=context.asset_context_event_id,
        evaluated_at=auth.observed_at,
        inventory_profile=context.inventory_profile,
        inventory_version=context.inventory_version,
        inventory_sha256=context.inventory_sha256,
        policy_profile=policy.profile.profile_id,
        policy_version=policy.profile.profile_version,
        policy_sha256=policy.sha256,
        protocol_profile=auth.protocol_profile,
        protocol_profile_version=auth.protocol_profile_version,
        protocol_profile_sha256=auth.protocol_profile_sha256,
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        canonicalization_version=CANONICALIZATION_VERSION,
        source_resolution=source.status,
        destination_resolution=destination.status,
        source_asset_id=source.asset_id,
        source_asset_key=source.asset_key,
        source_role=source.asset_role,
        source_zone=source.zone_id,
        destination_asset_id=destination.asset_id,
        destination_asset_key=destination.asset_key,
        destination_role=destination.asset_role,
        destination_zone=destination.zone_id,
        protocol=auth.protocol,
        operation_category=auth.operation_category,
        function_semantic=auth.function_semantic,
        function_code=auth.function_code,
        target_point=auth.target_point,
        point_access_class=auth.point_access_class,
        fictional_target_component=auth.fictional_target_component,
        operation_compatibility=auth.operation_compatibility,
        dimension_results=result.dimension_results,
        matched_path_id=result.matched_path_id,
        matched_rule_id=result.matched_rule_id,
        policy_status=result.policy_status,
        reason_code=result.reason_code,
        statement_template_id=result.statement_template_id,
        analyst_readable_statement=statement,
        malicious_intent_inferred=False,
        derivation_kind="COMMUNICATION_POLICY_EVALUATION",
        derived_from=(auth.semantic_event_id, context.asset_context_event_id),
        ground_truth_used=False,
    )


def _contextual_statement(
    auth: AuthorizationInput,
    context: AssetContextEvent,
    result: PolicyEvaluationResult,
    policy_version: str,
) -> str:
    source = context.source_resolution
    destination = context.destination_resolution
    if (
        source.asset_key is None
        or destination.asset_key is None
        or source.zone_id is None
        or destination.zone_id is None
    ):
        return result.analyst_readable_statement
    point = auth.target_point or "the mapped synthetic point"
    if result.reason_code.value == "COMMUNICATION_NOT_APPROVED" and source.asset_key == "IT-WS-01":
        return (
            f"IT-WS-01 in {source.zone_id.value} is not approved by synthetic policy "
            f"{policy_version} to use {auth.protocol} {auth.operation_category.value} for {point} "
            f"through PLC-01 in {destination.zone_id.value}; malicious intent is not determined."
        )
    if result.policy_status.value == "APPROVED":
        return (
            f"{source.asset_key} is approved by synthetic policy {policy_version} to use "
            f"{auth.protocol} {auth.operation_category.value} for {point} through "
            f"{destination.asset_key}; execution, physical effect, and malicious intent are "
            "not determined."
        )
    if result.policy_status.value == "DENIED":
        return (
            f"{source.asset_key} is not approved by synthetic policy {policy_version} to use "
            f"{auth.protocol} {auth.operation_category.value} for {point} through "
            f"{destination.asset_key}; malicious intent is not determined."
        )
    return result.analyst_readable_statement


def build_policy_provenance(
    *,
    finding: CommunicationPolicyFinding,
    asset_context_integrity_sha256: str,
) -> PolicyFindingDerivationProvenance:
    return PolicyFindingDerivationProvenance(
        derivation_kind="COMMUNICATION_POLICY_EVALUATION",
        source_evidence_id=finding.source_evidence_id,
        semantic_event_id=finding.semantic_event_id,
        semantic_evidence_integrity_sha256=finding.semantic_evidence_integrity_sha256,
        asset_context_event_id=finding.asset_context_event_id,
        asset_context_integrity_sha256=asset_context_integrity_sha256,
        inventory_profile=finding.inventory_profile,
        inventory_version=finding.inventory_version,
        inventory_sha256=finding.inventory_sha256,
        policy_profile=finding.policy_profile,
        policy_version=finding.policy_version,
        policy_sha256=finding.policy_sha256,
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        canonicalization_version=CANONICALIZATION_VERSION,
        educational_only=True,
        ground_truth_used=False,
    )


def _target_resolution(
    semantic: ProtocolSemanticEvent, inventory: LoadedInventory
) -> AssetResolution | None:
    if semantic.fictional_target_component is None:
        return None
    return resolve_identity(
        (
            IdentityClaim(
                identifier_type=IdentifierType.PROCESS_TAG,
                value=semantic.fictional_target_component,
            ),
        ),
        inventory,
    )


def _relevant_relationships(
    semantic: ProtocolSemanticEvent,
    destination: AssetResolution,
    target: AssetResolution | None,
    inventory: LoadedInventory,
) -> tuple[ResolvedRelationship, ...]:
    if destination.status is not ResolutionStatus.RESOLVED or destination.asset_key is None:
        return ()
    target_refs = {semantic.destination_identity}
    if target is not None and target.asset_key is not None:
        target_refs.add(target.asset_key)
    return tuple(
        ResolvedRelationship.model_validate(relationship.model_dump(mode="python"))
        for relationship in inventory.relationships
        if relationship.source_asset_key == destination.asset_key
        and relationship.target_ref in target_refs
    )
