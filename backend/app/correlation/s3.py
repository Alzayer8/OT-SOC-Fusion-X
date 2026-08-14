from __future__ import annotations

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
from app.correlation.process import classify_delta, maximum_persistence, representative_value
from app.correlation.profile import CorrelationRule
from app.correlation.temporal import RunConsistency, select_window


def evaluate_s3(
    request: CorrelationEvaluationInput,
    rule: CorrelationRule,
    consistency: RunConsistency,
) -> CorrelationDecision:
    anchor = request.cyber_context.command_observed_at if request.cyber_context else None
    if anchor is None:
        return reason_decision(
            CorrelationReasonCode.PARENT_EVIDENCE_NOT_VERIFIED,
            rule,
            request.telemetry,
        )
    thresholds = rule.thresholds
    window = select_window(
        request.telemetry,
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
        return reason_decision(
            CorrelationReasonCode.WINDOW_NOT_FINALIZED, rule, request.telemetry, **common
        )
    available = set(request.available_point_ids)
    has_valve = "control_valve_position_percent" in available
    has_flow = "pipeline_flow_rate_m3h" in available
    has_pressure = "pipeline_pressure_bar" in available
    if (has_valve and not (has_flow or has_pressure)) or (
        not has_valve and not (has_flow and has_pressure)
    ):
        return reason_decision(
            CorrelationReasonCode.MISSING_TELEMETRY, rule, request.telemetry, **common
        )
    if (
        len(window.baseline) < rule.window.minimum_baseline_samples
        or len(window.effect) < rule.window.minimum_effect_samples
    ):
        return reason_decision(
            CorrelationReasonCode.INSUFFICIENT_SAMPLES, rule, request.telemetry, **common
        )
    if window.gap_reason is not None:
        return reason_decision(window.gap_reason, rule, request.telemetry, **common)
    if (
        (
            has_valve
            and value_range(window.baseline, _valve)
            > _required(thresholds.valve_baseline_stability_percentage_points)
        )
        or (
            has_flow
            and value_range(window.baseline, _flow) > thresholds.flow_baseline_stability_m3h
        )
        or (
            has_pressure
            and value_range(window.baseline, _pressure) > thresholds.pressure_baseline_stability_bar
        )
    ):
        return reason_decision(
            CorrelationReasonCode.BASELINE_NOT_STABLE, rule, request.telemetry, **common
        )

    valve_baseline = arithmetic_mean(window.baseline, _valve) if has_valve else None
    flow_baseline = arithmetic_mean(window.baseline, _flow) if has_flow else None
    pressure_baseline = arithmetic_mean(window.baseline, _pressure) if has_pressure else None
    valve_target = _required(thresholds.valve_target_percent)
    valve_tolerance = _required(thresholds.valve_tolerance_percentage_points)
    valve_required = int(_required(thresholds.valve_persistence_samples))
    flow_decrease = _required(thresholds.flow_decrease_m3h)

    def valve_predicate(item: TelemetryEvidence) -> bool:
        return abs(_valve(item) - valve_target) <= valve_tolerance

    def flow_predicate(item: TelemetryEvidence) -> bool:
        return flow_baseline is not None and _flow(item) <= flow_baseline - flow_decrease

    def pressure_predicate(item: TelemetryEvidence) -> bool:
        return (
            pressure_baseline is not None
            and _pressure(item) >= pressure_baseline + thresholds.pressure_increase_bar
        )

    valve_persistence = maximum_persistence(window.effect, valve_predicate) if has_valve else 0
    flow_persistence = maximum_persistence(window.effect, flow_predicate) if has_flow else 0
    pressure_persistence = (
        maximum_persistence(window.effect, pressure_predicate) if has_pressure else 0
    )
    valve_match = has_valve and valve_persistence >= valve_required
    flow_match = has_flow and flow_persistence >= thresholds.flow_persistence_samples
    pressure_match = (
        has_pressure and pressure_persistence >= thresholds.pressure_persistence_samples
    )
    matched = (valve_match and (flow_match or pressure_match)) or (
        not has_valve and flow_match and pressure_match
    )

    observations: list[PointObservation] = []
    if has_valve and valve_baseline is not None:
        observed = representative_value(window.effect, _valve, valve_predicate, valve_required)
        observations.append(
            _numeric_observation(
                point_id="control_valve_position_percent",
                asset_key="CV-101",
                baseline=valve_baseline,
                observed=observed,
                unit="percentage_points_open",
                expected=ProcessChange.DECREASED,
                deadband=valve_tolerance,
                threshold=abs(valve_baseline - valve_target),
                required=valve_required,
                observed_persistence=valve_persistence,
                role=ObservationRole.REQUIRED,
                met=valve_match,
            )
        )
    if has_flow and flow_baseline is not None:
        observed = representative_value(
            window.effect, _flow, flow_predicate, thresholds.flow_persistence_samples
        )
        observations.append(
            _numeric_observation(
                point_id="pipeline_flow_rate_m3h",
                asset_key="PL-101",
                baseline=flow_baseline,
                observed=observed,
                unit="synthetic_m3h",
                expected=ProcessChange.DECREASED,
                deadband=thresholds.flow_unchanged_deadband_m3h,
                threshold=flow_decrease,
                required=thresholds.flow_persistence_samples,
                observed_persistence=flow_persistence,
                role=ObservationRole.REQUIRED,
                met=flow_match,
            )
        )
    if has_pressure and pressure_baseline is not None:
        observed = representative_value(
            window.effect,
            _pressure,
            pressure_predicate,
            thresholds.pressure_persistence_samples,
        )
        observations.append(
            _numeric_observation(
                point_id="pipeline_pressure_bar",
                asset_key="PL-101",
                baseline=pressure_baseline,
                observed=observed,
                unit="synthetic_bar",
                expected=ProcessChange.INCREASED,
                deadband=thresholds.pressure_unchanged_deadband_bar,
                threshold=thresholds.pressure_increase_bar,
                required=thresholds.pressure_persistence_samples,
                observed_persistence=pressure_persistence,
                role=ObservationRole.REQUIRED,
                met=pressure_match,
            )
        )
    observations.extend(_s3_inventory_observations(window.baseline, window.effect, rule))

    if matched:
        minimum = "VALVE_AND_DOWNSTREAM" if has_valve else "DUAL_DOWNSTREAM_WITHOUT_VALVE"
        return CorrelationDecision(
            status=CorrelationStatus.CORRELATED,
            reason_code=CorrelationReasonCode.CORRELATION_MATCH,
            anchor_time=anchor,
            correlation_start_time=window.start,
            correlation_end_time=window.end,
            evidence_observed_at=max(item.observed_at for item in request.telemetry),
            temporal_relation="FOLLOWED_WITHIN_WINDOW",
            simulation_id=consistency.simulation_id,
            configuration_hash=consistency.configuration_hash,
            simulator_version=consistency.simulator_version,
            telemetry_schema_version="2.0.0",
            run_origin=consistency.run_origin,
            baseline_sample_count=len(window.baseline),
            effect_sample_count=len(window.effect),
            maximum_gap_seconds=window.maximum_gap_seconds,
            matched_minimum_set=minimum,
            process_asset_keys=rule.process_asset_keys,
            affected_process_points=tuple(item.point_id for item in observations),
            observations=tuple(observations),
            statement_template_id=rule.statement_template_id,
            explanation=(
                "The CV-101 command event was followed by process observations consistent with "
                "the configured synthetic transfer-path rule; causation is not determined."
            ),
        )

    outside_match = _outside_match(
        window.after,
        has_valve=has_valve,
        has_flow=has_flow,
        has_pressure=has_pressure,
        valve_target=valve_target,
        valve_tolerance=valve_tolerance,
        valve_required=valve_required,
        flow_baseline=flow_baseline,
        flow_decrease=flow_decrease,
        flow_required=thresholds.flow_persistence_samples,
        pressure_baseline=pressure_baseline,
        pressure_increase=thresholds.pressure_increase_bar,
        pressure_required=thresholds.pressure_persistence_samples,
    )
    if outside_match:
        decision = reason_decision(
            CorrelationReasonCode.PROCESS_CHANGE_OUTSIDE_WINDOW,
            rule,
            request.telemetry,
            **common,
        )
        return decision.model_copy(update={"observations": tuple(observations)})

    no_change = all(
        observation.observed_direction is ProcessChange.UNCHANGED
        for observation in observations
        if observation.role is ObservationRole.REQUIRED
    )
    reason = (
        CorrelationReasonCode.NO_PROCESS_CHANGE
        if no_change
        else CorrelationReasonCode.PROCESS_EFFECT_DIRECTION_MISMATCH
    )
    decision = reason_decision(reason, rule, request.telemetry, **common)
    return decision.model_copy(update={"observations": tuple(observations)})


def _s3_inventory_observations(
    baseline: tuple[TelemetryEvidence, ...],
    effect: tuple[TelemetryEvidence, ...],
    rule: CorrelationRule,
) -> tuple[PointObservation, ...]:
    threshold = rule.thresholds.inventory_rate_reduction_percentage_points_per_second
    if threshold is None or len(baseline) < 2 or len(effect) < 2:
        return ()
    baseline_source = abs(endpoint_slope(baseline, _source_level))
    baseline_receiving = abs(endpoint_slope(baseline, _receiving_level))
    effect_source = abs(endpoint_slope(effect, _source_level))
    effect_receiving = abs(endpoint_slope(effect, _receiving_level))
    conservation = abs(effect_source - effect_receiving)
    source_met = baseline_source - effect_source >= threshold
    receiving_met = baseline_receiving - effect_receiving >= threshold
    conservation_met = conservation <= rule.thresholds.conservation_tolerance
    return (
        _numeric_observation(
            point_id="source_tank_level_percent",
            asset_key="TK-101",
            baseline=baseline_source,
            observed=effect_source,
            unit="percentage_points_per_second",
            expected=ProcessChange.DECREASED,
            deadband=0.0,
            threshold=threshold,
            required=len(effect),
            observed_persistence=len(effect),
            role=ObservationRole.SUPPORTING
            if source_met and conservation_met
            else ObservationRole.CONTRADICTING,
            met=source_met and conservation_met,
        ),
        _numeric_observation(
            point_id="receiving_tank_level_percent",
            asset_key="TK-102",
            baseline=baseline_receiving,
            observed=effect_receiving,
            unit="percentage_points_per_second",
            expected=ProcessChange.DECREASED,
            deadband=0.0,
            threshold=threshold,
            required=len(effect),
            observed_persistence=len(effect),
            role=ObservationRole.SUPPORTING
            if receiving_met and conservation_met
            else ObservationRole.CONTRADICTING,
            met=receiving_met and conservation_met,
        ),
    )


def _outside_match(
    telemetry: tuple[TelemetryEvidence, ...],
    *,
    has_valve: bool,
    has_flow: bool,
    has_pressure: bool,
    valve_target: float,
    valve_tolerance: float,
    valve_required: int,
    flow_baseline: float | None,
    flow_decrease: float,
    flow_required: int,
    pressure_baseline: float | None,
    pressure_increase: float,
    pressure_required: int,
) -> bool:
    valve = (
        has_valve
        and maximum_persistence(
            telemetry, lambda item: abs(_valve(item) - valve_target) <= valve_tolerance
        )
        >= valve_required
    )
    flow = (
        has_flow
        and flow_baseline is not None
        and maximum_persistence(
            telemetry, lambda item: _flow(item) <= flow_baseline - flow_decrease
        )
        >= flow_required
    )
    pressure = (
        has_pressure
        and pressure_baseline is not None
        and maximum_persistence(
            telemetry, lambda item: _pressure(item) >= pressure_baseline + pressure_increase
        )
        >= pressure_required
    )
    return (valve and (flow or pressure)) or (not has_valve and flow and pressure)


def _numeric_observation(
    *,
    point_id: str,
    asset_key: str,
    baseline: float,
    observed: float,
    unit: str,
    expected: ProcessChange,
    deadband: float,
    threshold: float,
    required: int,
    observed_persistence: int,
    role: ObservationRole,
    met: bool,
) -> PointObservation:
    delta = observed - baseline
    return PointObservation(
        point_id=point_id,
        asset_key=asset_key,
        baseline_value=baseline,
        observed_value=observed,
        delta=delta,
        unit=unit,
        expected_direction=expected,
        observed_direction=classify_delta(
            delta,
            deadband=deadband,
            increase_threshold=threshold,
            decrease_threshold=threshold,
        ),
        threshold=threshold,
        persistence_required=required,
        persistence_observed=observed_persistence,
        role=role,
        condition_met=met,
    )


def _required(value: float | int | None) -> float:
    if value is None:
        raise ValueError("the S3 profile is missing a required threshold")
    return float(value)


def _valve(item: TelemetryEvidence) -> float:
    return item.payload.control_valve_position_percent


def _flow(item: TelemetryEvidence) -> float:
    return item.payload.pipeline_flow_rate_m3h


def _pressure(item: TelemetryEvidence) -> float:
    return item.payload.pipeline_pressure_bar


def _source_level(item: TelemetryEvidence) -> float:
    return item.payload.source_tank_level_percent


def _receiving_level(item: TelemetryEvidence) -> float:
    return item.payload.receiving_tank_level_percent
