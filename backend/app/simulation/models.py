from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ProcessState:
    source_tank_level_percent: float
    receiving_tank_level_percent: float
    transfer_pump_command_percent: float
    control_valve_position_percent: float
    pipeline_flow_rate_m3h: float
    pipeline_pressure_bar: float
    process_temperature_c: float


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    """Public Oil & Gas lab output; scenario labels are intentionally excluded."""

    domain: str
    simulation_id: str
    sequence_number: int
    timestamp: datetime
    simulator_version: str
    configuration_hash: str
    simulation_time_seconds: int
    source_tank_level_percent: float
    receiving_tank_level_percent: float
    transfer_pump_command_percent: float
    transfer_pump_running: bool
    control_valve_position_percent: float
    pipeline_flow_rate_m3h: float
    pipeline_pressure_bar: float
    process_temperature_c: float

    def canonical_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["timestamp"] = self.timestamp.isoformat()
        return values


@dataclass(frozen=True, slots=True)
class GroundTruthEvent:
    """Evaluation-only scenario provenance; never embedded in TelemetrySample."""

    simulation_id: str
    timestamp: datetime
    simulation_time_seconds: int
    scenario_id: str
    scenario_version: str
    category: str
    active: bool
    configuration_hash: str


@dataclass(frozen=True, slots=True)
class SimulationStep:
    telemetry: TelemetrySample
    ground_truth_events: tuple[GroundTruthEvent, ...]
