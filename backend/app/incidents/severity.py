from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.incidents.audit import append_audit_event
from app.incidents.models import (
    AuditAction,
    CandidateMembership,
    Incident,
    IncidentSeverity,
    IncidentSeverityHistory,
    TimelineEntryType,
)
from app.incidents.timeline import append_timeline_entry

SEVERITY_HISTORY_ID_NAMESPACE = uuid.UUID("d22ac2cd-f1c4-5c4e-bcad-b54a4a222d99")
SEVERITY_RANK = {
    IncidentSeverity.LOW: 1,
    IncidentSeverity.MEDIUM: 2,
    IncidentSeverity.HIGH: 3,
}


def severity_increases(current: str, proposed: IncidentSeverity) -> bool:
    return SEVERITY_RANK[proposed] > SEVERITY_RANK[IncidentSeverity(current)]


def record_severity_escalation(
    session: Session,
    incident: Incident,
    *,
    proposed: IncidentSeverity,
    triggering_membership: CandidateMembership,
    calculated_at: datetime,
    request_id: str,
    version_before: int,
    version_after: int,
) -> IncidentSeverityHistory | None:
    if not severity_increases(incident.severity, proposed):
        return None
    previous = incident.severity
    name = "|".join(
        (
            str(incident.incident_id),
            previous,
            proposed.value,
            str(triggering_membership.evidence_id),
            str(version_after),
        )
    )
    history = IncidentSeverityHistory(
        severity_history_id=uuid.uuid5(SEVERITY_HISTORY_ID_NAMESPACE, name),
        incident_id=incident.incident_id,
        previous_severity=previous,
        new_severity=proposed.value,
        triggering_evidence_id=triggering_membership.evidence_id,
        triggering_integrity_sha256=triggering_membership.integrity_sha256,
        profile_version=incident.incident_profile_version,
        rule_version=incident.qualification_rule_version,
        calculated_at=calculated_at,
        aggregate_version=version_after,
    )
    session.add(history)
    incident.severity = proposed.value
    append_timeline_entry(
        session,
        incident,
        entry_type=TimelineEntryType.SEVERITY_CHANGED,
        reference_id=history.severity_history_id,
        observed_at=triggering_membership.observed_at,
        recorded_at=calculated_at,
        summary=f"Incident severity increased from {previous} to {proposed.value}.",
        actor_context="SYSTEM",
        aggregate_version=version_after,
    )
    append_audit_event(
        session,
        incident,
        action=AuditAction.SEVERITY_ESCALATED,
        occurred_at=calculated_at,
        actor_context="SYSTEM",
        request_id=request_id,
        result="ACCEPTED",
        safe_reason="Verified evidence increased investigation priority.",
        version_before=version_before,
        version_after=version_after,
        details={"previous": previous, "new": proposed.value},
    )
    return history
