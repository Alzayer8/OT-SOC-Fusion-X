from __future__ import annotations

import json
import math

import pytest

from app.simulation import (
    DOMAIN_IDENTIFIER,
    SIMULATOR_VERSION,
    OilGasTransferSimulator,
    ScenarioSchedule,
    SimulationConfig,
    approved_scenarios,
)


def test_active_domain_and_simulator_version_are_explicit() -> None:
    config = SimulationConfig()
    sample = OilGasTransferSimulator(config).step().telemetry
    assert config.domain == DOMAIN_IDENTIFIER == "oil_gas_transfer"
    assert sample.domain == "oil_gas_transfer"
    assert sample.simulator_version == SIMULATOR_VERSION == "3.0.0"
    assert config.canonical_dict()["simulator_version"] == "3.0.0"


def test_same_configuration_and_seed_produce_identical_serialized_telemetry() -> None:
    config = SimulationConfig(seed=17, noise_enabled=True, duration_seconds=120)
    assert OilGasTransferSimulator(config).telemetry_json(120) == OilGasTransferSimulator(
        config
    ).telemetry_json(120)


def test_seed_changes_only_enabled_noise() -> None:
    deterministic_one = OilGasTransferSimulator(
        SimulationConfig(seed=1, noise_enabled=False, duration_seconds=10)
    )
    deterministic_two = OilGasTransferSimulator(
        SimulationConfig(seed=2, noise_enabled=False, duration_seconds=10)
    )
    first_values = [
        (
            step.telemetry.pipeline_flow_rate_m3h,
            step.telemetry.pipeline_pressure_bar,
            step.telemetry.source_tank_level_percent,
            step.telemetry.receiving_tank_level_percent,
        )
        for step in deterministic_one.run_steps(10)
    ]
    second_values = [
        (
            step.telemetry.pipeline_flow_rate_m3h,
            step.telemetry.pipeline_pressure_bar,
            step.telemetry.source_tank_level_percent,
            step.telemetry.receiving_tank_level_percent,
        )
        for step in deterministic_two.run_steps(10)
    ]
    assert first_values == second_values
    noisy_one = OilGasTransferSimulator(
        SimulationConfig(seed=1, noise_enabled=True, duration_seconds=10)
    )
    noisy_two = OilGasTransferSimulator(
        SimulationConfig(seed=2, noise_enabled=True, duration_seconds=10)
    )
    assert noisy_one.telemetry_json(10) != noisy_two.telemetry_json(10)


def test_configuration_hash_is_stable_domain_bound_and_schedule_sensitive() -> None:
    config = SimulationConfig(scenarios=(ScenarioSchedule("S4", 12),))
    assert (
        config.configuration_hash
        == SimulationConfig(scenarios=(ScenarioSchedule("S4", 12),)).configuration_hash
    )
    assert (
        config.configuration_hash
        != SimulationConfig(scenarios=(ScenarioSchedule("S4", 13),)).configuration_hash
    )
    assert config.configuration_hash == (
        "625353fa7e156ddc83558a31be50b7774df8765f4425abb5b87db12769305d26"
    )


def test_reset_restores_inventory_clock_sequence_and_seeded_output() -> None:
    simulator = OilGasTransferSimulator(SimulationConfig(duration_seconds=10, noise_enabled=True))
    first = simulator.run_steps(5)
    simulator.reset()
    second = simulator.run_steps(5)
    assert first == second
    assert simulator.simulation_time_seconds == 5
    assert second[0].telemetry.sequence_number == 1


def test_fixed_timestamps_and_sequence_are_monotonic() -> None:
    steps = OilGasTransferSimulator(SimulationConfig(duration_seconds=5)).run_steps(5)
    assert [item.telemetry.sequence_number for item in steps] == [1, 2, 3, 4, 5]
    assert [item.telemetry.simulation_time_seconds for item in steps] == [1, 2, 3, 4, 5]
    assert (steps[1].telemetry.timestamp - steps[0].telemetry.timestamp).total_seconds() == 1


def test_normal_transfer_moves_both_tanks_and_conserves_inventory() -> None:
    config = SimulationConfig(duration_seconds=3_600)
    final = OilGasTransferSimulator(config).run_steps(3_600)[-1].telemetry
    source_loss = config.initial_source_tank_level_percent - final.source_tank_level_percent
    receiving_gain = (
        final.receiving_tank_level_percent - config.initial_receiving_tank_level_percent
    )
    assert source_loss > 0.0
    assert receiving_gain > 0.0
    assert source_loss == pytest.approx(receiving_gain, abs=1e-10)


def test_pump_command_increases_pipeline_flow() -> None:
    low = (
        OilGasTransferSimulator(
            SimulationConfig(duration_seconds=60, initial_transfer_pump_command_percent=25.0)
        )
        .run_steps(60)[-1]
        .telemetry
    )
    high = (
        OilGasTransferSimulator(
            SimulationConfig(duration_seconds=60, initial_transfer_pump_command_percent=75.0)
        )
        .run_steps(60)[-1]
        .telemetry
    )
    assert high.pipeline_flow_rate_m3h > low.pipeline_flow_rate_m3h


def test_valve_restriction_reduces_flow_and_increases_upstream_pressure() -> None:
    restricted = (
        OilGasTransferSimulator(
            SimulationConfig(duration_seconds=120, initial_control_valve_position_percent=20.0)
        )
        .run_steps(120)[-1]
        .telemetry
    )
    open_valve = (
        OilGasTransferSimulator(
            SimulationConfig(duration_seconds=120, initial_control_valve_position_percent=85.0)
        )
        .run_steps(120)[-1]
        .telemetry
    )
    assert restricted.pipeline_flow_rate_m3h < open_valve.pipeline_flow_rate_m3h
    assert restricted.pipeline_pressure_bar > open_valve.pipeline_pressure_bar


