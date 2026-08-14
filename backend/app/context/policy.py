from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.context.canonical import canonical_policy_bytes, sha256_hex
from app.context.inventory import LoadedInventory
from app.context.models import (
    POLICY_PROFILE_ID,
    POLICY_PROFILE_VERSION,
    REASON_PRECEDENCE,
    AssetContextEvent,
    AuthorizationDimensions,
    AuthorizationInput,
    CommunicationPolicyProfile,
    CommunicationPolicyRule,
    DimensionStatus,
    GovernedPath,
    PolicyEvaluationResult,
    PolicyReasonCode,
    PolicyStatus,
    ResolutionStatus,
)
from app.protocols.models import OperationCategory, OperationCompatibility, PointAccessClass
from app.protocols.profile import EXPECTED_PROFILE_SHA256 as EXPECTED_PROTOCOL_PROFILE_SHA256
from app.protocols.profile import LoadedProfile

MAX_PROFILE_BYTES = 65_536
PROFILE_ROOT = Path(__file__).resolve().parent / "profiles"
POLICY_FILENAME = "oil_gas_communication_policy_v1.json"
EXPECTED_POLICY_SHA256 = "f396a1eeae4318585c6b2c7290cbb2e409509f3d54bf6e2a276bc027d5d17159"


class PolicyProfileError(ValueError):
    pass


@dataclass(frozen=True)
class LoadedPolicy:
    profile: CommunicationPolicyProfile
    sha256: str

    @property
    def paths(self) -> dict[str, GovernedPath]:
        return {path.path_id: path for path in self.profile.governed_paths}

    @property
    def rules(self) -> tuple[CommunicationPolicyRule, ...]:
        return self.profile.rules


def load_policy_profile(
    profile_id: str = POLICY_PROFILE_ID,
    profile_version: str = POLICY_PROFILE_VERSION,
    *,
    expected_sha256: str | None = None,
    inventory: LoadedInventory | None = None,
    protocol_profile: LoadedProfile | None = None,
) -> LoadedPolicy:
    if (profile_id, profile_version) != (POLICY_PROFILE_ID, POLICY_PROFILE_VERSION):
        raise PolicyProfileError("The requested policy profile ID/version is not available.")
    path = PROFILE_ROOT / POLICY_FILENAME
    if path.is_symlink() or path.resolve().parent != PROFILE_ROOT.resolve():
        raise PolicyProfileError("The approved policy profile path is unsafe.")
    loaded = parse_policy_bytes(path.read_bytes())
    required = expected_sha256 or EXPECTED_POLICY_SHA256
    if required == "PENDING" or loaded.sha256 != required:
        raise PolicyProfileError("The policy profile digest does not match the approved digest.")
    if inventory is not None and protocol_profile is not None:
        validate_policy_dependencies(loaded, inventory, protocol_profile)
    return loaded


def parse_policy_bytes(content: bytes) -> LoadedPolicy:
    if not content or len(content) > MAX_PROFILE_BYTES:
        raise PolicyProfileError("The policy profile exceeds the approved size bound.")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        profile = CommunicationPolicyProfile.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise PolicyProfileError("The communication policy profile is invalid.") from exc
    if profile.protocol_profile_sha256 != EXPECTED_PROTOCOL_PROFILE_SHA256:
        raise PolicyProfileError("The policy protocol-profile digest is not approved.")
    if {path.path_id for path in profile.governed_paths} != {
        "PATH-HMI-PLC",
        "PATH-ENG-PLC",
        "PATH-IT-PLC",
    } or {rule.rule_id for rule in profile.rules} != {
        f"ACP-{number:03d}" for number in range(1, 7)
    }:
        raise PolicyProfileError("The frozen path or rule catalog is incomplete.")
    return LoadedPolicy(profile=profile, sha256=sha256_hex(canonical_policy_bytes(profile)))


