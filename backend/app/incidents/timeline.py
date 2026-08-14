from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.incidents.models import (
    CandidateMembership,
    Incident,
    IncidentTimelineEntry,
    TimelineEntryType,
)

TIMELINE_ID_NAMESPACE = uuid.UUID("25563193-2d83-5cfb-a768-a8f482547086")
TIMELINE_SCHEMA = "otsoc.incident.timeline_entry"
TIMELINE_SCHEMA_VERSION = "1.0.0"


def append_timeline_entry(
    session: Session,
    incident: Incident,
    *,
    entry_type: TimelineEntryType,
    reference_id: uuid.UUID,
    observed_at: datetime,
    recorded_at: datetime,
    summary: str,
    actor_context: str,
    aggregate_version: int,
    membership: CandidateMembership | None = None,
) -> IncidentTimelineEntry:
    name = "|".join(
        (
            str(incident.incident_id),
            entry_type.value,
            str(reference_id),
            "1.0.0",
        )
    )
    assets = [
        item
        for item in (
            incident.source_asset_id,
            incident.destination_asset_id,
            incident.controller_asset_id,
        )
        if item is not None
    ]
    entry = IncidentTimelineEntry(
        timeline_entry_id=uuid.uuid5(TIMELINE_ID_NAMESPACE, name),
        incident_id=incident.incident_id,
        timeline_schema=TIMELINE_SCHEMA,
        timeline_schema_version=TIMELINE_SCHEMA_VERSION,
        producer="otsoc_offline_incident_engine",
        producer_version="1.0.0",
        observed_at=observed_at,
        recorded_at=recorded_at,
        entry_type=entry_type.value,
        reference_id=reference_id,
        evidence_id=membership.evidence_id if membership is not None else None,
        evidence_type=membership.evidence_type if membership is not None else None,
        evidence_schema=membership.evidence_schema if membership is not None else None,
        evidence_schema_version=(
            membership.evidence_schema_version if membership is not None else None
        ),
        evidence_integrity_sha256=(membership.integrity_sha256 if membership is not None else None),
        received_at=membership.received_at if membership is not None else None,
        asset_ids=sorted(set(assets), key=str),
        process_asset_ids=sorted(set(incident.process_asset_ids), key=str),
        summary=summary,
        actor_context=actor_context,
        aggregate_version=aggregate_version,
    )
    session.add(entry)
    return entry
