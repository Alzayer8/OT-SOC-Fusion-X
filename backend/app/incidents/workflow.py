from __future__ import annotations

import hashlib
import unicodedata
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import LocalUser
from app.incidents.audit import append_audit_event
from app.incidents.models import (
    AuditAction,
    Incident,
    IncidentAuditEvent,
    IncidentDisposition,
    IncidentReport,
    IncidentReportRevision,
)
from app.incidents.notes import IncidentVersionConflictError
from app.incidents.schemas import (
    IncidentAuditListResponse,
    IncidentAuditResponse,
    IncidentReportAutoContext,
    IncidentReportFields,
    IncidentReportResponse,
)

REPORT_REVISION_NAMESPACE = uuid.UUID("9f74578a-a139-55c2-9c55-fb12c84bfbce")
REPORT_FIELD_NAMES = (
    "investigation_summary",
    "analyst_assessment",
    "evidence_assessment",
    "process_impact_assessment",
    "disposition_rationale",
    "recommended_follow_up",
    "final_conclusion",
)
ASSIGNABLE_ROLES = frozenset({"ADMIN", "SOC_ANALYST"})


class IncidentWorkflowError(ValueError):
    pass


def assign_incident(
    session: Session,
    incident_id: uuid.UUID,
    *,
    assignee_user_id: uuid.UUID | None,
    expected_version: int,
    actor_user: LocalUser,
    request_id: str,
    changed_at: datetime | None = None,
) -> Incident:
    incident = _locked_incident(session, incident_id, expected_version)
    assignee: LocalUser | None = None
    if assignee_user_id is not None:
        assignee = session.get(LocalUser, assignee_user_id)
        if assignee is None or not assignee.active or assignee.role not in ASSIGNABLE_ROLES:
            raise IncidentWorkflowError(
                "Assignee must be an active local analyst or administrator."
            )
    now = changed_at or datetime.now(UTC)
    before = incident.version
    previous = incident.assignee_user_id
    incident.assignee_user_id = assignee_user_id
    incident.assigned_at = now if assignee is not None else None
    incident.version = before + 1
    incident.updated_at = now
    append_audit_event(
        session,
        incident,
        action=AuditAction.ASSIGNMENT_CHANGED,
        occurred_at=now,
        actor_context=actor_user.display_name,
        actor_user_id=actor_user.user_id,
        request_id=request_id,
        result="ACCEPTED",
        safe_reason="Authenticated local assignment update.",
        version_before=before,
        version_after=incident.version,
        details={
            "previous_assignee_user_id": str(previous) if previous else None,
            "assignee_user_id": str(assignee_user_id) if assignee_user_id else None,
        },
    )
    return incident


def set_incident_disposition(
    session: Session,
    incident_id: uuid.UUID,
    *,
    disposition: IncidentDisposition,
    reason: str,
    expected_version: int,
    actor_user: LocalUser,
    request_id: str,
    changed_at: datetime | None = None,
) -> Incident:
    clean_reason = _bounded_plain_text(reason, maximum=2_000, allow_empty=False)
    incident = _locked_incident(session, incident_id, expected_version)
    now = changed_at or datetime.now(UTC)
    before = incident.version
    previous = incident.disposition
    incident.disposition = disposition.value
    incident.disposition_reason = clean_reason
    incident.disposition_set_by_user_id = actor_user.user_id
    incident.disposition_set_at = now
    incident.version = before + 1
    incident.updated_at = now
    append_audit_event(
        session,
        incident,
        action=AuditAction.DISPOSITION_CHANGED,
        occurred_at=now,
        actor_context=actor_user.display_name,
        actor_user_id=actor_user.user_id,
        request_id=request_id,
        result="ACCEPTED",
        safe_reason="Authenticated analyst disposition rationale recorded.",
        version_before=before,
        version_after=incident.version,
        details={"previous": previous, "new": disposition.value, "reason": clean_reason},
    )
    return incident


def get_incident_report(session: Session, incident_id: uuid.UUID) -> IncidentReportResponse:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise IncidentWorkflowError("Incident was not found.")
    return _report_response(incident, session.get(IncidentReport, incident_id))


def save_incident_report(
    session: Session,
    incident_id: uuid.UUID,
    *,
    fields: IncidentReportFields,
    expected_version: int,
    actor_user: LocalUser,
    request_id: str,
    saved_at: datetime | None = None,
) -> IncidentReportResponse:
    incident = session.scalar(
        select(Incident).where(Incident.incident_id == incident_id).with_for_update()
    )
    if incident is None:
        raise IncidentWorkflowError("Incident was not found.")
    clean = {
        name: _bounded_plain_text(getattr(fields, name), maximum=4_000, allow_empty=True)
        for name in REPORT_FIELD_NAMES
    }
    report = session.scalar(
        select(IncidentReport).where(IncidentReport.incident_id == incident_id).with_for_update()
    )
    current_version = 0 if report is None else report.version
    if current_version != expected_version:
        raise IncidentVersionConflictError("Incident report version is stale.")
    now = saved_at or datetime.now(UTC)
    next_version = current_version + 1
    if report is None:
        report = IncidentReport(
            incident_id=incident_id,
            version=next_version,
            created_by_user_id=actor_user.user_id,
            created_at=now,
            updated_by_user_id=actor_user.user_id,
            updated_at=now,
            **clean,
        )
        session.add(report)
    else:
        for name, value in clean.items():
            setattr(report, name, value)
        report.version = next_version
        report.updated_by_user_id = actor_user.user_id
        report.updated_at = now
    digest = hashlib.sha256(
        "\x1f".join(clean[name] for name in REPORT_FIELD_NAMES).encode("utf-8")
    ).hexdigest()
    revision = IncidentReportRevision(
        revision_id=uuid.uuid5(REPORT_REVISION_NAMESPACE, f"{incident_id}|{next_version}|{digest}"),
        incident_id=incident_id,
        version=next_version,
        saved_by_user_id=actor_user.user_id,
        saved_at=now,
        **clean,
    )
    session.add(revision)
    append_audit_event(
        session,
        incident,
        action=AuditAction.REPORT_SAVED,
        occurred_at=now,
        actor_context=actor_user.display_name,
        actor_user_id=actor_user.user_id,
        request_id=request_id,
        result="ACCEPTED",
        safe_reason="Bounded plain-text incident report saved.",
        version_before=incident.version,
        version_after=incident.version,
        details={"report_version": next_version, "fields_filled": _fields_filled(clean)},
    )
    session.flush()
    return _report_response(incident, report)


