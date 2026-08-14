from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.evidence.models import EvidenceBase

INCIDENT_PROFILE_ID = "otsoc.incident.oil_gas_transfer"
INCIDENT_PROFILE_VERSION = "1.0.0"
INCIDENT_SCHEMA = "otsoc.incident.record"
INCIDENT_SCHEMA_VERSION = "1.0.0"
INCIDENT_PRODUCER = "otsoc_offline_incident_engine"
INCIDENT_PRODUCER_VERSION = "1.0.0"
INCIDENT_CANONICALIZATION_VERSION = "otsoc-canonical-json-1"

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SemVer = Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]
SafeText = Annotated[str, Field(min_length=1, max_length=600)]


class StrictIncidentModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=False,
        allow_inf_nan=False,
        frozen=True,
    )


class IncidentCategory(StrEnum):
    ASSET_IDENTITY_ANOMALY = "ASSET_IDENTITY_ANOMALY"
    COMMUNICATION_POLICY_VIOLATION = "COMMUNICATION_POLICY_VIOLATION"
    CONTROL_COMMAND_INVESTIGATION = "CONTROL_COMMAND_INVESTIGATION"
    PROCESS_INCONSISTENCY = "PROCESS_INCONSISTENCY"


class IncidentSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"


class IncidentDisposition(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class EvidenceRole(StrEnum):
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    CONTEXT = "CONTEXT"


class TimelineEntryType(StrEnum):
    INCIDENT_CREATED = "INCIDENT_CREATED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    STATUS_CHANGED = "STATUS_CHANGED"
    SEVERITY_CHANGED = "SEVERITY_CHANGED"
    ANALYST_NOTE_ADDED = "ANALYST_NOTE_ADDED"


TIMELINE_ENTRY_ORDER = {value: index for index, value in enumerate(TimelineEntryType, start=1)}


class AuditAction(StrEnum):
    INCIDENT_CREATED = "INCIDENT_CREATED"
    INCIDENT_REUSED = "INCIDENT_REUSED"
    EVIDENCE_ENRICHED = "EVIDENCE_ENRICHED"
    STATUS_TRANSITIONED = "STATUS_TRANSITIONED"
    SEVERITY_ESCALATED = "SEVERITY_ESCALATED"
    ANALYST_NOTE_ADDED = "ANALYST_NOTE_ADDED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    ASSIGNMENT_CHANGED = "ASSIGNMENT_CHANGED"
    DISPOSITION_CHANGED = "DISPOSITION_CHANGED"
    REPORT_SAVED = "REPORT_SAVED"


class EvidenceSelection(StrictIncidentModel):
    evidence_id: uuid.UUID
    expected_integrity_sha256: Sha256


class IncidentQualificationRequest(StrictIncidentModel):
    policy_finding: EvidenceSelection | None = None
    correlation_finding: EvidenceSelection | None = None

    @model_validator(mode="after")
    def require_input(self) -> IncidentQualificationRequest:
        if self.policy_finding is None and self.correlation_finding is None:
            raise ValueError("at least one stored evidence selection is required")
        return self


class CandidateMembership(StrictIncidentModel):
    evidence_id: uuid.UUID
    evidence_type: str = Field(min_length=1, max_length=48)
    evidence_schema: str = Field(min_length=1, max_length=80)
    evidence_schema_version: SemVer
    integrity_sha256: Sha256
    role: EvidenceRole
    observed_at: AwareDatetime
    received_at: AwareDatetime


class QualifiedIncidentCandidate(StrictIncidentModel):
    qualification_rule_id: str = Field(min_length=1, max_length=80)
    qualification_rule_version: Literal["1.0.0"]
    category: IncidentCategory
    severity: IncidentSeverity
    title: str = Field(min_length=1, max_length=160)
    summary: SafeText
    primary_membership: CandidateMembership
    additional_memberships: tuple[CandidateMembership, ...]
    identity_asset_scope: tuple[str, ...]
    process_asset_scope: tuple[str, ...]
    target_point_scope: tuple[str, ...]
    source_asset_id: uuid.UUID | None
    destination_asset_id: uuid.UUID | None
    controller_asset_id: uuid.UUID | None
    process_asset_ids: tuple[uuid.UUID, ...]
    process_asset_keys: tuple[str, ...]
    correlation_rule_id: str | None
    correlation_rule_version: str | None
    run_scope: str = Field(min_length=1, max_length=160)
    configuration_scope: str = Field(min_length=1, max_length=160)
    bound_simulation_id: str | None
    bound_configuration_hash: Sha256 | None
    s3_semantic_evidence_id: uuid.UUID | None
    grouping_anchor: AwareDatetime
    first_observed_at: AwareDatetime
    last_observed_at: AwareDatetime
    policy_context: str
    correlation_context: str
    evidence_completeness: str
    ground_truth_used: Literal[False] = False
    malicious_intent_inferred: Literal[False] = False
    causality_inferred: Literal[False] = False

    @model_validator(mode="after")
    def validate_primary_membership(self) -> QualifiedIncidentCandidate:
        if self.primary_membership.role is not EvidenceRole.PRIMARY:
            raise ValueError("candidate primary evidence must use PRIMARY role")
        if any(item.role is EvidenceRole.PRIMARY for item in self.additional_memberships):
            raise ValueError("candidate may contain only one PRIMARY membership")
        ids = [
            self.primary_membership.evidence_id,
            *[m.evidence_id for m in self.additional_memberships],
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate evidence memberships must be unique")
        return self


class IncidentQualificationReceipt(StrictIncidentModel):
    outcome: Literal["created", "existing", "enriched", "evidence_only"]
    incident_id: uuid.UUID | None
    incident: IncidentRecordResponse | None
    reason: str = Field(min_length=1, max_length=200)


class Incident(EvidenceBase):
    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("grouping_key_sha256", name="uq_incidents_grouping_key"),
        CheckConstraint(
            "category IN ('ASSET_IDENTITY_ANOMALY', 'COMMUNICATION_POLICY_VIOLATION', "
            "'CONTROL_COMMAND_INVESTIGATION', 'PROCESS_INCONSISTENCY')",
            name="ck_incidents_category",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'INVESTIGATING', 'RESOLVED')", name="ck_incidents_status"
        ),
        CheckConstraint("severity IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_incidents_severity"),
        CheckConstraint(
            "disposition IN ('UNREVIEWED', 'TRUE_POSITIVE', 'FALSE_POSITIVE')",
            name="ck_incidents_disposition",
        ),
        CheckConstraint("version >= 1", name="ck_incidents_version"),
        CheckConstraint("evidence_count >= 1", name="ck_incidents_evidence_count"),
        CheckConstraint("ground_truth_used = false", name="ck_incidents_no_ground_truth"),
        CheckConstraint(
            "malicious_intent_inferred = false", name="ck_incidents_no_malicious_intent"
        ),
        CheckConstraint("causality_inferred = false", name="ck_incidents_no_causality"),
        Index("ix_incidents_list_order", "last_observed_at", "incident_id"),
        Index("ix_incidents_status_order", "status", "last_observed_at", "incident_id"),
        Index("ix_incidents_category_order", "category", "last_observed_at", "incident_id"),
        Index("ix_incidents_severity_order", "severity", "last_observed_at", "incident_id"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    incident_schema: Mapped[str] = mapped_column(String(80), nullable=False)
    incident_schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    incident_profile_id: Mapped[str] = mapped_column(String(80), nullable=False)
    incident_profile_version: Mapped[str] = mapped_column(String(16), nullable=False)
    incident_profile_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    qualification_rule_id: Mapped[str] = mapped_column(String(80), nullable=False)
    qualification_rule_version: Mapped[str] = mapped_column(String(16), nullable=False)
    grouping_key_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(600), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT")
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disposition: Mapped[str] = mapped_column(
        String(24), nullable=False, default=IncidentDisposition.UNREVIEWED.value
    )
    disposition_reason: Mapped[str | None] = mapped_column(Text)
    disposition_set_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT")
    )
    disposition_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    primary_evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_records.evidence_id", ondelete="RESTRICT"),
        nullable=False,
    )
    primary_evidence_type: Mapped[str] = mapped_column(String(48), nullable=False)
    primary_evidence_schema: Mapped[str] = mapped_column(String(80), nullable=False)
    primary_evidence_schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    primary_evidence_integrity_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_asset_scope: Mapped[list[str]] = mapped_column(ARRAY(String(160)), nullable=False)
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    destination_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    controller_asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    process_asset_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid(as_uuid=True)), nullable=False
    )
    process_asset_keys: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False)
    target_point_ids: Mapped[list[str]] = mapped_column(ARRAY(String(80)), nullable=False)
    correlation_rule_id: Mapped[str | None] = mapped_column(String(80))
    correlation_rule_version: Mapped[str | None] = mapped_column(String(16))
    run_scope: Mapped[str] = mapped_column(String(160), nullable=False)
    configuration_scope: Mapped[str] = mapped_column(String(160), nullable=False)
    bound_simulation_id: Mapped[str | None] = mapped_column(String(80))
    bound_configuration_hash: Mapped[str | None] = mapped_column(String(64))
    s3_semantic_evidence_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    grouping_epoch_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_context: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_context: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_completeness: Mapped[str] = mapped_column(String(48), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ground_truth_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    malicious_intent_inferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    causality_inferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list[IncidentEvidenceMembership]] = relationship(back_populates="incident")
    timeline_entries: Mapped[list[IncidentTimelineEntry]] = relationship(back_populates="incident")
    status_history: Mapped[list[IncidentStatusHistory]] = relationship(back_populates="incident")
    severity_history: Mapped[list[IncidentSeverityHistory]] = relationship(
        back_populates="incident"
    )
    notes: Mapped[list[IncidentNote]] = relationship(back_populates="incident")
    audit_events: Mapped[list[IncidentAuditEvent]] = relationship(back_populates="incident")
    report: Mapped[IncidentReport | None] = relationship(back_populates="incident")


