from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.context.canonical import deterministic_asset_id
from app.context.inventory import LoadedInventory, load_inventory_profile
from app.evidence.models import EvidenceRecord
from app.evidence.service import evidence_record_response, verify_record_integrity
from app.incidents.models import Incident, IncidentTimelineEntry
from app.incidents.repository import get_incident_detail
from app.lab.models import LabActiveContext, LabRun, LabRunEvidence, LabRunIncident
from app.product.schemas import (
    AssetCatalogResponse,
    AssetDetailResponse,
    AssetOverviewSummary,
    CorrelationOverviewSummary,
    IncidentCategorySummary,
    IncidentOverviewSummary,
    OverviewRunContext,
    OverviewSummaryResponse,
    PolicyOverviewSummary,
    ProductAsset,
    RecentActivity,
    ReplayBundleResponse,
    ReplayEvent,
    ReplayEventClass,
    ReplayWindowRequest,
)
from app.protocols.profile import LoadedProfile, load_profile

MAX_REPLAY_EVENTS = 2_000

EVENT_CLASS: dict[str, tuple[ReplayEventClass, int]] = {
    "synthetic_protocol_event": ("RAW_PROTOCOL", 10),
    "protocol_semantic_event": ("PROTOCOL_SEMANTIC", 20),
    "asset_context_event": ("ASSET_CONTEXT", 30),
    "communication_policy_finding": ("POLICY_FINDING", 40),
    "simulator_telemetry": ("TELEMETRY", 50),
    "correlation_finding": ("CORRELATION_FINDING", 60),
}


class ProductReadError(ValueError):
    pass


class ProductNotFoundError(ProductReadError):
    pass


def overview_summary(session: Session, *, as_of: datetime | None = None) -> OverviewSummaryResponse:
    generated_at = (as_of or datetime.now(UTC)).astimezone(UTC)
    context = session.get(LabActiveContext, 1)
    if context is None:
        raise ProductReadError("The active synthetic lab context is unavailable.")
    run = session.get(LabRun, context.active_run_id)
    if run is None or run.state != "COMPLETED":
        raise ProductReadError("The active synthetic lab run is unavailable.")
    effective_as_of = run.evidence_observed_to or run.completed_at or generated_at
    window_start = run.evidence_observed_from or effective_as_of
    incident_bins = _incident_bins(session, run_id=run.run_id)
    policy_bins = _json_status_bins_for_run(
        session,
        run_id=run.run_id,
        evidence_type="communication_policy_finding",
        payload_key="policy_status",
        values=("APPROVED", "DENIED", "UNKNOWN"),
    )
    correlation_bins = _json_status_bins_for_run(
        session,
        run_id=run.run_id,
        evidence_type="correlation_finding",
        payload_key="correlation_status",
        values=("CORRELATED", "NOT_CORRELATED", "INSUFFICIENT_EVIDENCE", "INDETERMINATE"),
    )
    inventory = load_inventory_profile()
    snapshot_record = _latest_run_telemetry(session, run.run_id)
    snapshot_scope = "ACTIVE_RUN"
    if snapshot_record is None and run.scenario_id in {"S1", "S2"}:
        baseline_run_id = session.scalar(
            select(LabRun.run_id).where(
                LabRun.scenario_id == "BASELINE", LabRun.state == "COMPLETED"
            )
        )
        if baseline_run_id is not None:
            snapshot_record = _latest_run_telemetry(session, baseline_run_id)
            snapshot_scope = "BASELINE_REFERENCE"
    if snapshot_record is None:
        snapshot_scope = "UNAVAILABLE"
    snapshot = (
        evidence_record_response(snapshot_record)
        if snapshot_record is not None and verify_record_integrity(snapshot_record)
        else None
    )
    activity_rows = session.scalars(
        select(IncidentTimelineEntry)
        .join(
            LabRunIncident,
            LabRunIncident.incident_id == IncidentTimelineEntry.incident_id,
        )
        .where(LabRunIncident.run_id == run.run_id)
        .order_by(
            IncidentTimelineEntry.observed_at.desc(),
            IncidentTimelineEntry.timeline_entry_id.asc(),
        )
        .limit(10)
    ).all()
    return OverviewSummaryResponse(
        generated_at=generated_at,
        as_of=effective_as_of,
        window_start=window_start,
        window_end=effective_as_of,
        window_complete=True,
        active_run=OverviewRunContext(
            run_id=run.run_id,
            scenario_id=run.scenario_id,
            scenario_state="COMPLETED",
            context_scope="CURRENT_RUN",
            evidence_simulation_id=run.evidence_simulation_id,
            configuration_hash=run.configuration_hash,
        ),
        incidents=IncidentOverviewSummary(
            total=incident_bins["total"],
            open=incident_bins["OPEN"],
            investigating=incident_bins["INVESTIGATING"],
            resolved=incident_bins["RESOLVED"],
            low=incident_bins["LOW"],
            medium=incident_bins["MEDIUM"],
            high=incident_bins["HIGH"],
            high_non_resolved=incident_bins["high_non_resolved"],
            categories=IncidentCategorySummary(
                asset_identity_anomaly=incident_bins["ASSET_IDENTITY_ANOMALY"],
                communication_policy_violation=incident_bins["COMMUNICATION_POLICY_VIOLATION"],
                control_command_investigation=incident_bins["CONTROL_COMMAND_INVESTIGATION"],
                process_inconsistency=incident_bins["PROCESS_INCONSISTENCY"],
            ),
        ),
        policy_findings=PolicyOverviewSummary(
            total=sum(policy_bins.values()),
            approved=policy_bins["APPROVED"],
            denied=policy_bins["DENIED"],
            unknown=policy_bins["UNKNOWN"],
        ),
        correlations=CorrelationOverviewSummary(
            total=sum(correlation_bins.values()),
            correlated=correlation_bins["CORRELATED"],
            not_correlated=correlation_bins["NOT_CORRELATED"],
            insufficient_evidence=correlation_bins["INSUFFICIENT_EVIDENCE"],
            indeterminate=correlation_bins["INDETERMINATE"],
        ),
        assets=AssetOverviewSummary(
            total=11,
            enabled=sum(asset.enabled for asset in inventory.profile.assets),
            cyber=6,
            process=5,
        ),
        recent_activity=tuple(
            RecentActivity(
                activity_id=row.timeline_entry_id,
                incident_id=row.incident_id,
                entry_type=row.entry_type,
                observed_at=row.observed_at,
                summary=row.summary,
                asset_ids=tuple(row.asset_ids),
            )
            for row in activity_rows
        ),
        process_snapshot_status="COMPLETE" if snapshot is not None else "UNAVAILABLE",
        process_snapshot_scope=snapshot_scope,
        process_snapshot_message=(
            (
                "Coherent stored telemetry from the active synthetic run is available."
                if snapshot_scope == "ACTIVE_RUN"
                else (
                    "No scenario telemetry exists; the verified Baseline process reference "
                    "is shown."
                )
            )
            if snapshot is not None
            else "Process telemetry is unavailable for this evidence window."
        ),
        process_snapshot=snapshot,
        linked_valve_command=None,
    )


