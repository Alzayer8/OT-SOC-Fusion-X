from __future__ import annotations

import json
from typing import Any

from app.simulation import (
    DOMAIN_IDENTIFIER,
    SIMULATOR_VERSION,
    OilGasTransferSimulator,
    ScenarioSchedule,
    SimulationConfig,
    approved_scenarios,
)


def fixture_document() -> dict[str, Any]:
    schedules = (
        ScenarioSchedule("S3", start_time_seconds=2, end_time_seconds=4),
        ScenarioSchedule("S4", start_time_seconds=5),
    )
    config = SimulationConfig(duration_seconds=8, seed=20260809, scenarios=schedules)
    steps = OilGasTransferSimulator(config).run_steps(8)
    return {
        "fixture_version": "2.0.0",
        "domain": DOMAIN_IDENTIFIER,
        "simulator_version": SIMULATOR_VERSION,
        "configuration_hash": config.configuration_hash,
        "seed": config.seed,
        "scenario_versions": {
            scenario_id: definition.scenario_version
            for scenario_id, definition in approved_scenarios().items()
        },
        "scenario_schedule": [schedule.canonical_dict() for schedule in schedules],
        "telemetry": [step.telemetry.canonical_dict() for step in steps],
        "ground_truth": [
            {
                "simulation_id": event.simulation_id,
                "timestamp": event.timestamp.isoformat(),
                "simulation_time_seconds": event.simulation_time_seconds,
                "scenario_id": event.scenario_id,
                "scenario_version": event.scenario_version,
                "category": event.category,
                "active": event.active,
                "configuration_hash": event.configuration_hash,
            }
            for step in steps
            for event in step.ground_truth_events
        ],
    }


def main() -> int:
    print(json.dumps(fixture_document(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
