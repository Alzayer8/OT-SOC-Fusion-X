from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.incidents.audit import append_audit_event
from app.incidents.grouping import grouping_epoch_start
from app.incidents.identity import IncidentIdentity, deterministic_incident_identity
from app.incidents.lifecycle import STATUS_HISTORY_ID_NAMESPACE
from app.incidents.memberships import verify_qualification_evidence
from app.incidents.models import (
    INCIDENT_PROFILE_ID,
    INCIDENT_PROFILE_VERSION,
    INCIDENT_SCHEMA,
    INCIDENT_SCHEMA_VERSION,
    AuditAction,
    CandidateMembership,
    EvidenceRole,
    Incident,
    IncidentEvidenceMembership,
    IncidentQualificationReceipt,
    IncidentQualificationRequest,
    IncidentSeverityHistory,
    IncidentStatus,
    IncidentStatusHistory,
    QualifiedIncidentCandidate,
    TimelineEntryType,
)
from app.incidents.profile import LoadedIncidentProfile, load_incident_profile
from app.incidents.qualification import qualify_incident
from app.incidents.repository import incident_response
from app.incidents.severity import (
    SEVERITY_HISTORY_ID_NAMESPACE,
    record_severity_escalation,
    severity_increases,
)
from app.incidents.timeline import append_timeline_entry

MEMBERSHIP_ID_NAMESPACE = uuid.UUID("a441344d-2a87-5468-9d40-e1f40cff84d2")


class IncidentPersistenceError(ValueError):
    pass


def qualify_stored_evidence(
    session: Session,
    request: IncidentQualificationRequest,
    *,
    recorded_at: datetime | None = None,
    request_id: str = "offline-incident-qualification",
) -> IncidentQualificationReceipt:
    now = recorded_at or datetime.now(UTC)
    profile = load_incident_profile()
    bundle = verify_qualification_evidence(session, request)
    candidate = qualify_incident(bundle, profile)
    if candidate is None:
        return IncidentQualificationReceipt(
            outcome="evidence_only",
            incident_id=None,
            incident=None,
            reason="Verified evidence does not satisfy a frozen incident qualification rule.",
        )
    epoch = grouping_epoch_start(candidate.grouping_anchor)
    identity = deterministic_incident_identity(
        candidate,
        profile_id=profile.profile.profile_id,
        profile_version=profile.profile.profile_version,
        profile_sha256=profile.sha256,
        grouping_epoch=epoch,
    )
    incident, created = _insert_or_load_incident(
        session,
        candidate,
        identity,
        profile,
        epoch=epoch,
        now=now,
        request_id=request_id,
    )
    if not created and _requires_separate_bound_scope(incident, candidate):
        candidate = candidate.model_copy(
            update={
                "run_scope": candidate.bound_simulation_id,
                "configuration_scope": candidate.bound_configuration_hash,
            }
        )
        identity = deterministic_incident_identity(
            candidate,
            profile_id=profile.profile.profile_id,
            profile_version=profile.profile.profile_version,
            profile_sha256=profile.sha256,
            grouping_epoch=epoch,
        )
        incident, created = _insert_or_load_incident(
            session,
            candidate,
            identity,
            profile,
            epoch=epoch,
            now=now,
            request_id=request_id,
        )
    outcome = (
        "created"
        if created
        else _enrich_incident(
            session,
            incident,
            candidate,
            now=now,
            request_id=request_id,
        )
    )
    session.flush()
    session.refresh(incident)
    return IncidentQualificationReceipt(
        outcome=outcome,
        incident_id=incident.incident_id,
        incident=incident_response(incident),
        reason=(
            "A frozen qualification rule created a deterministic incident."
            if outcome == "created"
            else "The deterministic incident was enriched with compatible verified evidence."
            if outcome == "enriched"
            else "The deterministic incident and memberships already existed."
        ),
    )


