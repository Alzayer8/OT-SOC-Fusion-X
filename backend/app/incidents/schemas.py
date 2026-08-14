from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.incidents.models import (
    EvidenceRole,
    IncidentCategory,
    IncidentDisposition,
    IncidentRecordResponse,
    IncidentSeverity,
    IncidentStatus,
    Sha256,
    StrictIncidentModel,
    TimelineEntryType,
)


class IncidentMembershipResponse(StrictIncidentModel):
    membership_id: uuid.UUID
    evidence_id: uuid.UUID
    evidence_type: str
    evidence_schema: str
    evidence_schema_version: str
    integrity_sha256: Sha256
    role: EvidenceRole
    observed_at: datetime
    received_at: datetime
    added_at: datetime


class IncidentTimelineResponse(StrictIncidentModel):
    timeline_entry_id: uuid.UUID
    observed_at: datetime
    recorded_at: datetime
    entry_type: TimelineEntryType
    reference_id: uuid.UUID
    evidence_id: uuid.UUID | None
    evidence_type: str | None
    evidence_schema: str | None
    evidence_schema_version: str | None
    evidence_integrity_sha256: str | None
    received_at: datetime | None
    asset_ids: tuple[uuid.UUID, ...]
    process_asset_ids: tuple[uuid.UUID, ...]
    summary: str
    actor_context: str
    aggregate_version: int


class IncidentStatusHistoryResponse(StrictIncidentModel):
    status_history_id: uuid.UUID
    previous_status: IncidentStatus | None
    new_status: IncidentStatus
    changed_at: datetime
    actor_context: str
    actor_user_id: uuid.UUID | None = None
    reason: str | None
    request_id: str
    version_before: int
    version_after: int


class IncidentSeverityHistoryResponse(StrictIncidentModel):
    severity_history_id: uuid.UUID
    previous_severity: IncidentSeverity | None
    new_severity: IncidentSeverity
    triggering_evidence_id: uuid.UUID
    triggering_integrity_sha256: Sha256
    profile_version: str
    rule_version: str
    calculated_at: datetime
    aggregate_version: int


class IncidentNoteResponse(StrictIncidentModel):
    note_id: uuid.UUID
    content: str
    actor_context: str
    actor_user_id: uuid.UUID | None = None
    created_at: datetime
    aggregate_version: int


class IncidentLineageReference(StrictIncidentModel):
    evidence_id: uuid.UUID
    evidence_type: str
    integrity_sha256: Sha256
    relationship: str


class IncidentContextResponse(StrictIncidentModel):
    policy: str
    correlation: str
    evidence_completeness: str
    unavailable: tuple[str, ...]


class IncidentDetailResponse(StrictIncidentModel):
    incident: IncidentRecordResponse
    evidence_memberships: tuple[IncidentMembershipResponse, ...]
    lineage_references: tuple[IncidentLineageReference, ...]
    timeline: tuple[IncidentTimelineResponse, ...]
    status_history: tuple[IncidentStatusHistoryResponse, ...]
    severity_history: tuple[IncidentSeverityHistoryResponse, ...]
    notes: tuple[IncidentNoteResponse, ...]
    context: IncidentContextResponse


class IncidentListResponse(StrictIncidentModel):
    items: tuple[IncidentRecordResponse, ...]
    limit: int = Field(ge=1, le=100)
    next_cursor: str | None


class IncidentStatusPatchRequest(StrictIncidentModel):
    new_status: IncidentStatus
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class IncidentNoteCreateRequest(StrictIncidentModel):
    content: str = Field(min_length=1, max_length=2_000)
    expected_version: int = Field(ge=1)


class IncidentMutationResponse(StrictIncidentModel):
    incident: IncidentRecordResponse
    operation: Literal[
        "status_changed",
        "note_added",
        "assignment_changed",
        "disposition_changed",
    ]
    warnings: tuple[str, ...] = ()


class IncidentAssignmentPatchRequest(StrictIncidentModel):
    assignee_user_id: uuid.UUID | None
    expected_version: int = Field(ge=1)


class IncidentDispositionPatchRequest(StrictIncidentModel):
    disposition: IncidentDisposition
    reason: str = Field(min_length=1, max_length=2_000)
    expected_version: int = Field(ge=1)


class IncidentReportFields(StrictIncidentModel):
    investigation_summary: str = Field(default="", max_length=4_000)
    analyst_assessment: str = Field(default="", max_length=4_000)
    evidence_assessment: str = Field(default="", max_length=4_000)
    process_impact_assessment: str = Field(default="", max_length=4_000)
    disposition_rationale: str = Field(default="", max_length=4_000)
    recommended_follow_up: str = Field(default="", max_length=4_000)
    final_conclusion: str = Field(default="", max_length=4_000)


class IncidentReportPutRequest(IncidentReportFields):
    expected_version: int = Field(ge=0)


class IncidentReportAutoContext(StrictIncidentModel):
    incident_id: uuid.UUID
    category: IncidentCategory
    severity: IncidentSeverity
    status: IncidentStatus
    disposition: IncidentDisposition
    assignee_user_id: uuid.UUID | None
    affected_assets: tuple[str, ...]
    first_observed_at: datetime
    last_observed_at: datetime
    evidence_count: int
    protocol_context: str
    policy_context: str
    correlation_context: str
    process_context: str


class IncidentReportResponse(IncidentReportFields):
    incident_id: uuid.UUID
    version: int = Field(ge=0)
    created_by_user_id: uuid.UUID | None
    created_at: datetime | None
    updated_by_user_id: uuid.UUID | None
    updated_at: datetime | None
    fields_filled: int = Field(ge=0, le=7)
    fields_total: Literal[7] = 7
    auto_context: IncidentReportAutoContext


class IncidentAuditResponse(StrictIncidentModel):
    audit_id: uuid.UUID
    action: str
    actor_user_id: uuid.UUID | None
    actor_display_name: str
    occurred_at: datetime
    summary: str
    result: str
    request_id: str


class IncidentAuditListResponse(StrictIncidentModel):
    items: tuple[IncidentAuditResponse, ...]


class IncidentListFilters(StrictIncidentModel):
    status: IncidentStatus | None = None
    category: IncidentCategory | None = None
    severity: IncidentSeverity | None = None
    asset_id: uuid.UUID | None = None
    observed_from: AwareDatetime | None = None
    observed_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_time_bounds(self) -> IncidentListFilters:
        if (self.observed_from is None) != (self.observed_to is None):
            raise ValueError("observed_from and observed_to must be supplied together")
        if self.observed_from is not None and self.observed_to is not None:
            if self.observed_from > self.observed_to:
                raise ValueError("observed_from must not be later than observed_to")
            if self.observed_to - self.observed_from > timedelta(days=31):
                raise ValueError("incident list time range must not exceed 31 days")
        return self
