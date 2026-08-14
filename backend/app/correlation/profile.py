from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.context.inventory import EXPECTED_INVENTORY_SHA256, LoadedInventory
from app.context.policy import EXPECTED_POLICY_SHA256, LoadedPolicy
from app.correlation.canonical import canonical_profile_bytes, sha256_hex
from app.correlation.models import (
    CORRELATION_PROFILE_ID,
    CORRELATION_PROFILE_VERSION,
    REASON_PRECEDENCE,
    CorrelationReasonCode,
    CorrelationStatus,
    PointId,
    SafeKey,
    SemVer,
    Sha256,
)
from app.protocols.profile import EXPECTED_PROFILE_SHA256 as EXPECTED_PROTOCOL_PROFILE_SHA256
from app.protocols.profile import LoadedProfile as LoadedProtocolProfile

MAX_PROFILE_BYTES = 65_536
PROFILE_ROOT = Path(__file__).resolve().parent / "profiles"
PROFILE_FILENAME = "oil_gas_correlation_v1.json"
EXPECTED_CORRELATION_PROFILE_SHA256 = (
    "bf0be174d58627da7ecf17ebde325d0aa5ad57a742b92df2ac524f46ae2856c2"
)


class CorrelationProfileError(ValueError):
    pass


class StrictProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False, frozen=True)


class DependencySet(StrictProfileModel):
    inventory_profile_id: Literal["otsoc.asset_inventory.oil_gas_transfer"]
    inventory_profile_version: Literal["1.0.0"]
    inventory_profile_sha256: Sha256
    policy_profile_id: Literal["otsoc.communication_policy.oil_gas_transfer"]
    policy_profile_version: Literal["1.0.0"]
    policy_profile_sha256: Sha256
    protocol_profile_id: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    protocol_profile_version: Literal["1.0.0"]
    protocol_profile_sha256: Sha256
    telemetry_schema: Literal["otsoc.simulator.telemetry"]
    telemetry_schema_version: Literal["2.0.0"]
    simulator_version: Literal["3.0.0"]
    process_model_version: Literal["3.6"]


class RelationshipMapping(StrictProfileModel):
    source_asset_key: SafeKey
    relationship_type: Literal["CONTROLS", "OBSERVES", "PROCESS_PATH"]
    target_asset_key: SafeKey


class WindowContract(StrictProfileModel):
    baseline_seconds: int = Field(gt=0, le=60)
    effect_seconds: int = Field(gt=0, le=120)
    cadence_seconds: Literal[1]
    minimum_baseline_samples: int = Field(gt=0, le=60)
    minimum_effect_samples: int = Field(gt=0, le=120)
    maximum_gap_seconds: Literal[2]
    baseline_start_inclusive: Literal[True]
    baseline_end_inclusive: Literal[False]
    effect_start_inclusive: Literal[True]
    effect_end_inclusive: Literal[True]


class ThresholdContract(StrictProfileModel):
    valve_target_percent: float | None = Field(default=None, ge=0.0, le=100.0)
    valve_tolerance_percentage_points: float | None = Field(default=None, ge=0.0)
    valve_persistence_samples: int | None = Field(default=None, gt=0)
    flow_decrease_m3h: float | None = Field(default=None, ge=0.0)
    flow_unchanged_deadband_m3h: float = Field(ge=0.0)
    flow_persistence_samples: int = Field(gt=0)
    pressure_increase_bar: float = Field(ge=0.0)
    pressure_unchanged_deadband_bar: float = Field(ge=0.0)
    pressure_persistence_samples: int = Field(gt=0)
    inventory_rate_reduction_percentage_points_per_second: float | None = Field(
        default=None, ge=0.0
    )
    inventory_stagnation_percentage_points_per_second: float | None = Field(default=None, ge=0.0)
    conservation_tolerance: float = Field(ge=0.0)
    low_flow_threshold_m3h: float | None = Field(default=None, ge=0.0)
    terminal_inventory_seconds: int | None = Field(default=None, gt=0)
    flow_baseline_stability_m3h: float = Field(ge=0.0)
    pressure_baseline_stability_bar: float = Field(ge=0.0)
    valve_baseline_stability_percentage_points: float | None = Field(default=None, ge=0.0)


class CorrelationRule(StrictProfileModel):
    rule_id: str = Field(min_length=1, max_length=80)
    rule_version: SemVer
    evaluator_branch: Literal["S3", "S4"]
    process_asset_keys: tuple[SafeKey, ...]
    point_ids: tuple[PointId, ...]
    relationships: tuple[RelationshipMapping, ...]
    window: WindowContract
    thresholds: ThresholdContract
    statement_template_id: str = Field(min_length=1, max_length=80)