def _insert_or_load_incident(
    session: Session,
    candidate: QualifiedIncidentCandidate,
    identity: IncidentIdentity,
    profile: LoadedIncidentProfile,
    *,
    epoch: datetime,
    now: datetime,
    request_id: str,
) -> tuple[Incident, bool]:
    primary = candidate.primary_membership
    values = {
        "incident_id": identity.incident_id,
        "incident_schema": INCIDENT_SCHEMA,
        "incident_schema_version": INCIDENT_SCHEMA_VERSION,
        "incident_profile_id": INCIDENT_PROFILE_ID,
        "incident_profile_version": INCIDENT_PROFILE_VERSION,
        "incident_profile_sha256": profile.sha256,
        "qualification_rule_id": candidate.qualification_rule_id,
        "qualification_rule_version": candidate.qualification_rule_version,
        "grouping_key_sha256": identity.grouping_key_sha256,
        "category": candidate.category.value,
        "title": candidate.title,
        "summary": candidate.summary,
        "status": IncidentStatus.OPEN.value,
        "severity": candidate.severity.value,
        "primary_evidence_id": primary.evidence_id,
        "primary_evidence_type": primary.evidence_type,
        "primary_evidence_schema": primary.evidence_schema,
        "primary_evidence_schema_version": primary.evidence_schema_version,
        "primary_evidence_integrity_sha256": primary.integrity_sha256,
        "identity_asset_scope": list(sorted(candidate.identity_asset_scope)),
        "source_asset_id": candidate.source_asset_id,
        "destination_asset_id": candidate.destination_asset_id,
        "controller_asset_id": candidate.controller_asset_id,
        "process_asset_ids": list(candidate.process_asset_ids),
        "process_asset_keys": list(candidate.process_asset_keys),
        "target_point_ids": list(candidate.target_point_scope),
        "correlation_rule_id": candidate.correlation_rule_id,
        "correlation_rule_version": candidate.correlation_rule_version,
        "run_scope": candidate.run_scope,
        "configuration_scope": candidate.configuration_scope,
        "bound_simulation_id": candidate.bound_simulation_id,
        "bound_configuration_hash": candidate.bound_configuration_hash,
        "s3_semantic_evidence_id": candidate.s3_semantic_evidence_id,
        "grouping_epoch_start": epoch,
        "first_observed_at": candidate.first_observed_at,
        "last_observed_at": candidate.last_observed_at,
        "policy_context": candidate.policy_context,
        "correlation_context": candidate.correlation_context,
        "evidence_completeness": candidate.evidence_completeness,
        "version": 1,
        "evidence_count": 1 + len(candidate.additional_memberships),
        "ground_truth_used": False,
        "malicious_intent_inferred": False,
        "causality_inferred": False,
        "created_at": now,
        "updated_at": now,
    }
    inserted = session.execute(
        insert(Incident)
        .values(**values)
        .on_conflict_do_nothing(constraint="uq_incidents_grouping_key")
        .returning(Incident.incident_id)
    ).scalar_one_or_none()
    if inserted is None:
        existing = session.scalar(
            select(Incident)
            .where(Incident.grouping_key_sha256 == identity.grouping_key_sha256)
            .with_for_update()
        )
        if existing is None:
            raise IncidentPersistenceError("Incident uniqueness conflict could not be resolved.")
        if existing.incident_id != identity.incident_id:
            raise IncidentPersistenceError("Incident grouping identity is inconsistent.")
        return existing, False
    incident = session.scalar(
        select(Incident).where(Incident.incident_id == inserted).with_for_update()
    )
    if incident is None:
        raise IncidentPersistenceError("Created incident could not be reloaded.")
    _record_creation(session, incident, candidate, now=now, request_id=request_id)
    return incident, True


def _record_creation(
    session: Session,
    incident: Incident,
    candidate: QualifiedIncidentCandidate,
    *,
    now: datetime,
    request_id: str,
) -> None:
    memberships = (candidate.primary_membership, *candidate.additional_memberships)
    for membership in memberships:
        _insert_membership(session, incident, membership, now=now)
    status_name = "|".join((str(incident.incident_id), "INITIAL", IncidentStatus.OPEN.value))
    session.add(
        IncidentStatusHistory(
            status_history_id=uuid.uuid5(STATUS_HISTORY_ID_NAMESPACE, status_name),
            incident_id=incident.incident_id,
            previous_status=None,
            new_status=IncidentStatus.OPEN.value,
            changed_at=now,
            actor_context="SYSTEM",
            reason=None,
            request_id=request_id,
            version_before=0,
            version_after=1,
        )
    )
    severity_name = "|".join((str(incident.incident_id), "INITIAL", candidate.severity.value))
    session.add(
        IncidentSeverityHistory(
            severity_history_id=uuid.uuid5(SEVERITY_HISTORY_ID_NAMESPACE, severity_name),
            incident_id=incident.incident_id,
            previous_severity=None,
            new_severity=candidate.severity.value,
            triggering_evidence_id=candidate.primary_membership.evidence_id,
            triggering_integrity_sha256=candidate.primary_membership.integrity_sha256,
            profile_version=incident.incident_profile_version,
            rule_version=incident.qualification_rule_version,
            calculated_at=now,
            aggregate_version=1,
        )
    )
    append_timeline_entry(
        session,
        incident,
        entry_type=TimelineEntryType.INCIDENT_CREATED,
        reference_id=incident.incident_id,
        observed_at=candidate.primary_membership.observed_at,
        recorded_at=now,
        summary="A frozen qualification rule created this analyst investigation container.",
        actor_context="SYSTEM",
        aggregate_version=1,
    )
    append_audit_event(
        session,
        incident,
        action=AuditAction.INCIDENT_CREATED,
        occurred_at=now,
        actor_context="SYSTEM",
        request_id=request_id,
        result="ACCEPTED",
        safe_reason="Verified stored evidence satisfied a frozen qualification rule.",
        version_before=0,
        version_after=1,
        details={"qualification_rule_id": incident.qualification_rule_id},
    )


