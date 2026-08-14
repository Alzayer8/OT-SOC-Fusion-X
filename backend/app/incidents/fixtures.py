from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "events" / "phase-7b-incidents"
MANIFEST_FILENAME = "manifest.json"


class IncidentFixtureError(ValueError):
    pass


class StrictFixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, frozen=True)


class FixtureSetup(StrictFixtureModel):
    kind: Literal[
        "S1",
        "DUPLICATE",
        "S2",
        "S3_APPROVED_NOT_CORRELATED",
        "S3_DENIED_NOT_CORRELATED",
        "S3_APPROVED_CORRELATED",
        "S3_DENIED_CORRELATED",
        "S4_CORRELATED",
        "S4_NOT_CORRELATED",
        "S3_LATE_ENRICHMENT",
        "S4_DIFFERENT_RUN",
        "S4_DIFFERENT_CONFIGURATION",
        "TIMELINE_TIE",
        "INVALID_HASH",
        "UNRELATED_EVIDENCE",
        "CONCURRENT_DUPLICATE",
        "VALID_LIFECYCLE",
        "INVALID_LIFECYCLE",
        "ANALYST_NOTE",
        "GROUND_TRUTH_REJECTION",
    ]
    context_fixture: str | None = None
    correlation_fixture: str | None = None
    duplicate_of: str | None = None
    correlation_status: str | None = None
    mutate_simulation_id: str | None = None
    mutate_configuration_hash: str | None = None
    concurrent_attempts: int | None = Field(default=None, ge=1, le=16)
    transitions: tuple[str, ...] = ()
    note_text: str | None = Field(default=None, max_length=2_000)
    inject_forbidden_field: str | None = None


class FrozenIncidentFixture(StrictFixtureModel):
    catalog_id: str = Field(pattern=r"^P7B-F0(?:0[1-9]|1[0-9]|20)$")
    fixture_schema: Literal["otsoc.phase7b.incident_fixture"]
    fixture_schema_version: Literal["1.0.0"]
    profile_id: Literal["otsoc.incident.oil_gas_transfer"]
    profile_version: Literal["1.0.0"]
    setup: FixtureSetup
    expected_assertions: tuple[str, ...] = Field(min_length=1)
    educational_only: Literal[True]
    contains_ground_truth: Literal[False]


class ManifestEntry(StrictFixtureModel):
    catalog_id: str = Field(pattern=r"^P7B-F0(?:0[1-9]|1[0-9]|20)$")
    file: str = Field(pattern=r"^p7b-f0(?:0[1-9]|1[0-9]|20)\.json$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FixtureManifest(StrictFixtureModel):
    fixture_set_id: Literal["otsoc.phase7b.incidents"]
    fixture_set_version: Literal["1.0.0"]
    fixture_count: Literal[20]
    fixtures: tuple[ManifestEntry, ...] = Field(min_length=20, max_length=20)

    @model_validator(mode="after")
    def validate_catalog(self) -> FixtureManifest:
        expected = {f"P7B-F{number:03d}" for number in range(1, 21)}
        ids = {item.catalog_id for item in self.fixtures}
        files = {item.file for item in self.fixtures}
        if ids != expected or len(files) != 20:
            raise ValueError("fixture manifest must contain the exact P7B-F001 through F020 set")
        return self


@dataclass(frozen=True)
class VerifiedFixtureSet:
    manifest: FixtureManifest
    fixtures: tuple[FrozenIncidentFixture, ...]


def verify_fixture_set() -> VerifiedFixtureSet:
    manifest = _load_json_model(FIXTURE_ROOT / MANIFEST_FILENAME, FixtureManifest)
    fixtures: list[FrozenIncidentFixture] = []
    for entry in sorted(manifest.fixtures, key=lambda item: item.catalog_id):
        path = _safe_fixture_path(entry.file)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != entry.sha256:
            raise IncidentFixtureError("An incident fixture digest does not match its manifest.")
        fixture = _parse_model(content, FrozenIncidentFixture)
        if fixture.catalog_id != entry.catalog_id:
            raise IncidentFixtureError("An incident fixture ID does not match its manifest entry.")
        fixtures.append(fixture)
    return VerifiedFixtureSet(manifest=manifest, fixtures=tuple(fixtures))


def load_fixture(filename: str) -> tuple[FrozenIncidentFixture, bytes]:
    manifest = _load_json_model(FIXTURE_ROOT / MANIFEST_FILENAME, FixtureManifest)
    entry = next((item for item in manifest.fixtures if item.file == filename), None)
    if entry is None:
        raise IncidentFixtureError("The incident fixture is not listed in the manifest.")
    content = _safe_fixture_path(filename).read_bytes()
    if hashlib.sha256(content).hexdigest() != entry.sha256:
        raise IncidentFixtureError("The incident fixture digest does not match its manifest.")
    return _parse_model(content, FrozenIncidentFixture), content


def _safe_fixture_path(filename: str) -> Path:
    path = FIXTURE_ROOT / filename
    if path.is_symlink() or path.resolve().parent != FIXTURE_ROOT.resolve():
        raise IncidentFixtureError("The requested incident fixture path is unsafe.")
    return path


def _load_json_model[ModelType: BaseModel](path: Path, model: type[ModelType]) -> ModelType:
    if path.is_symlink() or path.resolve().parent != FIXTURE_ROOT.resolve():
        raise IncidentFixtureError("The incident fixture manifest path is unsafe.")
    return _parse_model(path.read_bytes(), model)


def _parse_model[ModelType: BaseModel](content: bytes, model: type[ModelType]) -> ModelType:
    if not content or len(content) > 32_768:
        raise IncidentFixtureError("An incident fixture exceeds the approved size bound.")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        return model.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise IncidentFixtureError("An incident fixture is invalid.") from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IncidentFixtureError("An incident fixture has a duplicate JSON key.")
        result[key] = value
    return result