def asset_catalog() -> AssetCatalogResponse:
    inventory = load_inventory_profile()
    protocol = load_profile()
    return AssetCatalogResponse(
        profile_id=inventory.profile.profile_id,
        profile_version=inventory.profile.profile_version,
        profile_sha256=inventory.sha256,
        domain=inventory.profile.domain,
        educational_only=True,
        disclaimer=inventory.profile.disclaimer,
        zones=inventory.profile.zones,
        assets=tuple(
            _product_asset(asset.asset_key, inventory, protocol)
            for asset in inventory.profile.assets
        ),
        relationships=inventory.profile.relationships,
    )


def asset_detail(asset_key: str) -> AssetDetailResponse:
    inventory = load_inventory_profile()
    protocol = load_profile()
    asset = inventory.assets.get(asset_key)
    if asset is None:
        raise ProductNotFoundError("The synthetic asset was not found.")
    zone = inventory.zones[asset.zone_id.value]
    inbound = tuple(item for item in inventory.relationships if item.target_ref == asset_key)
    outbound = tuple(item for item in inventory.relationships if item.source_asset_key == asset_key)
    return AssetDetailResponse(
        profile_id=inventory.profile.profile_id,
        profile_version=inventory.profile.profile_version,
        profile_sha256=inventory.sha256,
        asset=_product_asset(asset_key, inventory, protocol),
        zone=zone,
        inbound_relationships=inbound,
        outbound_relationships=outbound,
    )


