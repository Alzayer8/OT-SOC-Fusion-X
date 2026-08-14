from __future__ import annotations

import json
import math
import random
from datetime import timedelta

from app.simulation.config import DOMAIN_IDENTIFIER, SIMULATOR_VERSION, SimulationConfig
from app.simulation.models import GroundTruthEvent, ProcessState, SimulationStep, TelemetrySample
from app.simulation.scenarios import approved_scenarios


class OilGasTransferSimulator:
    """Fixed-step synthetic liquid-transfer model with no external I/O or control interface."""

    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.simulation_id = f"sim-oilgas-{config.configuration_hash[:16]}"
        self.reset()

    def reset(self) -> None:
        self._sequence = 0
        self._time_seconds = 0
        self._active_scenarios: frozenset[str] = frozenset()
        self._rng = random.Random(self.config.seed)
        self._state = ProcessState(
            source_tank_level_percent=self.config.initial_source_tank_level_percent,
            receiving_tank_level_percent=self.config.initial_receiving_tank_level_percent,
            transfer_pump_command_percent=self.config.initial_transfer_pump_command_percent,
            control_valve_position_percent=self.config.initial_control_valve_position_percent,
            pipeline_flow_rate_m3h=self.config.initial_pipeline_flow_rate_m3h,
            pipeline_pressure_bar=self.config.initial_pipeline_pressure_bar,
            process_temperature_c=self.config.initial_process_temperature_c,
        )

    @property
    def state(self) -> ProcessState:
        return self._state

    @property
    def simulation_time_seconds(self) -> int:
        return self._time_seconds

    def step(self) -> SimulationStep:
        next_time = self._time_seconds + self.config.timestep_seconds
        active = self._active_at(next_time)
        truths = self._truth_transitions(active, next_time)
        command, valve_position, flow_path_factor = self._scenario_inputs(active)
        self._state = self._advance(command, valve_position, flow_path_factor)
        self._time_seconds = next_time
        self._sequence += 1
        self._active_scenarios = active
        return SimulationStep(self._telemetry(), truths)

    def run_steps(self, steps: int) -> tuple[SimulationStep, ...]:
        if steps < 0 or self._time_seconds + steps > self.config.duration_seconds:
            raise ValueError("steps exceed configured simulation duration")
        return tuple(self.step() for _ in range(steps))

    def run_for_duration(self, seconds: int) -> tuple[SimulationStep, ...]:
        if seconds % self.config.timestep_seconds != 0:
            raise ValueError("duration must align to timestep")
        return self.run_steps(seconds // self.config.timestep_seconds)

    def telemetry_json(self, steps: int) -> str:
        return json.dumps(
            [step.telemetry.canonical_dict() for step in self.run_steps(steps)],
            sort_keys=True,
            separators=(",", ":"),
        )

    def _active_at(self, time_seconds: int) -> frozenset[str]:
        return frozenset(
            schedule.scenario_id
            for schedule in self.config.scenarios
            if schedule.start_time_seconds <= time_seconds
            and (schedule.end_time_seconds is None or time_seconds < schedule.end_time_seconds)
        )

    def _truth_transitions(
        self, active: frozenset[str], time_seconds: int
    ) -> tuple[GroundTruthEvent, ...]:
        changed = sorted(active.symmetric_difference(self._active_scenarios))
        definitions = approved_scenarios()
        return tuple(
            GroundTruthEvent(
                simulation_id=self.simulation_id,
                timestamp=self.config.start_time + timedelta(seconds=time_seconds),
                simulation_time_seconds=time_seconds,
                scenario_id=scenario_id,
                scenario_version=definitions[scenario_id].scenario_version,
                category=definitions[scenario_id].category,
                active=scenario_id in active,
                configuration_hash=self.config.configuration_hash,
            )
            for scenario_id in changed
        )

    def _scenario_inputs(self, active: frozenset[str]) -> tuple[float, float, float]:
        command = self.config.initial_transfer_pump_command_percent
        valve_position = self.config.initial_control_valve_position_percent
        flow_path_factor = 1.0
        definitions = approved_scenarios()
        for scenario_id in sorted(active):
            definition = definitions[scenario_id]
            if definition.action_value is None:
                raise RuntimeError("active scenario action is missing its value")
            if definition.action_type == "set_control_valve_position":
                valve_position = definition.action_value
            elif definition.action_type == "set_flow_path_factor":
                flow_path_factor = definition.action_value
        return command, valve_position, flow_path_factor

    def _advance(
        self, command: float, valve_position: float, flow_path_factor: float
    ) -> ProcessState:
        cfg = self.config
        pump_running = command > 1.0
        pump_effort = command / 100.0 if pump_running else 0.0
        valve_fraction = valve_position / 100.0
        flow_noise = (
            self._rng.uniform(-cfg.noise_amplitude_m3h, cfg.noise_amplitude_m3h)
            if cfg.noise_enabled and pump_running
            else 0.0
        )
        target_flow = self._clamp(
            cfg.max_pipeline_flow_rate_m3h * pump_effort * valve_fraction * flow_path_factor
            + flow_noise,
            0.0,
            cfg.max_pipeline_flow_rate_m3h,
        )
        unconstrained_flow_change = (
            target_flow - self._state.pipeline_flow_rate_m3h
        ) / cfg.flow_time_constant_seconds
        flow_change = self._clamp(
            unconstrained_flow_change,
            -cfg.max_flow_rate_change_m3h_per_second,
            cfg.max_flow_rate_change_m3h_per_second,
        )
        dynamic_flow = self._clamp(
            self._state.pipeline_flow_rate_m3h + flow_change,
            0.0,
            cfg.max_pipeline_flow_rate_m3h,
        )

        source_quantity = (
            self._state.source_tank_level_percent / 100.0 * cfg.tank_capacity_synthetic_m3
        )
        receiving_capacity = (
            (100.0 - self._state.receiving_tank_level_percent)
            / 100.0
            * cfg.tank_capacity_synthetic_m3
        )
        transferable_quantity = min(source_quantity, receiving_capacity)
        inventory_limited_flow = transferable_quantity * 3_600.0 / cfg.timestep_seconds
        flow = min(dynamic_flow, inventory_limited_flow)
        transferred_quantity = flow * cfg.timestep_seconds / 3_600.0
        level_change = transferred_quantity / cfg.tank_capacity_synthetic_m3 * 100.0
        source_level = self._state.source_tank_level_percent - level_change
        receiving_level = self._state.receiving_tank_level_percent + level_change

        effective_restriction = 1.0 - valve_fraction * flow_path_factor
        target_pressure = (
            cfg.baseline_pressure_bar
            + cfg.pump_pressure_gain_bar * pump_effort
            + cfg.restriction_pressure_gain_bar * pump_effort * effective_restriction
            - cfg.flow_pressure_relief_bar_per_m3h * flow
        )
        pressure_change = self._clamp(
            (target_pressure - self._state.pipeline_pressure_bar)
            / cfg.pressure_time_constant_seconds,
            -cfg.max_pressure_change_bar_per_second,
            cfg.max_pressure_change_bar_per_second,
        )
        pressure = self._clamp(
            self._state.pipeline_pressure_bar + pressure_change,
            0.0,
            cfg.max_pipeline_pressure_bar,
        )

        target_temperature = cfg.ambient_temperature_c + cfg.pump_temperature_gain_c * pump_effort
        temperature = self._clamp(
            self._state.process_temperature_c
            + (target_temperature - self._state.process_temperature_c)
            / cfg.temperature_time_constant_seconds,
            0.0,
            80.0,
        )
        values = (
            source_level,
            receiving_level,
            command,
            valve_position,
            flow,
            pressure,
            temperature,
        )
        if not all(math.isfinite(value) for value in values):
            raise RuntimeError("simulation produced a non-finite value")
        if source_level < -1e-9 or receiving_level > 100.0 + 1e-9:
            raise RuntimeError("inventory conservation produced an invalid tank level")
        return ProcessState(
            source_tank_level_percent=self._clamp(source_level, 0.0, 100.0),
            receiving_tank_level_percent=self._clamp(receiving_level, 0.0, 100.0),
            transfer_pump_command_percent=command,
            control_valve_position_percent=valve_position,
            pipeline_flow_rate_m3h=flow,
            pipeline_pressure_bar=pressure,
            process_temperature_c=temperature,
        )

    def _telemetry(self) -> TelemetrySample:
        state = self._state
        return TelemetrySample(
            domain=DOMAIN_IDENTIFIER,
            simulation_id=self.simulation_id,
            sequence_number=self._sequence,
            timestamp=self.config.start_time + timedelta(seconds=self._time_seconds),
            simulator_version=SIMULATOR_VERSION,
            configuration_hash=self.config.configuration_hash,
            simulation_time_seconds=self._time_seconds,
            source_tank_level_percent=state.source_tank_level_percent,
            receiving_tank_level_percent=state.receiving_tank_level_percent,
            transfer_pump_command_percent=state.transfer_pump_command_percent,
            transfer_pump_running=state.transfer_pump_command_percent > 1.0,
            control_valve_position_percent=state.control_valve_position_percent,
            pipeline_flow_rate_m3h=state.pipeline_flow_rate_m3h,
            pipeline_pressure_bar=state.pipeline_pressure_bar,
            process_temperature_c=state.process_temperature_c,
        )

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(value, upper))