class IncidentEvidenceMembership(EvidenceBase):
    __tablename__ = "incident_evidence_memberships"
    __table_args__ = (
        UniqueConstraint("incident_id", "evidence_id", name="uq_incident_evidence_membership"),
        CheckConstraint(
            "role IN ('PRIMARY', 'SUPPORTING', 'CONTRADICTING', 'CONTEXT')",
            name="ck_incident_membership_role",
        ),
    )

    membership_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_records.evidence_id", ondelete="RESTRICT"),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(48), nullable=False)
    evidence_schema: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    integrity_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    incident: Mapped[Incident] = relationship(back_populates="memberships")


class IncidentTimelineEntry(EvidenceBase):
    __tablename__ = "incident_timeline_entries"
    __table_args__ = (
        UniqueConstraint(
            "incident_id", "entry_type", "reference_id", name="uq_incident_timeline_reference"
        ),
        CheckConstraint(
            "entry_type IN ('INCIDENT_CREATED', 'EVIDENCE_ADDED', 'STATUS_CHANGED', "
            "'SEVERITY_CHANGED', 'ANALYST_NOTE_ADDED')",
            name="ck_incident_timeline_type",
        ),
        Index(
            "ix_incident_timeline_semantic_order", "incident_id", "observed_at", "timeline_entry_id"
        ),
    )

    timeline_entry_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False
    )
    timeline_schema: Mapped[str] = mapped_column(String(80), nullable=False)
    timeline_schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    producer: Mapped[str] = mapped_column(String(80), nullable=False)
    producer_version: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    evidence_type: Mapped[str | None] = mapped_column(String(48))
    evidence_schema: Mapped[str | None] = mapped_column(String(80))
    evidence_schema_version: Mapped[str | None] = mapped_column(String(16))
    evidence_integrity_sha256: Mapped[str | None] = mapped_column(String(64))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    asset_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid(as_uuid=True)), nullable=False)
    process_asset_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(Uuid(as_uuid=True)), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    actor_context: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    incident: Mapped[Incident] = relationship(back_populates="timeline_entries")


