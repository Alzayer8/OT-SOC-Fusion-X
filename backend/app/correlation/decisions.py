from __future__ import annotations

from datetime import UTC, datetime

from app.correlation.models import (
    CorrelationDecision,
    CorrelationReasonCode,
    CorrelationStatus,
    TelemetryEvidence,
)
from app.correlation.profile import CorrelationRule

STATUS_BY_REASON: dict[CorrelationReasonCode, CorrelationStatus] = {
    CorrelationReasonCode.PARENT_EVIDENCE_NOT_VERIFIED: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.PROFILE_VERSION_UNSUPPORTED: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.PROFILE_DIGEST_MISMATCH: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.UNSUPPORTED_CORRELATION_RULE: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.RUN_ID_MISMATCH: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.CONFIGURATION_MISMATCH: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.SIMULATOR_VERSION_MISMATCH: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.CLOCK_SEQUENCE_MISMATCH: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.ASSET_RELATION_MISMATCH: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.POINT_RELATION_NOT_DEFINED: CorrelationStatus.INDETERMINATE,
    CorrelationReasonCode.WINDOW_NOT_FINALIZED: CorrelationStatus.INSUFFICIENT_EVIDENCE,
    CorrelationReasonCode.MISSING_TELEMETRY: CorrelationStatus.INSUFFICIENT_EVIDENCE,
    CorrelationReasonCode.INSUFFICIENT_SAMPLES: CorrelationStatus.INSUFFICIENT_EVIDENCE,
    CorrelationReasonCode.TELEMETRY_GAP_EXCEEDED: CorrelationStatus.INSUFFICIENT_EVIDENCE,
    CorrelationReasonCode.BASELINE_NOT_STABLE: CorrelationStatus.INSUFFICIENT_EVIDENCE,
    CorrelationReasonCode.PROCESS_CHANGE_OUTSIDE_WINDOW: CorrelationStatus.NOT_CORRELATED,
    CorrelationReasonCode.PROCESS_EFFECT_DIRECTION_MISMATCH: CorrelationStatus.NOT_CORRELATED,
    CorrelationReasonCode.NO_PROCESS_CHANGE: CorrelationStatus.NOT_CORRELATED,
    CorrelationReasonCode.CORRELATION_MATCH: CorrelationStatus.CORRELATED,
}


def reason_decision(
    reason: CorrelationReasonCode,
    rule: CorrelationRule,
    telemetry: tuple[TelemetryEvidence, ...],
    *,
    anchor: datetime | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    simulation_id: str | None = None,
    configuration_hash: str | None = None,
    simulator_version: str | None = None,
    run_origin: datetime | None = None,
    baseline_count: int = 0,
    effect_count: int = 0,
    maximum_gap_seconds: float | None = None,
) -> CorrelationDecision:
    observed_at = (
        max((item.observed_at for item in telemetry), default=None)
        or anchor
        or datetime(1970, 1, 1, tzinfo=UTC)
    )
    explanation = {
        CorrelationReasonCode.PARENT_EVIDENCE_NOT_VERIFIED: (
            "Required stored parent evidence could not be verified."
        ),
        CorrelationReasonCode.PROFILE_VERSION_UNSUPPORTED: (
            "The requested correlation profile version is unsupported."
        ),
        CorrelationReasonCode.PROFILE_DIGEST_MISMATCH: (
            "The requested correlation profile digest is not approved."
        ),
        CorrelationReasonCode.UNSUPPORTED_CORRELATION_RULE: (
            "The requested correlation rule is unsupported."
        ),
        CorrelationReasonCode.RUN_ID_MISMATCH: (
            "Stored telemetry spans more than one synthetic run and was not correlated."
        ),
        CorrelationReasonCode.CONFIGURATION_MISMATCH: (
            "Stored telemetry spans incompatible synthetic configurations and was not correlated."
        ),
        CorrelationReasonCode.SIMULATOR_VERSION_MISMATCH: (
            "Stored telemetry uses an unsupported simulator version."
        ),
        CorrelationReasonCode.CLOCK_SEQUENCE_MISMATCH: (
            "Stored telemetry time, sequence, or run origin is inconsistent."
        ),
        CorrelationReasonCode.ASSET_RELATION_MISMATCH: (
            "The stored asset relationship does not match the configured correlation path."
        ),
        CorrelationReasonCode.POINT_RELATION_NOT_DEFINED: (
            "The selected process point is not defined by the configured correlation rule."
        ),
        CorrelationReasonCode.WINDOW_NOT_FINALIZED: (
            "The stored synthetic effect window is not finalized."
        ),
        CorrelationReasonCode.MISSING_TELEMETRY: (
            "Required synthetic process telemetry is unavailable."
        ),
        CorrelationReasonCode.INSUFFICIENT_SAMPLES: (
            "The stored window does not contain the required sample count."
        ),
        CorrelationReasonCode.TELEMETRY_GAP_EXCEEDED: (
            "The stored window exceeds the configured telemetry-gap tolerance."
        ),
        CorrelationReasonCode.BASELINE_NOT_STABLE: (
            "The preceding synthetic baseline is not stable under the configured deadbands."
        ),
        CorrelationReasonCode.PROCESS_CHANGE_OUTSIDE_WINDOW: (
            "A consistent process observation occurred only after the configured effect window."
        ),
        CorrelationReasonCode.PROCESS_EFFECT_DIRECTION_MISMATCH: (
            "Complete process observations do not satisfy the configured direction and persistence."
        ),
        CorrelationReasonCode.NO_PROCESS_CHANGE: (
            "Complete process observations show no qualifying change in the configured window."
        ),
        CorrelationReasonCode.CORRELATION_MATCH: (
            "Stored observations satisfy the configured correlation rule; "
            "causation is not determined."
        ),
    }[reason]
    return CorrelationDecision(
        status=STATUS_BY_REASON[reason],
        reason_code=reason,
        anchor_time=anchor,
        correlation_start_time=start,
        correlation_end_time=end,
        evidence_observed_at=observed_at,
        temporal_relation=(
            "NO_MATCHING_CHANGE"
            if reason
            in {
                CorrelationReasonCode.NO_PROCESS_CHANGE,
                CorrelationReasonCode.PROCESS_CHANGE_OUTSIDE_WINDOW,
                CorrelationReasonCode.PROCESS_EFFECT_DIRECTION_MISMATCH,
            }
            else "UNAVAILABLE"
        ),
        simulation_id=simulation_id,
        configuration_hash=configuration_hash,
        simulator_version=simulator_version,
        telemetry_schema_version="2.0.0" if telemetry else None,
        run_origin=run_origin,
        baseline_sample_count=baseline_count,
        effect_sample_count=effect_count,
        maximum_gap_seconds=maximum_gap_seconds,
        matched_minimum_set=None,
        process_asset_keys=rule.process_asset_keys,
        affected_process_points=rule.point_ids,
        observations=(),
        statement_template_id=reason.value,
        explanation=explanation,
    )