def test_pump_off_causes_existing_flow_and_pressure_to_decay() -> None:
    config = SimulationConfig(
        duration_seconds=60,
        initial_transfer_pump_command_percent=0.0,
        initial_pipeline_flow_rate_m3h=6.0,
        initial_pipeline_pressure_bar=2.0,
    )
    steps = OilGasTransferSimulator(config).run_steps(60)
    assert steps[-1].telemetry.pipeline_flow_rate_m3h < steps[0].telemetry.pipeline_flow_rate_m3h
    assert steps[-1].telemetry.pipeline_flow_rate_m3h < 0.01
    assert steps[-1].telemetry.pipeline_pressure_bar < steps[0].telemetry.pipeline_pressure_bar


def test_s3_changes_and_releases_valve_at_exact_times_with_truth() -> None:
    config = SimulationConfig(
        duration_seconds=8,
        scenarios=(ScenarioSchedule("S3", start_time_seconds=3, end_time_seconds=6),),
    )
    steps = OilGasTransferSimulator(config).run_steps(8)
    assert steps[1].telemetry.control_valve_position_percent == 70.0
    assert steps[2].telemetry.control_valve_position_percent == 25.0
    assert steps[5].telemetry.control_valve_position_percent == 70.0
    assert [
        (event.simulation_time_seconds, event.active) for event in steps[2].ground_truth_events
    ] == [(3, True)]
    assert [
        (event.simulation_time_seconds, event.active) for event in steps[5].ground_truth_events
    ] == [(6, False)]


def test_s4_pump_running_no_flow_raises_pressure_and_stagnates_inventory() -> None:
    config = SimulationConfig(
        duration_seconds=180,
        scenarios=(ScenarioSchedule("S4", start_time_seconds=60),),
    )
    steps = OilGasTransferSimulator(config).run_steps(180)
    before = steps[58].telemetry
    after = steps[-1].telemetry
    assert after.transfer_pump_running is True
    assert after.pipeline_flow_rate_m3h < 0.001
    assert after.pipeline_pressure_bar > before.pipeline_pressure_bar + 0.5
    assert after.source_tank_level_percent == pytest.approx(
        steps[-30].telemetry.source_tank_level_percent, abs=1e-5
    )
    assert after.receiving_tank_level_percent == pytest.approx(
        steps[-30].telemetry.receiving_tank_level_percent, abs=1e-5
    )
    assert steps[59].ground_truth_events[0].scenario_id == "S4"
    assert steps[59].ground_truth_events[0].active is True


def test_s1_and_s2_remain_metadata_only() -> None:
    for scenario_id in ("S1", "S2"):
        assert approved_scenarios()[scenario_id].metadata_only is True
        with pytest.raises(ValueError, match="metadata-only"):
            SimulationConfig(scenarios=(ScenarioSchedule(scenario_id, 1),))


def test_active_scenarios_have_no_superseded_process_semantics() -> None:
    catalog = json.dumps(
        {key: value.description for key, value in approved_scenarios().items()}
    ).lower()
    assert "heat exchanger" not in catalog
    assert "cooling" not in catalog
    assert "temperature rise" not in catalog


def test_ground_truth_is_separate_from_public_telemetry() -> None:
    step = OilGasTransferSimulator(
        SimulationConfig(duration_seconds=2, scenarios=(ScenarioSchedule("S4", 1),))
    ).step()
    assert "scenario" not in json.dumps(step.telemetry.canonical_dict()).lower()
    assert step.ground_truth_events[0].scenario_id == "S4"
    assert step.ground_truth_events[0].scenario_version == "2.0.0"


@pytest.mark.parametrize("duration", [600, 3_600, 21_600, 86_400])
def test_normal_operation_is_finite_stable_bounded_and_balanced(duration: int) -> None:
    config = SimulationConfig(duration_seconds=duration)
    steps = OilGasTransferSimulator(config).run_steps(duration)
    for sample in (item.telemetry for item in steps):
        values = (
            sample.source_tank_level_percent,
            sample.receiving_tank_level_percent,
            sample.transfer_pump_command_percent,
            sample.control_valve_position_percent,
            sample.pipeline_flow_rate_m3h,
            sample.pipeline_pressure_bar,
            sample.process_temperature_c,
        )
        assert all(math.isfinite(value) for value in values)
        assert 0.0 <= sample.source_tank_level_percent <= 100.0
        assert 0.0 <= sample.receiving_tank_level_percent <= 100.0
        assert 0.0 <= sample.transfer_pump_command_percent <= 100.0
        assert 0.0 <= sample.control_valve_position_percent <= 100.0
        assert 0.0 <= sample.pipeline_flow_rate_m3h <= 12.0
        assert 0.0 <= sample.pipeline_pressure_bar <= 4.0
        assert 0.0 <= sample.process_temperature_c <= 80.0
    final = steps[-1].telemetry
    assert (
        config.initial_source_tank_level_percent - final.source_tank_level_percent
    ) == pytest.approx(
        final.receiving_tank_level_percent - config.initial_receiving_tank_level_percent,
        abs=1e-9,
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"domain": "cooling_loop"},
        {"timestep_seconds": 2},
        {"duration_seconds": 0},
        {"initial_transfer_pump_command_percent": 101},
        {"initial_control_valve_position_percent": -1},
        {"max_pipeline_flow_rate_m3h": 0},
        {"noise_amplitude_m3h": 0.2},
        {"scenarios": (ScenarioSchedule("S1", 1),)},
        {"scenarios": (ScenarioSchedule("unknown", 1),)},
    ],
)
def test_invalid_configuration_fails_closed(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        SimulationConfig(**kwargs)
