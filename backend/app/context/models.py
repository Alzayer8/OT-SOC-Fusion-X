from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.protocols.models import (
    FunctionSemantic,
    OperationCategory,
    OperationCompatibility,
    PointAccessClass,
)

INVENTORY_PROFILE_ID = "otsoc.asset_inventory.oil_gas_transfer"
INVENTORY_PROFILE_VERSION = "1.0.0"
POLICY_PROFILE_ID = "otsoc.communication_policy.oil_gas_transfer"
POLICY_PROFILE_VERSION = "1.0.0"
ASSET_CONTEXT_SCHEMA = "otsoc.asset.context_event"
ASSET_CONTEXT_SCHEMA_VERSION = "1.0.0"
POLICY_FINDING_SCHEMA = "otsoc.communication_policy.finding"
POLICY_FINDING_SCHEMA_VERSION = "1.0.0"
RESOLVER_NAME = "otsoc_exact_asset_resolver"
RESOLVER_VERSION = "1.0.0"
EVALUATOR_NAME = "otsoc_communication_policy_evaluator"
EVALUATOR_VERSION = "1.0.0"

SafeKey = Annotated[
    str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
]
SemVer = Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class StrictContextModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
        allow_inf_nan=False,
        frozen=True,
    )


class AssetKind(StrEnum):
    CYBER = "CYBER"
    PROCESS = "PROCESS"


class AssetType(StrEnum):
    OT_CONTROLLER = "OT_CONTROLLER"
    HUMAN_MACHINE_INTERFACE = "HUMAN_MACHINE_INTERFACE"
    ENGINEERING_WORKSTATION = "ENGINEERING_WORKSTATION"
    IT_WORKSTATION = "IT_WORKSTATION"
    MONITORING_SENSOR = "MONITORING_SENSOR"
    OT_SOC_PLATFORM = "OT_SOC_PLATFORM"
    SOURCE_TANK = "SOURCE_TANK"
    TRANSFER_PUMP = "TRANSFER_PUMP"
    PIPELINE = "PIPELINE"
    CONTROL_VALVE = "CONTROL_VALVE"
    RECEIVING_TANK = "RECEIVING_TANK"


class AssetRole(StrEnum):
    CONTROL_EXECUTION = "CONTROL_EXECUTION"
    OPERATOR_INTERFACE = "OPERATOR_INTERFACE"
    ENGINEERING_MAINTENANCE = "ENGINEERING_MAINTENANCE"
    ENTERPRISE_USER = "ENTERPRISE_USER"
    PASSIVE_MONITOR = "PASSIVE_MONITOR"
    ANALYST_PLATFORM = "ANALYST_PLATFORM"
    SOURCE_STORAGE = "SOURCE_STORAGE"
    LIQUID_TRANSFER = "LIQUID_TRANSFER"
    TRANSFER_PATH = "TRANSFER_PATH"
    FLOW_CONTROL = "FLOW_CONTROL"
    DESTINATION_STORAGE = "DESTINATION_STORAGE"


class ZoneId(StrEnum):
    IT_ZONE = "IT_ZONE"
    OT_CONTROL_ZONE = "OT_CONTROL_ZONE"
    PROCESS_ZONE = "PROCESS_ZONE"
    MONITORING_ZONE = "MONITORING_ZONE"
    SOC_ZONE = "SOC_ZONE"


class TrustClassification(StrEnum):
    NO_OT_CONTROL_TRUST = "NO_OT_CONTROL_TRUST"
    LIMITED_CONTROL_TRUST = "LIMITED_CONTROL_TRUST"
    NON_NETWORK_PROCESS_CONTEXT = "NON_NETWORK_PROCESS_CONTEXT"
    PASSIVE_OBSERVATION_ONLY = "PASSIVE_OBSERVATION_ONLY"
    READ_ONLY_ANALYST_CONTEXT = "READ_ONLY_ANALYST_CONTEXT"


