from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.context.canonical import sha256_hex
from app.context.fixtures import load_fixture as load_context_fixture
from app.context.fixtures import verify_fixture_set as verify_context_fixture_set
from app.context.inventory import EXPECTED_INVENTORY_SHA256, load_inventory_profile
from app.context.policy import EXPECTED_POLICY_SHA256, load_policy_profile
from app.correlation.fixtures import load_fixture as load_correlation_fixture
from app.correlation.fixtures import verify_fixture_set as verify_correlation_fixture_set
from app.correlation.profile import (
    EXPECTED_CORRELATION_PROFILE_SHA256,
    load_correlation_profile,
)
from app.incidents.profile import EXPECTED_INCIDENT_PROFILE_SHA256, load_incident_profile
from app.protocols.profile import EXPECTED_PROFILE_SHA256, load_profile

DATASET_ID = "otsoc.final-evaluation.oil-gas-transfer"
DATASET_VERSION = "1.0.0"
DATASET_SEED = 20260811
EXPECTED_DATASET_SHA256 = "aaa409d8af1461a33312d3e9c829b3f57755e18936555c80befabe6b77ba5d88"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = PROJECT_ROOT / "fixtures" / "evaluation" / "phase-9b" / "manifest.json"


class DatasetError(ValueError):
    pass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProfileReference(StrictModel):
    profile_id: str = Field(min_length=1, max_length=100)
    profile_version: Literal["1.0.0"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DatasetProfiles(StrictModel):
    protocol: ProfileReference
    inventory: ProfileReference
    policy: ProfileReference
    correlation: ProfileReference
    incident: ProfileReference


class FixtureReference(StrictModel):
    file: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9._-]+\.json$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RunConfiguration(StrictModel):
    configuration_id: str = Field(pattern=r"^otsoc-eval-v1-[a-z0-9-]+-config-001$")
    scenario: Literal["NORMAL_BACKGROUND", "S3_DENIED_CORRELATED", "S4_PROCESS_INCONSISTENCY"]
    seed: Literal[20260811]
    simulator_version: Literal["3.0.0"]
    process_model_version: Literal["3.6"]
    telemetry_schema_version: Literal["2.0.0"]


class DatasetCase(StrictModel):
    case_id: str = Field(pattern=r"^OTSOC-EVAL-V1-(?:BG|S[1-4])-001$")
    case_kind: Literal["BACKGROUND", "S1", "S2", "S3", "S4"]
    run_id: str | None
    configuration: RunConfiguration | None
    context_fixtures: tuple[FixtureReference, ...] = Field(max_length=2)
    correlation_fixture: FixtureReference | None

    @model_validator(mode="after")
    def validate_case_shape(self) -> DatasetCase:
        run_bound = self.case_kind in {"BACKGROUND", "S3", "S4"}
        if run_bound != (self.run_id is not None and self.configuration is not None):
            raise ValueError("run-bound cases require both run and configuration")
        if self.case_kind in {"BACKGROUND", "S3", "S4"}:
            if self.correlation_fixture is None:
                raise ValueError("run-bound cases require one correlation fixture")
        elif self.correlation_fixture is not None:
            raise ValueError("S1/S2 must not contain process correlation input")
        return self

    @property
    def configuration_hash(self) -> str | None:
        if self.configuration is None:
            return None
        content = json.dumps(
            self.configuration.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(content).hexdigest()


class DatasetManifest(StrictModel):
    dataset_id: Literal["otsoc.final-evaluation.oil-gas-transfer"]
    dataset_version: Literal["1.0.0"]
    display_id: Literal["OTSOC-FINAL-EVAL-V1"]
    seed: Literal[20260811]
    environment_classification: Literal["SYNTHETIC_OFFLINE_ADVISORY_ACADEMIC"]
    educational_only: Literal[True]
    contains_ground_truth: Literal[False]
    profiles: DatasetProfiles
    cases: tuple[DatasetCase, ...] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def validate_catalog(self) -> DatasetManifest:
        expected = {
            "OTSOC-EVAL-V1-BG-001": "BACKGROUND",
            "OTSOC-EVAL-V1-S1-001": "S1",
            "OTSOC-EVAL-V1-S2-001": "S2",
            "OTSOC-EVAL-V1-S3-001": "S3",
            "OTSOC-EVAL-V1-S4-001": "S4",
        }
        observed = {item.case_id: item.case_kind for item in self.cases}
        if observed != expected:
            raise ValueError("the frozen five-case catalog is incomplete")
        if [item.case_id for item in self.cases] != list(expected):
            raise ValueError("the frozen case order changed")
        return self

    def case(self, case_id: str) -> DatasetCase:
        return next(item for item in self.cases if item.case_id == case_id)


class LoadedDataset(StrictModel):
    manifest: DatasetManifest
    sha256: Literal["aaa409d8af1461a33312d3e9c829b3f57755e18936555c80befabe6b77ba5d88"]


def load_dataset() -> LoadedDataset:
    try:
        content = DATASET_PATH.read_bytes()
        if not content or len(content) > 65_536:
            raise DatasetError("the final dataset manifest exceeds its size bound")
        digest = hashlib.sha256(content).hexdigest()
        if digest != EXPECTED_DATASET_SHA256:
            raise DatasetError("the final dataset manifest digest is not approved")
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        manifest = DatasetManifest.model_validate(document)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, DatasetError):
            raise
        raise DatasetError("the final dataset manifest is invalid") from exc
    _verify_profiles(manifest.profiles)
    _verify_fixtures(manifest)
    return LoadedDataset(manifest=manifest, sha256=digest)


def _verify_profiles(profiles: DatasetProfiles) -> None:
    protocol = load_profile()
    inventory = load_inventory_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=protocol)
    correlation = load_correlation_profile(
        inventory=inventory,
        policy=policy,
        protocol_profile=protocol,
    )
    incident = load_incident_profile()
    expected = {
        "protocol": EXPECTED_PROFILE_SHA256,
        "inventory": EXPECTED_INVENTORY_SHA256,
        "policy": EXPECTED_POLICY_SHA256,
        "correlation": EXPECTED_CORRELATION_PROFILE_SHA256,
        "incident": EXPECTED_INCIDENT_PROFILE_SHA256,
    }
    observed = {
        "protocol": profiles.protocol.sha256,
        "inventory": profiles.inventory.sha256,
        "policy": profiles.policy.sha256,
        "correlation": profiles.correlation.sha256,
        "incident": profiles.incident.sha256,
    }
    loaded = {
        "protocol": protocol.sha256,
        "inventory": inventory.sha256,
        "policy": policy.sha256,
        "correlation": correlation.sha256,
        "incident": incident.sha256,
    }
    if observed != expected or loaded != expected:
        raise DatasetError("a frozen profile digest is inconsistent")


def _verify_fixtures(manifest: DatasetManifest) -> None:
    verify_context_fixture_set()
    correlation_profile = load_correlation_profile()
    verify_correlation_fixture_set(correlation_profile)
    for case in manifest.cases:
        for reference in case.context_fixtures:
            _, content = load_context_fixture(reference.file)
            if sha256_hex(content) != reference.sha256:
                raise DatasetError("a final context fixture digest is inconsistent")
        if case.correlation_fixture is not None:
            _, content = load_correlation_fixture(case.correlation_fixture.file)
            if sha256_hex(content) != case.correlation_fixture.sha256:
                raise DatasetError("a final correlation fixture digest is inconsistent")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DatasetError("the final dataset manifest contains a duplicate JSON key")
        result[key] = value
    return result
