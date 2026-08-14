from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.incidents.models import AuditAction, Incident, IncidentAuditEvent

AUDIT_ID_NAMESPACE = uuid.UUID("69519277-aac3-59b8-a1bf-d81215fe17b8")


def append_audit_event(
    session: Session,
    incident: Incident,
    *,
    action: AuditAction,
    occurred_at: datetime,
    actor_context: str,
    actor_user_id: uuid.UUID | None = None,
    request_id: str,
    result: str,
    safe_reason: str | None,
    version_before: int,
    version_after: int,
    details: dict[str, Any] | None = None,
) -> IncidentAuditEvent:
    detail_values = details or {}
    detail_digest = hashlib.sha256(repr(sorted(detail_values.items())).encode("utf-8")).hexdigest()
    name = "|".join(
        (
            str(incident.incident_id),
            action.value,
            request_id,
            str(version_before),
            str(version_after),
            detail_digest,
        )
    )
    event = IncidentAuditEvent(
        audit_event_id=uuid.uuid5(AUDIT_ID_NAMESPACE, name),
        incident_id=incident.incident_id,
        action=action.value,
        occurred_at=occurred_at,
        actor_context=actor_context,
        actor_user_id=actor_user_id,
        request_id=request_id,
        result=result,
        safe_reason=safe_reason,
        version_before=version_before,
        version_after=version_after,
        details=detail_values,
    )
    session.add(event)
    return event
