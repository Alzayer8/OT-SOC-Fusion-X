from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.correlation.baseline import arithmetic_mean, endpoint_slope, value_range
from app.correlation.decisions import reason_decision
from app.correlation.models import (
    CorrelationDecision,
    CorrelationEvaluationInput,
    CorrelationReasonCode,
    CorrelationStatus,
    ObservationRole,
    PointObservation,
    ProcessChange,
    TelemetryEvidence,
)
from app.correlation.process import maximum_persistence, representative_value
from app.correlation.profile import CorrelationRule
from app.correlation.s3 import _numeric_observation
from app.correlation.temporal import RunConsistency, canonical_telemetry, select_window


def evaluate_s4(
    request: CorrelationEvaluationInput,
    rule: CorrelationRule,
    consistency: RunConsistency,
) -> CorrelationDecision:
    ordered = canonical_telemetry(request.telemetry)
    if not ordered:
        return reason_decision(CorrelationReasonCode.MISSING_TELEMETRY, rule, ordered)
    anchor = _find_anchor(ordered, rule)
    if anchor is None:
        scope_seconds = (ordered[-1].observed_at - ordered[0].observed_at).total_seconds()
        reason = (
            CorrelationReasonCode.INSUFFICIENT_SAMPLES
            if len(ordered)
            < rule.window.minimum_baseline_samples + rule.window.minimum_effect_samples
            or scope_seconds < rule.window.baseline_seconds + rule.window.effect_seconds
            else CorrelationReasonCode.NO_PROCESS_CHANGE
        )
        return reason_decision(
            reason,
            rule,
            ordered,
            simulation_id=consistency.simulation_id,
            configuration_hash=consistency.configuration_hash,
            simulator_version=consistency.simulator_version,
            run_origin=consistency.run_origin,
        )
    window = select_window(
        ordered,
        anchor=anchor,
        baseline_seconds=rule.window.baseline_seconds,
        effect_seconds=rule.window.effect_seconds,
        maximum_gap_seconds=rule.window.maximum_gap_seconds,
    )
    common: dict[str, Any] = {
        "anchor": anchor,
        "start": window.start,
        "end": window.end,
        "simulation_id": consistency.simulation_id,
        "configuration_hash": consistency.configuration_hash,
        "simulator_version": consistency.simulator_version,
        "run_origin": consistency.run_origin,
        "baseline_count": len(window.baseline),
        "effect_count": len(window.effect),
        "maximum_gap_seconds": window.maximum_gap_seconds,
    }
    if not window.finalized:
        return reason_decision(CorrelationReasonCode.WINDOW_NOT_FINALIZED, rule, ordered, **common)
    required_points = set(rule.point_ids)
    if not required_points.issubset(request.available_point_ids):
        return reason_decision(CorrelationReasonCode.MISSING_TELEMETRY, rule, ordered, **common)
    if (
        len(window.baseline) < rule.window.minimum_baseline_samples
        or len(window.effect) < rule.window.minimum_effect_samples
    ):
        return reason_decision(CorrelationReasonCode.INSUFFICIENT_SAMPLES, rule, ordered, **common)
    if window.gap_reason is not None:
        return reason_decision(window.gap_reason, rule, ordered, **common)
    thresholds = rule.thresholds
    if (
        value_range(window.baseline, _flow) > thresholds.flow_baseline_stability_m3h
        or value_range(window.baseline, _pressure) > thresholds.pressure_baseline_stability_bar
        or not all(item.payload.transfer_pump_running for item in window.baseline)
    ):
        return reason_decision(CorrelationReasonCode.BASELINE_NOT_STABLE, rule, ordered, **common)

    flow_baseline = arithmetic_mean(window.baseline, _flow)
    pressure_baseline = arithmetic_mean(window.baseline, _pressure)
    low_flow = _required(thresholds.low_flow_threshold_m3h)
    pump_persistence = maximum_persistence(
        window.effect, lambda item: item.payload.transfer_pump_running
    )
    flow_persistence = maximum_persistence(window.effect, lambda item: _flow(item) <= low_flow)
    pressure_persistence = maximum_persistence(
        window.effect,
        lambda item: _pressure(item) >= pressure_baseline + thresholds.pressure_increase_bar,
    )
    required = thresholds.flow_persistence_samples
    pump_match = pump_persistence >= required
    flow_match = flow_persistence >= required
    pressure_match = pressure_persistence >= thresholds.pressure_persistence_samples
    terminal_seconds = int(_required(thresholds.terminal_inventory_seconds))
    terminal = tuple(
        item
        for item in window.effect
        if item.observed_at >= window.end - timedelta(seconds=terminal_seconds)
    )
    terminal_span = (
        (terminal[-1].observed_at - terminal[0].observed_at).total_seconds()
        if len(terminal) >= 2
        else 0.0
    )
    source_slope = (
        abs(endpoint_slope(terminal, _source_level)) if terminal_span >= terminal_seconds else None
    )
    receiving_slope = (
        abs(endpoint_slope(terminal, _receiving_level))
        if terminal_span >= terminal_seconds
        else None
    )
    inventory_threshold = _required(thresholds.inventory_stagnation_percentage_points_per_second)
    inventory_match = (
        source_slope is not None
        and receiving_slope is not None
        and source_slope <= inventory_threshold
        and receiving_slope <= inventory_threshold
        and abs(source_slope - receiving_slope) <= thresholds.conservation_tolerance
    )

    flow_observed = representative_value(
        window.effect, _flow, lambda item: _flow(item) <= low_flow, required
    )
    pressure_observed = representative_value(
        window.effect,
        _pressure,
        lambda item: _pressure(item) >= pressure_baseline + thresholds.pressure_increase_bar,
        thresholds.pressure_persistence_samples,
    )
    observations = (
        PointObservation(
            point_id="transfer_pump_running",
            asset_key="P-101",
            baseline_value=True,
            observed_value=pump_match,
            delta=None,
            unit="boolean",
            expected_direction=ProcessChange.UNCHANGED,
            observed_direction=ProcessChange.UNCHANGED if pump_match else ProcessChange.UNAVAILABLE,
            threshold=None,
            persistence_required=required,
            persistence_observed=pump_persistence,
            role=ObservationRole.REQUIRED,
            condition_met=pump_match,
        ),
        _numeric_observation(
            point_id="pipeline_flow_rate_m3h",
            asset_key="PL-101",
            baseline=flow_baseline,
            observed=flow_observed,
            unit="synthetic_m3h",
            expected=ProcessChange.DECREASED,
            deadband=thresholds.flow_unchanged_deadband_m3h,
            threshold=flow_baseline - low_flow,
            required=required,
            observed_persistence=flow_persistence,
            role=ObservationRole.REQUIRED,
            met=flow_match,
        ),
        _numeric_observation(
            point_id="pipeline_pressure_bar",
            asset_key="PL-101",
            baseline=pressure_baseline,
            observed=pressure_observed,
            unit="synthetic_bar",
            expected=ProcessChange.INCREASED,
            deadband=thresholds.pressure_unchanged_deadband_bar,
            threshold=thresholds.pressure_increase_bar,
            required=thresholds.pressure_persistence_samples,
            observed_persistence=pressure_persistence,
            role=ObservationRole.REQUIRED,
            met=pressure_match,
        ),
        _inventory_observation(
            "source_tank_level_percent",
            "TK-101",
            source_slope,
            inventory_threshold,
            inventory_match,
            len(terminal),
        ),
        _inventory_observation(
            "receiving_tank_level_percent",
            "TK-102",
            receiving_slope,
            inventory_threshold,
            inventory_match,
            len(terminal),
        ),
    )
    if pump_match and flow_match and pressure_match and inventory_match:
        return CorrelationDecision(
            status=CorrelationStatus.CORRELATED,
            reason_code=CorrelationReasonCode.CORRELATION_MATCH,
            anchor_time=anchor,
            correlation_start_time=window.start,
            correlation_end_time=window.end,
            evidence_observed_at=max(item.observed_at for item in ordered),
            temporal_relation="PROCESS_ONLY_WITHIN_WINDOW",
            simulation_id=consistency.simulation_id,
            configuration_hash=consistency.configuration_hash,
            simulator_version=consistency.simulator_version,
            telemetry_schema_version="2.0.0",
            run_origin=consistency.run_origin,
            baseline_sample_count=len(window.baseline),
            effect_sample_count=len(window.effect),
            maximum_gap_seconds=window.maximum_gap_seconds,
            matched_minimum_set="S4_PROCESS_INCONSISTENCY",
            process_asset_keys=rule.process_asset_keys,
            affected_process_points=tuple(item.point_id for item in observations),
            observations=observations,
            statement_template_id=rule.statement_template_id,
            explanation=(
                "P-101 remained observed as running while PL-101 flow was low, pressure increased, "
                "and tank movement stagnated inside one synthetic run; no cyber cause is asserted."
            ),
        )
    decision = reason_decision(
        CorrelationReasonCode.PROCESS_EFFECT_DIRECTION_MISMATCH, rule, ordered, **common
    )
    return decision.model_copy(update={"observations": observations})