def validate_policy_dependencies(
    policy: LoadedPolicy, inventory: LoadedInventory, protocol_profile: LoadedProfile
) -> None:
    profile = policy.profile
    if (
        profile.inventory_profile_id != inventory.profile.profile_id
        or profile.inventory_profile_version != inventory.profile.profile_version
    ):
        raise PolicyProfileError("Policy inventory dependency does not match the loaded profile.")
    if (
        profile.protocol_profile_id != protocol_profile.profile.profile_id
        or profile.protocol_profile_version != protocol_profile.profile.profile_version
        or profile.protocol_profile_sha256 != protocol_profile.sha256
    ):
        raise PolicyProfileError("Policy protocol dependency does not match the loaded profile.")
    assets = inventory.assets
    points = {point.point_id: point for point in protocol_profile.profile.points}
    for path in profile.governed_paths:
        source = assets.get(path.source_asset_key)
        destination = assets.get(path.destination_asset_key)
        if source is None or destination is None:
            raise PolicyProfileError("A governed path references an unknown asset.")
        if (source.asset_role, source.zone_id) != (path.source_role, path.source_zone):
            raise PolicyProfileError("A governed path has invalid source context.")
        if (destination.asset_role, destination.zone_id) != (
            path.destination_role,
            path.destination_zone,
        ):
            raise PolicyProfileError("A governed path has invalid destination context.")
        if path.approved_protocols != ("modbus_tcp",):
            raise PolicyProfileError("A governed path declares an unsupported protocol.")
    for rule in profile.rules:
        for point_id in rule.point_ids:
            point = points.get(point_id)
            if point is None or point.access_class not in rule.point_access_classes:
                raise PolicyProfileError("A policy rule has invalid point classification.")


