from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import AuthenticatedPrincipal
from app.context.inventory import load_inventory_profile
from app.context.policy import load_policy_profile
from app.core.config import Settings, get_settings
from app.correlation.profile import load_correlation_profile
from app.incidents.profile import load_incident_profile
from app.protocols.profile import load_profile
from app.schemas.meta import ActiveProfileMetadata, ActiveSchemaMetadata, MetadataResponse

router = APIRouter(prefix="/api/v1", tags=["metadata"])
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/meta", response_model=MetadataResponse)
def metadata(settings: SettingsDependency, actor: AuthenticatedPrincipal) -> MetadataResponse:
    del actor
    protocol = load_profile()
    inventory = load_inventory_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=protocol)
    correlation = load_correlation_profile(
        inventory=inventory,
        policy=policy,
        protocol_profile=protocol,
    )
    incident = load_incident_profile()
    return MetadataResponse(
        application_name=settings.app_name,
        application_version=settings.app_version,
        environment=settings.app_env,
        api_version=settings.api_version,
        operating_mode="SYNTHETIC_OFFLINE",
        domain="oil_gas_transfer",
        active_profiles=(
            ActiveProfileMetadata(
                profile_id=protocol.profile.profile_id,
                version=protocol.profile.profile_version,
                sha256=protocol.sha256,
            ),
            ActiveProfileMetadata(
                profile_id=inventory.profile.profile_id,
                version=inventory.profile.profile_version,
                sha256=inventory.sha256,
            ),
            ActiveProfileMetadata(
                profile_id=policy.profile.profile_id,
                version=policy.profile.profile_version,
                sha256=policy.sha256,
            ),
            ActiveProfileMetadata(
                profile_id=correlation.profile.profile_id,
                version=correlation.profile.profile_version,
                sha256=correlation.sha256,
            ),
            ActiveProfileMetadata(
                profile_id=incident.profile.profile_id,
                version=incident.profile.profile_version,
                sha256=incident.sha256,
            ),
        ),
        active_schemas=(
            ActiveSchemaMetadata(schema_id="otsoc.simulator.telemetry", version="2.0.0"),
            ActiveSchemaMetadata(schema_id="otsoc.synthetic_modbus.event", version="1.0.0"),
            ActiveSchemaMetadata(schema_id="otsoc.protocol.semantic_event", version="1.0.0"),
            ActiveSchemaMetadata(schema_id="otsoc.asset.context_event", version="1.0.0"),
            ActiveSchemaMetadata(schema_id="otsoc.communication_policy.finding", version="1.0.0"),
            ActiveSchemaMetadata(
                schema_id="otsoc.cyber_physical.correlation_finding", version="1.0.0"
            ),
            ActiveSchemaMetadata(schema_id="otsoc.incident.record", version="1.0.0"),
        ),
    )
