from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.context.canonical import canonical_inventory_bytes, sha256_hex
from app.context.models import (
    INVENTORY_PROFILE_ID,
    INVENTORY_PROFILE_VERSION,
    AssetDefinition,
    AssetInventoryProfile,
    IdentifierType,
    RelationshipDefinition,
    ZoneDefinition,
)
from app.protocols.profile import EXPECTED_PROFILE_SHA256 as EXPECTED_PROTOCOL_PROFILE_SHA256

MAX_PROFILE_BYTES = 65_536
PROFILE_ROOT = Path(__file__).resolve().parent / "profiles"
INVENTORY_FILENAME = "oil_gas_asset_inventory_v1.json"
EXPECTED_INVENTORY_SHA256 = "5b101619ae8fbb279c2b79938a09ab6fc4432712c0f8f03e5d3edead43edb01b"


class InventoryProfileError(ValueError):
    pass


@dataclass(frozen=True)
class LoadedInventory:
    profile: AssetInventoryProfile
    sha256: str

    @property
    def assets(self) -> dict[str, AssetDefinition]:
        return {asset.asset_key: asset for asset in self.profile.assets}

    @property
    def zones(self) -> dict[str, ZoneDefinition]:
        return {zone.zone_id.value: zone for zone in self.profile.zones}

    @property
    def identifier_index(self) -> dict[tuple[IdentifierType, str], AssetDefinition]:
        return {
            (identifier.identifier_type, identifier.value): asset
            for asset in self.profile.assets
            for identifier in asset.identifiers
        }

    @property
    def relationships(self) -> tuple[RelationshipDefinition, ...]:
        return self.profile.relationships


def load_inventory_profile(
    profile_id: str = INVENTORY_PROFILE_ID,
    profile_version: str = INVENTORY_PROFILE_VERSION,
    *,
    expected_sha256: str | None = None,
) -> LoadedInventory:
    if (profile_id, profile_version) != (INVENTORY_PROFILE_ID, INVENTORY_PROFILE_VERSION):
        raise InventoryProfileError("The requested inventory profile ID/version is not available.")
    path = PROFILE_ROOT / INVENTORY_FILENAME
    if path.is_symlink() or path.resolve().parent != PROFILE_ROOT.resolve():
        raise InventoryProfileError("The approved inventory profile path is unsafe.")
    loaded = parse_inventory_bytes(path.read_bytes())
    required = expected_sha256 or EXPECTED_INVENTORY_SHA256
    if required == "PENDING" or loaded.sha256 != required:
        raise InventoryProfileError(
            "The inventory profile digest does not match the approved digest."
        )
    return loaded


def parse_inventory_bytes(content: bytes) -> LoadedInventory:
    if not content or len(content) > MAX_PROFILE_BYTES:
        raise InventoryProfileError("The inventory profile exceeds the approved size bound.")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        profile = AssetInventoryProfile.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise InventoryProfileError("The inventory profile is invalid.") from exc
    if profile.protocol_profile_sha256 != EXPECTED_PROTOCOL_PROFILE_SHA256:
        raise InventoryProfileError("The inventory protocol-profile digest is not approved.")
    return LoadedInventory(profile=profile, sha256=sha256_hex(canonical_inventory_bytes(profile)))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InventoryProfileError("The inventory profile contains a duplicate JSON key.")
        result[key] = value
    return result
