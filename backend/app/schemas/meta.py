from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel


class ActiveProfileMetadata(ApiModel):
    profile_id: str
    version: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ActiveSchemaMetadata(ApiModel):
    schema_id: str
    version: str


class MetadataResponse(ApiModel):
    application_name: str
    application_version: str
    environment: str
    api_version: str
    operating_mode: Literal["SYNTHETIC_OFFLINE"]
    domain: Literal["oil_gas_transfer"]
    active_profiles: tuple[ActiveProfileMetadata, ...]
    active_schemas: tuple[ActiveSchemaMetadata, ...]