def evaluate_policy(
    auth: AuthorizationInput,
    context: AssetContextEvent,
    loaded_policy: LoadedPolicy,
) -> PolicyEvaluationResult:
    dimensions = _dimensions()
    source = context.source_resolution
    destination = context.destination_resolution

    if not auth.source_evidence_verified:
        return _result(
            dimensions, PolicyStatus.UNKNOWN, PolicyReasonCode.SOURCE_EVIDENCE_NOT_VERIFIED
        )
    if not auth.semantic_evidence_verified:
        return _result(
            dimensions, PolicyStatus.UNKNOWN, PolicyReasonCode.SEMANTIC_EVIDENCE_NOT_VERIFIED
        )
    if (
        source.status is ResolutionStatus.CONFLICT
        or destination.status is ResolutionStatus.CONFLICT
    ):
        return _result(dimensions, PolicyStatus.UNKNOWN, PolicyReasonCode.IDENTITY_CONFLICT)
    if source.status is ResolutionStatus.UNKNOWN:
        dimensions = dimensions.model_copy(
            update={"source_asset_known": DimensionStatus.NOT_SATISFIED}
        )
        return _result(dimensions, PolicyStatus.UNKNOWN, PolicyReasonCode.SOURCE_UNKNOWN)
    if destination.status is ResolutionStatus.UNKNOWN:
        dimensions = dimensions.model_copy(
            update={
                "source_asset_known": DimensionStatus.SATISFIED,
                "destination_asset_known": DimensionStatus.NOT_SATISFIED,
            }
        )
        return _result(dimensions, PolicyStatus.UNKNOWN, PolicyReasonCode.DESTINATION_UNKNOWN)

    dimensions = dimensions.model_copy(
        update={
            "source_asset_known": DimensionStatus.SATISFIED,
            "destination_asset_known": DimensionStatus.SATISFIED,
        }
    )
    if source.enabled is False:
        return _result(dimensions, PolicyStatus.DENIED, PolicyReasonCode.SOURCE_DISABLED)
    if destination.enabled is False:
        return _result(dimensions, PolicyStatus.DENIED, PolicyReasonCode.DESTINATION_DISABLED)

    path = next(
        (
            candidate
            for candidate in loaded_policy.profile.governed_paths
            if candidate.source_asset_key == source.asset_key
            and candidate.destination_asset_key == destination.asset_key
        ),
        None,
    )
    if path is None:
        return _result(dimensions, PolicyStatus.UNKNOWN, PolicyReasonCode.POLICY_NOT_CLASSIFIED)
    if source.zone_id != path.source_zone:
        dimensions = dimensions.model_copy(
            update={"source_zone_expected": DimensionStatus.NOT_SATISFIED}
        )
        return _result(
            dimensions,
            PolicyStatus.DENIED,
            PolicyReasonCode.SOURCE_ZONE_UNEXPECTED,
            path_id=path.path_id,
        )
    if destination.zone_id != path.destination_zone:
        dimensions = dimensions.model_copy(
            update={
                "source_zone_expected": DimensionStatus.SATISFIED,
                "destination_zone_expected": DimensionStatus.NOT_SATISFIED,
            }
        )
        return _result(
            dimensions,
            PolicyStatus.DENIED,
            PolicyReasonCode.DESTINATION_ZONE_UNEXPECTED,
            path_id=path.path_id,
        )
    dimensions = dimensions.model_copy(
        update={
            "source_zone_expected": DimensionStatus.SATISFIED,
            "destination_zone_expected": DimensionStatus.SATISFIED,
        }
    )

    if auth.operation_category is OperationCategory.WRITE and (
        auth.point_access_class is PointAccessClass.READ_ONLY
        or auth.operation_compatibility is OperationCompatibility.INCOMPATIBLE
    ):
        dimensions = dimensions.model_copy(
            update={"point_classification_allows": DimensionStatus.NOT_SATISFIED}
        )
        return _result(
            dimensions,
            PolicyStatus.DENIED,
            PolicyReasonCode.POINT_WRITE_NOT_APPROVED,
            path_id=path.path_id,
        )
    dimensions = dimensions.model_copy(
        update={"point_classification_allows": DimensionStatus.SATISFIED}
    )
    if auth.protocol not in path.approved_protocols:
        dimensions = dimensions.model_copy(
            update={"protocol_approved": DimensionStatus.NOT_SATISFIED}
        )
        return _result(
            dimensions,
            PolicyStatus.DENIED,
            PolicyReasonCode.PROTOCOL_NOT_APPROVED,
            path_id=path.path_id,
        )
    dimensions = dimensions.model_copy(update={"protocol_approved": DimensionStatus.SATISFIED})
    rule = _matching_rule(auth, path.path_id, loaded_policy)
    if rule is None:
        dimensions = dimensions.model_copy(
            update={"operation_approved": DimensionStatus.NOT_SATISFIED}
        )
        return _result(
            dimensions,
            PolicyStatus.DENIED,
            PolicyReasonCode.OPERATION_NOT_APPROVED,
            path_id=path.path_id,
        )
    if rule.decision == "DENIED":
        updates = {"operation_approved": DimensionStatus.NOT_SATISFIED}
        if rule.reason_code is PolicyReasonCode.SOURCE_ROLE_NOT_APPROVED:
            updates = {
                "operation_approved": DimensionStatus.SATISFIED,
                "communication_path_approved": DimensionStatus.SATISFIED,
                "source_role_approved": DimensionStatus.NOT_SATISFIED,
            }
        elif rule.reason_code is PolicyReasonCode.COMMUNICATION_NOT_APPROVED:
            updates = {
                "operation_approved": DimensionStatus.SATISFIED,
                "communication_path_approved": DimensionStatus.NOT_SATISFIED,
                "source_role_approved": DimensionStatus.SATISFIED,
            }
        dimensions = dimensions.model_copy(update=updates)
        return _result(
            dimensions,
            PolicyStatus.DENIED,
            rule.reason_code,
            path_id=path.path_id,
            rule_id=rule.rule_id,
        )
    dimensions = dimensions.model_copy(
        update={
            "communication_path_approved": DimensionStatus.SATISFIED,
            "operation_approved": DimensionStatus.SATISFIED,
            "source_role_approved": DimensionStatus.SATISFIED,
        }
    )
    return _result(
        dimensions,
        PolicyStatus.APPROVED,
        PolicyReasonCode.POLICY_MATCH_APPROVED,
        path_id=path.path_id,
        rule_id=rule.rule_id,
    )


def unsupported_profile_result() -> PolicyEvaluationResult:
    return _result(
        _dimensions(), PolicyStatus.UNKNOWN, PolicyReasonCode.PROFILE_VERSION_UNSUPPORTED
    )


def select_primary_reason(candidates: set[PolicyReasonCode]) -> PolicyReasonCode:
    for reason in REASON_PRECEDENCE:
        if reason in candidates:
            return reason
    raise PolicyProfileError("No policy reason candidate was supplied.")


