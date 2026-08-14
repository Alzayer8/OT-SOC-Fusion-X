from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from app.correlation.evaluator import evaluate_correlation
from app.correlation.fixtures import build_fixture_input, load_fixture
from app.correlation.profile import load_correlation_profile
from app.correlation.temporal import select_window

BENCHMARK_OPERATIONS = 1_000


@dataclass(frozen=True, slots=True)
class CorrelationBenchmarkResult:
    operations_per_measurement: int
    temporal_selection_seconds: float
    temporal_selections_per_second: float
    s3_evaluation_seconds: float
    s3_evaluations_per_second: float
    s4_evaluation_seconds: float
    s4_evaluations_per_second: float
    persistence_measured: bool = False
    scope: str = "bounded local offline development measurement; not production capacity"


def main() -> int:
    profile = load_correlation_profile()
    s3_fixture, _ = load_fixture("p6b-f001.json")
    s4_fixture, _ = load_fixture("p6b-f008.json")
    s3_input = build_fixture_input(s3_fixture, profile)
    s4_input = build_fixture_input(s4_fixture, profile)

    temporal_start = time.perf_counter()
    for _ in range(BENCHMARK_OPERATIONS):
        select_window(
            s3_input.telemetry,
            anchor=s3_fixture.anchor_time,
            baseline_seconds=10,
            effect_seconds=30,
            maximum_gap_seconds=2,
        )
    temporal_seconds = time.perf_counter() - temporal_start

    s3_start = time.perf_counter()
    for _ in range(BENCHMARK_OPERATIONS):
        evaluate_correlation(s3_input, profile)
    s3_seconds = time.perf_counter() - s3_start

    s4_start = time.perf_counter()
    for _ in range(BENCHMARK_OPERATIONS):
        evaluate_correlation(s4_input, profile)
    s4_seconds = time.perf_counter() - s4_start

    result = CorrelationBenchmarkResult(
        operations_per_measurement=BENCHMARK_OPERATIONS,
        temporal_selection_seconds=temporal_seconds,
        temporal_selections_per_second=BENCHMARK_OPERATIONS / temporal_seconds,
        s3_evaluation_seconds=s3_seconds,
        s3_evaluations_per_second=BENCHMARK_OPERATIONS / s3_seconds,
        s4_evaluation_seconds=s4_seconds,
        s4_evaluations_per_second=BENCHMARK_OPERATIONS / s4_seconds,
    )
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
