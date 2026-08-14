from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from app.correlation.models import CorrelationReasonCode, TelemetryEvidence


@dataclass(frozen=True)
class RunConsistency:
    reason: CorrelationReasonCode | None
    simulation_id: str | None
    configuration_hash: str | None
    simulator_version: str | None
    run_origin: datetime | None


@dataclass(frozen=True)
class WindowSelection:
    baseline: tuple[TelemetryEvidence, ...]
    effect: tuple[TelemetryEvidence, ...]
    after: tuple[TelemetryEvidence, ...]
    start: datetime
    end: datetime
    finalized: bool
    maximum_gap_seconds: float | None
    gap_reason: CorrelationReasonCode | None


def canonical_telemetry(
    telemetry: tuple[TelemetryEvidence, ...],
) -> tuple[TelemetryEvidence, ...]:
    unique: dict[object, TelemetryEvidence] = {}
    for sample in telemetry:
        existing = unique.get(sample.evidence_id)
        if existing is not None and existing != sample:
            raise ValueError("one telemetry evidence ID has conflicting content")
        unique[sample.evidence_id] = sample
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (item.observed_at, item.sequence_number, str(item.evidence_id)),
        )
    )


def validate_run_consistency(telemetry: tuple[TelemetryEvidence, ...]) -> RunConsistency:
    if not telemetry:
        return RunConsistency(None, None, None, None, None)
    ordered = canonical_telemetry(telemetry)
    run_ids = {item.payload.simulation_id for item in ordered}
    configurations = {item.payload.configuration_hash for item in ordered}
    simulator_versions = {item.payload.simulator_version for item in ordered}
    if len(run_ids) != 1:
        return RunConsistency(CorrelationReasonCode.RUN_ID_MISMATCH, None, None, None, None)
    if len(configurations) != 1:
        return RunConsistency(
            CorrelationReasonCode.CONFIGURATION_MISMATCH,
            next(iter(run_ids)),
            None,
            None,
            None,
        )
    if simulator_versions != {"3.0.0"}:
        return RunConsistency(
            CorrelationReasonCode.SIMULATOR_VERSION_MISMATCH,
            next(iter(run_ids)),
            next(iter(configurations)),
            None,
            None,
        )
    timestamps = [item.observed_at for item in ordered]
    sequences = [item.sequence_number for item in ordered]
    if len(timestamps) != len(set(timestamps)) or len(sequences) != len(set(sequences)):
        return RunConsistency(
            CorrelationReasonCode.CLOCK_SEQUENCE_MISMATCH,
            next(iter(run_ids)),
            next(iter(configurations)),
            next(iter(simulator_versions)),
            None,
        )
    origins = {
        (item.observed_at - timedelta(seconds=item.payload.simulation_time_seconds)).astimezone(UTC)
        for item in ordered
    }
    if len(origins) != 1:
        return RunConsistency(
            CorrelationReasonCode.CLOCK_SEQUENCE_MISMATCH,
            next(iter(run_ids)),
            next(iter(configurations)),
            next(iter(simulator_versions)),
            None,
        )
    return RunConsistency(
        None,
        next(iter(run_ids)),
        next(iter(configurations)),
        next(iter(simulator_versions)),
        next(iter(origins)),
    )


def select_window(
    telemetry: tuple[TelemetryEvidence, ...],
    *,
    anchor: datetime,
    baseline_seconds: int,
    effect_seconds: int,
    maximum_gap_seconds: int,
) -> WindowSelection:
    ordered = canonical_telemetry(telemetry)
    start = anchor - timedelta(seconds=baseline_seconds)
    end = anchor + timedelta(seconds=effect_seconds)
    baseline = tuple(item for item in ordered if start <= item.observed_at < anchor)
    effect = tuple(item for item in ordered if anchor <= item.observed_at <= end)
    after = tuple(item for item in ordered if item.observed_at > end)
    finalized = bool(ordered) and ordered[-1].observed_at >= end
    gaps = tuple(_adjacent_gaps(baseline)) + tuple(_adjacent_gaps(effect))
    max_gap = max((item[0] for item in gaps), default=None)
    invalid_sequence = any(item[1] for item in gaps)
    reason = (
        CorrelationReasonCode.TELEMETRY_GAP_EXCEEDED
        if invalid_sequence or (max_gap is not None and max_gap > maximum_gap_seconds)
        else None
    )
    return WindowSelection(
        baseline=baseline,
        effect=effect,
        after=after,
        start=start,
        end=end,
        finalized=finalized,
        maximum_gap_seconds=max_gap,
        gap_reason=reason,
    )


def maximum_gap(telemetry: tuple[TelemetryEvidence, ...]) -> float | None:
    return max((item[0] for item in _adjacent_gaps(telemetry)), default=None)


def _adjacent_gaps(
    telemetry: tuple[TelemetryEvidence, ...],
) -> tuple[tuple[float, bool], ...]:
    result: list[tuple[float, bool]] = []
    for previous, current in pairwise(telemetry):
        time_delta = (current.observed_at - previous.observed_at).total_seconds()
        sequence_delta = current.sequence_number - previous.sequence_number
        invalid = time_delta <= 0 or sequence_delta <= 0 or float(sequence_delta) != time_delta
        result.append((time_delta, invalid))
    return tuple(result)
