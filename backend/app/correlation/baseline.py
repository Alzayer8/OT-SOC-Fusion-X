from __future__ import annotations

from collections.abc import Callable
from math import fsum

from app.correlation.models import TelemetryEvidence


def arithmetic_mean(
    telemetry: tuple[TelemetryEvidence, ...], accessor: Callable[[TelemetryEvidence], float]
) -> float:
    if not telemetry:
        raise ValueError("a baseline mean requires at least one sample")
    values = tuple(accessor(item) for item in telemetry)
    return fsum(values) / len(values)


def value_range(
    telemetry: tuple[TelemetryEvidence, ...], accessor: Callable[[TelemetryEvidence], float]
) -> float:
    if not telemetry:
        raise ValueError("a baseline range requires at least one sample")
    values = tuple(accessor(item) for item in telemetry)
    return max(values) - min(values)


def endpoint_slope(
    telemetry: tuple[TelemetryEvidence, ...], accessor: Callable[[TelemetryEvidence], float]
) -> float:
    if len(telemetry) < 2:
        raise ValueError("an endpoint slope requires two samples")
    first = telemetry[0]
    last = telemetry[-1]
    seconds = (last.observed_at - first.observed_at).total_seconds()
    if seconds <= 0:
        raise ValueError("an endpoint slope requires a positive time span")
    return (accessor(last) - accessor(first)) / seconds
