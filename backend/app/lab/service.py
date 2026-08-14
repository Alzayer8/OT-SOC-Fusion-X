from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.audit import append_soc_audit_event
from app.auth.models import SocAuditAction, SocAuditResult
from app.core.config import Settings
from app.evidence.models import EvidenceRecord
from app.evidence.service import verify_record_integrity
from app.incidents.models import Incident
from app.lab.catalog import (
    LabScenarioId,
    dataset_case,
    loaded_lab_dataset,
    scenario_catalog,
    scenario_definition,
)
from app.lab.models import (
    LabActivationReason,
    LabActiveContext,
    LabEvidenceRole,
    LabRun,
    LabRunEvidence,
    LabRunIncident,
    LabRunState,
)
from app.lab.schemas import (
    LabCatalogResponse,
    LabContextResponse,
    LabRunListResponse,
    LabRunResponse,
    LabScenarioCatalogItem,
    LabStartResponse,
)
from app.tools.phase9_demo_seed import DatasetCaseExecution, execute_dataset_case

LAB_CONTEXT_SINGLETON_ID = 1
MAX_LINKED_EVIDENCE = 2_000
BASELINE_RUN_NAMESPACE = uuid.UUID("79b9f46c-c7b9-5b57-a838-93639aa982a0")


class LabError(ValueError):
    pass


class LabNotInitializedError(LabError):
    pass


class LabRunNotFoundError(LabError):
    pass


class LabRunConflictError(LabError):
    pass


class LabPipelineError(LabError):
    pass


class LabIntegrityError(LabError):
    pass


def read_catalog() -> LabCatalogResponse:
    loaded = loaded_lab_dataset()
    return LabCatalogResponse(
        dataset_id=loaded.manifest.dataset_id,
        dataset_version=loaded.manifest.dataset_version,
        dataset_sha256=loaded.sha256,
        items=tuple(
            LabScenarioCatalogItem(
                scenario_id=item.scenario_id,
                title=item.title,
                description=item.description,
                dataset_case_id=item.dataset_case_id,
                definition_version=item.definition_version,
                synthetic=item.synthetic,
                execution_mode=item.execution_mode,
            )
            for item in scenario_catalog()
        ),
    )


def startup_baseline(
    settings: Settings,
    session: Session,
    *,
    actor_context: str = "SYSTEM",
    occurred_at: datetime | None = None,
) -> LabContextResponse:
    """Recover interrupted runs and make the verified Baseline active on every start."""

    now = occurred_at or datetime.now(UTC)
    stale = session.scalars(
        select(LabRun).where(LabRun.state == LabRunState.RUNNING.value).with_for_update()
    ).all()
    for run in stale:
        _mark_failed(run, now=now, failure_code="BACKEND_RESTARTED")
    session.commit()

    baseline = _ensure_baseline(
        settings,
        session,
        actor_user_id=None,
        actor_context=actor_context,
        occurred_at=now,
    )
    return _activate_run(
        session,
        baseline,
        actor_user_id=None,
        actor_context=actor_context,
        reason=LabActivationReason.STARTUP_BASELINE,
        occurred_at=now,
    )


