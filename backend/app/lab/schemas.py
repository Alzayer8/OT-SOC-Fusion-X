from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.lab.catalog import LabScenarioId
from app.lab.models import LabActivationReason, LabRunState
from app.schemas.common import ApiModel


class LabScenarioCatalogItem(ApiModel):
    scenario_id: LabScenarioId
    title: str
    description: str
    dataset_case_id: str
    definition_version: Literal["1.0.0"]
    state: Literal["READY"] = "READY"
    synthetic: Literal[True]
    execution_mode: Literal["FROZEN_DETERMINISTIC_PIPELINE"]


class LabCatalogResponse(ApiModel):
    dataset_id: Literal["otsoc.final-evaluation.oil-gas-transfer"]
    dataset_version: Literal["1.0.0"]
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: tuple[LabScenarioCatalogItem, ...] = Field(min_length=5, max_length=5)


class LabRunStartRequest(ApiModel):
    scenario_id: LabScenarioId


class LabNoFieldsRequest(ApiModel):
    """Optional empty body contract for lab mutations that accept no controls."""


class LabRunResponse(ApiModel):
    run_id: uuid.UUID
    scenario_id: LabScenarioId
    scenario_title: str
    definition_version: Literal["1.0.0"]
    dataset_id: Literal["otsoc.final-evaluation.oil-gas-transfer"]
    dataset_version: Literal["1.0.0"]
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_case_id: str
    simulation_id: str | None
    configuration_id: str | None
    configuration_hash: str | None
    status: LabRunState
    started_by_user_id: uuid.UUID | None
    started_by: uuid.UUID | None
    started_by_display_name: str
    started_at: datetime
    completed_at: datetime | None
    window_start: datetime | None
    window_end: datetime | None
    evidence_count: int = Field(ge=0)
    incident_count: int = Field(ge=0)
    incident_ids: tuple[uuid.UUID, ...]
    failure_code: str | None


class LabRunListResponse(ApiModel):
    items: tuple[LabRunResponse, ...]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0, le=10_000)
    total: int = Field(ge=0)


class LabContextResponse(ApiModel):
    context_version: int = Field(ge=1)
    activation_reason: LabActivationReason
    changed_at: datetime
    changed_by_user_id: uuid.UUID | None
    changed_by_actor: str
    active_run: LabRunResponse


class LabStartResponse(ApiModel):
    active_run: LabRunResponse
    run: LabRunResponse
