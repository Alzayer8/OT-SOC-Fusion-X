from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.incidents.audit import append_audit_event
from app.incidents.models import (
    AuditAction,
    Incident,
    IncidentStatus,
    IncidentStatusHistory,
    TimelineEntryType,
)
from app.incidents.notes import (
    IncidentNoteError,
    IncidentVersionConflictError,
    validate_note_text,
)
from app.incidents.timeline import append_timeline_entry

STATUS_HISTORY_ID_NAMESPACE = uuid.UUID("18131f2f-b42b-5c82-af12-ffb09581380e")
ALLOWED_TRANSITIONS = {
    (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING),
    (IncidentStatus.OPEN, IncidentStatus.RESOLVED),
    (IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED),
    (IncidentStatus.RESOLVED, IncidentStatus.INVESTIGATING),
}


class IncidentLifecycleError(ValueError):
    pass


def transition_incident_status(
    session: Session,
    incident_id: uuid.UUID,
    *,
    new_status: IncidentStatus,
    expected_version: int,
    actor_context: str,
    actor_user_id: uuid.UUID | None = None,
    reason: str | None,
    request_id: str,
    changed_at: datetime | None = None,
) -> Incident:
    incident = session.scalar(
        select(Incident).where(Incident.incident_id == incident_id).with_for_update()
    )
    if incident is None:
        raise IncidentLifecycleError("Incident was not found.")
    if incident.version != expected_version:
        raise IncidentVersionConflictError("Incident aggregate version is stale.")
    previous = IncidentStatus(incident.status)
    if (previous, new_status) not in ALLOWED_TRANSITIONS:
        raise IncidentLifecycleError("The requested incident status transition is not allowed.")
    requires_reason = new_status is IncidentStatus.RESOLVED or previous is IncidentStatus.RESOLVED
    try:
        clean_reason = validate_note_text(reason, maximum=500) if reason is not None else None
    except IncidentNoteError as exc:
        raise IncidentLifecycleError(str(exc)) from exc
    if requires_reason and clean_reason is None:
        raise IncidentLifecycleError("A resolution or reopen reason is required.")
    now = changed_at or datetime.now(UTC)
    before = incident.version
    after = before + 1
    name = "|".join(
        (str(incident_id), previous.value, new_status.value, actor_context, str(before))
    )
    history = IncidentStatusHistory(
        status_history_id=uuid.uuid5(STATUS_HISTORY_ID_NAMESPACE, name),
        incident_id=incident_id,
        previous_status=previous.value,
        new_status=new_status.value,
        changed_at=now,
        actor_context=actor_context,
        actor_user_id=actor_user_id,
        reason=clean_reason,
        request_id=request_id,
        version_before=before,
        version_after=after,
    )
    session.add(history)
    incident.status = new_status.value
    incident.version = after
    incident.updated_at = now
    append_timeline_entry(
        session,
        incident,
        entry_type=TimelineEntryType.STATUS_CHANGED,
        reference_id=history.status_history_id,
        observed_at=now,
        recorded_at=now,
        summary=f"Incident status changed from {previous.value} to {new_status.value}.",
        actor_context=actor_context,
        aggregate_version=after,
    )
    action = AuditAction.STATUS_TRANSITIONED
    append_audit_event(
        session,
        incident,
        action=action,
        occurred_at=now,
        actor_context=actor_context,
        actor_user_id=actor_user_id,
        request_id=request_id,
        result="ACCEPTED",
        safe_reason="Authenticated incident lifecycle reason recorded.",
        version_before=before,
        version_after=after,
        details={
            "previous": previous.value,
            "new": new_status.value,
            "reason": clean_reason,
        },
    )
    return incident