def _matching_rule(
    auth: AuthorizationInput, path_id: str, loaded_policy: LoadedPolicy
) -> CommunicationPolicyRule | None:
    matches = [
        rule
        for rule in loaded_policy.rules
        if rule.enabled
        and rule.path_id == path_id
        and rule.protocol == auth.protocol
        and auth.operation_category in rule.operations
        and auth.function_semantic in rule.function_semantics
        and auth.target_point in rule.point_ids
        and auth.point_access_class in rule.point_access_classes
    ]
    if len(matches) > 1:
        denies = [rule for rule in matches if rule.decision == "DENIED"]
        if len(denies) == 1:
            return denies[0]
        raise PolicyProfileError("Ambiguous same-precedence policy rules matched.")
    return matches[0] if matches else None


def _dimensions() -> AuthorizationDimensions:
    return AuthorizationDimensions(
        source_asset_known=DimensionStatus.UNKNOWN,
        destination_asset_known=DimensionStatus.UNKNOWN,
        source_zone_expected=DimensionStatus.UNKNOWN,
        destination_zone_expected=DimensionStatus.UNKNOWN,
        communication_path_approved=DimensionStatus.UNKNOWN,
        protocol_approved=DimensionStatus.UNKNOWN,
        operation_approved=DimensionStatus.UNKNOWN,
        point_classification_allows=DimensionStatus.UNKNOWN,
        source_role_approved=DimensionStatus.UNKNOWN,
    )


def _result(
    dimensions: AuthorizationDimensions,
    status: PolicyStatus,
    reason: PolicyReasonCode,
    *,
    path_id: str | None = None,
    rule_id: str | None = None,
) -> PolicyEvaluationResult:
    template, statement = _statement(status, reason)
    return PolicyEvaluationResult(
        dimension_results=dimensions,
        matched_path_id=path_id,
        matched_rule_id=rule_id,
        policy_status=status,
        reason_code=reason,
        statement_template_id=template,
        analyst_readable_statement=statement,
    )


def _statement(status: PolicyStatus, reason: PolicyReasonCode) -> tuple[str, str]:
    if reason is PolicyReasonCode.SOURCE_UNKNOWN:
        return (
            "SOURCE_IDENTITY_UNKNOWN",
            "The source identity for this synthetic protocol event is not present in asset "
            "inventory 1.0.0; authorization remains unknown and malicious intent is not "
            "determined.",
        )
    if reason is PolicyReasonCode.DESTINATION_UNKNOWN:
        return (
            "DESTINATION_IDENTITY_UNKNOWN",
            "The destination identity is not present in asset inventory 1.0.0; authorization "
            "remains unknown and malicious intent is not determined.",
        )
    if reason is PolicyReasonCode.IDENTITY_CONFLICT:
        return (
            "IDENTITY_CLAIMS_CONFLICT",
            "Authoritative synthetic identity claims conflict; no asset was selected and "
            "malicious intent is not determined.",
        )
    if reason is PolicyReasonCode.POINT_WRITE_NOT_APPROVED:
        return (
            "POINT_WRITE_INCOMPATIBLE",
            "The synthetic write targets a read-only point; source authorization cannot "
            "override protocol-semantic incompatibility.",
        )
    if reason in {
        PolicyReasonCode.PROFILE_VERSION_UNSUPPORTED,
        PolicyReasonCode.POLICY_PROFILE_INVALID,
    }:
        return (
            "PROFILE_UNAVAILABLE",
            "The requested synthetic profile cannot support policy evaluation; authorization "
            "remains unknown.",
        )
    if reason is PolicyReasonCode.POLICY_NOT_CLASSIFIED:
        return (
            "COMMUNICATION_UNCLASSIFIED",
            "No exact path in synthetic policy 1.0.0 classifies this communication; "
            "authorization remains unknown.",
        )
    if status is PolicyStatus.APPROVED:
        return (
            "COMMUNICATION_APPROVED",
            "The communication is approved by synthetic policy 1.0.0; execution, physical "
            "effect, and malicious intent are not determined.",
        )
    if status is PolicyStatus.DENIED:
        return (
            "COMMUNICATION_DENIED",
            "The communication is not approved by synthetic policy 1.0.0; malicious intent is "
            "not determined.",
        )
    return (
        "COMMUNICATION_UNCLASSIFIED",
        "Synthetic policy evaluation is unknown and malicious intent is not determined.",
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyProfileError("The policy profile contains a duplicate JSON key.")
        result[key] = value
    return result
