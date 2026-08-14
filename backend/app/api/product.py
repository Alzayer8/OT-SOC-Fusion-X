from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthPrincipal, require_permission
from app.auth.models import Permission
from app.db.session import get_db_session
from app.product.schemas import (
    AssetCatalogResponse,
    AssetDetailResponse,
    OverviewSummaryResponse,
    ReplayBundleResponse,
    ReplayWindowRequest,
)
from app.product.service import (
    ProductNotFoundError,
    ProductReadError,
    asset_catalog,
    asset_detail,
    overview_summary,
    replay_for_correlation,
    replay_for_incident,
    replay_for_window,
)

router = APIRouter(prefix="/api/v1", tags=["product"])
DatabaseSession = Annotated[Session, Depends(get_db_session)]
ProductReadPrincipal = Annotated[
    AuthPrincipal, Depends(require_permission(Permission.READ_PRODUCT))
]
ReplayReadPrincipal = Annotated[AuthPrincipal, Depends(require_permission(Permission.READ_REPLAY))]


@router.get("/overview/summary", response_model=OverviewSummaryResponse)
def read_overview_summary(
    session: DatabaseSession, actor: ProductReadPrincipal
) -> OverviewSummaryResponse:
    del actor
    try:
        return overview_summary(session)
    except ProductReadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/assets", response_model=AssetCatalogResponse)
def read_asset_catalog(actor: ProductReadPrincipal) -> AssetCatalogResponse:
    del actor
    return asset_catalog()


@router.get("/assets/{asset_key}", response_model=AssetDetailResponse)
def read_asset_detail(
    asset_key: Annotated[
        str,
        Path(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
    ],
    actor: ProductReadPrincipal,
) -> AssetDetailResponse:
    del actor
    try:
        return asset_detail(asset_key)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/replay", response_model=ReplayBundleResponse)
def read_replay_bundle(
    session: DatabaseSession,
    actor: ReplayReadPrincipal,
    incident_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    correlation_evidence_id: uuid.UUID | None = None,
    simulation_id: Annotated[
        str | None,
        Query(min_length=5, max_length=80, pattern=r"^[a-zA-Z0-9._:-]+$"),
    ] = None,
    configuration_hash: Annotated[str | None, Query(pattern=r"^[0-9a-f]{64}$")] = None,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
    evidence_type: Annotated[list[str] | None, Query()] = None,
) -> ReplayBundleResponse:
    del actor
    window_values = (simulation_id, configuration_hash, observed_from, observed_to)
    has_window = any(value is not None for value in window_values) or evidence_type is not None
    source_count = (
        int(incident_id is not None) + int(correlation_evidence_id is not None) + int(has_window)
    )
    if source_count != 1:
        raise HTTPException(status_code=422, detail="Exactly one replay source is required.")
    if run_id is not None and incident_id is None:
        raise HTTPException(status_code=422, detail="run_id requires an incident replay source.")
    try:
        if incident_id is not None:
            return replay_for_incident(session, incident_id, run_id=run_id)
        if correlation_evidence_id is not None:
            return replay_for_correlation(session, correlation_evidence_id)
        request = ReplayWindowRequest(
            simulation_id=simulation_id,
            configuration_hash=configuration_hash,
            observed_from=observed_from,
            observed_to=observed_to,
            evidence_types=tuple(evidence_type or ()),
        )
        return replay_for_window(session, request)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProductReadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