class IncidentStatusHistory(EvidenceBase):
    __tablename__ = "incident_status_history"

    status_history_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False
    )
    previous_status: Mapped[str | None] = mapped_column(String(24))
    new_status: Mapped[str] = mapped_column(String(24), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_context: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT")
    )
    reason: Mapped[str | None] = mapped_column(String(500))
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version_before: Mapped[int] = mapped_column(Integer, nullable=False)
    version_after: Mapped[int] = mapped_column(Integer, nullable=False)
    incident: Mapped[Incident] = relationship(back_populates="status_history")


class IncidentSeverityHistory(EvidenceBase):
    __tablename__ = "incident_severity_history"

    severity_history_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False
    )
    previous_severity: Mapped[str | None] = mapped_column(String(16))
    new_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    triggering_evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_records.evidence_id", ondelete="RESTRICT"),
        nullable=False,
    )
    triggering_integrity_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_version: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(16), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    incident: Mapped[Incident] = relationship(back_populates="severity_history")


class IncidentNote(EvidenceBase):
    __tablename__ = "incident_notes"

    note_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    actor_context: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT")
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    incident: Mapped[Incident] = relationship(back_populates="notes")


class IncidentAuditEvent(EvidenceBase):
    __tablename__ = "incident_audit_events"

    audit_event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_context: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT")
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    safe_reason: Mapped[str | None] = mapped_column(String(300))
    version_before: Mapped[int] = mapped_column(Integer, nullable=False)
    version_after: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    incident: Mapped[Incident] = relationship(back_populates="audit_events")


