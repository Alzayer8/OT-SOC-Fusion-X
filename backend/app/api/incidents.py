from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.audit import append_soc_audit_event
from app.auth.dependencies import AuthPrincipal, require_mutation_permission, require_permission
from app.auth.models import LocalUser, Permission, SocAuditAction, SocAuditResult
from app.db.session import get_db_session
from app.incidents.lifecycle import IncidentLifecycleError, transition_incident_status
from app.incidents.models import Incident, IncidentStatus
from app.incidents.notes import (
    IncidentNoteError,
    IncidentVersionConflictError,
    add_analyst_note,
)
from app.incidents.repository import (
    IncidentCursorError,
    get_incident_detail,
    incident_response,
    list_incidents,
)
from app.incidents.schemas import (
    IncidentAssignmentPatchRequest,
    IncidentAuditListResponse,
    IncidentDetailResponse,
    IncidentDispositionPatchRequest,
    IncidentListFilters,
    IncidentListResponse,
    IncidentMutationResponse,
    IncidentNoteCreateRequest,
    IncidentReportFields,
    IncidentReportPutRequest,
    IncidentReportResponse,
    IncidentStatusPatchRequest,
)
from app.incidents.workflow import (
    IncidentWorkflowError,
    assign_incident,
    get_incident_report,
    list_incident_audit,
    save_incident_report,
    set_incident_disposition,
    validate_resolution_ready,
)

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])
DatabaseSession = Annotated[Session, Depends(get_db_session)]
ReadPrincipal = Annotated[AuthPrincipal, Depends(require_permission(Permission.READ_INCIDENT))]
StatusPrincipal = Annotated[
    AuthPrincipal,
    Depends(require_mutation_permission(Permission.CHANGE_INCIDENT_STATUS)),
]
NotePrincipal = Annotated[
    AuthPrincipal,
    Depends(require_mutation_permission(Permission.WRITE_INCIDENT_NOTE)),
]
AssignmentPrincipal = Annotated[
    AuthPrincipal,
    Depends(require_mutation_permission(Permission.ASSIGN_INCIDENT)),
]
DispositionPrincipal = Annotated[
    AuthPrincipal,
    Depends(require_mutation_permission(Permission.SET_INCIDENT_DISPOSITION)),
]
ReportPrincipal = Annotated[
    AuthPrincipal,
    Depends(require_mutation_permission(Permission.WRITE_INCIDENT_REPORT)),
]


