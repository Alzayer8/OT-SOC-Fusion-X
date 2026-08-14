from __future__ import annotations

from app.context.canonical import deterministic_asset_id
from app.context.inventory import LoadedInventory
from app.context.models import (
    AssetResolution,
    IdentityClaim,
    ResolutionStatus,
)


def resolve_identity(
    claims: tuple[IdentityClaim, ...], loaded_inventory: LoadedInventory
) -> AssetResolution:
    matches = [
        loaded_inventory.identifier_index.get((claim.identifier_type, claim.value))
        for claim in claims
    ]
    known = [asset for asset in matches if asset is not None]
    if not known:
        return _unresolved(ResolutionStatus.UNKNOWN)
    if len(known) != len(matches) or len({asset.asset_key for asset in known}) != 1:
        return _unresolved(ResolutionStatus.CONFLICT)
    asset = known[0]
    return AssetResolution(
        status=ResolutionStatus.RESOLVED,
        known_asset=True,
        enabled=asset.enabled,
        asset_id=deterministic_asset_id(
            inventory_profile_id=loaded_inventory.profile.profile_id,
            asset_key=asset.asset_key,
        ),
        asset_key=asset.asset_key,
        asset_kind=asset.asset_kind,
        asset_type=asset.asset_type,
        asset_role=asset.asset_role,
        zone_id=asset.zone_id,
        criticality=asset.criticality,
    )


def _unresolved(status: ResolutionStatus) -> AssetResolution:
    return AssetResolution(
        status=status,
        known_asset=False,
        enabled=None,
        asset_id=None,
        asset_key=None,
        asset_kind=None,
        asset_type=None,
        asset_role=None,
        zone_id=None,
        criticality=None,
    )