def _enrich_incident(
    session: Session,
    incident: Incident,
    candidate: QualifiedIncidentCandidate,
    *,
    now: datetime,
    request_id: str,
) -> str:
    if incident.qualification_rule_id != candidate.qualification_rule_id:
        raise IncidentPersistenceError("Qualification rule mismatch prevents incident grouping.")
    before = incident.version
    inserted_memberships: list[CandidateMembership] = []
    proposed_memberships = (candidate.primary_membership, *candidate.additional_memberships)
    for membership in proposed_memberships:
        effective = membership
        if (
            membership.role is EvidenceRole.PRIMARY
            and membership.evidence_id != incident.primary_evidence_id
        ):
            effective = membership.model_copy(update={"role": EvidenceRole.SUPPORTING})
        if _insert_membership(session, incident, effective, now=now):
            inserted_memberships.append(effective)
    binding_changed = _bind_s3_scope(incident, candidate)
    severity_changed = severity_increases(incident.severity, candidate.severity)
    if not inserted_memberships and not binding_changed and not severity_changed:
        return "existing"
    after = before + 1
    incident.version = after
    incident.updated_at = now
    incident.evidence_count += len(inserted_memberships)
    incident.first_observed_at = min(incident.first_observed_at, candidate.first_observed_at)
    incident.last_observed_at = max(incident.last_observed_at, candidate.last_observed_at)
    incident.policy_context = candidate.policy_context
    incident.correlation_context = candidate.correlation_context
    incident.evidence_completeness = candidate.evidence_completeness
    process = {
        key: asset_id
        for key, asset_id in zip(
            incident.process_asset_keys,
            incident.process_asset_ids,
            strict=True,
        )
    }
    process.update(
        dict(zip(candidate.process_asset_keys, candidate.process_asset_ids, strict=True))
    )
    incident.process_asset_keys = sorted(process)
    incident.process_asset_ids = [process[key] for key in incident.process_asset_keys]
    incident.target_point_ids = sorted(
        set(incident.target_point_ids) | set(candidate.target_point_scope)
    )
    for membership in inserted_memberships:
        append_timeline_entry(
            session,
            incident,
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            reference_id=membership.evidence_id,
            observed_at=membership.observed_at,
            recorded_at=now,
            summary="Compatible verified evidence was added to this investigation container.",
            actor_context="SYSTEM",
            aggregate_version=after,
            membership=membership,
        )
        append_audit_event(
            session,
            incident,
            action=AuditAction.EVIDENCE_ENRICHED,
            occurred_at=now,
            actor_context="SYSTEM",
            request_id=request_id,
            result="ACCEPTED",
            safe_reason="Verified evidence matched the deterministic incident grouping scope.",
            version_before=before,
            version_after=after,
            details={"evidence_id": str(membership.evidence_id), "role": membership.role.value},
        )
    if severity_changed:
        trigger = next(
            (item for item in inserted_memberships if item.evidence_type == "correlation_finding"),
            candidate.primary_membership,
        )
        record_severity_escalation(
            session,
            incident,
            proposed=candidate.severity,
            triggering_membership=trigger,
            calculated_at=now,
            request_id=request_id,
            version_before=before,
            version_after=after,
        )
    return "enriched"


def _insert_membership(
    session: Session,
    incident: Incident,
    membership: CandidateMembership,
    *,
    now: datetime,
) -> bool:
    membership_id = uuid.uuid5(
        MEMBERSHIP_ID_NAMESPACE,
        f"{incident.incident_id}|{membership.evidence_id}",
    )
    inserted = session.execute(
        insert(IncidentEvidenceMembership)
        .values(
            membership_id=membership_id,
            incident_id=incident.incident_id,
            evidence_id=membership.evidence_id,
            evidence_type=membership.evidence_type,
            evidence_schema=membership.evidence_schema,
            evidence_schema_version=membership.evidence_schema_version,
            integrity_sha256=membership.integrity_sha256,
            role=membership.role.value,
            observed_at=membership.observed_at,
            received_at=membership.received_at,
            added_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_incident_evidence_membership")
        .returning(IncidentEvidenceMembership.membership_id)
    ).scalar_one_or_none()
    return inserted is not None


def _bind_s3_scope(incident: Incident, candidate: QualifiedIncidentCandidate) -> bool:
    incoming_run = candidate.bound_simulation_id
    incoming_config = candidate.bound_configuration_hash
    if incoming_run is None and incoming_config is None:
        return False
    if incoming_run is None or incoming_config is None:
        raise IncidentPersistenceError("S3 binding requires both run and configuration.")
    if incident.bound_simulation_id is None and incident.bound_configuration_hash is None:
        incident.bound_simulation_id = incoming_run
        incident.bound_configuration_hash = incoming_config
        return True
    if (
        incident.bound_simulation_id != incoming_run
        or incident.bound_configuration_hash != incoming_config
    ):
        raise IncidentPersistenceError("A bound incident cannot mix run/configuration scope.")
    return False


def _requires_separate_bound_scope(
    incident: Incident,
    candidate: QualifiedIncidentCandidate,
) -> bool:
    return bool(
        candidate.bound_simulation_id is not None
        and candidate.bound_configuration_hash is not None
        and incident.bound_simulation_id is not None
        and incident.bound_configuration_hash is not None
        and (
            incident.bound_simulation_id != candidate.bound_simulation_id
            or incident.bound_configuration_hash != candidate.bound_configuration_hash
        )
    )
