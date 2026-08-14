from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.simulation.scenarios import ScenarioSchedule

DOMAIN_IDENTIFIER = "oil_gas_transfer"
SIMULATOR_VERSION = "3.0.0"


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Synthetic academic transfer-process parameters; never plant-derived."""

    domain: str = DOMAIN_IDENTIFIER
    timestep_seconds: int = 1
    seed: int = 20260809
    duration_seconds: int = 3600
    start_time: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    initial_source_tank_level_percent: float = 72.0
    initial_receiving_tank_level_percent: float = 18.0
    initial_transfer_pump_command_percent: float = 55.0
    initial_control_valve_position_percent: float = 70.0
    initial_pipeline_flow_rate_m3h: float = 0.0
    initial_pipeline_pressure_bar: float = 0.30
    initial_process_temperature_c: float = 26.0
    tank_capacity_synthetic_m3: float = 1_000.0
    max_pipeline_flow_rate_m3h: float = 12.0
    max_pipeline_pressure_bar: float = 4.0
    flow_time_constant_seconds: float = 8.0
    pressure_time_constant_seconds: float = 5.0
    temperature_time_constant_seconds: float = 900.0
    max_flow_rate_change_m3h_per_second: float = 2.5
    max_pressure_change_bar_per_second: float = 0.5
    baseline_pressure_bar: float = 0.30
    pump_pressure_gain_bar: float = 1.40
    restriction_pressure_gain_bar: float = 1.80
    flow_pressure_relief_bar_per_m3h: float = 0.04
    ambient_temperature_c: float = 24.0
    pump_temperature_gain_c: float = 1.5
    noise_enabled: bool = False
    noise_amplitude_m3h: float = 0.02
    scenarios: tuple[ScenarioSchedule, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.domain != DOMAIN_IDENTIFIER:
            raise ValueError(f"domain must be {DOMAIN_IDENTIFIER}")
        if self.timestep_seconds != 1:
            raise ValueError("Phase 3.6 uses a fixed one-second timestep")
        if not 1 <= self.duration_seconds <= 86_400:
            raise ValueError("duration_seconds must be between 1 and 86400")
        if self.start_time.tzinfo is None or self.start_time.utcoffset() is None:
            raise ValueError("start_time must be timezone-aware")
        bounded_percentages = (
            self.initial_source_tank_level_percent,
            self.initial_receiving_tank_level_percent,
            self.initial_transfer_pump_command_percent,
            self.initial_control_valve_position_percent,
        )
        if not all(0.0 <= value <= 100.0 for value in bounded_percentages):
            raise ValueError("initial level, pump, and valve percentages must be within 0..100")
        positive = (
            self.tank_capacity_synthetic_m3,
            self.max_pipeline_flow_rate_m3h,
            self.max_pipeline_pressure_bar,
            self.flow_time_constant_seconds,
            self.pressure_time_constant_seconds,
            self.temperature_time_constant_seconds,
            self.max_flow_rate_change_m3h_per_second,
            self.max_pressure_change_bar_per_second,
        )
        if not all(value > 0.0 for value in positive):
            raise ValueError("process coefficients and capacities must be positive")
        if not 0.0 <= self.initial_pipeline_flow_rate_m3h <= self.max_pipeline_flow_rate_m3h:
            raise ValueError("initial pipeline flow is outside synthetic bounds")
        if not 0.0 <= self.initial_pipeline_pressure_bar <= self.max_pipeline_pressure_bar:
            raise ValueError("initial pipeline pressure is outside synthetic bounds")
        if not 0.0 <= self.initial_process_temperature_c <= 80.0:
            raise ValueError("initial process temperature is outside synthetic bounds")
        if not 0.0 <= self.noise_amplitude_m3h <= 0.1:
            raise ValueError("noise amplitude must be bounded within 0..0.1 m3/h")
        numeric_values = tuple(
            value
            for value in asdict(self).values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )
        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("configuration values must be finite")
        for schedule in self.scenarios:
            schedule.validate()

    def canonical_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["simulator_version"] = SIMULATOR_VERSION
        data["start_time"] = self.start_time.isoformat()
        data["scenarios"] = [schedule.canonical_dict() for schedule in self.scenarios]
        return data

    @property
    def configuration_hash(self) -> str:
        payload = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
