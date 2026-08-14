from __future__ import annotations

from typing import Literal

from app.schemas.common import ApiModel


class LivenessResponse(ApiModel):
    status: Literal["ok"]
    service: str
    version: str


class ReadinessResponse(ApiModel):
    status: Literal["ready", "unavailable"]
    database: Literal["available", "unavailable"]
