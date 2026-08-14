from __future__ import annotations

from collections.abc import Callable
from math import fsum

from app.correlation.models import ProcessChange, TelemetryEvidence


def classify_delta(
    delta: float,
    *,
    deadband: float,
    increase_threshold: float,
    decrease_threshold: float,
) -> ProcessChange:
    if abs(delta) <= deadband:
        return ProcessChange.UNCHANGED
    if delta > 0:
        return ProcessChange.INCREASED
    return ProcessChange.DECREASED


def maximum_persistence(
    telemetry: tuple[TelemetryEvidence, ...],
    predicate: Callable[[TelemetryEvidence], bool],
) -> int:
    longest = 0
    current = 0
    for sample in telemetry:
        if predicate(sample):
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def representative_value(
    telemetry: tuple[TelemetryEvidence, ...],
    accessor: Callable[[TelemetryEvidence], float],
    predicate: Callable[[TelemetryEvidence], bool],
    required: int,
) -> float:
    runs: list[list[TelemetryEvidence]] = []
    current: list[TelemetryEvidence] = []
    for sample in telemetry:
        if predicate(sample):
            current.append(sample)
        else:
            if len(current) >= required:
                runs.append(current)
            current = []
    if len(current) >= required:
        runs.append(current)
    selected = runs[-1][-required:] if runs else list(telemetry[-required:])
    if not selected:
        raise ValueError("a representative value requires telemetry")
    return fsum(accessor(item) for item in selected) / len(selected)
