from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.db.health import database_is_ready
from app.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/live", response_model=LivenessResponse)
def liveness(settings: SettingsDependency) -> LivenessResponse:
    return LivenessResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness(settings: SettingsDependency) -> ReadinessResponse | JSONResponse:
    if database_is_ready(settings):
        return ReadinessResponse(status="ready", database="available")
    body = ReadinessResponse(status="unavailable", database="unavailable")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=body.model_dump(mode="json"),
    )
