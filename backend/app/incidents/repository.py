from __future__ import annotations

import base64
import html
import json
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Select, false, or_, select
from sqlalchemy.orm import Session

from app.auth.models import LocalUser
from app.evidence.models import EvidenceRecord
from app.incidents.models import (
    TIMELINE_ENTRY_ORDER,
    Incident,
    IncidentEvidenceMembership,
    IncidentNote,
    IncidentRecordResponse,
    IncidentSeverity,
    IncidentSeverityHistory,
    IncidentStatus,
    IncidentStatusHistory,
    IncidentTimelineEntry,
    TimelineEntryType,
)
from app.incidents.schemas import (
    IncidentContextResponse,
    IncidentDetailResponse,
    IncidentLineageReference,
    IncidentListFilters,
    IncidentListResponse,
    IncidentMembershipResponse,
    IncidentNoteResponse,
    IncidentSeverityHistoryResponse,
    IncidentStatusHistoryResponse,
    IncidentTimelineResponse,
)
from app.lab.models import LabActiveContext, LabRun, LabRunIncident


class IncidentCursorError(ValueError):
    pass


def incident_response(
    incident: Incident,
    *,
    assignee_display_name: str | None = None,
    run_id: uuid.UUID | None = None,
    scenario_id: str | None = None,
) -> IncidentRecordResponse:
    return IncidentRecordResponse(
        incident_id=incident.incident_id,
        run_id=run_id,
        scenario_id=scenario_id,
        incident_schema=incident.incident_schema,
        incident_schema_version=incident.incident_schema_version,
        incident_profile_id=incident.incident_profile_id,
        incident_profile_version=incident.incident_profile_version,
        incident_profile_sha256=incident.incident_profile_sha256,
        qualification_rule_id=incident.qualification_rule_id,
        qualification_rule_version=incident.qualification_rule_version,
        grouping_key_sha256=incident.grouping_key_sha256,
        category=incident.category,
        title=incident.title,
        summary=incident.summary,
        status=incident.status,
        severity=incident.severity,
        assignee_user_id=incident.assignee_user_id,
        assignee_display_name=assignee_display_name,
        assigned_at=incident.assigned_at,
        disposition=incident.disposition,
        disposition_reason=incident.disposition_reason,
        disposition_set_by_user_id=incident.disposition_set_by_user_id,
        disposition_set_at=incident.disposition_set_at,
        primary_evidence_id=incident.primary_evidence_id,
        primary_evidence_type=incident.primary_evidence_type,
        primary_evidence_schema=incident.primary_evidence_schema,
        primary_evidence_schema_version=incident.primary_evidence_schema_version,
        primary_evidence_integrity_sha256=incident.primary_evidence_integrity_sha256,
        source_asset_id=incident.source_asset_id,
        destination_asset_id=incident.destination_asset_id,
        controller_asset_id=incident.controller_asset_id,
        process_asset_ids=tuple(incident.process_asset_ids),
        process_asset_keys=tuple(incident.process_asset_keys),
        target_point_ids=tuple(incident.target_point_ids),
        correlation_rule_id=incident.correlation_rule_id,
        correlation_rule_version=incident.correlation_rule_version,
        run_scope=incident.run_scope,
        configuration_scope=incident.configuration_scope,
        bound_simulation_id=incident.bound_simulation_id,
        bound_configuration_hash=incident.bound_configuration_hash,
        s3_semantic_evidence_id=incident.s3_semantic_evidence_id,
        grouping_epoch_start=incident.grouping_epoch_start,
        first_observed_at=incident.first_observed_at,
        last_observed_at=incident.last_observed_at,
        policy_context=incident.policy_context,
        correlation_context=incident.correlation_context,
        evidence_completeness=incident.evidence_completeness,
        version=incident.version,
        evidence_count=incident.evidence_count,
        ground_truth_used=False,
        malicious_intent_inferred=False,
        causality_inferred=False,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


def get_incident_detail(session: Session, incident_id: uuid.UUID) -> IncidentDetailResponse | None:
    incident = session.get(Incident, incident_id)
    if incident is None:
        return None
    memberships = session.scalars(
        select(IncidentEvidenceMembership)
        .where(IncidentEvidenceMembership.incident_id == incident_id)
        .order_by(IncidentEvidenceMembership.role, IncidentEvidenceMembership.evidence_id)
    ).all()
    timeline = session.scalars(
        select(IncidentTimelineEntry).where(IncidentTimelineEntry.incident_id == incident_id)
    ).all()
    timeline = sorted(
        timeline,
        key=lambda item: (
            item.observed_at,
            TIMELINE_ENTRY_ORDER[TimelineEntryType(item.entry_type)],
            str(item.reference_id),
            str(item.timeline_entry_id),
        ),
    )
    status_history = session.scalars(
        select(IncidentStatusHistory)
        .where(IncidentStatusHistory.incident_id == incident_id)
        .order_by(IncidentStatusHistory.changed_at, IncidentStatusHistory.status_history_id)
    ).all()
    severity_history = session.scalars(
        select(IncidentSeverityHistory)
        .where(IncidentSeverityHistory.incident_id == incident_id)
        .order_by(
            IncidentSeverityHistory.calculated_at,
            IncidentSeverityHistory.severity_history_id,
        )
    ).all()
    notes = session.scalars(
        select(IncidentNote)
        .where(IncidentNote.incident_id == incident_id)
        .order_by(IncidentNote.created_at, IncidentNote.note_id)
    ).all()
    run_id, scenario_id = _incident_run_context(session, incident_id)
    return IncidentDetailResponse(
        incident=incident_response(
            incident,
            assignee_display_name=_assignee_display_name(session, incident),
            run_id=run_id,
            scenario_id=scenario_id,
        ),
        evidence_memberships=tuple(_membership_response(item) for item in memberships),
        lineage_references=_lineage_references(session, memberships),
        timeline=tuple(_timeline_response(item) for item in timeline),
        status_history=tuple(_status_history_response(item) for item in status_history),
        severity_history=tuple(_severity_history_response(item) for item in severity_history),
        notes=tuple(_note_response(item) for item in notes),
        context=IncidentContextResponse(
            policy=incident.policy_context,
            correlation=incident.correlation_context,
            evidence_completeness=incident.evidence_completeness,
            unavailable=tuple(
                label
                for label, value in (
                    ("source_asset", incident.source_asset_id),
                    ("destination_asset", incident.destination_asset_id),
                    (
                        "correlation",
                        None if incident.correlation_context == "UNAVAILABLE" else True,
                    ),
                    ("policy", None if incident.policy_context == "UNAVAILABLE" else True),
                )
                if value is None
            ),
        ),
    )


def list_incidents(
    session: Session,
    *,
    filters: IncidentListFilters,
    limit: int,
    cursor: str | None,
    scope: str = "CURRENT",
    run_id: uuid.UUID | None = None,
) -> IncidentListResponse:
    statement: Select[tuple[Incident]] = select(Incident)
    response_run_id: uuid.UUID | None = None
    response_scenario_id: str | None = None
    if scope not in {"CURRENT", "ALL_HISTORY", "RUN"}:
        raise IncidentCursorError("Incident scope is invalid.")
    if scope == "CURRENT":
        context = session.get(LabActiveContext, 1)
        if context is None:
            statement = statement.where(false())
        else:
            response_run_id = context.active_run_id
            run = session.get(LabRun, context.active_run_id)
            response_scenario_id = run.scenario_id if run is not None else None
            statement = statement.join(
                LabRunIncident, LabRunIncident.incident_id == Incident.incident_id
            ).where(LabRunIncident.run_id == context.active_run_id)
    elif scope == "RUN":
        if run_id is None:
            raise IncidentCursorError("run_id is required for RUN incident scope.")
        run = session.get(LabRun, run_id)
        if run is None:
            raise IncidentCursorError("The requested synthetic run was not found.")
        response_run_id = run_id
        response_scenario_id = run.scenario_id
        statement = statement.join(
            LabRunIncident, LabRunIncident.incident_id == Incident.incident_id
        ).where(LabRunIncident.run_id == run_id)
    elif run_id is not None:
        raise IncidentCursorError("run_id may only be used with RUN incident scope.")
    if filters.status is not None:
        statement = statement.where(Incident.status == filters.status.value)
    if filters.category is not None:
        statement = statement.where(Incident.category == filters.category.value)
    if filters.severity is not None:
        statement = statement.where(Incident.severity == filters.severity.value)
    if filters.asset_id is not None:
        statement = statement.where(
            or_(
                Incident.source_asset_id == filters.asset_id,
                Incident.destination_asset_id == filters.asset_id,
                Incident.controller_asset_id == filters.asset_id,
                Incident.process_asset_ids.contains([filters.asset_id]),
            )
        )
    if filters.observed_from is not None and filters.observed_to is not None:
        statement = statement.where(
            Incident.last_observed_at >= filters.observed_from,
            Incident.last_observed_at <= filters.observed_to,
        )
    if cursor is not None:
        cursor_time, cursor_id = decode_cursor(cursor)
        statement = statement.where(
            or_(
                Incident.last_observed_at < cursor_time,
                ((Incident.last_observed_at == cursor_time) & (Incident.incident_id > cursor_id)),
            )
        )
    rows = session.scalars(
        statement.order_by(Incident.last_observed_at.desc(), Incident.incident_id.asc()).limit(
            limit + 1
        )
    ).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = encode_cursor(page[-1]) if has_more and page else None
    return IncidentListResponse(
        items=tuple(
            incident_response(
                item,
                assignee_display_name=_assignee_display_name(session, item),
                run_id=response_run_id,
                scenario_id=response_scenario_id,
            )
            for item in page
        ),
        limit=limit,
        next_cursor=next_cursor,
    )


def _assignee_display_name(session: Session, incident: Incident) -> str | None:
    if incident.assignee_user_id is None:
        return None
    assignee = session.get(LocalUser, incident.assignee_user_id)
    return assignee.display_name if assignee is not None else None


def _incident_run_context(
    session: Session, incident_id: uuid.UUID
) -> tuple[uuid.UUID | None, str | None]:
    context = session.get(LabActiveContext, 1)
    if context is not None:
        current = session.scalar(
            select(LabRun)
            .join(LabRunIncident, LabRunIncident.run_id == LabRun.run_id)
            .where(
                LabRun.run_id == context.active_run_id,
                LabRunIncident.incident_id == incident_id,
            )
        )
        if current is not None:
            return current.run_id, current.scenario_id
    historical = session.scalar(
        select(LabRun)
        .join(LabRunIncident, LabRunIncident.run_id == LabRun.run_id)
        .where(LabRunIncident.incident_id == incident_id)
        .order_by(LabRun.started_at.desc(), LabRun.run_id)
        .limit(1)
    )
    if historical is None:
        return None, None
    return historical.run_id, historical.scenario_id


def encode_cursor(incident: Incident) -> str:
    document = json.dumps(
        {
            "last_observed_at": incident.last_observed_at.isoformat(),
            "incident_id": str(incident.incident_id),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(document).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    if not 1 <= len(cursor) <= 512:
        raise IncidentCursorError("Incident cursor is invalid.")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.b64decode(padded, altchars=b"-_", validate=True)
        document = json.loads(raw.decode("utf-8"))
        if set(document) != {"last_observed_at", "incident_id"}:
            raise ValueError
        parsed_time = TypeAdapter(datetime).validate_python(document["last_observed_at"])
        if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
            raise ValueError
        return parsed_time, uuid.UUID(document["incident_id"])
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise IncidentCursorError("Incident cursor is invalid.") from exc


def _membership_response(item: IncidentEvidenceMembership) -> IncidentMembershipResponse:
    return IncidentMembershipResponse(
        membership_id=item.membership_id,
        evidence_id=item.evidence_id,
        evidence_type=item.evidence_type,
        evidence_schema=item.evidence_schema,
        evidence_schema_version=item.evidence_schema_version,
        integrity_sha256=item.integrity_sha256,
        role=item.role,
        observed_at=item.observed_at,
        received_at=item.received_at,
        added_at=item.added_at,
    )


def _timeline_response(item: IncidentTimelineEntry) -> IncidentTimelineResponse:
    return IncidentTimelineResponse(
        timeline_entry_id=item.timeline_entry_id,
        observed_at=item.observed_at,
        recorded_at=item.recorded_at,
        entry_type=item.entry_type,
        reference_id=item.reference_id,
        evidence_id=item.evidence_id,
        evidence_type=item.evidence_type,
        evidence_schema=item.evidence_schema,
        evidence_schema_version=item.evidence_schema_version,
        evidence_integrity_sha256=item.evidence_integrity_sha256,
        received_at=item.received_at,
        asset_ids=tuple(item.asset_ids),
        process_asset_ids=tuple(item.process_asset_ids),
        summary=item.summary,
        actor_context=item.actor_context,
        aggregate_version=item.aggregate_version,
    )


def _status_history_response(item: IncidentStatusHistory) -> IncidentStatusHistoryResponse:
    return IncidentStatusHistoryResponse(
        status_history_id=item.status_history_id,
        previous_status=IncidentStatus(item.previous_status) if item.previous_status else None,
        new_status=IncidentStatus(item.new_status),
        changed_at=item.changed_at,
        actor_context=item.actor_context,
        actor_user_id=item.actor_user_id,
        reason=item.reason,
        request_id=item.request_id,
        version_before=item.version_before,
        version_after=item.version_after,
    )


def _severity_history_response(item: IncidentSeverityHistory) -> IncidentSeverityHistoryResponse:
    return IncidentSeverityHistoryResponse(
        severity_history_id=item.severity_history_id,
        previous_severity=(
            IncidentSeverity(item.previous_severity) if item.previous_severity else None
        ),
        new_severity=IncidentSeverity(item.new_severity),
        triggering_evidence_id=item.triggering_evidence_id,
        triggering_integrity_sha256=item.triggering_integrity_sha256,
        profile_version=item.profile_version,
        rule_version=item.rule_version,
        calculated_at=item.calculated_at,
        aggregate_version=item.aggregate_version,
    )


def _note_response(item: IncidentNote) -> IncidentNoteResponse:
    return IncidentNoteResponse(
        note_id=item.note_id,
        content=html.escape(item.content, quote=True),
        actor_context=item.actor_context,
        actor_user_id=item.actor_user_id,
        created_at=item.created_at,
        aggregate_version=item.aggregate_version,
    )


def _lineage_references(
    session: Session,
    memberships: Sequence[IncidentEvidenceMembership],
) -> tuple[IncidentLineageReference, ...]:
    references: dict[uuid.UUID, IncidentLineageReference] = {}
    records = session.scalars(
        select(EvidenceRecord).where(
            EvidenceRecord.evidence_id.in_([item.evidence_id for item in memberships])
        )
    ).all()
    for membership in memberships:
        references[membership.evidence_id] = IncidentLineageReference(
            evidence_id=membership.evidence_id,
            evidence_type=membership.evidence_type,
            integrity_sha256=membership.integrity_sha256,
            relationship=f"INCIDENT_{membership.role}",
        )
    for record in records:
        payload = record.payload
        if record.evidence_type == "communication_policy_finding":
            _add_payload_reference(
                references,
                payload,
                "source_evidence_id",
                "source_evidence_integrity_sha256",
                "synthetic_protocol_event",
                "POLICY_RAW_PARENT",
            )
            _add_payload_reference(
                references,
                payload,
                "semantic_event_id",
                "semantic_evidence_integrity_sha256",
                "protocol_semantic_event",
                "POLICY_SEMANTIC_PARENT",
            )
        elif record.evidence_type == "correlation_finding":
            for key, hash_key, evidence_type, relationship in (
                (
                    "primary_cyber_evidence_id",
                    "primary_cyber_evidence_integrity_sha256",
                    "synthetic_protocol_event",
                    "CORRELATION_CYBER_PARENT",
                ),
                (
                    "semantic_evidence_id",
                    "semantic_evidence_integrity_sha256",
                    "protocol_semantic_event",
                    "CORRELATION_SEMANTIC_PARENT",
                ),
                (
                    "asset_context_evidence_id",
                    "asset_context_evidence_integrity_sha256",
                    "asset_context_event",
                    "CORRELATION_ASSET_PARENT",
                ),
                (
                    "policy_finding_evidence_id",
                    "policy_finding_evidence_integrity_sha256",
                    "communication_policy_finding",
                    "CORRELATION_POLICY_PARENT",
                ),
            ):
                _add_payload_reference(
                    references, payload, key, hash_key, evidence_type, relationship
                )
            for telemetry in payload.get("telemetry_parents", []):
                _add_reference(
                    references,
                    telemetry.get("evidence_id"),
                    telemetry.get("integrity_sha256"),
                    "simulator_telemetry",
                    "CORRELATION_TELEMETRY_PARENT",
                )
    return tuple(
        sorted(references.values(), key=lambda item: (item.evidence_type, str(item.evidence_id)))
    )


def _add_payload_reference(
    references: dict[uuid.UUID, IncidentLineageReference],
    payload: dict[str, Any],
    id_key: str,
    hash_key: str,
    evidence_type: str,
    relationship: str,
) -> None:
    _add_reference(
        references,
        payload.get(id_key),
        payload.get(hash_key),
        evidence_type,
        relationship,
    )


def _add_reference(
    references: dict[uuid.UUID, IncidentLineageReference],
    evidence_id: object,
    digest: object,
    evidence_type: str,
    relationship: str,
) -> None:
    if not isinstance(evidence_id, str) or not isinstance(digest, str):
        return
    try:
        parsed_id = uuid.UUID(evidence_id)
        item = IncidentLineageReference(
            evidence_id=parsed_id,
            evidence_type=evidence_type,
            integrity_sha256=digest,
            relationship=relationship,
        )
    except (ValueError, ValidationError):
        return
    references.setdefault(parsed_id, item)
