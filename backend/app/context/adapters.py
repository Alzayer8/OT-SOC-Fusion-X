from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.context.canonical import (
    deterministic_context_source_event_id,
    deterministic_finding_source_event_id,
)
from app.context.findings import (
    authorization_input_from_semantic,
    build_asset_context_event,
    build_policy_finding,
    build_policy_provenance,
)
from app.context.inventory import EXPECTED_INVENTORY_SHA256, LoadedInventory
from app.context.models import (
    ASSET_CONTEXT_SCHEMA_VERSION,
    EVALUATOR_VERSION,
    POLICY_FINDING_SCHEMA_VERSION,
    RESOLVER_NAME,
    RESOLVER_VERSION,
    AssetContextDerivationProvenance,
    AssetContextEvent,
    AssetContextEvidenceEnvelope,
    CommunicationPolicyFinding,
    IdentityClaim,
    PolicyFindingEvidenceEnvelope,
)
from app.context.policy import LoadedPolicy, evaluate_policy
from app.evidence.canonical import deterministic_evidence_id_from_fields
from app.evidence.models import EvidenceRecord
from app.evidence.schemas import EvidenceIngestionReceipt
from app.evidence.service import ingest_internal_evidence, verify_record_integrity
from app.protocols.models import ProtocolSemanticEvent

ASSET_CONTEXT_SOURCE_ID = uuid.UUID("2f41bc75-eebd-535e-8473-2eef00a7b457")
POLICY_FINDING_SOURCE_ID = uuid.UUID("a054a5bc-960a-5ae0-ad10-61a3897425bf")
ASSET_CONTEXT_SOURCE_KEY = "asset-context-resolver"
POLICY_FINDING_SOURCE_KEY = "communication-policy-evaluator"


class AssetPolicyEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class AssetPolicyWorkflowResult:
    context_receipt: EvidenceIngestionReceipt
    finding_receipt: EvidenceIngestionReceipt
    context_event: AssetContextEvent
    policy_finding: CommunicationPolicyFinding


def persist_asset_context(
    session: Session,
    semantic_evidence_id: uuid.UUID,
    inventory: LoadedInventory,
    *,
    source_claims: tuple[IdentityClaim, ...] | None = None,
    destination_claims: tuple[IdentityClaim, ...] | None = None,
    expected_semantic_sha256: str | None = None,
    receipt_timestamp: datetime | None = None,
) -> tuple[EvidenceIngestionReceipt, AssetContextEvent]:
    if inventory.sha256 != EXPECTED_INVENTORY_SHA256:
        raise AssetPolicyEvidenceError("The asset inventory digest is not approved.")
    semantic_record = _verified_record(session, semantic_evidence_id, "protocol_semantic_event")
    if expected_semantic_sha256 is not None and (
        semantic_record.integrity_sha256 != expected_semantic_sha256
    ):
        raise AssetPolicyEvidenceError("The supplied semantic evidence digest does not match.")
    semantic = _semantic_payload(semantic_record)
    _verify_raw_parent(session, semantic)
    source_event_id = deterministic_context_source_event_id(
        semantic_event_id=semantic.semantic_event_id,
        inventory_profile=inventory.profile.profile_id,
        inventory_version=inventory.profile.profile_version,
        inventory_sha256=inventory.sha256,
        resolver_version=RESOLVER_VERSION,
        context_schema_version=ASSET_CONTEXT_SCHEMA_VERSION,
    )
    evidence_id = deterministic_evidence_id_from_fields(
        source_id=ASSET_CONTEXT_SOURCE_ID,
        source_event_id=str(source_event_id),
        evidence_type="asset_context_event",
        payload_schema_version=ASSET_CONTEXT_SCHEMA_VERSION,
    )
    context = build_asset_context_event(
        context_event_id=evidence_id,
        semantic=semantic,
        semantic_integrity_sha256=semantic_record.integrity_sha256,
        inventory=inventory,
        source_claims=source_claims,
        destination_claims=destination_claims,
    )
    provenance = AssetContextDerivationProvenance(
        derivation_kind="ASSET_CONTEXT_RESOLUTION",
        semantic_event_id=semantic.semantic_event_id,
        semantic_evidence_integrity_sha256=semantic_record.integrity_sha256,
        inventory_profile=inventory.profile.profile_id,
        inventory_version=inventory.profile.profile_version,
        inventory_sha256=inventory.sha256,
        resolver_name=RESOLVER_NAME,
        resolver_version=RESOLVER_VERSION,
        canonicalization_version="otsoc-canonical-json-1",
        educational_only=True,
        ground_truth_used=False,
    )
    envelope = AssetContextEvidenceEnvelope(
        source_key=ASSET_CONTEXT_SOURCE_KEY,
        source_event_id=str(source_event_id),
        evidence_type="asset_context_event",
        observed_at=semantic.observed_at,
        sequence_number=semantic_record.sequence_number or 0,
        payload_schema="otsoc.asset.context_event",
        payload_schema_version=ASSET_CONTEXT_SCHEMA_VERSION,
        payload=context,
        provenance=provenance,
    )
    receipt = ingest_internal_evidence(
        session, envelope, receipt_timestamp=receipt_timestamp, request_id="offline-asset-context"
    )
    if receipt.evidence_id != context.asset_context_event_id:
        raise AssetPolicyEvidenceError("The asset-context evidence identity is inconsistent.")
    return receipt, context


