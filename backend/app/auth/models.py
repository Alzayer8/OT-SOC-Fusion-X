from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.evidence.models import EvidenceBase


class Role(StrEnum):
    ADMIN = "ADMIN"
    SOC_ANALYST = "SOC_ANALYST"
    OT_ENGINEER = "OT_ENGINEER"
    READ_ONLY = "READ_ONLY"


class Permission(StrEnum):
    READ_PRODUCT = "product:read"
    READ_INCIDENT = "incident:read"
    READ_EVIDENCE = "evidence:read"
    READ_REPLAY = "replay:read"
    READ_REPORTS = "reports:read"
    WRITE_INCIDENT_NOTE = "incident:note:write"
    ASSIGN_INCIDENT = "incident:assign"
    CHANGE_INCIDENT_STATUS = "incident:status:write"
    SET_INCIDENT_DISPOSITION = "incident:disposition:write"
    WRITE_INCIDENT_REPORT = "incident:report:write"
    REVIEW_PLAYBOOK = "playbook:review"
    MANAGE_SCENARIOS = "scenario:manage"
    MANAGE_USERS = "users:manage"
    READ_GLOBAL_AUDIT = "audit:read"


_READ_PERMISSIONS = frozenset(
    {
        Permission.READ_PRODUCT,
        Permission.READ_INCIDENT,
        Permission.READ_EVIDENCE,
        Permission.READ_REPLAY,
        Permission.READ_REPORTS,
    }
)
_ANALYST_PERMISSIONS = frozenset(
    {
        Permission.WRITE_INCIDENT_NOTE,
        Permission.ASSIGN_INCIDENT,
        Permission.CHANGE_INCIDENT_STATUS,
        Permission.SET_INCIDENT_DISPOSITION,
        Permission.WRITE_INCIDENT_REPORT,
        Permission.REVIEW_PLAYBOOK,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.READ_ONLY: _READ_PERMISSIONS,
    Role.OT_ENGINEER: _READ_PERMISSIONS | {Permission.WRITE_INCIDENT_NOTE},
    Role.SOC_ANALYST: _READ_PERMISSIONS | _ANALYST_PERMISSIONS,
    Role.ADMIN: frozenset(Permission),
}


class SocAuditAction(StrEnum):
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    LOCAL_USER_CREATED = "LOCAL_USER_CREATED"
    LOCAL_USER_UPDATED = "LOCAL_USER_UPDATED"
    LOCAL_USER_PASSWORD_RESET = "LOCAL_USER_PASSWORD_RESET"
    INCIDENT_ASSIGNED = "INCIDENT_ASSIGNED"
    INCIDENT_STATUS_CHANGED = "INCIDENT_STATUS_CHANGED"
    INCIDENT_DISPOSITION_CHANGED = "INCIDENT_DISPOSITION_CHANGED"
    INCIDENT_NOTE_ADDED = "INCIDENT_NOTE_ADDED"
    INCIDENT_REPORT_SAVED = "INCIDENT_REPORT_SAVED"
    SCENARIO_STARTED = "SCENARIO_STARTED"
    SCENARIO_COMPLETED = "SCENARIO_COMPLETED"
    RETURNED_TO_BASELINE = "RETURNED_TO_BASELINE"
    LAB_RESET = "LAB_RESET"


class SocAuditResult(StrEnum):
    ACCEPTED = "ACCEPTED"
    DENIED = "DENIED"
    FAILED = "FAILED"


class LocalUser(EvidenceBase):
    __tablename__ = "local_users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'SOC_ANALYST', 'OT_ENGINEER', 'READ_ONLY')",
            name="ck_local_users_role",
        ),
        CheckConstraint("version >= 1", name="ck_local_users_version"),
        Index("ix_local_users_active_role", "active", "role", "username"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuthSession(EvidenceBase):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="ck_auth_sessions_expiry"),
        Index("ix_auth_sessions_user_expiry", "user_id", "expires_at"),
        Index("ix_auth_sessions_active_lookup", "token_digest", "revoked_at", "expires_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("local_users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SocAuditEvent(EvidenceBase):
    __tablename__ = "soc_audit_events"
    __table_args__ = (
        CheckConstraint(
            "result IN ('ACCEPTED', 'DENIED', 'FAILED')", name="ck_soc_audit_events_result"
        ),
        Index("ix_soc_audit_events_time", "occurred_at", "audit_event_id"),
        Index("ix_soc_audit_events_actor_time", "actor_user_id", "occurred_at"),
        Index("ix_soc_audit_events_incident_time", "incident_id", "occurred_at"),
        Index("ix_soc_audit_events_run_time", "scenario_run_id", "occurred_at"),
    )

    audit_event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT")
    )
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("local_users.user_id", ondelete="RESTRICT")
    )
    subject_label: Mapped[str | None] = mapped_column(String(80))
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("incidents.incident_id", ondelete="RESTRICT")
    )
    scenario_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lab_runs.run_id", ondelete="RESTRICT")
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    safe_reason: Mapped[str | None] = mapped_column(String(300))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