def replay_for_incident(
    session: Session, incident_id: uuid.UUID, *, run_id: uuid.UUID | None = None
) -> ReplayBundleResponse:
    detail = get_incident_detail(session, incident_id)
    if detail is None:
        raise ProductNotFoundError("The replay incident was not found.")
    lab_run = _incident_lab_run(session, incident_id, run_id=run_id)
    expected_scope = (
        detail.incident.bound_simulation_id,
        detail.incident.bound_configuration_hash,
    )
    roots = {item.evidence_id: item.integrity_sha256 for item in detail.evidence_memberships}
    records, gaps = _verified_closure(session, roots, expected_scope=expected_scope)
    evidence_events = [_evidence_event(record) for record in records]
    incident_events = [
        ReplayEvent(
            event_id=item.timeline_entry_id,
            event_class="INCIDENT_EVENT",
            sort_rank=70,
            observed_at=item.observed_at,
            summary=item.summary,
            incident_event=item,
            integrity_verified=True,
        )
        for item in detail.timeline
    ]
    events = _ordered_events([*evidence_events, *incident_events])
    _enforce_bundle_bound(events)
    return _bundle(
        source_kind="INCIDENT",
        lab_run=lab_run,
        incident=detail.incident,
        correlation_evidence_id=None,
        simulation_id=expected_scope[0],
        configuration_hash=expected_scope[1],
        events=events,
        gaps=gaps,
    )


def replay_for_correlation(
    session: Session, correlation_evidence_id: uuid.UUID
) -> ReplayBundleResponse:
    root = session.get(EvidenceRecord, correlation_evidence_id)
    if root is None or root.evidence_type != "correlation_finding":
        raise ProductNotFoundError("The replay correlation finding was not found.")
    scope = _record_scope(root)
    records, gaps = _verified_closure(
        session,
        {root.evidence_id: root.integrity_sha256},
        expected_scope=scope,
    )
    events = _ordered_events([_evidence_event(record) for record in records])
    _enforce_bundle_bound(events)
    return _bundle(
        source_kind="CORRELATION",
        lab_run=None,
        incident=None,
        correlation_evidence_id=correlation_evidence_id,
        simulation_id=scope[0],
        configuration_hash=scope[1],
        events=events,
        gaps=gaps,
    )


def replay_for_window(session: Session, request: ReplayWindowRequest) -> ReplayBundleResponse:
    rows = session.scalars(
        select(EvidenceRecord)
        .where(
            EvidenceRecord.evidence_type.in_(request.evidence_types),
            EvidenceRecord.observed_at >= request.observed_from,
            EvidenceRecord.observed_at <= request.observed_to,
            EvidenceRecord.payload["simulation_id"].as_string() == request.simulation_id,
            EvidenceRecord.payload["configuration_hash"].as_string() == request.configuration_hash,
        )
        .order_by(EvidenceRecord.observed_at, EvidenceRecord.evidence_id)
        .limit(MAX_REPLAY_EVENTS + 1)
    ).all()
    if len(rows) > MAX_REPLAY_EVENTS:
        raise ProductReadError("The replay bundle exceeds the 2,000-event bound.")
    verified: list[EvidenceRecord] = []
    gaps: list[str] = []
    for row in rows:
        if verify_record_integrity(row):
            verified.append(row)
        else:
            gaps.append(f"Evidence {row.evidence_id} failed integrity verification.")
    events = _ordered_events([_evidence_event(record) for record in verified])
    return ReplayBundleResponse(
        source_kind="EVIDENCE_WINDOW",
        lab_run_id=None,
        scenario_id=None,
        incident=None,
        correlation_evidence_id=None,
        simulation_id=request.simulation_id,
        configuration_hash=request.configuration_hash,
        observed_from=request.observed_from,
        observed_to=request.observed_to,
        events=tuple(events),
        completeness="PARTIAL" if gaps else "COMPLETE",
        gaps=tuple(gaps),
        truncated=False,
    )


def _incident_bins(session: Session, *, run_id: uuid.UUID) -> dict[str, int]:
    row = (
        session.execute(
            select(
                func.count().label("total"),
                *[
                    func.sum(case((Incident.status == value, 1), else_=0)).label(value)
                    for value in ("OPEN", "INVESTIGATING", "RESOLVED")
                ],
                *[
                    func.sum(case((Incident.severity == value, 1), else_=0)).label(value)
                    for value in ("LOW", "MEDIUM", "HIGH")
                ],
                func.sum(
                    case(
                        ((Incident.severity == "HIGH") & (Incident.status != "RESOLVED"), 1),
                        else_=0,
                    )
                ).label("high_non_resolved"),
                *[
                    func.sum(case((Incident.category == value, 1), else_=0)).label(value)
                    for value in (
                        "ASSET_IDENTITY_ANOMALY",
                        "COMMUNICATION_POLICY_VIOLATION",
                        "CONTROL_COMMAND_INVESTIGATION",
                        "PROCESS_INCONSISTENCY",
                    )
                ],
            )
            .select_from(Incident)
            .join(LabRunIncident, LabRunIncident.incident_id == Incident.incident_id)
            .where(LabRunIncident.run_id == run_id)
        )
        .one()
        ._mapping
    )
    return {key: int(row[key] or 0) for key in row}