def _find_anchor(
    telemetry: tuple[TelemetryEvidence, ...], rule: CorrelationRule
) -> datetime | None:
    for current in telemetry:
        start = current.observed_at - timedelta(seconds=rule.window.baseline_seconds)
        baseline = tuple(
            item for item in telemetry if start <= item.observed_at < current.observed_at
        )
        if len(baseline) < rule.window.minimum_baseline_samples:
            continue
        if not current.payload.transfer_pump_running or not all(
            item.payload.transfer_pump_running for item in baseline
        ):
            continue
        if value_range(baseline, _flow) > rule.thresholds.flow_baseline_stability_m3h:
            continue
        baseline_flow = arithmetic_mean(baseline, _flow)
        if _flow(current) <= baseline_flow - _required(rule.thresholds.flow_decrease_m3h):
            return current.observed_at
    return None


def _inventory_observation(
    point_id: str,
    asset_key: str,
    slope: float | None,
    threshold: float,
    met: bool,
    persistence: int,
) -> PointObservation:
    return PointObservation(
        point_id=point_id,
        asset_key=asset_key,
        baseline_value=None,
        observed_value=slope,
        delta=None,
        unit="percentage_points_per_second",
        expected_direction=ProcessChange.UNCHANGED,
        observed_direction=(
            ProcessChange.UNCHANGED
            if slope is not None and slope <= threshold
            else ProcessChange.INCREASED
        ),
        threshold=threshold,
        persistence_required=20,
        persistence_observed=persistence,
        role=ObservationRole.REQUIRED,
        condition_met=met,
    )


def _required(value: float | int | None) -> float:
    if value is None:
        raise ValueError("the S4 profile is missing a required threshold")
    return float(value)


def _flow(item: TelemetryEvidence) -> float:
    return item.payload.pipeline_flow_rate_m3h


def _pressure(item: TelemetryEvidence) -> float:
    return item.payload.pipeline_pressure_bar


def _source_level(item: TelemetryEvidence) -> float:
    return item.payload.source_tank_level_percent


def _receiving_level(item: TelemetryEvidence) -> float:
    return item.payload.receiving_tank_level_percent