class CorrelationProfile(StrictProfileModel):
    profile_id: Literal["otsoc.correlation.oil_gas_transfer"]
    profile_version: SemVer
    domain: Literal["oil_gas_transfer"]
    educational_only: Literal[True]
    disclaimer: Literal[
        "Fictional academic synthetic correlation parameters; not plant-derived alarms."
    ]
    finding_schema: Literal["otsoc.cyber_physical.correlation_finding"]
    finding_schema_version: Literal["1.0.0"]
    dependencies: DependencySet
    statuses: tuple[CorrelationStatus, ...]
    reason_precedence: tuple[CorrelationReasonCode, ...]
    rules: tuple[CorrelationRule, ...] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_frozen_contract(self) -> CorrelationProfile:
        if self.profile_version != CORRELATION_PROFILE_VERSION:
            raise ValueError("unsupported correlation profile version")
        if set(self.statuses) != set(CorrelationStatus) or len(self.statuses) != 4:
            raise ValueError("correlation status catalog differs from the contract")
        if self.reason_precedence != REASON_PRECEDENCE:
            raise ValueError("correlation reason precedence differs from the contract")
        by_id = {rule.rule_id: rule for rule in self.rules}
        if len(by_id) != 2 or set(by_id) != {
            "CPR-S3-CV-TRANSFER-001",
            "CPR-S4-PUMP-FLOW-001",
        }:
            raise ValueError("exactly the two approved correlation rules are required")
        s3 = by_id["CPR-S3-CV-TRANSFER-001"]
        s4 = by_id["CPR-S4-PUMP-FLOW-001"]
        if (s3.rule_version, s3.evaluator_branch) != ("1.0.0", "S3") or (
            s4.rule_version,
            s4.evaluator_branch,
        ) != ("1.0.0", "S4"):
            raise ValueError("correlation rule identity/version is invalid")
        if (
            s3.window.baseline_seconds,
            s3.window.effect_seconds,
            s3.window.minimum_baseline_samples,
            s3.window.minimum_effect_samples,
        ) != (10, 30, 8, 24):
            raise ValueError("S3 window differs from the frozen contract")
        if (
            s4.window.baseline_seconds,
            s4.window.effect_seconds,
            s4.window.minimum_baseline_samples,
            s4.window.minimum_effect_samples,
        ) != (10, 60, 8, 50):
            raise ValueError("S4 window differs from the frozen contract")
        if any(rule.window.maximum_gap_seconds != 2 for rule in self.rules):
            raise ValueError("maximum telemetry gap must be two seconds")
        if (
            set(s3.process_asset_keys) != {"CV-101", "PL-101", "TK-101", "TK-102"}
            or len(s3.process_asset_keys) != 4
        ):
            raise ValueError("S3 process assets differ from the frozen contract")
        if (
            set(s4.process_asset_keys) != {"P-101", "PL-101", "TK-101", "TK-102"}
            or len(s4.process_asset_keys) != 4
        ):
            raise ValueError("S4 process assets differ from the frozen contract")
        if (
            set(s3.point_ids)
            != {
                "control_valve_position_percent",
                "pipeline_flow_rate_m3h",
                "pipeline_pressure_bar",
                "source_tank_level_percent",
                "receiving_tank_level_percent",
            }
            or len(s3.point_ids) != 5
        ):
            raise ValueError("S3 process points differ from the frozen contract")
        if (
            set(s4.point_ids)
            != {
                "transfer_pump_running",
                "pipeline_flow_rate_m3h",
                "pipeline_pressure_bar",
                "source_tank_level_percent",
                "receiving_tank_level_percent",
            }
            or len(s4.point_ids) != 5
        ):
            raise ValueError("S4 process points differ from the frozen contract")
        s3_relationships = {
            (item.source_asset_key, item.relationship_type, item.target_asset_key)
            for item in s3.relationships
        }
        s4_relationships = {
            (item.source_asset_key, item.relationship_type, item.target_asset_key)
            for item in s4.relationships
        }
        if (
            s3_relationships
            != {
                ("PLC-01", "CONTROLS", "CV-101"),
                ("CV-101", "PROCESS_PATH", "PL-101"),
                ("TK-101", "PROCESS_PATH", "TK-102"),
            }
            or len(s3.relationships) != 3
        ):
            raise ValueError("S3 relationships differ from the frozen contract")
        if (
            s4_relationships
            != {
                ("PLC-01", "CONTROLS", "P-101"),
                ("P-101", "PROCESS_PATH", "PL-101"),
                ("TK-101", "PROCESS_PATH", "TK-102"),
            }
            or len(s4.relationships) != 3
        ):
            raise ValueError("S4 relationships differ from the frozen contract")
        if s3.thresholds != ThresholdContract(
            valve_target_percent=25.0,
            valve_tolerance_percentage_points=0.5,
            valve_persistence_samples=3,
            flow_decrease_m3h=0.5,
            flow_unchanged_deadband_m3h=0.1,
            flow_persistence_samples=5,
            pressure_increase_bar=0.1,
            pressure_unchanged_deadband_bar=0.05,
            pressure_persistence_samples=5,
            inventory_rate_reduction_percentage_points_per_second=0.00002,
            conservation_tolerance=0.000000001,
            flow_baseline_stability_m3h=0.1,
            pressure_baseline_stability_bar=0.05,
            valve_baseline_stability_percentage_points=0.5,
        ):
            raise ValueError("S3 thresholds differ from the frozen contract")
        if s4.thresholds != ThresholdContract(
            flow_decrease_m3h=0.5,
            flow_unchanged_deadband_m3h=0.1,
            flow_persistence_samples=10,
            pressure_increase_bar=0.5,
            pressure_unchanged_deadband_bar=0.05,
            pressure_persistence_samples=10,
            inventory_stagnation_percentage_points_per_second=0.00001,
            conservation_tolerance=0.000000001,
            low_flow_threshold_m3h=0.1,
            terminal_inventory_seconds=20,
            flow_baseline_stability_m3h=0.1,
            pressure_baseline_stability_bar=0.05,
        ):
            raise ValueError("S4 thresholds differ from the frozen contract")
        return self