class IncidentReport(EvidenceBase):
    __tablename__ = "incident_reports"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    investigation_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    analyst_assessment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_assessment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    process_impact_assessment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    disposition_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommended_follow_up: Mapped[str] = mapped_column(Text, nullable=False, default="")
    final_conclusion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    incident: Mapped[Incident] = relationship(back_populates="report")


class IncidentReportRevision(EvidenceBase):
    __tablename__ = "incident_report_revisions"
    __table_args__ = (
        UniqueConstraint("incident_id", "version", name="uq_incident_report_revision"),
        CheckConstraint("version >= 1", name="ck_incident_report_revision_version"),
    )

    revision_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT"), nullable=False
    )
    investigation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    analyst_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    process_impact_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    disposition_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_follow_up: Mapped[str] = mapped_column(Text, nullable=False)
    final_conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    saved_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT"), nullable=False
    )
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IncidentRecordResponse(StrictIncidentModel):
    incident_id: uuid.UUID
    run_id: uuid.UUID | None = None
    scenario_id: Literal["BASELINE", "S1", "S2", "S3", "S4"] | None = None
    incident_schema: Literal["otsoc.incident.record"]
    incident_schema_version: Literal["1.0.0"]
    incident_profile_id: Literal["otsoc.incident.oil_gas_transfer"]
    incident_profile_version: Literal["1.0.0"]
    incident_profile_sha256: Sha256
    qualification_rule_id: str
    qualification_rule_version: Literal["1.0.0"]
    grouping_key_sha256: Sha256
    category: IncidentCategory
    title: str
    summary: str
    status: IncidentStatus
    severity: IncidentSeverity
    assignee_user_id: uuid.UUID | None
    assignee_display_name: str | None = None
    assigned_at: datetime | None
    disposition: IncidentDisposition
    disposition_reason: str | None
    disposition_set_by_user_id: uuid.UUID | None
    disposition_set_at: datetime | None
    primary_evidence_id: uuid.UUID
    primary_evidence_type: str
    primary_evidence_schema: str
    primary_evidence_schema_version: str
    primary_evidence_integrity_sha256: Sha256
    source_asset_id: uuid.UUID | None
    destination_asset_id: uuid.UUID | None
    controller_asset_id: uuid.UUID | None
    process_asset_ids: tuple[uuid.UUID, ...]
    process_asset_keys: tuple[str, ...]
    target_point_ids: tuple[str, ...]
    correlation_rule_id: str | None
    correlation_rule_version: str | None
    run_scope: str
    configuration_scope: str
    bound_simulation_id: str | None
    bound_configuration_hash: str | None
    s3_semantic_evidence_id: uuid.UUID | None
    grouping_epoch_start: datetime
    first_observed_at: datetime
    last_observed_at: datetime
    policy_context: str
    correlation_context: str
    evidence_completeness: str
    version: int
    evidence_count: int
    ground_truth_used: Literal[False]
    malicious_intent_inferred: Literal[False]
    causality_inferred: Literal[False]
    created_at: datetime
    updated_at: datetime
