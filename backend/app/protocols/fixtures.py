from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.protocols.canonical import sha256_hex
from app.protocols.models import (
    PROFILE_ID,
    PROFILE_VERSION,
    InterpretationStatus,
    ReasonCode,
    SyntheticModbusEvent,
)
from app.protocols.profile import EXPECTED_PROFILE_SHA256

MAX_FIXTURE_BYTES = 8_192
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = PROJECT_ROOT / "fixtures" / "events" / "phase-4b-synthetic-modbus"
FIXTURE_FILES = frozenset(
    {
        "p4b-normal-read-flow.json",
        "p4b-normal-approved-write-pump.json",
        "p4b-s3-valve-command-25.json",
        "p4b-unknown-address.json",
        "p4b-unsupported-operation.json",
        "p4b-malformed-value.json",
        "p4b-out-of-range-value.json",
        "p4b-duplicate-evidence.json",
    }
)


class FixtureValidationError(ValueError):
    pass


class StrictFixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class FixtureManifestEntry(StrictFixtureModel):
    catalog_id: str = Field(min_length=1, max_length=80)
    file: str = Field(min_length=1, max_length=100)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(gt=0, le=MAX_FIXTURE_BYTES)
    event_id: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=120)
    expected_status: InterpretationStatus
    expected_reason: ReasonCode
    expected_point: str | None
    expected_value: str | None
    expected_statement: str = Field(min_length=1, max_length=240)
    classification: Literal["normal", "negative", "s3", "duplicate"]
    contains_ground_truth: Literal[False]


class FixtureManifest(StrictFixtureModel):
    fixture_set_id: Literal["otsoc.phase4b.synthetic_modbus"]
    fixture_set_version: Literal["1.0.0"]
    educational_only: Literal[True]
    generator: Literal["otsoc_static_fixture"]
    generator_version: Literal["1.0.0"]
    source_revision: Literal["phase-4b-contract-1.0.0"]
    profile_id: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    profile_version: Literal["1.0.0"]
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixtures: tuple[FixtureManifestEntry, ...] = Field(min_length=8, max_length=8)

    @model_validator(mode="after")
    def validate_catalog(self) -> FixtureManifest:
        if self.profile_id != PROFILE_ID or self.profile_version != PROFILE_VERSION:
            raise ValueError("fixture manifest profile identity is unsupported")
        if self.profile_sha256 != EXPECTED_PROFILE_SHA256:
            raise ValueError("fixture manifest profile digest is not approved")
        files = [item.file for item in self.fixtures]
        ids = [item.catalog_id for item in self.fixtures]
        if set(files) != FIXTURE_FILES or len(ids) != len(set(ids)):
            raise ValueError("fixture catalog is incomplete or contains duplicates")
        return self


def load_fixture(file_name: str) -> tuple[SyntheticModbusEvent, bytes]:
    if file_name not in FIXTURE_FILES:
        raise FixtureValidationError("The requested fixture is not allowlisted.")
    path = FIXTURE_ROOT / file_name
    if path.is_symlink() or path.resolve().parent != FIXTURE_ROOT.resolve():
        raise FixtureValidationError("The approved fixture path is unsafe.")
    content = path.read_bytes()
    if not content or len(content) > MAX_FIXTURE_BYTES:
        raise FixtureValidationError("The fixture exceeds the approved size bound.")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        event = SyntheticModbusEvent.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise FixtureValidationError("The fixture document is invalid.") from exc
    return event, content


def verify_fixture_set() -> FixtureManifest:
    manifest_path = FIXTURE_ROOT / "manifest.json"
    content = manifest_path.read_bytes()
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        manifest = FixtureManifest.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise FixtureValidationError("The fixture manifest is invalid.") from exc
    for item in manifest.fixtures:
        event, fixture_bytes = load_fixture(item.file)
        if len(fixture_bytes) != item.bytes or sha256_hex(fixture_bytes) != item.sha256:
            raise FixtureValidationError("A fixture byte length or digest does not match.")
        if event.fixture_id != item.event_id:
            raise FixtureValidationError("A fixture event identity does not match its manifest.")
    return manifest


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FixtureValidationError("The fixture contains a duplicate JSON key.")
        result[key] = value
    return result
