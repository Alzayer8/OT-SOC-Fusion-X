from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    AuthenticatedPrincipal,
    AuthPrincipal,
    require_mutation_permission,
)
from app.auth.models import Permission
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.lab.catalog import LabScenarioId
from app.lab.models import LabRunState
from app.lab.schemas import (
    LabCatalogResponse,
    LabContextResponse,
    LabNoFieldsRequest,
    LabRunListResponse,
    LabRunResponse,
    LabRunStartRequest,
    LabStartResponse,
)
from app.lab.service import (
    LabError,
    LabIntegrityError,
    LabNotInitializedError,
    LabPipelineError,
    LabRunConflictError,
    LabRunNotFoundError,
    activate_baseline,
    list_run_history,
    read_catalog,
    read_current_context,
    read_run,
    reset_lab,
    start_scenario,
)

router = APIRouter(prefix="/api/v1/lab", tags=["scenario-lab"])
DatabaseSession = Annotated[Session, Depends(get_db_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
AdminPrincipal = Annotated[
    AuthPrincipal,
    Depends(require_mutation_permission(Permission.MANAGE_SCENARIOS)),
]


@router.get("/catalog", response_model=LabCatalogResponse)
def get_lab_catalog(actor: AuthenticatedPrincipal) -> LabCatalogResponse:
    del actor
    return read_catalog()


@router.get("/context", response_model=LabContextResponse)
def get_lab_context(
    session: DatabaseSession,
    actor: AuthenticatedPrincipal,
) -> LabContextResponse:
    del actor
    try:
        return read_current_context(session)
    except LabError as exc:
        raise _lab_http_error(exc) from exc


@router.get("/runs", response_model=LabRunListResponse)
def get_lab_runs(
    session: DatabaseSession,
    actor: AuthenticatedPrincipal,
    scenario_id: LabScenarioId | None = None,
    run_state: Annotated[LabRunState | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> LabRunListResponse:
    del actor
    return list_run_history(
        session,
        scenario_id=scenario_id,
        state=run_state,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=LabRunResponse)
def get_lab_run(
    run_id: uuid.UUID,
    session: DatabaseSession,
    actor: AuthenticatedPrincipal,
) -> LabRunResponse:
    del actor
    try:
        return read_run(session, run_id)
    except LabError as exc:
        raise _lab_http_error(exc) from exc


@router.post("/start", response_model=LabStartResponse)
def post_lab_start(
    payload: LabRunStartRequest,
    request: Request,
    settings: SettingsDependency,
    session: DatabaseSession,
    actor: AdminPrincipal,
) -> LabStartResponse:
    try:
        return start_scenario(
            settings,
            session,
            payload.scenario_id,
            actor_user_id=actor.user_id,
            actor_context=actor.user.display_name,
            request_id=_request_id(request),
        )
    except LabError as exc:
        raise _lab_http_error(exc) from exc


@router.post("/baseline", response_model=LabContextResponse)
def post_lab_baseline(
    request: Request,
    session: DatabaseSession,
    actor: AdminPrincipal,
    payload: Annotated[LabNoFieldsRequest | None, Body()] = None,
) -> LabContextResponse:
    del payload
    try:
        return activate_baseline(
            session,
            actor_user_id=actor.user_id,
            actor_context=actor.user.display_name,
            request_id=_request_id(request),
        )
    except LabError as exc:
        raise _lab_http_error(exc) from exc


@router.post("/reset", response_model=LabContextResponse)
def post_lab_reset(
    request: Request,
    session: DatabaseSession,
    actor: AdminPrincipal,
    payload: Annotated[LabNoFieldsRequest | None, Body()] = None,
) -> LabContextResponse:
    del payload
    try:
        return reset_lab(
            session,
            actor_user_id=actor.user_id,
            actor_context=actor.user.display_name,
            request_id=_request_id(request),
        )
    except LabError as exc:
        raise _lab_http_error(exc) from exc


def _request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and 8 <= len(value) <= 64:
        return value
    return "scenario-lab-request-unavailable"


def _lab_http_error(exc: LabError) -> HTTPException:
    if isinstance(exc, LabRunNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, LabRunConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(
        exc,
        (LabNotInitializedError, LabPipelineError, LabIntegrityError),
    ):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
