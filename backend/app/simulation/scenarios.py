from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    scenario_id: str
    scenario_version: str
    name: str
    description: str
    category: str
    affected_variables: tuple[str, ...]
    action_type: str | None
    action_value: float | None
    metadata_only: bool = False


@dataclass(frozen=True, slots=True)
class ScenarioSchedule:
    scenario_id: str
    start_time_seconds: int
    end_time_seconds: int | None = None

    def validate(self) -> None:
        definition = approved_scenarios().get(self.scenario_id)
        if definition is None:
            raise ValueError(f"Unknown scenario_id: {self.scenario_id}")
        if definition.metadata_only:
            raise ValueError(f"{self.scenario_id} is metadata-only in Phase 3.6")
        if self.start_time_seconds < 0:
            raise ValueError("scenario start_time_seconds cannot be negative")
        if self.end_time_seconds is not None and self.end_time_seconds <= self.start_time_seconds:
            raise ValueError("scenario end_time_seconds must follow start_time_seconds")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "start_time_seconds": self.start_time_seconds,
            "end_time_seconds": self.end_time_seconds,
        }


def approved_scenarios() -> dict[str, ScenarioDefinition]:
    return {
        "S1": ScenarioDefinition(
            "S1",
            "2.0.0",
            "Unauthorized OT asset",
            "Metadata only; future synthetic Oil & Gas network evidence is not implemented.",
            "unknown_ot_asset",
            (),
            None,
            None,
            True,
        ),
        "S2": ScenarioDefinition(
            "S2",
            "2.0.0",
            "Unexpected IT-to-controller communication",
            "Metadata only; future zone-to-controller evidence is not implemented.",
            "unexpected_it_to_controller",
            (),
            None,
            None,
            True,
        ),
        "S3": ScenarioDefinition(
            "S3",
            "2.0.0",
            "Unauthorized control-valve position change",
            "Internal synthetic valve-position change; no protocol, attacker, or PLC behavior.",
            "abstract_valve_position_change",
            ("control_valve_position_percent",),
            "set_control_valve_position",
            25.0,
        ),
        "S4": ScenarioDefinition(
            "S4",
            "2.0.0",
            "Transfer pump running with no pipeline flow",
            "Internal synthetic flow-path restriction with pressure and inventory stagnation.",
            "pump_running_no_flow_pressure_inventory_inconsistency",
            (
                "transfer_pump_running",
                "pipeline_flow_rate_m3h",
                "pipeline_pressure_bar",
                "source_tank_level_percent",
                "receiving_tank_level_percent",
            ),
            "set_flow_path_factor",
            0.0,
        ),
    }
