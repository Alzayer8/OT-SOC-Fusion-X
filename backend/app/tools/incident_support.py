from __future__ import annotations

import hashlib
from datetime import datetime

from app.context.adapters import persist_asset_context_and_finding
from app.context.fixtures import load_fixture as load_context_fixture
from app.context.inventory import load_inventory_profile
from app.context.policy import load_policy_profile
from app.core.config import Settings
from app.correlation.fixtures import build_fixture_input
from app.correlation.fixtures import load_fixture as load_correlation_fixture
from app.correlation.persistence import (
    CorrelationPersistenceRequest,
    ParentSelection,
    persist_correlation_finding,
)
from app.correlation.profile import load_correlation_profile
from app.db.session import session_scope
from app.evidence.models import EvidenceRecord
from app.evidence.schemas import EvidenceIngestRequest, EvidenceProvenance, OilGasTelemetryPayloadV2
from app.evidence.service import ingest_evidence
from app.incidents.models import EvidenceSelection, IncidentQualificationRequest
from app.protocols.adapters import persist_raw_event, persist_semantic_evidence
from app.protocols.profile import load_profile


def incident_selection(record: EvidenceRecord) -> EvidenceSelection:
    return EvidenceSelection(
        evidence_id=record.evidence_id,
        expected_integrity_sha256=record.integrity_sha256,
    )


def correlation_selection(record: EvidenceRecord) -> ParentSelection:
    return ParentSelection(
        evidence_id=record.evidence_id,
        expected_integrity_sha256=record.integrity_sha256,
    )


def persist_policy_chain(
    settings: Settings,
    context_fixture: str,
    *,
    receipt_timestamp: datetime | None = None,
) -> EvidenceSelection:
    fixture, fixture_bytes = load_context_fixture(context_fixture)
    protocol = load_profile()
    inventory = load_inventory_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=protocol)
    with session_scope(settings) as session:
        raw = persist_raw_event(
            session,
            fixture.event,
            fixture_bytes=fixture_bytes,
            receipt_timestamp=receipt_timestamp,
        )
    with session_scope(settings) as session:
        semantic, _ = persist_semantic_evidence(
            session,
            raw.evidence_id,
            protocol,
            receipt_timestamp=receipt_timestamp,
        )
    with session_scope(settings) as session:
        workflow = persist_asset_context_and_finding(
            session,
            semantic.evidence_id,
            inventory,
            policy,
            source_claims=fixture.source_identity_claims,
            destination_claims=fixture.destination_identity_claims,
            receipt_timestamp=receipt_timestamp,
        )
        policy_record = session.get(EvidenceRecord, workflow.finding_receipt.evidence_id)
        if policy_record is None:
            raise RuntimeError("policy evidence could not be reloaded")
        return incident_selection(policy_record)


def persist_correlation_chain(
    settings: Settings,
    correlation_fixture: str,
    *,
    context_fixture: str | None = None,
    simulation_id: str | None = None,
    configuration_hash: str | None = None,
    seed: int = 20260809,
    receipt_timestamp: datetime | None = None,
) -> IncidentQualificationRequest:
    policy_selection = (
        persist_policy_chain(
            settings,
            context_fixture,
            receipt_timestamp=receipt_timestamp,
        )
        if context_fixture
        else None
    )
    profile = load_correlation_profile()
    fixture, _ = load_correlation_fixture(correlation_fixture)
    built = build_fixture_input(fixture, profile)
    time_shift = None
    if policy_selection is not None:
        with session_scope(settings) as session:
            policy_record = session.get(EvidenceRecord, policy_selection.evidence_id)
            if policy_record is None:
                raise RuntimeError("policy evidence could not be reloaded")
            semantic_record = session.get(
                EvidenceRecord, policy_record.payload["semantic_event_id"]
            )
            if semantic_record is None or built.cyber_context is None:
                raise RuntimeError("semantic evidence could not be reloaded")
            time_shift = semantic_record.observed_at - built.cyber_context.command_observed_at
    selections: list[ParentSelection] = []
    variant = hashlib.sha256(
        f"{context_fixture}|{simulation_id}|{configuration_hash}".encode()
    ).hexdigest()[:12]
    for item in built.telemetry:
        payload = item.payload.model_copy(
            update={
                "simulation_id": simulation_id or item.payload.simulation_id,
                "configuration_hash": configuration_hash or item.payload.configuration_hash,
                "timestamp": (
                    item.payload.timestamp + time_shift
                    if time_shift is not None
                    else item.payload.timestamp
                ),
            }
        )
        envelope = EvidenceIngestRequest(
            source_key="simulator-primary",
            source_event_id=f"p7b:{fixture.catalog_id}:{variant}:{item.sequence_number}",
            evidence_type="simulator_telemetry",
            observed_at=payload.timestamp,
            sequence_number=item.sequence_number,
            payload_schema="otsoc.simulator.telemetry",
            payload_schema_version="2.0.0",
            payload=OilGasTelemetryPayloadV2.model_validate(payload.model_dump()),
            provenance=EvidenceProvenance(
                producer="otsoc_simulator",
                producer_version="3.0.0",
                domain="oil_gas_transfer",
                simulation_id=payload.simulation_id,
                configuration_hash=payload.configuration_hash,
                seed=seed,
            ),
        )
        with session_scope(settings) as session:
            receipt = ingest_evidence(
                session,
                envelope,
                receipt_timestamp=receipt_timestamp,
            )
            record = session.get(EvidenceRecord, receipt.evidence_id)
            if record is None:
                raise RuntimeError("telemetry evidence could not be reloaded")
            selections.append(correlation_selection(record))
    semantic_parent = None
    context_parent = None
    policy_parent = None
    if policy_selection is not None:
        with session_scope(settings) as session:
            policy_record = session.get(EvidenceRecord, policy_selection.evidence_id)
            if policy_record is None:
                raise RuntimeError("policy evidence could not be reloaded")
            semantic_record = session.get(
                EvidenceRecord, policy_record.payload["semantic_event_id"]
            )
            context_record = session.get(
                EvidenceRecord, policy_record.payload["asset_context_event_id"]
            )
            if semantic_record is None or context_record is None:
                raise RuntimeError("S3 lineage could not be reloaded")
            semantic_parent = correlation_selection(semantic_record)
            context_parent = correlation_selection(context_record)
            policy_parent = correlation_selection(policy_record)
    request = CorrelationPersistenceRequest(
        rule_id=fixture.rule_id,
        semantic_parent=semantic_parent,
        asset_context_parent=context_parent,
        policy_parent=policy_parent,
        telemetry_parents=tuple(selections),
    )
    with session_scope(settings) as session:
        result = persist_correlation_finding(session, request)
        record = session.get(EvidenceRecord, result.receipt.evidence_id)
        if record is None:
            raise RuntimeError("correlation evidence could not be reloaded")
        return IncidentQualificationRequest(
            policy_finding=policy_selection,
            correlation_finding=incident_selection(record),
        )