@router.get("", response_model=IncidentListResponse)
def read_incident_list(
    session: DatabaseSession,
    actor: ReadPrincipal,
    scope: Literal["CURRENT", "ALL_HISTORY", "RUN"] = "CURRENT",
    run_id: uuid.UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    category: str | None = None,
    severity: str | None = None,
    asset_id: uuid.UUID | None = None,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
) -> IncidentListResponse:
    del actor
    try:
        filters = IncidentListFilters(
            status=status_filter,
            category=category,
            severity=severity,
            asset_id=asset_id,
            observed_from=observed_from,
            observed_to=observed_to,
        )
        return list_incidents(
            session,
            filters=filters,
            limit=limit,
            cursor=cursor,
            scope=scope,
            run_id=run_id,
        )
    except (ValidationError, IncidentCursorError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{incident_id}", response_model=IncidentDetailResponse)
def read_incident_detail(
    incident_id: uuid.UUID,
    session: DatabaseSession,
    actor: ReadPrincipal,
) -> IncidentDetailResponse:
    del actor
    detail = get_incident_detail(session, incident_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Incident was not found.")
    return detail


@router.patch("/{incident_id}/status", response_model=IncidentMutationResponse)
def patch_incident_status(
    incident_id: uuid.UUID,
    payload: IncidentStatusPatchRequest,
    request: Request,
    session: DatabaseSession,
    actor: StatusPrincipal,
) -> IncidentMutationResponse:
    warnings: tuple[str, ...] = ()
    if payload.new_status is IncidentStatus.RESOLVED:
        candidate = session.get(Incident, incident_id)
        if candidate is not None:
            try:
                validate_resolution_ready(session, candidate)
            except IncidentWorkflowError as exc:
                warnings = (
                    f"Resolution readiness warning: {exc} "
                    "Phase 7B lifecycle remains authoritative.",
                )
    try:
        incident = transition_incident_status(
            session,
            incident_id,
            new_status=payload.new_status,
            expected_version=payload.expected_version,
            actor_context=actor.user.display_name,
            actor_user_id=actor.user_id,
            reason=payload.reason,
            request_id=_request_id(request),
        )
    except IncidentVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IncidentLifecycleError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    append_soc_audit_event(
        session,
        action=SocAuditAction.INCIDENT_STATUS_CHANGED,
        result=SocAuditResult.ACCEPTED,
        request_id=_request_id(request),
        actor_user_id=actor.user_id,
        incident_id=incident_id,
        safe_reason="Authenticated incident lifecycle update.",
        details={"new_status": payload.new_status.value},
    )
    return IncidentMutationResponse(
        incident=_incident_response(session, incident),
        operation="status_changed",
        warnings=warnings,
    )


@router.post("/{incident_id}/notes", response_model=IncidentMutationResponse)
def create_incident_note(
    incident_id: uuid.UUID,
    payload: IncidentNoteCreateRequest,
    request: Request,
    session: DatabaseSession,
    actor: NotePrincipal,
) -> IncidentMutationResponse:
    try:
        incident = add_analyst_note(
            session,
            incident_id,
            content=payload.content,
            expected_version=payload.expected_version,
            actor_context=actor.user.display_name,
            actor_user_id=actor.user_id,
            request_id=_request_id(request),
        )
    except IncidentVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IncidentNoteError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    append_soc_audit_event(
        session,
        action=SocAuditAction.INCIDENT_NOTE_ADDED,
        result=SocAuditResult.ACCEPTED,
        request_id=_request_id(request),
        actor_user_id=actor.user_id,
        incident_id=incident_id,
        safe_reason="Bounded analyst note appended.",
        details={"aggregate_version": incident.version},
    )
    return IncidentMutationResponse(
        incident=_incident_response(session, incident), operation="note_added"
    )


@router.patch("/{incident_id}/assignment", response_model=IncidentMutationResponse)
def patch_incident_assignment(
    incident_id: uuid.UUID,
    payload: IncidentAssignmentPatchRequest,
    request: Request,
    session: DatabaseSession,
    actor: AssignmentPrincipal,
) -> IncidentMutationResponse:
    try:
        incident = assign_incident(
            session,
            incident_id,
            assignee_user_id=payload.assignee_user_id,
            expected_version=payload.expected_version,
            actor_user=actor.user,
            request_id=_request_id(request),
        )
    except IncidentVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IncidentWorkflowError as exc:
        code = 404 if "not found" in str(exc).lower() else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    append_soc_audit_event(
        session,
        action=SocAuditAction.INCIDENT_ASSIGNED,
        result=SocAuditResult.ACCEPTED,
        request_id=_request_id(request),
        actor_user_id=actor.user_id,
        subject_user_id=payload.assignee_user_id,
        incident_id=incident_id,
        safe_reason="Authenticated local incident assignment updated.",
        details={"assigned": payload.assignee_user_id is not None},
    )
    return IncidentMutationResponse(
        incident=_incident_response(session, incident), operation="assignment_changed"
    )


@router.patch("/{incident_id}/disposition", response_model=IncidentMutationResponse)
def patch_incident_disposition(
    incident_id: uuid.UUID,
    payload: IncidentDispositionPatchRequest,
    request: Request,
    session: DatabaseSession,
    actor: DispositionPrincipal,
) -> IncidentMutationResponse:
    try:
        incident = set_incident_disposition(
            session,
            incident_id,
            disposition=payload.disposition,
            reason=payload.reason,
            expected_version=payload.expected_version,
            actor_user=actor.user,
            request_id=_request_id(request),
        )
    except IncidentVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IncidentWorkflowError as exc:
        code = 404 if "not found" in str(exc).lower() else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    append_soc_audit_event(
        session,
        action=SocAuditAction.INCIDENT_DISPOSITION_CHANGED,
        result=SocAuditResult.ACCEPTED,
        request_id=_request_id(request),
        actor_user_id=actor.user_id,
        incident_id=incident_id,
        safe_reason="Analyst disposition recorded without changing evidence.",
        details={"disposition": payload.disposition.value},
    )
    return IncidentMutationResponse(
        incident=_incident_response(session, incident), operation="disposition_changed"
    )


@router.get("/{incident_id}/report", response_model=IncidentReportResponse)
def read_incident_report(
    incident_id: uuid.UUID,
    session: DatabaseSession,
    actor: ReadPrincipal,
) -> IncidentReportResponse:
    del actor
    try:
        return get_incident_report(session, incident_id)
    except IncidentWorkflowError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{incident_id}/report", response_model=IncidentReportResponse)
def put_incident_report(
    incident_id: uuid.UUID,
    payload: IncidentReportPutRequest,
    request: Request,
    session: DatabaseSession,
    actor: ReportPrincipal,
) -> IncidentReportResponse:
    fields = IncidentReportFields.model_validate(payload.model_dump(exclude={"expected_version"}))
    try:
        report = save_incident_report(
            session,
            incident_id,
            fields=fields,
            expected_version=payload.expected_version,
            actor_user=actor.user,
            request_id=_request_id(request),
        )
    except IncidentVersionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IncidentWorkflowError as exc:
        code = 404 if "not found" in str(exc).lower() else 422
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    append_soc_audit_event(
        session,
        action=SocAuditAction.INCIDENT_REPORT_SAVED,
        result=SocAuditResult.ACCEPTED,
        request_id=_request_id(request),
        actor_user_id=actor.user_id,
        incident_id=incident_id,
        safe_reason="Bounded plain-text incident report saved.",
        details={"report_version": report.version, "fields_filled": report.fields_filled},
    )
    return report


@router.get("/{incident_id}/audit", response_model=IncidentAuditListResponse)
def read_incident_audit(
    incident_id: uuid.UUID,
    session: DatabaseSession,
    actor: ReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> IncidentAuditListResponse:
    del actor
    try:
        return list_incident_audit(session, incident_id, limit=limit)
    except IncidentWorkflowError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _incident_response(session: Session, incident: Incident):  # type: ignore[no-untyped-def]
    assignee = (
        session.get(LocalUser, incident.assignee_user_id)
        if incident.assignee_user_id is not None
        else None
    )
    return incident_response(
        incident,
        assignee_display_name=assignee.display_name if assignee is not None else None,
    )


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unavailable")
