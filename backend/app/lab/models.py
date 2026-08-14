from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.evidence.models import EvidenceBase


class LabRunState(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LabEvidenceRole(StrEnum):
    ROOT = "ROOT"
    LINEAGE = "LINEAGE"


class LabActivationReason(StrEnum):
    STARTUP_BASELINE = "STARTUP_BASELINE"
    SCENARIO_COMPLETED = "SCENARIO_COMPLETED"
    RETURN_BASELINE = "RETURN_BASELINE"
    RESET = "RESET"


class LabRun(EvidenceBase):
    __tablename__ = "lab_runs"
    __table_args__ = (
        CheckConstraint(
            "scenario_id IN ('BASELINE', 'S1', 'S2', 'S3', 'S4')",
            name="ck_lab_runs_scenario",
        ),
        CheckConstraint(
            "state IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_lab_runs_state",
        ),
        CheckConstraint(
            "(state = 'RUNNING' AND completed_at IS NULL) OR "
            "(state IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)",
            name="ck_lab_runs_completion",
        ),
        CheckConstraint(
            "(state = 'FAILED' AND failure_code IS NOT NULL) OR "
            "(state != 'FAILED' AND failure_code IS NULL)",
            name="ck_lab_runs_failure",
        ),
        CheckConstraint(
            "evidence_observed_from IS NULL OR evidence_observed_to IS NULL OR "
            "evidence_observed_from <= evidence_observed_to",
            name="ck_lab_runs_evidence_window",
        ),
        Index(
            "uq_lab_runs_one_baseline",
            "scenario_id",
            unique=True,
            postgresql_where=text("scenario_id = 'BASELINE'"),
        ),
        Index(
            "uq_lab_runs_one_running",
            "state",
            unique=True,
            postgresql_where=text("state = 'RUNNING'"),
        ),
        Index("ix_lab_runs_history", text("started_at DESC"), "run_id"),
        Index("ix_lab_runs_scenario_history", "scenario_id", text("started_at DESC")),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(12), nullable=False)
    definition_version: Mapped[str] = mapped_column(String(16), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(100), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(16), nullable=False)
    dataset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_case_id: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_simulation_id: Mapped[str | None] = mapped_column(String(80))
    configuration_id: Mapped[str | None] = mapped_column(String(100))
    configuration_hash: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    started_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT")
    )
    started_by_actor: Mapped[str] = mapped_column(String(80), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_observed_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_observed_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LabRunEvidence(EvidenceBase):
    __tablename__ = "lab_run_evidence"
    __table_args__ = (
        CheckConstraint("role IN ('ROOT', 'LINEAGE')", name="ck_lab_run_evidence_role"),
        Index("ix_lab_run_evidence_evidence", "evidence_id", "run_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lab_runs.run_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evidence_records.evidence_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LabRunIncident(EvidenceBase):
    __tablename__ = "lab_run_incidents"
    __table_args__ = (Index("ix_lab_run_incidents_incident", "incident_id", "run_id"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lab_runs.run_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("incidents.incident_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LabActiveContext(EvidenceBase):
    __tablename__ = "lab_active_context"
    __table_args__ = (
        CheckConstraint("singleton_id = 1", name="ck_lab_active_context_singleton"),
        CheckConstraint("version >= 1", name="ck_lab_active_context_version"),
        CheckConstraint(
            "activation_reason IN ('STARTUP_BASELINE', 'SCENARIO_COMPLETED', "
            "'RETURN_BASELINE', 'RESET')",
            name="ck_lab_active_context_reason",
        ),
    )

    singleton_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    active_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lab_runs.run_id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT")
    )
    changed_by_actor: Mapped[str] = mapped_column(String(80), nullable=False)
    activation_reason: Mapped[str] = mapped_column(String(32), nullable=False)