def validate_resolution_ready(session: Session, incident: Incident) -> None:
    if IncidentDisposition(incident.disposition) is IncidentDisposition.UNREVIEWED:
        raise IncidentWorkflowError("A reviewed analyst disposition is required before resolution.")
    report = session.get(IncidentReport, incident.incident_id)
    if report is None or not report.final_conclusion.strip():
        raise IncidentWorkflowError("A Final Conclusion is required before resolution.")


def list_incident_audit(
    session: Session, incident_id: uuid.UUID, *, limit: int = 100
) -> IncidentAuditListResponse:
    if session.get(Incident, incident_id) is None:
        raise IncidentWorkflowError("Incident was not found.")
    events = session.scalars(
        select(IncidentAuditEvent)
        .where(IncidentAuditEvent.incident_id == incident_id)
        .order_by(IncidentAuditEvent.occurred_at, IncidentAuditEvent.audit_event_id)
        .limit(limit)
    ).all()
    user_ids = {event.actor_user_id for event in events if event.actor_user_id is not None}
    users = {
        user.user_id: user
        for user in session.scalars(select(LocalUser).where(LocalUser.user_id.in_(user_ids))).all()
    }
    return IncidentAuditListResponse(
        items=tuple(
            IncidentAuditResponse(
                audit_id=event.audit_event_id,
                action=event.action,
                actor_user_id=event.actor_user_id,
                actor_display_name=(
                    users[event.actor_user_id].display_name
                    if event.actor_user_id in users
                    else event.actor_context
                ),
                occurred_at=event.occurred_at,
                summary=_audit_summary(event),
                result=event.result,
                request_id=event.request_id,
            )
            for event in events
        )
    )


def _locked_incident(session: Session, incident_id: uuid.UUID, expected_version: int) -> Incident:
    incident = session.scalar(
        select(Incident).where(Incident.incident_id == incident_id).with_for_update()
    )
    if incident is None:
        raise IncidentWorkflowError("Incident was not found.")
    if incident.version != expected_version:
        raise IncidentVersionConflictError("Incident aggregate version is stale.")
    return incident


def _bounded_plain_text(value: str, *, maximum: int, allow_empty: bool) -> str:
    if len(value) > maximum or (not allow_empty and not value.strip()):
        minimum = 0 if allow_empty else 1
        raise IncidentWorkflowError(
            f"Plain text must contain between {minimum} and {maximum} characters."
        )
    if "\x00" in value or any(
        unicodedata.category(char) == "Cc" and char not in "\n\t" for char in value
    ):
        raise IncidentWorkflowError("Plain text contains an unsafe control character.")
    return value


def _report_response(incident: Incident, report: IncidentReport | None) -> IncidentReportResponse:
    values = (
        {name: "" for name in REPORT_FIELD_NAMES}
        if report is None
        else {name: getattr(report, name) for name in REPORT_FIELD_NAMES}
    )
    affected = tuple(
        dict.fromkeys(
            [
                *incident.process_asset_keys,
                *([str(incident.source_asset_id)] if incident.source_asset_id is not None else []),
                *(
                    [str(incident.destination_asset_id)]
                    if incident.destination_asset_id is not None
                    else []
                ),
            ]
        )
    )
    return IncidentReportResponse(
        incident_id=incident.incident_id,
        version=0 if report is None else report.version,
        created_by_user_id=None if report is None else report.created_by_user_id,
        created_at=None if report is None else report.created_at,
        updated_by_user_id=None if report is None else report.updated_by_user_id,
        updated_at=None if report is None else report.updated_at,
        fields_filled=_fields_filled(values),
        auto_context=IncidentReportAutoContext(
            incident_id=incident.incident_id,
            category=incident.category,
            severity=incident.severity,
            status=incident.status,
            disposition=incident.disposition,
            assignee_user_id=incident.assignee_user_id,
            affected_assets=affected,
            first_observed_at=incident.first_observed_at,
            last_observed_at=incident.last_observed_at,
            evidence_count=incident.evidence_count,
            protocol_context=(
                f"{incident.primary_evidence_type}; targets: "
                + (", ".join(incident.target_point_ids) or "none")
            ),
            policy_context=incident.policy_context,
            correlation_context=incident.correlation_context,
            process_context=(
                ", ".join(incident.process_asset_keys)
                if incident.process_asset_keys
                else "No process asset context is available for this incident."
            ),
        ),
        **values,
    )


def _fields_filled(values: dict[str, str]) -> int:
    return sum(bool(values[name].strip()) for name in REPORT_FIELD_NAMES)


def _audit_summary(event: IncidentAuditEvent) -> str:
    reason = event.details.get("reason")
    if event.action in {
        AuditAction.STATUS_TRANSITIONED.value,
        AuditAction.DISPOSITION_CHANGED.value,
    } and isinstance(reason, str):
        return reason
    return event.safe_reason or event.action.replace("_", " ").title()
