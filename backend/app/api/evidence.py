from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthPrincipal, require_mutation_permission, require_permission
from app.auth.models import Permission
from app.db.session import get_db_session
from app.evidence.schemas import (
    MAX_EVIDENCE_REQUEST_BYTES,
    EvidenceIngestionReceipt,
    EvidenceIngestRequest,
    EvidenceListResponse,
    EvidenceRecordResponse,
)
from app.evidence.service import (
    EvidenceCursorError,
    EvidenceIdentityConflictError,
    EvidencePayloadTooLargeError,
    EvidenceSourceNotFoundError,
    get_evidence,
    ingest_evidence,
    list_evidence,
)

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])
DatabaseSession = Annotated[Session, Depends(get_db_session)]
EvidenceReadPrincipal = Annotated[
    AuthPrincipal, Depends(require_permission(Permission.READ_EVIDENCE))
]
EvidenceWritePrincipal = Annotated[
    AuthPrincipal,
    Depends(require_mutation_permission(Permission.MANAGE_SCENARIOS)),
]


def _enforce_request_size(request: Request) -> None:
    raw_length = request.headers.get("content-length")
    if raw_length is None:
        raise HTTPException(status_code=411, detail="Content-Length is required.")
    try:
        content_length = int(raw_length)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Content-Length is invalid.") from exc
    if content_length < 1 or content_length > MAX_EVIDENCE_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="Evidence request body exceeds the size limit.")


@router.post(
    "",
    response_model=EvidenceIngestionReceipt,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_201_CREATED: {"model": EvidenceIngestionReceipt}},
)
def create_evidence(
    payload: EvidenceIngestRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
    actor: EvidenceWritePrincipal,
) -> EvidenceIngestionReceipt:
    del actor
    _enforce_request_size(request)
    try:
        receipt = ingest_evidence(
            session,
            payload,
            request_id=getattr(request.state, "request_id", "unavailable"),
        )
    except EvidenceSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EvidencePayloadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except EvidenceIdentityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if receipt.status == "accepted":
        response.status_code = status.HTTP_201_CREATED
    return receipt


@router.get("/{evidence_id}", response_model=EvidenceRecordResponse)
def read_evidence(
    evidence_id: uuid.UUID,
    session: DatabaseSession,
    actor: EvidenceReadPrincipal,
) -> EvidenceRecordResponse:
    del actor
    record = get_evidence(session, evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence record was not found.")
    return record


@router.get("", response_model=EvidenceListResponse)
def read_evidence_list(
    session: DatabaseSession,
    actor: EvidenceReadPrincipal,
    scope: Literal["CURRENT", "ALL_HISTORY", "RUN"] = "CURRENT",
    run_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    evidence_type: Literal[
        "simulator_telemetry",
        "synthetic_protocol_event",
        "protocol_semantic_event",
        "asset_context_event",
        "communication_policy_finding",
        "correlation_finding",
    ]
    | None = None,
    source_key: Annotated[
        str | None,
        Query(min_length=3, max_length=64, pattern=r"^[a-z0-9][a-z0-9._-]+$"),
    ] = None,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
) -> EvidenceListResponse:
    del actor
    if cursor is not None and offset != 0:
        raise HTTPException(
            status_code=422, detail="Cursor and non-zero offset cannot be combined."
        )
    if (observed_from is None) != (observed_to is None):
        raise HTTPException(
            status_code=422, detail="Evidence time bounds must be supplied together."
        )
    if observed_from is not None and observed_to is not None:
        if observed_from > observed_to:
            raise HTTPException(
                status_code=422, detail="observed_from must not exceed observed_to."
            )
        if observed_to - observed_from > timedelta(days=31):
            raise HTTPException(
                status_code=422, detail="Evidence time range must not exceed 31 days."
            )
    try:
        return list_evidence(
            session,
            limit=limit,
            offset=offset,
            cursor=cursor,
            evidence_type=evidence_type,
            source_key=source_key,
            observed_from=observed_from,
            observed_to=observed_to,
            scope=scope,
            run_id=run_id,
        )
    except EvidenceCursorError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