def start_scenario(
    settings: Settings,
    session: Session,
    scenario_id: LabScenarioId,
    *,
    actor_user_id: uuid.UUID,
    actor_context: str,
    request_id: str,
    occurred_at: datetime | None = None,
) -> LabStartResponse:
    if scenario_id is LabScenarioId.BASELINE:
        raise LabError("BASELINE is selected through the dedicated return-to-Baseline operation.")
    now = occurred_at or datetime.now(UTC)
    if session.scalar(
        select(func.count()).select_from(LabRun).where(LabRun.state == LabRunState.RUNNING.value)
    ):
        raise LabRunConflictError("Another synthetic scenario run is already in progress.")
    run = _new_run(
        scenario_id,
        actor_user_id=actor_user_id,
        actor_context=actor_context,
        started_at=now,
    )
    session.add(run)
    try:
        # The audit row has a restrictive FK to this run. Flush the run first so insertion
        # ordering stays explicit even though the tables live in separate feature modules.
        session.flush()
        append_soc_audit_event(
            session,
            action=SocAuditAction.SCENARIO_STARTED,
            result=SocAuditResult.ACCEPTED,
            request_id=request_id,
            actor_user_id=actor_user_id,
            subject_label=scenario_id.value,
            scenario_run_id=run.run_id,
            details={
                "scenario_id": scenario_id.value,
                "dataset_case_id": run.dataset_case_id,
            },
            occurred_at=now,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise LabRunConflictError("Another synthetic scenario run is already in progress.") from exc

    completed = _execute_run(
        settings,
        session,
        run.run_id,
        scenario_id,
        audit_actor_user_id=actor_user_id,
        audit_request_id=request_id,
    )
    completed_at = completed.completed_at or datetime.now(UTC)
    context = _activate_run(
        session,
        completed,
        actor_user_id=actor_user_id,
        actor_context=actor_context,
        reason=LabActivationReason.SCENARIO_COMPLETED,
        occurred_at=completed_at,
    )
    return LabStartResponse(
        active_run=context.active_run,
        run=_run_response(session, completed),
    )


def activate_baseline(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    actor_context: str,
    request_id: str,
    occurred_at: datetime | None = None,
) -> LabContextResponse:
    baseline = _completed_baseline(session)
    now = occurred_at or datetime.now(UTC)
    append_soc_audit_event(
        session,
        action=SocAuditAction.RETURNED_TO_BASELINE,
        result=SocAuditResult.ACCEPTED,
        request_id=request_id,
        actor_user_id=actor_user_id,
        subject_label=LabScenarioId.BASELINE.value,
        scenario_run_id=baseline.run_id,
        details={"scenario_id": LabScenarioId.BASELINE.value},
        occurred_at=now,
    )
    context = _activate_run(
        session,
        baseline,
        actor_user_id=actor_user_id,
        actor_context=actor_context,
        reason=LabActivationReason.RETURN_BASELINE,
        occurred_at=now,
    )
    return context


def reset_lab(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    actor_context: str,
    request_id: str,
    occurred_at: datetime | None = None,
) -> LabContextResponse:
    """Project-local reset: select Baseline and retain every immutable historical row."""

    running = session.scalar(
        select(func.count()).select_from(LabRun).where(LabRun.state == LabRunState.RUNNING.value)
    )
    if running:
        raise LabRunConflictError("The synthetic lab cannot reset while a run is in progress.")
    baseline = _completed_baseline(session)
    now = occurred_at or datetime.now(UTC)
    append_soc_audit_event(
        session,
        action=SocAuditAction.LAB_RESET,
        result=SocAuditResult.ACCEPTED,
        request_id=request_id,
        actor_user_id=actor_user_id,
        subject_label="SCENARIO_LAB",
        scenario_run_id=baseline.run_id,
        details={
            "active_scenario_id": LabScenarioId.BASELINE.value,
            "history_retained": True,
        },
        occurred_at=now,
    )
    context = _activate_run(
        session,
        baseline,
        actor_user_id=actor_user_id,
        actor_context=actor_context,
        reason=LabActivationReason.RESET,
        occurred_at=now,
    )
    return context


def read_current_context(session: Session) -> LabContextResponse:
    context = session.get(LabActiveContext, LAB_CONTEXT_SINGLETON_ID)
    if context is None:
        raise LabNotInitializedError("The Synthetic Scenario Lab has not been initialized.")
    run = session.get(LabRun, context.active_run_id)
    if run is None or run.state != LabRunState.COMPLETED.value:
        raise LabIntegrityError("The active lab context does not reference a completed run.")
    return LabContextResponse(
        context_version=context.version,
        activation_reason=LabActivationReason(context.activation_reason),
        changed_at=context.changed_at,
        changed_by_user_id=context.changed_by_user_id,
        changed_by_actor=context.changed_by_actor,
        active_run=_run_response(session, run),
    )


def read_run(session: Session, run_id: uuid.UUID) -> LabRunResponse:
    run = session.get(LabRun, run_id)
    if run is None:
        raise LabRunNotFoundError("The synthetic scenario run was not found.")
    return _run_response(session, run)


def list_run_history(
    session: Session,
    *,
    scenario_id: LabScenarioId | None,
    state: LabRunState | None,
    limit: int,
    offset: int,
) -> LabRunListResponse:
    filters: list[Any] = []
    if scenario_id is not None:
        filters.append(LabRun.scenario_id == scenario_id.value)
    if state is not None:
        filters.append(LabRun.state == state.value)
    total = session.scalar(select(func.count()).select_from(LabRun).where(*filters))
    runs = session.scalars(
        select(LabRun)
        .where(*filters)
        .order_by(LabRun.started_at.desc(), LabRun.run_id)
        .limit(limit)
        .offset(offset)
    ).all()
    return LabRunListResponse(
        items=tuple(_run_response(session, item) for item in runs),
        limit=limit,
        offset=offset,
        total=int(total or 0),
    )


def _ensure_baseline(
    settings: Settings,
    session: Session,
    *,
    actor_user_id: uuid.UUID | None,
    actor_context: str,
    occurred_at: datetime,
) -> LabRun:
    baseline = session.scalar(
        select(LabRun).where(LabRun.scenario_id == LabScenarioId.BASELINE.value)
    )
    if baseline is None:
        baseline = _new_run(
            LabScenarioId.BASELINE,
            actor_user_id=actor_user_id,
            actor_context=actor_context,
            started_at=occurred_at,
            run_id=_baseline_run_id(),
        )
        session.add(baseline)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            baseline = session.scalar(
                select(LabRun).where(LabRun.scenario_id == LabScenarioId.BASELINE.value)
            )
            if baseline is None:
                raise LabRunConflictError("The Baseline run could not be initialized.") from exc
    elif baseline.state != LabRunState.COMPLETED.value:
        baseline.state = LabRunState.RUNNING.value
        baseline.completed_at = None
        baseline.failure_code = None
        baseline.updated_at = occurred_at
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise LabRunConflictError(
                "The Baseline cannot initialize while another run is in progress."
            ) from exc

    # Re-execution is intentionally idempotent. It verifies the frozen inputs and repairs only
    # missing association rows; source evidence and incidents remain immutable.
    completed = _execute_run(
        settings,
        session,
        baseline.run_id,
        LabScenarioId.BASELINE,
        completed_at=occurred_at,
    )
    incident_count = session.scalar(
        select(func.count())
        .select_from(LabRunIncident)
        .where(LabRunIncident.run_id == completed.run_id)
    )
    if incident_count:
        raise LabIntegrityError("The verified Baseline unexpectedly references an incident.")
    return completed


def _execute_run(
    settings: Settings,
    session: Session,
    run_id: uuid.UUID,
    scenario_id: LabScenarioId,
    *,
    completed_at: datetime | None = None,
    audit_actor_user_id: uuid.UUID | None = None,
    audit_request_id: str | None = None,
) -> LabRun:
    try:
        execution = execute_dataset_case(settings, dataset_case(scenario_id))
        finished_at = completed_at or datetime.now(UTC)
        run = session.get(LabRun, run_id)
        if run is None:
            raise LabIntegrityError("The scenario run disappeared during execution.")
        records = _verified_execution_closure(session, execution, scenario_id)
        _link_execution(
            session,
            run,
            execution,
            records,
            linked_at=finished_at,
        )
        run.state = LabRunState.COMPLETED.value
        run.completed_at = finished_at
        run.failure_code = None
        run.updated_at = finished_at
        if records:
            run.evidence_observed_from = min(item.observed_at for item in records)
            run.evidence_observed_to = max(item.observed_at for item in records)
        if audit_actor_user_id is not None and audit_request_id is not None:
            append_soc_audit_event(
                session,
                action=SocAuditAction.SCENARIO_COMPLETED,
                result=SocAuditResult.ACCEPTED,
                request_id=audit_request_id,
                actor_user_id=audit_actor_user_id,
                subject_label=scenario_id.value,
                scenario_run_id=run.run_id,
                details={
                    "scenario_id": scenario_id.value,
                    "dataset_case_id": run.dataset_case_id,
                    "evidence_count": len(records),
                    "incident_count": len(execution.incident_ids),
                },
                occurred_at=finished_at,
            )
        session.commit()
        return run
    except Exception as exc:
        session.rollback()
        failed_at = completed_at or datetime.now(UTC)
        failed = session.get(LabRun, run_id)
        if failed is not None:
            _mark_failed(
                failed,
                now=failed_at,
                failure_code="PIPELINE_EXECUTION_FAILED",
            )
            if audit_actor_user_id is not None and audit_request_id is not None:
                append_soc_audit_event(
                    session,
                    action=SocAuditAction.SCENARIO_COMPLETED,
                    result=SocAuditResult.FAILED,
                    request_id=audit_request_id,
                    actor_user_id=audit_actor_user_id,
                    subject_label=scenario_id.value,
                    scenario_run_id=failed.run_id,
                    safe_reason="The frozen synthetic scenario pipeline failed safely.",
                    details={"scenario_id": scenario_id.value},
                    occurred_at=failed_at,
                )
            session.commit()
        if isinstance(exc, LabError):
            raise
        raise LabPipelineError("The frozen synthetic scenario pipeline failed safely.") from exc


def _new_run(
    scenario_id: LabScenarioId,
    *,
    actor_user_id: uuid.UUID | None,
    actor_context: str,
    started_at: datetime,
    run_id: uuid.UUID | None = None,
) -> LabRun:
    if not 1 <= len(actor_context) <= 80:
        raise LabError("The authenticated actor identity is outside the approved bound.")
    loaded = loaded_lab_dataset()
    definition = scenario_definition(scenario_id)
    case = dataset_case(scenario_id)
    return LabRun(
        run_id=run_id or uuid.uuid4(),
        scenario_id=scenario_id.value,
        definition_version=definition.definition_version,
        dataset_id=loaded.manifest.dataset_id,
        dataset_version=loaded.manifest.dataset_version,
        dataset_sha256=loaded.sha256,
        dataset_case_id=case.case_id,
        evidence_simulation_id=case.run_id,
        configuration_id=(
            case.configuration.configuration_id if case.configuration is not None else None
        ),
        configuration_hash=case.configuration_hash,
        state=LabRunState.RUNNING.value,
        started_by_user_id=actor_user_id,
        started_by_actor=actor_context,
        started_at=started_at,
        completed_at=None,
        evidence_observed_from=None,
        evidence_observed_to=None,
        failure_code=None,
        created_at=started_at,
        updated_at=started_at,
    )


def _link_execution(
    session: Session,
    run: LabRun,
    execution: DatasetCaseExecution,
    records: tuple[EvidenceRecord, ...],
    *,
    linked_at: datetime,
) -> None:
    if execution.case_id != run.dataset_case_id:
        raise LabIntegrityError("The executed case does not match the scenario run contract.")
    root_ids = {item.selection.evidence_id for item in execution.evidence_roots}
    for record in records:
        session.execute(
            insert(LabRunEvidence)
            .values(
                run_id=run.run_id,
                evidence_id=record.evidence_id,
                role=(
                    LabEvidenceRole.ROOT.value
                    if record.evidence_id in root_ids
                    else LabEvidenceRole.LINEAGE.value
                ),
                linked_at=linked_at,
            )
            .on_conflict_do_nothing(index_elements=("run_id", "evidence_id"))
        )
    for incident_id in execution.incident_ids:
        incident = session.get(Incident, incident_id)
        if incident is None:
            raise LabIntegrityError("A resulting incident could not be verified.")
        session.execute(
            insert(LabRunIncident)
            .values(run_id=run.run_id, incident_id=incident_id, linked_at=linked_at)
            .on_conflict_do_nothing(index_elements=("run_id", "incident_id"))
        )


def _verified_execution_closure(
    session: Session,
    execution: DatasetCaseExecution,
    scenario_id: LabScenarioId,
) -> tuple[EvidenceRecord, ...]:
    roots = [
        (item.selection.evidence_id, item.selection.expected_integrity_sha256)
        for item in execution.evidence_roots
    ]
    if not roots:
        raise LabIntegrityError("The scenario execution did not produce an evidence root.")
    case = dataset_case(scenario_id)
    expected_scope = (case.run_id, case.configuration_hash)
    pending = list(roots)
    visited: set[uuid.UUID] = set()
    accepted: dict[uuid.UUID, EvidenceRecord] = {}
    while pending:
        evidence_id, expected_digest = pending.pop(0)
        if evidence_id in visited:
            existing = accepted.get(evidence_id)
            if existing is not None and existing.integrity_sha256 != expected_digest:
                raise LabIntegrityError("One evidence parent was referenced with two digests.")
            continue
        visited.add(evidence_id)
        record = session.scalar(
            select(EvidenceRecord)
            .options(joinedload(EvidenceRecord.source))
            .where(EvidenceRecord.evidence_id == evidence_id)
        )
        if record is None:
            raise LabIntegrityError("A required scenario evidence record is unavailable.")
        if record.integrity_sha256 != expected_digest or not verify_record_integrity(record):
            raise LabIntegrityError("A required scenario evidence record failed verification.")
        scope = _record_scope(record)
        if scope != (None, None) and scope != expected_scope:
            raise LabIntegrityError(
                "A scenario evidence record belongs to a different run/configuration."
            )
        if expected_scope == (None, None) and scope != (None, None):
            raise LabIntegrityError("An unbound scenario referenced process-run evidence.")
        accepted[evidence_id] = record
        pending.extend(_parent_references(record))
        if len(visited) > MAX_LINKED_EVIDENCE:
            raise LabIntegrityError("The scenario evidence closure exceeds its bound.")
    return tuple(
        sorted(
            accepted.values(),
            key=lambda item: (item.observed_at, item.evidence_type, str(item.evidence_id)),
        )
    )


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
        for item in payload.get("telemetry_parents", []):
            if not isinstance(item, dict):
                raise LabIntegrityError("A correlation telemetry parent is malformed.")
            pairs.append((item.get("evidence_id"), item.get("integrity_sha256")))
    result: list[tuple[uuid.UUID, str]] = []
    for raw_id, raw_digest in pairs:
        if raw_id is None and raw_digest is None:
            continue
        if not isinstance(raw_digest, str) or len(raw_digest) != 64:
            raise LabIntegrityError("An evidence parent digest is malformed.")
        try:
            parsed_id = uuid.UUID(str(raw_id))
        except (TypeError, ValueError) as exc:
            raise LabIntegrityError("An evidence parent identity is malformed.") from exc
        result.append((parsed_id, raw_digest))
    return result


def _record_scope(record: EvidenceRecord) -> tuple[str | None, str | None]:
    simulation_id = record.payload.get("simulation_id")
    configuration_hash = record.payload.get("configuration_hash")
    return (
        simulation_id if isinstance(simulation_id, str) else None,
        configuration_hash if isinstance(configuration_hash, str) else None,
    )


def _activate_run(
    session: Session,
    run: LabRun,
    *,
    actor_user_id: uuid.UUID | None,
    actor_context: str,
    reason: LabActivationReason,
    occurred_at: datetime,
) -> LabContextResponse:
    if run.state != LabRunState.COMPLETED.value:
        raise LabIntegrityError("Only a completed synthetic run can become active.")
    context = session.scalar(
        select(LabActiveContext)
        .where(LabActiveContext.singleton_id == LAB_CONTEXT_SINGLETON_ID)
        .with_for_update()
    )
    if context is None:
        context = LabActiveContext(
            singleton_id=LAB_CONTEXT_SINGLETON_ID,
            active_run_id=run.run_id,
            version=1,
            changed_at=occurred_at,
            changed_by_user_id=actor_user_id,
            changed_by_actor=actor_context,
            activation_reason=reason.value,
        )
        session.add(context)
    else:
        context.active_run_id = run.run_id
        context.version += 1
        context.changed_at = occurred_at
        context.changed_by_user_id = actor_user_id
        context.changed_by_actor = actor_context
        context.activation_reason = reason.value
    session.commit()
    return read_current_context(session)


def _completed_baseline(session: Session) -> LabRun:
    baseline = session.scalar(
        select(LabRun).where(LabRun.scenario_id == LabScenarioId.BASELINE.value)
    )
    if baseline is None or baseline.state != LabRunState.COMPLETED.value:
        raise LabNotInitializedError("The verified Baseline is not available.")
    return baseline


def _mark_failed(run: LabRun, *, now: datetime, failure_code: str) -> None:
    run.state = LabRunState.FAILED.value
    run.completed_at = now
    run.failure_code = failure_code
    run.updated_at = now


def _run_response(session: Session, run: LabRun) -> LabRunResponse:
    evidence_count = session.scalar(
        select(func.count()).select_from(LabRunEvidence).where(LabRunEvidence.run_id == run.run_id)
    )
    incident_ids = tuple(
        session.scalars(
            select(LabRunIncident.incident_id)
            .where(LabRunIncident.run_id == run.run_id)
            .order_by(LabRunIncident.incident_id)
        ).all()
    )
    scenario_id = LabScenarioId(run.scenario_id)
    return LabRunResponse(
        run_id=run.run_id,
        scenario_id=scenario_id,
        scenario_title=scenario_definition(scenario_id).title,
        definition_version=run.definition_version,
        dataset_id=run.dataset_id,
        dataset_version=run.dataset_version,
        dataset_sha256=run.dataset_sha256,
        dataset_case_id=run.dataset_case_id,
        simulation_id=run.evidence_simulation_id,
        configuration_id=run.configuration_id,
        configuration_hash=run.configuration_hash,
        status=LabRunState(run.state),
        started_by_user_id=run.started_by_user_id,
        started_by=run.started_by_user_id,
        started_by_display_name=run.started_by_actor,
        started_at=run.started_at,
        completed_at=run.completed_at,
        window_start=run.evidence_observed_from,
        window_end=run.evidence_observed_to,
        evidence_count=int(evidence_count or 0),
        incident_count=len(incident_ids),
        incident_ids=incident_ids,
        failure_code=run.failure_code,
    )


def _baseline_run_id() -> uuid.UUID:
    loaded = loaded_lab_dataset()
    identity = "|".join(
        (
            loaded.manifest.dataset_id,
            loaded.manifest.dataset_version,
            loaded.sha256,
            LabScenarioId.BASELINE.value,
        )
    )
    return uuid.uuid5(BASELINE_RUN_NAMESPACE, identity)
