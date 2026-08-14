from __future__ import annotations

from app.context.inventory import LoadedInventory
from app.context.models import AssetResolution, ResolutionStatus, ZoneDefinition


def resolve_zone(
    resolution: AssetResolution, loaded_inventory: LoadedInventory
) -> ZoneDefinition | None:
    if resolution.status is not ResolutionStatus.RESOLVED or resolution.zone_id is None:
        return None
    return loaded_inventory.zones.get(resolution.zone_id.value)
