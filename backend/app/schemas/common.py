from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetail(ApiModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(ApiModel):
    error: ErrorDetail
