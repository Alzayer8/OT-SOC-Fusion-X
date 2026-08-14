from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.context.canonical import sha256_hex
from app.context.models import (
    INVENTORY_PROFILE_VERSION,
    POLICY_PROFILE_VERSION,
    IdentityClaim,
    PolicyReasonCode,
    PolicyStatus,
    ResolutionStatus,
)
from app.protocols.models import SyntheticModbusEvent

MAX_FIXTURE_BYTES = 12_288
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = PROJECT_ROOT / "fixtures" / "events" / "phase-5b-asset-policy"
FIXTURE_FILES = frozenset(
    {
        "known_hmi_approved_read.json",
        "known_hmi_approved_pump_command.json",
        "s1_unknown_source_asset.json",
        "s2_it_to_controller.json",
        "s3_hmi_approved_valve_command.json",
        "s3_engineering_denied_valve_command.json",
        "unknown_destination.json",
        "identity_conflict.json",
        "unsupported_policy_profile_version.json",
        "duplicate_policy_evaluation.json",
    }
)


class ContextFixtureError(ValueError):
    pass


class StrictFixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, frozen=True)


class AssetPolicyFixture(StrictFixtureModel):
    fixture_set_id: Literal["otsoc.asset_policy.phase5b"]
    fixture_set_version: Literal["1.0.0"]
    fixture_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    inventory_profile_version: Literal["1.0.0"]
    policy_profile_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    source_identity_claims: tuple[IdentityClaim, ...] = Field(min_length=1, max_length=4)
    destination_identity_claims: tuple[IdentityClaim, ...] = Field(min_length=1, max_length=4)
    event: SyntheticModbusEvent

    @model_validator(mode="after")
    def validate_fixture_identity(self) -> AssetPolicyFixture:
        if self.inventory_profile_version != INVENTORY_PROFILE_VERSION:
            raise ValueError("fixture inventory version is unsupported")
        if self.event.fixture_id != self.fixture_id:
            raise ValueError("fixture ID does not match the nested protocol event")
        return self


class FixtureManifestEntry(StrictFixtureModel):
    catalog_id: str = Field(min_length=1, max_length=80)
    file: str = Field(min_length=1, max_length=100)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(gt=0, le=MAX_FIXTURE_BYTES)
    event_id: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=160)
    expected_source_resolution: ResolutionStatus
    expected_destination_resolution: ResolutionStatus
    expected_status: PolicyStatus
    expected_reason: PolicyReasonCode
    classification: Literal["normal", "s1", "s2", "s3", "negative", "duplicate"]
    contains_ground_truth: Literal[False]


class FixtureManifest(StrictFixtureModel):
    fixture_set_id: Literal["otsoc.asset_policy.phase5b"]
    fixture_set_version: Literal["1.0.0"]
    educational_only: Literal[True]
    inventory_profile_id: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    inventory_profile_version: Literal["1.0.0"]
    inventory_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_profile_id: Literal["otsoc.communication_policy.oil_gas_transfer"]
    policy_profile_version: Literal["1.0.0"]
    policy_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixtures: tuple[FixtureManifestEntry, ...] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def validate_manifest_catalog(self) -> FixtureManifest:
        files = [item.file for item in self.fixtures]
        ids = [item.catalog_id for item in self.fixtures]
        if set(files) != FIXTURE_FILES or len(ids) != len(set(ids)):
            raise ValueError("fixture manifest is incomplete or contains duplicates")
        if self.policy_profile_version != POLICY_PROFILE_VERSION:
            raise ValueError("fixture manifest policy version is unsupported")
        return self


def load_fixture(file_name: str) -> tuple[AssetPolicyFixture, bytes]:
    if file_name not in FIXTURE_FILES:
        raise ContextFixtureError("The requested Phase 5B fixture is not allowlisted.")
    path = FIXTURE_ROOT / file_name
    if path.is_symlink() or path.resolve().parent != FIXTURE_ROOT.resolve():
        raise ContextFixtureError("The approved Phase 5B fixture path is unsafe.")
    content = path.read_bytes()
    if not content or len(content) > MAX_FIXTURE_BYTES:
        raise ContextFixtureError("The Phase 5B fixture exceeds the approved size bound.")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        fixture = AssetPolicyFixture.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ContextFixtureError("The Phase 5B fixture document is invalid.") from exc
    return fixture, content


def verify_fixture_set() -> FixtureManifest:
    from app.context.inventory import EXPECTED_INVENTORY_SHA256
    from app.context.policy import EXPECTED_POLICY_SHA256

    content = (FIXTURE_ROOT / "manifest.json").read_bytes()
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        manifest = FixtureManifest.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ContextFixtureError("The Phase 5B fixture manifest is invalid.") from exc
    if (
        manifest.inventory_profile_sha256 != EXPECTED_INVENTORY_SHA256
        or manifest.policy_profile_sha256 != EXPECTED_POLICY_SHA256
    ):
        raise ContextFixtureError("The fixture manifest profile digest is not approved.")
    for item in manifest.fixtures:
        fixture, fixture_bytes = load_fixture(item.file)
        if len(fixture_bytes) != item.bytes or sha256_hex(fixture_bytes) != item.sha256:
            raise ContextFixtureError("A Phase 5B fixture byte length or digest does not match.")
        if fixture.event.fixture_id != item.event_id:
            raise ContextFixtureError("A Phase 5B event identity does not match its manifest.")
    return manifest


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContextFixtureError("The Phase 5B fixture contains a duplicate JSON key.")
        result[key] = value
    return result
