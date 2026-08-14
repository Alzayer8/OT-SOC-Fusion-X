from __future__ import annotations

import hashlib
import unicodedata
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.incidents.audit import append_audit_event
from app.incidents.models import (
    AuditAction,
    Incident,
    IncidentNote,
    TimelineEntryType,
)
from app.incidents.timeline import append_timeline_entry

NOTE_ID_NAMESPACE = uuid.UUID("a33ea2e2-d9fd-5d87-8b1f-d07334e1a5c6")


class IncidentNoteError(ValueError):
    pass


class IncidentVersionConflictError(ValueError):
    pass


def validate_note_text(content: str, *, maximum: int = 2_000) -> str:
    if not 1 <= len(content) <= maximum:
        raise IncidentNoteError(f"Note text must contain between 1 and {maximum} characters.")
    if "\x00" in content:
        raise IncidentNoteError("Note text must not contain NUL.")
    if any(unicodedata.category(char) == "Cc" and char not in "\n\t" for char in content):
        raise IncidentNoteError("Note text contains an unsafe control character.")
    return content


def add_analyst_note(
    session: Session,
    incident_id: uuid.UUID,
    *,
    content: str,
    expected_version: int,
    actor_context: str,
    actor_user_id: uuid.UUID | None = None,
    request_id: str,
    created_at: datetime | None = None,
) -> Incident:
    clean = validate_note_text(content)
    incident = session.scalar(
        select(Incident).where(Incident.incident_id == incident_id).with_for_update()
    )
    if incident is None:
        raise IncidentNoteError("Incident was not found.")
    if incident.version != expected_version:
        raise IncidentVersionConflictError("Incident aggregate version is stale.")
    now = created_at or datetime.now(UTC)
    before = incident.version
    after = before + 1
    content_digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()
    name = "|".join((str(incident_id), actor_context, content_digest, str(before)))
    note = IncidentNote(
        note_id=uuid.uuid5(NOTE_ID_NAMESPACE, name),
        incident_id=incident_id,
        content=clean,
        actor_context=actor_context,
        actor_user_id=actor_user_id,
        request_id=request_id,
        created_at=now,
        aggregate_version=after,
    )
    session.add(note)
    incident.version = after
    incident.updated_at = now
    append_timeline_entry(
        session,
        incident,
        entry_type=TimelineEntryType.ANALYST_NOTE_ADDED,
        reference_id=note.note_id,
        observed_at=now,
        recorded_at=now,
        summary="An analyst note was added to the investigation container.",
        actor_context=actor_context,
        aggregate_version=after,
    )
    append_audit_event(
        session,
        incident,
        action=AuditAction.ANALYST_NOTE_ADDED,
        occurred_at=now,
        actor_context=actor_context,
        actor_user_id=actor_user_id,
        request_id=request_id,
        result="ACCEPTED",
        safe_reason="Bounded analyst context appended.",
        version_before=before,
        version_after=after,
        details={"note_id": str(note.note_id)},
    )
    return incident
