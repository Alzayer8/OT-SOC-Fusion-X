from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.context.models import AssetDefinition, RelationshipDefinition, ZoneDefinition
from app.evidence.schemas import EvidenceRecordResponse
from app.incidents.models import IncidentRecordResponse
from app.incidents.schemas import IncidentTimelineResponse
from app.schemas.common import ApiModel


class IncidentCategorySummary(ApiModel):
    asset_identity_anomaly: int = Field(ge=0)
    communication_policy_violation: int = Field(ge=0)
    control_command_investigation: int = Field(ge=0)
    process_inconsistency: int = Field(ge=0)


class IncidentOverviewSummary(ApiModel):
    total: int = Field(ge=0)
    open: int = Field(ge=0)
    investigating: int = Field(ge=0)
    resolved: int = Field(ge=0)
    low: int = Field(ge=0)
    medium: int = Field(ge=0)
    high: int = Field(ge=0)
    high_non_resolved: int = Field(ge=0)
    categories: IncidentCategorySummary


class PolicyOverviewSummary(ApiModel):
    total: int = Field(ge=0)
    approved: int = Field(ge=0)
    denied: int = Field(ge=0)
    unknown: int = Field(ge=0)


class CorrelationOverviewSummary(ApiModel):
    total: int = Field(ge=0)
    correlated: int = Field(ge=0)
    not_correlated: int = Field(ge=0)
    insufficient_evidence: int = Field(ge=0)
    indeterminate: int = Field(ge=0)


class AssetOverviewSummary(ApiModel):
    total: Literal[11]
    enabled: int = Field(ge=0, le=11)
    cyber: Literal[6]
    process: Literal[5]


class RecentActivity(ApiModel):
    activity_id: uuid.UUID
    incident_id: uuid.UUID
    entry_type: str
    observed_at: datetime
    summary: str
    asset_ids: tuple[uuid.UUID, ...]


class OverviewRunContext(ApiModel):
    run_id: uuid.UUID
    scenario_id: Literal["BASELINE", "S1", "S2", "S3", "S4"]
    scenario_state: Literal["COMPLETED"]
    context_scope: Literal["CURRENT_RUN"]
    evidence_simulation_id: str | None
    configuration_hash: str | None


class OverviewSummaryResponse(ApiModel):
    generated_at: datetime
    as_of: datetime
    window_start: datetime
    window_end: datetime
    window_complete: Literal[True]
    active_run: OverviewRunContext
    incidents: IncidentOverviewSummary
    policy_findings: PolicyOverviewSummary
    correlations: CorrelationOverviewSummary
    assets: AssetOverviewSummary
    recent_activity: tuple[RecentActivity, ...]
    process_snapshot_status: Literal["COMPLETE", "UNAVAILABLE"]
    process_snapshot_scope: Literal["ACTIVE_RUN", "BASELINE_REFERENCE", "UNAVAILABLE"]
    process_snapshot_message: str
    process_snapshot: EvidenceRecordResponse | None
    linked_valve_command: EvidenceRecordResponse | None


class ProductAsset(ApiModel):
    asset_id: uuid.UUID
    definition: AssetDefinition
    process_point_ids: tuple[str, ...]


class AssetCatalogResponse(ApiModel):
    profile_id: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    profile_version: Literal["1.0.0"]
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    domain: Literal["oil_gas_transfer"]
    educational_only: Literal[True]
    disclaimer: str
    zones: tuple[ZoneDefinition, ...] = Field(min_length=5, max_length=5)
    assets: tuple[ProductAsset, ...] = Field(min_length=11, max_length=11)
    relationships: tuple[RelationshipDefinition, ...] = Field(min_length=9, max_length=9)


class AssetDetailResponse(ApiModel):
    profile_id: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    profile_version: Literal["1.0.0"]
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    asset: ProductAsset
    zone: ZoneDefinition
    inbound_relationships: tuple[RelationshipDefinition, ...]
    outbound_relationships: tuple[RelationshipDefinition, ...]


ReplaySourceKind = Literal["INCIDENT", "CORRELATION", "EVIDENCE_WINDOW"]
ReplayEventClass = Literal[
    "RAW_PROTOCOL",
    "PROTOCOL_SEMANTIC",
    "ASSET_CONTEXT",
    "POLICY_FINDING",
    "TELEMETRY",
    "CORRELATION_FINDING",
    "INCIDENT_EVENT",
]


class ReplayEvent(ApiModel):
    event_id: uuid.UUID
    event_class: ReplayEventClass
    sort_rank: Literal[10, 20, 30, 40, 50, 60, 70]
    observed_at: datetime
    summary: str
    evidence: EvidenceRecordResponse | None = None
    incident_event: IncidentTimelineResponse | None = None
    integrity_verified: Literal[True]

    @model_validator(mode="after")
    def require_one_payload(self) -> ReplayEvent:
        if (self.evidence is None) == (self.incident_event is None):
            raise ValueError("replay event must contain exactly one event payload")
        return self


class ReplayBundleResponse(ApiModel):
    source_kind: ReplaySourceKind
    lab_run_id: uuid.UUID | None = None
    scenario_id: Literal["BASELINE", "S1", "S2", "S3", "S4"] | None = None
    incident: IncidentRecordResponse | None
    correlation_evidence_id: uuid.UUID | None
    simulation_id: str | None
    configuration_hash: str | None
    observed_from: datetime | None
    observed_to: datetime | None
    events: tuple[ReplayEvent, ...] = Field(max_length=2_000)
    completeness: Literal["COMPLETE", "PARTIAL"]
    gaps: tuple[str, ...]
    truncated: Literal[False]


class ReplayWindowRequest(ApiModel):
    simulation_id: str = Field(min_length=5, max_length=80, pattern=r"^[a-zA-Z0-9._:-]+$")
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_from: AwareDatetime
    observed_to: AwareDatetime
    evidence_types: tuple[
        Literal[
            "simulator_telemetry",
            "synthetic_protocol_event",
            "protocol_semantic_event",
            "asset_context_event",
            "communication_policy_finding",
            "correlation_finding",
        ],
        ...,
    ]

    @model_validator(mode="after")
    def validate_window(self) -> ReplayWindowRequest:
        if self.observed_from > self.observed_to:
            raise ValueError("observed_from must not be later than observed_to")
        if (self.observed_to - self.observed_from).total_seconds() > 900:
            raise ValueError("replay evidence window must not exceed 15 minutes")
        if not self.evidence_types or len(set(self.evidence_types)) != len(self.evidence_types):
            raise ValueError("replay evidence types must be non-empty and unique")
        return self