class Criticality(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IdentifierType(StrEnum):
    LOGICAL_ID = "LOGICAL_ID"
    PROTOCOL_ENDPOINT_ID = "PROTOCOL_ENDPOINT_ID"
    PROCESS_TAG = "PROCESS_TAG"


class RelationshipType(StrEnum):
    HOSTS_ENDPOINT = "HOSTS_ENDPOINT"
    CONTROLS = "CONTROLS"
    OBSERVES = "OBSERVES"
    MONITORS = "MONITORS"


class RelationshipTargetKind(StrEnum):
    ASSET = "ASSET"
    ENDPOINT = "ENDPOINT"


class ResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


class PolicyStatus(StrEnum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    UNKNOWN = "UNKNOWN"


class DimensionStatus(StrEnum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PolicyReasonCode(StrEnum):
    SOURCE_EVIDENCE_NOT_VERIFIED = "SOURCE_EVIDENCE_NOT_VERIFIED"
    SEMANTIC_EVIDENCE_NOT_VERIFIED = "SEMANTIC_EVIDENCE_NOT_VERIFIED"
    PROFILE_VERSION_UNSUPPORTED = "PROFILE_VERSION_UNSUPPORTED"
    POLICY_PROFILE_INVALID = "POLICY_PROFILE_INVALID"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    SOURCE_UNKNOWN = "SOURCE_UNKNOWN"
    DESTINATION_UNKNOWN = "DESTINATION_UNKNOWN"
    SOURCE_DISABLED = "SOURCE_DISABLED"
    DESTINATION_DISABLED = "DESTINATION_DISABLED"
    SOURCE_ZONE_UNEXPECTED = "SOURCE_ZONE_UNEXPECTED"
    DESTINATION_ZONE_UNEXPECTED = "DESTINATION_ZONE_UNEXPECTED"
    POINT_WRITE_NOT_APPROVED = "POINT_WRITE_NOT_APPROVED"
    PROTOCOL_NOT_APPROVED = "PROTOCOL_NOT_APPROVED"
    OPERATION_NOT_APPROVED = "OPERATION_NOT_APPROVED"
    SOURCE_ROLE_NOT_APPROVED = "SOURCE_ROLE_NOT_APPROVED"
    COMMUNICATION_NOT_APPROVED = "COMMUNICATION_NOT_APPROVED"
    POLICY_NOT_CLASSIFIED = "POLICY_NOT_CLASSIFIED"
    POLICY_MATCH_APPROVED = "POLICY_MATCH_APPROVED"


REASON_PRECEDENCE = tuple(PolicyReasonCode)


class Identifier(StrictContextModel):
    identifier_type: IdentifierType
    value: SafeKey


class ZoneDefinition(StrictContextModel):
    zone_id: ZoneId
    name: Annotated[str, Field(min_length=1, max_length=80)]
    purpose: Annotated[str, Field(min_length=1, max_length=180)]
    trust_classification: TrustClassification
    allowed_relationship_types: tuple[RelationshipType, ...]


class AssetDefinition(StrictContextModel):
    asset_key: SafeKey
    display_name: Annotated[str, Field(min_length=1, max_length=120)]
    asset_kind: AssetKind
    asset_type: AssetType
    asset_role: AssetRole
    zone_id: ZoneId
    criticality: Criticality
    process_role: Annotated[str, Field(min_length=1, max_length=80)] | None
    protocol_capabilities: tuple[Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")], ...]
    enabled: bool
    identifiers: tuple[Identifier, ...] = Field(min_length=1, max_length=4)


class RelationshipDefinition(StrictContextModel):
    relationship_type: RelationshipType
    source_asset_key: SafeKey
    target_kind: RelationshipTargetKind
    target_ref: SafeKey


class AssetInventoryProfile(StrictContextModel):
    profile_id: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    profile_version: SemVer
    domain: Literal["oil_gas_transfer"]
    educational_only: Literal[True]
    disclaimer: Literal[
        "Fictional academic synthetic inventory; non-plant-derived and not for real equipment."
    ]
    protocol_profile_id: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    protocol_profile_version: Literal["1.0.0"]
    protocol_profile_sha256: Sha256
    zones: tuple[ZoneDefinition, ...] = Field(min_length=5, max_length=5)
    assets: tuple[AssetDefinition, ...] = Field(min_length=11, max_length=11)
    relationships: tuple[RelationshipDefinition, ...] = Field(min_length=9, max_length=9)

    @model_validator(mode="after")
    def validate_inventory_contract(self) -> AssetInventoryProfile:
        if self.profile_version != INVENTORY_PROFILE_VERSION:
            raise ValueError("unsupported inventory profile version")
        zone_ids = [zone.zone_id for zone in self.zones]
        if len(set(zone_ids)) != 5 or set(zone_ids) != set(ZoneId):
            raise ValueError("inventory must contain the five approved zones")
        asset_keys = [asset.asset_key for asset in self.assets]
        if len(set(asset_keys)) != 11:
            raise ValueError("inventory must contain eleven unique assets")
        if sum(asset.asset_kind is AssetKind.CYBER for asset in self.assets) != 6:
            raise ValueError("inventory must contain six cyber assets")
        if sum(asset.asset_kind is AssetKind.PROCESS for asset in self.assets) != 5:
            raise ValueError("inventory must contain five process assets")
        identifiers = [
            (identifier.identifier_type, identifier.value)
            for asset in self.assets
            for identifier in asset.identifiers
        ]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate typed asset identifier")
        asset_map = {asset.asset_key: asset for asset in self.assets}
        endpoint_values = {
            identifier.value
            for asset in self.assets
            for identifier in asset.identifiers
            if identifier.identifier_type is IdentifierType.PROTOCOL_ENDPOINT_ID
        }
        relationship_keys: list[tuple[RelationshipType, str, str, str]] = []
        zone_map = {zone.zone_id: zone for zone in self.zones}
        for asset in self.assets:
            if asset.zone_id not in zone_map:
                raise ValueError("asset references an unknown zone")
        for relationship in self.relationships:
            source = asset_map.get(relationship.source_asset_key)
            if source is None:
                raise ValueError("relationship source does not exist")
            if (
                relationship.relationship_type
                not in zone_map[source.zone_id].allowed_relationship_types
            ):
                raise ValueError("relationship type is not allowed from the source zone")
            if relationship.target_kind is RelationshipTargetKind.ASSET:
                if relationship.target_ref not in asset_map:
                    raise ValueError("relationship target asset does not exist")
                if relationship.target_ref == relationship.source_asset_key:
                    raise ValueError("asset self relationships are prohibited")
            elif relationship.target_ref not in endpoint_values:
                raise ValueError("relationship endpoint target does not exist")
            relationship_keys.append(
                (
                    relationship.relationship_type,
                    relationship.source_asset_key,
                    relationship.target_kind,
                    relationship.target_ref,
                )
            )
        if len(relationship_keys) != len(set(relationship_keys)):
            raise ValueError("duplicate asset relationship")
        return self


class GovernedPath(StrictContextModel):
    path_id: SafeKey
    source_asset_key: SafeKey
    source_role: AssetRole
    source_zone: ZoneId
    destination_asset_key: SafeKey
    destination_role: AssetRole
    destination_zone: ZoneId
    approved_protocols: tuple[Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")], ...]
    unlisted_posture: Literal["DENIED"]


class CommunicationPolicyRule(StrictContextModel):
    rule_id: SafeKey
    path_id: SafeKey
    source_asset_key: SafeKey
    source_role: AssetRole
    source_zone: ZoneId
    destination_asset_key: SafeKey
    destination_role: AssetRole
    destination_zone: ZoneId
    protocol: Literal["modbus_tcp"]
    operations: tuple[OperationCategory, ...] = Field(min_length=1)
    function_semantics: tuple[FunctionSemantic, ...] = Field(min_length=1)
    point_ids: tuple[Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")], ...] = Field(min_length=1)
    point_access_classes: tuple[PointAccessClass, ...] = Field(min_length=1)
    decision: Literal["APPROVED", "DENIED"]
    reason_code: PolicyReasonCode
    enabled: Literal[True]


class CommunicationPolicyProfile(StrictContextModel):
    profile_id: Literal["otsoc.communication_policy.oil_gas_transfer"]
    profile_version: SemVer
    educational_only: Literal[True]
    disclaimer: Literal[
        "Fictional academic synthetic policy; descriptive only and not a network rule set."
    ]
    inventory_profile_id: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    inventory_profile_version: Literal["1.0.0"]
    protocol_profile_id: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    protocol_profile_version: Literal["1.0.0"]
    protocol_profile_sha256: Sha256
    governed_paths: tuple[GovernedPath, ...] = Field(min_length=3, max_length=3)
    rules: tuple[CommunicationPolicyRule, ...] = Field(min_length=6, max_length=6)
    reason_precedence: tuple[PolicyReasonCode, ...]

    @model_validator(mode="after")
    def validate_policy_structure(self) -> CommunicationPolicyProfile:
        path_ids = [path.path_id for path in self.governed_paths]
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(path_ids) != len(set(path_ids)) or len(rule_ids) != len(set(rule_ids)):
            raise ValueError("duplicate policy path or rule")
        if self.reason_precedence != REASON_PRECEDENCE:
            raise ValueError("policy reason-code precedence differs from the contract")
        path_map = {path.path_id: path for path in self.governed_paths}
        for rule in self.rules:
            path = path_map.get(rule.path_id)
            if path is None:
                raise ValueError("policy rule references an unknown path")
            if (
                rule.source_asset_key,
                rule.source_role,
                rule.source_zone,
                rule.destination_asset_key,
                rule.destination_role,
                rule.destination_zone,
            ) != (
                path.source_asset_key,
                path.source_role,
                path.source_zone,
                path.destination_asset_key,
                path.destination_role,
                path.destination_zone,
            ):
                raise ValueError("policy rule identity context differs from its path")
            if any(token in {"*", "ANY"} for token in rule.point_ids):
                raise ValueError("wildcard policy selectors are prohibited")
        return self


class IdentityClaim(StrictContextModel):
    identifier_type: IdentifierType
    value: SafeKey


class AssetResolution(StrictContextModel):
    status: ResolutionStatus
    known_asset: bool
    enabled: bool | None
    asset_id: uuid.UUID | None
    asset_key: str | None
    asset_kind: AssetKind | None
    asset_type: AssetType | None
    asset_role: AssetRole | None
    zone_id: ZoneId | None
    criticality: Criticality | None

    @model_validator(mode="after")
    def validate_resolution_shape(self) -> AssetResolution:
        trusted = (
            self.asset_id,
            self.asset_key,
            self.asset_kind,
            self.asset_type,
            self.asset_role,
            self.zone_id,
            self.criticality,
        )
        if self.status is ResolutionStatus.RESOLVED:
            if (
                not self.known_asset
                or self.enabled is None
                or any(value is None for value in trusted)
            ):
                raise ValueError("resolved identity requires complete trusted context")
        elif (
            self.known_asset
            or self.enabled is not None
            or any(value is not None for value in trusted)
        ):
            raise ValueError("unknown/conflict identity cannot contain trusted asset context")
        return self


class ResolvedRelationship(StrictContextModel):
    relationship_type: RelationshipType
    source_asset_key: SafeKey
    target_kind: RelationshipTargetKind
    target_ref: SafeKey


class AssetContextEvent(StrictContextModel):
    asset_context_event_id: uuid.UUID
    asset_context_schema: Literal["otsoc.asset.context_event"]
    asset_context_schema_version: Literal["1.0.0"]
    source_evidence_id: uuid.UUID
    source_evidence_integrity_sha256: Sha256
    semantic_event_id: uuid.UUID
    semantic_evidence_integrity_sha256: Sha256
    inventory_profile: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    inventory_version: SemVer
    inventory_sha256: Sha256
    resolver_name: Literal["otsoc_exact_asset_resolver"]
    resolver_version: SemVer
    canonicalization_version: Literal["otsoc-canonical-json-1"]
    observed_at: AwareDatetime
    source_identity_claims: tuple[IdentityClaim, ...] = Field(min_length=1, max_length=4)
    destination_identity_claims: tuple[IdentityClaim, ...] = Field(min_length=1, max_length=4)
    source_resolution: AssetResolution
    destination_resolution: AssetResolution
    relevant_relationships: tuple[ResolvedRelationship, ...]
    target_process_asset: AssetResolution | None
    derivation_kind: Literal["ASSET_CONTEXT_RESOLUTION"]
    derived_from: uuid.UUID
    ground_truth_used: Literal[False]


class AuthorizationDimensions(StrictContextModel):
    source_asset_known: DimensionStatus
    destination_asset_known: DimensionStatus
    source_zone_expected: DimensionStatus
    destination_zone_expected: DimensionStatus
    communication_path_approved: DimensionStatus
    protocol_approved: DimensionStatus
    operation_approved: DimensionStatus
    point_classification_allows: DimensionStatus
    source_role_approved: DimensionStatus


class AuthorizationInput(StrictContextModel):
    source_evidence_verified: bool
    semantic_evidence_verified: bool
    source_evidence_id: uuid.UUID
    source_evidence_integrity_sha256: Sha256
    semantic_event_id: uuid.UUID
    semantic_evidence_integrity_sha256: Sha256
    observed_at: AwareDatetime
    protocol_profile: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    protocol_profile_version: Literal["1.0.0"]
    protocol_profile_sha256: Sha256
    protocol: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
    operation_category: OperationCategory
    function_semantic: FunctionSemantic | None
    function_code: int = Field(ge=0, le=255)
    target_point: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")] | None
    point_access_class: PointAccessClass | None
    fictional_target_component: SafeKey | None
    operation_compatibility: OperationCompatibility


class PolicyEvaluationResult(StrictContextModel):
    dimension_results: AuthorizationDimensions
    matched_path_id: str | None
    matched_rule_id: str | None
    policy_status: PolicyStatus
    reason_code: PolicyReasonCode
    statement_template_id: str
    analyst_readable_statement: str


class CommunicationPolicyFinding(StrictContextModel):
    finding_id: uuid.UUID
    finding_schema: Literal["otsoc.communication_policy.finding"]
    finding_schema_version: Literal["1.0.0"]
    source_evidence_id: uuid.UUID
    source_evidence_integrity_sha256: Sha256
    semantic_event_id: uuid.UUID
    semantic_evidence_integrity_sha256: Sha256
    asset_context_event_id: uuid.UUID
    evaluated_at: AwareDatetime
    inventory_profile: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    inventory_version: SemVer
    inventory_sha256: Sha256
    policy_profile: Literal["otsoc.communication_policy.oil_gas_transfer"]
    policy_version: SemVer
    policy_sha256: Sha256
    protocol_profile: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    protocol_profile_version: Literal["1.0.0"]
    protocol_profile_sha256: Sha256
    evaluator_name: Literal["otsoc_communication_policy_evaluator"]
    evaluator_version: SemVer
    canonicalization_version: Literal["otsoc-canonical-json-1"]
    source_resolution: ResolutionStatus
    destination_resolution: ResolutionStatus
    source_asset_id: uuid.UUID | None
    source_asset_key: str | None
    source_role: AssetRole | None
    source_zone: ZoneId | None
    destination_asset_id: uuid.UUID | None
    destination_asset_key: str | None
    destination_role: AssetRole | None
    destination_zone: ZoneId | None
    protocol: str
    operation_category: OperationCategory
    function_semantic: FunctionSemantic | None
    function_code: int
    target_point: str | None
    point_access_class: PointAccessClass | None
    fictional_target_component: str | None
    operation_compatibility: OperationCompatibility
    dimension_results: AuthorizationDimensions
    matched_path_id: str | None
    matched_rule_id: str | None
    policy_status: PolicyStatus
    reason_code: PolicyReasonCode
    statement_template_id: str
    analyst_readable_statement: str
    malicious_intent_inferred: Literal[False]
    derivation_kind: Literal["COMMUNICATION_POLICY_EVALUATION"]
    derived_from: tuple[uuid.UUID, uuid.UUID]
    ground_truth_used: Literal[False]


class AssetContextDerivationProvenance(StrictContextModel):
    derivation_kind: Literal["ASSET_CONTEXT_RESOLUTION"]
    semantic_event_id: uuid.UUID
    semantic_evidence_integrity_sha256: Sha256
    inventory_profile: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    inventory_version: SemVer
    inventory_sha256: Sha256
    resolver_name: Literal["otsoc_exact_asset_resolver"]
    resolver_version: SemVer
    canonicalization_version: Literal["otsoc-canonical-json-1"]
    educational_only: Literal[True]
    ground_truth_used: Literal[False]


class PolicyFindingDerivationProvenance(StrictContextModel):
    derivation_kind: Literal["COMMUNICATION_POLICY_EVALUATION"]
    source_evidence_id: uuid.UUID
    semantic_event_id: uuid.UUID
    semantic_evidence_integrity_sha256: Sha256
    asset_context_event_id: uuid.UUID
    asset_context_integrity_sha256: Sha256
    inventory_profile: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    inventory_version: SemVer
    inventory_sha256: Sha256
    policy_profile: Literal["otsoc.communication_policy.oil_gas_transfer"]
    policy_version: SemVer
    policy_sha256: Sha256
    evaluator_name: Literal["otsoc_communication_policy_evaluator"]
    evaluator_version: SemVer
    canonicalization_version: Literal["otsoc-canonical-json-1"]
    educational_only: Literal[True]
    ground_truth_used: Literal[False]


class AssetContextEvidenceEnvelope(StrictContextModel):
    source_key: Literal["asset-context-resolver"]
    source_event_id: Annotated[str, Field(pattern=r"^[a-f0-9-]{36}$")]
    evidence_type: Literal["asset_context_event"]
    observed_at: AwareDatetime
    sequence_number: int = Field(ge=0, le=86_400_000)
    payload_schema: Literal["otsoc.asset.context_event"]
    payload_schema_version: Literal["1.0.0"]
    payload: AssetContextEvent
    provenance: AssetContextDerivationProvenance

    @model_validator(mode="after")
    def validate_context_envelope(self) -> AssetContextEvidenceEnvelope:
        if self.payload.observed_at != self.observed_at:
            raise ValueError("asset context timestamp does not match observed_at")
        if self.payload.semantic_event_id != self.provenance.semantic_event_id:
            raise ValueError("asset context semantic evidence ID does not match provenance")
        if (
            self.payload.semantic_evidence_integrity_sha256
            != self.provenance.semantic_evidence_integrity_sha256
        ):
            raise ValueError("asset context semantic digest does not match provenance")
        if self.payload.inventory_sha256 != self.provenance.inventory_sha256:
            raise ValueError("asset context inventory digest does not match provenance")
        if str(self.payload.asset_context_event_id) == str(self.payload.semantic_event_id):
            raise ValueError("asset context evidence must not reuse the semantic evidence ID")
        return self


class PolicyFindingEvidenceEnvelope(StrictContextModel):
    source_key: Literal["communication-policy-evaluator"]
    source_event_id: Annotated[str, Field(pattern=r"^[a-f0-9-]{36}$")]
    evidence_type: Literal["communication_policy_finding"]
    observed_at: AwareDatetime
    sequence_number: int = Field(ge=0, le=86_400_000)
    payload_schema: Literal["otsoc.communication_policy.finding"]
    payload_schema_version: Literal["1.0.0"]
    payload: CommunicationPolicyFinding
    provenance: PolicyFindingDerivationProvenance

    @model_validator(mode="after")
    def validate_finding_envelope(self) -> PolicyFindingEvidenceEnvelope:
        if self.payload.evaluated_at != self.observed_at:
            raise ValueError("policy finding timestamp does not match observed_at")
        if self.payload.semantic_event_id != self.provenance.semantic_event_id:
            raise ValueError("policy finding semantic ID does not match provenance")
        if self.payload.asset_context_event_id != self.provenance.asset_context_event_id:
            raise ValueError("policy finding context ID does not match provenance")
        if self.payload.policy_sha256 != self.provenance.policy_sha256:
            raise ValueError("policy finding digest does not match provenance")
        if self.payload.inventory_sha256 != self.provenance.inventory_sha256:
            raise ValueError("policy finding inventory digest does not match provenance")
        if str(self.payload.finding_id) in {
            str(self.payload.semantic_event_id),
            str(self.payload.asset_context_event_id),
        }:
            raise ValueError("policy finding must use an independent evidence identity")
        return self