def _json_status_bins_for_run(
    session: Session,
    *,
    run_id: uuid.UUID,
    evidence_type: str,
    payload_key: str,
    values: tuple[str, ...],
) -> dict[str, int]:
    status_value = EvidenceRecord.payload[payload_key].as_string()
    row = (
        session.execute(
            select(
                *[
                    func.sum(case((status_value == value, 1), else_=0)).label(value)
                    for value in values
                ]
            )
            .select_from(EvidenceRecord)
            .join(LabRunEvidence, LabRunEvidence.evidence_id == EvidenceRecord.evidence_id)
            .where(
                LabRunEvidence.run_id == run_id,
                EvidenceRecord.evidence_type == evidence_type,
            )
        )
        .one()
        ._mapping
    )
    return {value: int(row[value] or 0) for value in values}


def _latest_run_telemetry(session: Session, run_id: uuid.UUID) -> EvidenceRecord | None:
    return session.scalar(
        select(EvidenceRecord)
        .join(LabRunEvidence, LabRunEvidence.evidence_id == EvidenceRecord.evidence_id)
        .where(
            LabRunEvidence.run_id == run_id,
            EvidenceRecord.evidence_type == "simulator_telemetry",
            EvidenceRecord.payload_schema_version == "2.0.0",
        )
        .order_by(EvidenceRecord.observed_at.desc(), EvidenceRecord.evidence_id.desc())
        .limit(1)
    )


def _product_asset(
    asset_key: str, inventory: LoadedInventory, protocol: LoadedProfile
) -> ProductAsset:
    definition = inventory.assets[asset_key]
    return ProductAsset(
        asset_id=deterministic_asset_id(
            inventory_profile_id=inventory.profile.profile_id,
            asset_key=asset_key,
        ),
        definition=definition,
        process_point_ids=tuple(
            point.point_id for point in protocol.profile.points if point.component == asset_key
        ),
    )


def _verified_closure(
    session: Session,
    roots: dict[uuid.UUID, str],
    *,
    expected_scope: tuple[str | None, str | None],
) -> tuple[list[EvidenceRecord], list[str]]:
    pending = list(roots.items())
    visited: set[uuid.UUID] = set()
    accepted: list[EvidenceRecord] = []
    gaps: list[str] = []
    while pending:
        evidence_id, expected_digest = pending.pop(0)
        if evidence_id in visited:
            continue
        visited.add(evidence_id)
        record = session.get(EvidenceRecord, evidence_id)
        if record is None:
            gaps.append(f"Referenced evidence {evidence_id} is unavailable.")
            continue
        if record.integrity_sha256 != expected_digest or not verify_record_integrity(record):
            gaps.append(f"Referenced evidence {evidence_id} failed integrity verification.")
            continue
        scope = _record_scope(record)
        if scope[0] is not None and expected_scope[0] is not None and scope != expected_scope:
            gaps.append(
                f"Referenced evidence {evidence_id} belongs to a different run/configuration."
            )
            continue
        accepted.append(record)
        pending.extend(_parent_references(record))
        if len(visited) > MAX_REPLAY_EVENTS:
            raise ProductReadError("The replay lineage exceeds the 2,000-event bound.")
    return accepted, gaps