@dataclass(frozen=True)
class LoadedCorrelationProfile:
    profile: CorrelationProfile
    sha256: str

    @property
    def rules(self) -> dict[str, CorrelationRule]:
        return {rule.rule_id: rule for rule in self.profile.rules}


def load_correlation_profile(
    profile_id: str = CORRELATION_PROFILE_ID,
    profile_version: str = CORRELATION_PROFILE_VERSION,
    *,
    expected_sha256: str | None = None,
    inventory: LoadedInventory | None = None,
    policy: LoadedPolicy | None = None,
    protocol_profile: LoadedProtocolProfile | None = None,
) -> LoadedCorrelationProfile:
    if (profile_id, profile_version) != (CORRELATION_PROFILE_ID, CORRELATION_PROFILE_VERSION):
        raise CorrelationProfileError(
            "The requested correlation profile ID/version is unavailable."
        )
    path = PROFILE_ROOT / PROFILE_FILENAME
    if path.is_symlink() or path.resolve().parent != PROFILE_ROOT.resolve():
        raise CorrelationProfileError("The approved correlation profile path is unsafe.")
    loaded = parse_correlation_profile_bytes(path.read_bytes())
    required = expected_sha256 or EXPECTED_CORRELATION_PROFILE_SHA256
    if required == "PENDING" or loaded.sha256 != required:
        raise CorrelationProfileError("The correlation profile digest is not approved.")
    validate_correlation_dependencies(loaded, inventory, policy, protocol_profile)
    return loaded


def parse_correlation_profile_bytes(content: bytes) -> LoadedCorrelationProfile:
    if not content or len(content) > MAX_PROFILE_BYTES:
        raise CorrelationProfileError("The correlation profile exceeds the approved size bound.")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        profile = CorrelationProfile.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise CorrelationProfileError("The correlation profile is invalid.") from exc
    return LoadedCorrelationProfile(
        profile=profile,
        sha256=sha256_hex(canonical_profile_bytes(profile)),
    )


def validate_correlation_dependencies(
    loaded: LoadedCorrelationProfile,
    inventory: LoadedInventory | None,
    policy: LoadedPolicy | None,
    protocol_profile: LoadedProtocolProfile | None,
) -> None:
    dependencies = loaded.profile.dependencies
    if (
        dependencies.inventory_profile_sha256 != EXPECTED_INVENTORY_SHA256
        or dependencies.policy_profile_sha256 != EXPECTED_POLICY_SHA256
        or dependencies.protocol_profile_sha256 != EXPECTED_PROTOCOL_PROFILE_SHA256
    ):
        raise CorrelationProfileError("A frozen correlation dependency digest is invalid.")
    if inventory is not None and (
        dependencies.inventory_profile_id != inventory.profile.profile_id
        or dependencies.inventory_profile_version != inventory.profile.profile_version
        or dependencies.inventory_profile_sha256 != inventory.sha256
    ):
        raise CorrelationProfileError("The loaded asset inventory does not match the profile.")
    if policy is not None and (
        dependencies.policy_profile_id != policy.profile.profile_id
        or dependencies.policy_profile_version != policy.profile.profile_version
        or dependencies.policy_profile_sha256 != policy.sha256
    ):
        raise CorrelationProfileError("The loaded policy does not match the profile.")
    if protocol_profile is not None and (
        dependencies.protocol_profile_id != protocol_profile.profile.profile_id
        or dependencies.protocol_profile_version != protocol_profile.profile.profile_version
        or dependencies.protocol_profile_sha256 != protocol_profile.sha256
    ):
        raise CorrelationProfileError("The loaded protocol profile does not match the profile.")
    if inventory is not None:
        assets = inventory.assets
        relationships = {
            (item.source_asset_key, item.relationship_type.value, item.target_ref)
            for item in inventory.relationships
        }
        for rule in loaded.profile.rules:
            if any(asset_key not in assets for asset_key in rule.process_asset_keys):
                raise CorrelationProfileError("A correlation rule references an unknown asset.")
            for relation in rule.relationships:
                if (
                    relation.relationship_type != "PROCESS_PATH"
                    and (
                        relation.source_asset_key,
                        relation.relationship_type,
                        relation.target_asset_key,
                    )
                    not in relationships
                ):
                    raise CorrelationProfileError("A correlation relationship is not approved.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CorrelationProfileError("The correlation profile has a duplicate JSON key.")
        result[key] = value
    return result