def persist_policy_finding(
    session: Session,
    semantic_evidence_id: uuid.UUID,
    asset_context_event_id: uuid.UUID,
    inventory: LoadedInventory,
    policy: LoadedPolicy,
    *,
    expected_semantic_sha256: str | None = None,
    expected_context_sha256: str | None = None,
    receipt_timestamp: datetime | None = None,
) -> tuple[EvidenceIngestionReceipt, CommunicationPolicyFinding]:
    semantic_record = _verified_record(session, semantic_evidence_id, "protocol_semantic_event")
    context_record = _verified_record(session, asset_context_event_id, "asset_context_event")
    if expected_semantic_sha256 is not None and (
        semantic_record.integrity_sha256 != expected_semantic_sha256
    ):
        raise AssetPolicyEvidenceError("The supplied semantic evidence digest does not match.")
    if (
        expected_context_sha256 is not None
        and context_record.integrity_sha256 != expected_context_sha256
    ):
        raise AssetPolicyEvidenceError("The supplied asset-context digest does not match.")
    semantic = _semantic_payload(semantic_record)
    _verify_raw_parent(session, semantic)
    try:
        context = AssetContextEvent.model_validate(context_record.payload)
    except ValidationError as exc:
        raise AssetPolicyEvidenceError("The stored asset-context payload is invalid.") from exc
    if (
        context.semantic_event_id != semantic.semantic_event_id
        or context.semantic_evidence_integrity_sha256 != semantic_record.integrity_sha256
        or context.inventory_profile != inventory.profile.profile_id
        or context.inventory_version != inventory.profile.profile_version
        or context.inventory_sha256 != inventory.sha256
    ):
        raise AssetPolicyEvidenceError("The asset context does not match its verified parents.")
    auth = authorization_input_from_semantic(
        semantic, semantic_integrity_sha256=semantic_record.integrity_sha256
    )
    result = evaluate_policy(auth, context, policy)
    source_event_id = deterministic_finding_source_event_id(
        semantic_event_id=semantic.semantic_event_id,
        asset_context_event_id=context.asset_context_event_id,
        inventory_profile=inventory.profile.profile_id,
        inventory_version=inventory.profile.profile_version,
        inventory_sha256=inventory.sha256,
        policy_profile=policy.profile.profile_id,
        policy_version=policy.profile.profile_version,
        policy_sha256=policy.sha256,
        evaluator_version=EVALUATOR_VERSION,
        finding_schema_version=POLICY_FINDING_SCHEMA_VERSION,
    )
    evidence_id = deterministic_evidence_id_from_fields(
        source_id=POLICY_FINDING_SOURCE_ID,
        source_event_id=str(source_event_id),
        evidence_type="communication_policy_finding",
        payload_schema_version=POLICY_FINDING_SCHEMA_VERSION,
    )
    finding = build_policy_finding(
        finding_id=evidence_id,
        auth=auth,
        context=context,
        result=result,
        policy=policy,
    )
    envelope = PolicyFindingEvidenceEnvelope(
        source_key=POLICY_FINDING_SOURCE_KEY,
        source_event_id=str(source_event_id),
        evidence_type="communication_policy_finding",
        observed_at=semantic.observed_at,
        sequence_number=semantic_record.sequence_number or 0,
        payload_schema="otsoc.communication_policy.finding",
        payload_schema_version=POLICY_FINDING_SCHEMA_VERSION,
        payload=finding,
        provenance=build_policy_provenance(
            finding=finding, asset_context_integrity_sha256=context_record.integrity_sha256
        ),
    )
    receipt = ingest_internal_evidence(
        session, envelope, receipt_timestamp=receipt_timestamp, request_id="offline-policy-finding"
    )
    if receipt.evidence_id != finding.finding_id:
        raise AssetPolicyEvidenceError("The policy-finding evidence identity is inconsistent.")
    return receipt, finding