def _parent_references(record: EvidenceRecord) -> list[tuple[uuid.UUID, str]]:
    payload = record.payload
    pairs: list[tuple[object, object]] = []
    if record.evidence_type == "protocol_semantic_event":
        pairs.append(
            (payload.get("source_evidence_id"), payload.get("source_evidence_integrity_sha256"))
        )
    elif record.evidence_type == "asset_context_event":
        pairs.extend(
            (
                (
                    payload.get("source_evidence_id"),
                    payload.get("source_evidence_integrity_sha256"),
                ),
                (
                    payload.get("semantic_event_id"),
                    payload.get("semantic_evidence_integrity_sha256"),
                ),
            )
        )
    elif record.evidence_type == "communication_policy_finding":
        pairs.extend(
            (
                (
                    payload.get("source_evidence_id"),
                    payload.get("source_evidence_integrity_sha256"),
                ),
                (
                    payload.get("semantic_event_id"),
                    payload.get("semantic_evidence_integrity_sha256"),
                ),
                (
                    payload.get("asset_context_event_id"),
                    record.provenance.get("asset_context_integrity_sha256"),
                ),
            )
        )
    elif record.evidence_type == "correlation_finding":
        for id_key, hash_key in (
            ("primary_cyber_evidence_id", "primary_cyber_evidence_integrity_sha256"),
            ("semantic_evidence_id", "semantic_evidence_integrity_sha256"),
            ("asset_context_evidence_id", "asset_context_evidence_integrity_sha256"),
            ("policy_finding_evidence_id", "policy_finding_evidence_integrity_sha256"),
        ):
            pairs.append((payload.get(id_key), payload.get(hash_key)))
        pairs.extend(
            (item.get("evidence_id"), item.get("integrity_sha256"))
            for item in payload.get("telemetry_parents", [])
            if isinstance(item, dict)
        )
    references: list[tuple[uuid.UUID, str]] = []
    for raw_id, digest in pairs:
        if raw_id is None or not isinstance(digest, str):
            continue
        try:
            references.append((uuid.UUID(str(raw_id)), digest))
        except ValueError:
            continue
    return references


def _record_scope(record: EvidenceRecord) -> tuple[str | None, str | None]:
    simulation_id = record.payload.get("simulation_id")
    configuration_hash = record.payload.get("configuration_hash")
    return (
        simulation_id if isinstance(simulation_id, str) else None,
        configuration_hash if isinstance(configuration_hash, str) else None,
    )


def _evidence_event(record: EvidenceRecord) -> ReplayEvent:
    event_class, rank = EVENT_CLASS[record.evidence_type]
    return ReplayEvent(
        event_id=record.evidence_id,
        event_class=event_class,
        sort_rank=rank,
        observed_at=record.observed_at,
        summary=_evidence_summary(record),
        evidence=evidence_record_response(record),
        integrity_verified=True,
    )


def _evidence_summary(record: EvidenceRecord) -> str:
    payload: dict[str, Any] = record.payload
    for key in ("semantic_statement", "analyst_readable_statement", "analyst_readable_explanation"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    labels = {
        "synthetic_protocol_event": "Offline synthetic protocol record.",
        "asset_context_event": "Synthetic asset and zone context resolved.",
        "simulator_telemetry": "Stored synthetic process telemetry observation.",
    }
    return labels.get(record.evidence_type, "Stored synthetic evidence record.")


def _ordered_events(events: Iterable[ReplayEvent]) -> list[ReplayEvent]:
    return sorted(events, key=lambda item: (item.observed_at, item.sort_rank, str(item.event_id)))


def _enforce_bundle_bound(events: list[ReplayEvent]) -> None:
    if len(events) > MAX_REPLAY_EVENTS:
        raise ProductReadError("The replay bundle exceeds the 2,000-event bound.")


def _bundle(
    *,
    source_kind: str,
    lab_run: LabRun | None,
    incident: Any,
    correlation_evidence_id: uuid.UUID | None,
    simulation_id: str | None,
    configuration_hash: str | None,
    events: list[ReplayEvent],
    gaps: list[str],
) -> ReplayBundleResponse:
    return ReplayBundleResponse(
        source_kind=source_kind,
        lab_run_id=lab_run.run_id if lab_run is not None else None,
        scenario_id=lab_run.scenario_id if lab_run is not None else None,
        incident=incident,
        correlation_evidence_id=correlation_evidence_id,
        simulation_id=simulation_id,
        configuration_hash=configuration_hash,
        observed_from=events[0].observed_at if events else None,
        observed_to=events[-1].observed_at if events else None,
        events=tuple(events),
        completeness="PARTIAL" if gaps else "COMPLETE",
        gaps=tuple(gaps),
        truncated=False,
    )


def _incident_lab_run(
    session: Session, incident_id: uuid.UUID, *, run_id: uuid.UUID | None
) -> LabRun | None:
    statement = (
        select(LabRun)
        .join(LabRunIncident, LabRunIncident.run_id == LabRun.run_id)
        .where(LabRunIncident.incident_id == incident_id)
    )
    if run_id is not None:
        run = session.scalar(statement.where(LabRun.run_id == run_id))
        if run is None:
            raise ProductNotFoundError(
                "The incident is not associated with the requested synthetic run."
            )
        return run
    context = session.get(LabActiveContext, 1)
    if context is not None:
        current = session.scalar(statement.where(LabRun.run_id == context.active_run_id))
        if current is not None:
            return current
    return session.scalar(statement.order_by(LabRun.started_at.desc(), LabRun.run_id).limit(1))