def persist_asset_context_and_finding(
    session: Session,
    semantic_evidence_id: uuid.UUID,
    inventory: LoadedInventory,
    policy: LoadedPolicy,
    *,
    source_claims: tuple[IdentityClaim, ...] | None = None,
    destination_claims: tuple[IdentityClaim, ...] | None = None,
    receipt_timestamp: datetime | None = None,
) -> AssetPolicyWorkflowResult:
    context_receipt, context = persist_asset_context(
        session,
        semantic_evidence_id,
        inventory,
        source_claims=source_claims,
        destination_claims=destination_claims,
        receipt_timestamp=receipt_timestamp,
    )
    finding_receipt, finding = persist_policy_finding(
        session,
        semantic_evidence_id,
        context_receipt.evidence_id,
        inventory,
        policy,
        receipt_timestamp=receipt_timestamp,
    )
    return AssetPolicyWorkflowResult(
        context_receipt=context_receipt,
        finding_receipt=finding_receipt,
        context_event=context,
        policy_finding=finding,
    )


def _verified_record(
    session: Session, evidence_id: uuid.UUID, expected_type: str
) -> EvidenceRecord:
    record = session.scalar(
        select(EvidenceRecord)
        .options(joinedload(EvidenceRecord.source))
        .where(EvidenceRecord.evidence_id == evidence_id)
    )
    if record is None or record.evidence_type != expected_type:
        raise AssetPolicyEvidenceError("The required parent evidence record was not found.")
    if not verify_record_integrity(record):
        raise AssetPolicyEvidenceError("The parent evidence integrity check failed.")
    return record


def _semantic_payload(record: EvidenceRecord) -> ProtocolSemanticEvent:
    try:
        semantic = ProtocolSemanticEvent.model_validate(record.payload)
    except ValidationError as exc:
        raise AssetPolicyEvidenceError("The stored semantic payload is invalid.") from exc
    if semantic.semantic_event_id != record.evidence_id:
        raise AssetPolicyEvidenceError("The semantic payload identity does not match its record.")
    return semantic


def _verify_raw_parent(session: Session, semantic: ProtocolSemanticEvent) -> None:
    raw = _verified_record(session, semantic.source_evidence_id, "synthetic_protocol_event")
    if raw.integrity_sha256 != semantic.source_evidence_integrity_sha256:
        raise AssetPolicyEvidenceError("The semantic event references a substituted raw parent.")
