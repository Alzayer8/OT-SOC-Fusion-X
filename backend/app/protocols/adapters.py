from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.evidence.canonical import deterministic_evidence_id_from_fields
from app.evidence.models import EvidenceRecord
from app.evidence.schemas import (
    EvidenceIngestionReceipt,
    SemanticDerivationProvenance,
    SemanticEvidenceEnvelope,
    SyntheticProtocolEvidenceEnvelope,
    SyntheticProtocolProvenance,
)
from app.evidence.service import ingest_internal_evidence, verify_record_integrity
from app.protocols.canonical import deterministic_semantic_source_event_id, sha256_hex
from app.protocols.decoder import DECODER_NAME, DECODER_VERSION, decode_event
from app.protocols.models import ProtocolSemanticEvent, SyntheticModbusEvent
from app.protocols.profile import EXPECTED_PROFILE_SHA256, LoadedProfile

RAW_SOURCE_ID = uuid.UUID("4eecb667-d128-5c1f-bd61-28444df4ed8c")
SEMANTIC_SOURCE_ID = uuid.UUID("8db5c3ac-ca9e-59e6-8176-95cffeed43d6")
RAW_SOURCE_KEY = "synthetic-modbus-fixture-primary"
SEMANTIC_SOURCE_KEY = "protocol-semantics-decoder"


class ProtocolEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class ProtocolEvidenceWorkflowResult:
    raw_receipt: EvidenceIngestionReceipt
    semantic_receipt: EvidenceIngestionReceipt
    semantic_event: ProtocolSemanticEvent


def protocol_event_to_evidence(
    event: SyntheticModbusEvent,
    *,
    fixture_sha256: str,
    sequence_number: int | None = None,
) -> SyntheticProtocolEvidenceEnvelope:
    return SyntheticProtocolEvidenceEnvelope(
        source_key=RAW_SOURCE_KEY,
        source_event_id=event.fixture_id,
        evidence_type="synthetic_protocol_event",
        observed_at=event.observed_at,
        sequence_number=event.transaction_id if sequence_number is None else sequence_number,
        payload_schema="otsoc.synthetic_modbus.event",
        payload_schema_version="1.0.0",
        payload=event,
        provenance=SyntheticProtocolProvenance(
            fixture_set_id="otsoc.phase4b.synthetic_modbus",
            fixture_set_version="1.0.0",
            generator="otsoc_static_fixture",
            generator_version="1.0.0",
            fixture_sha256=fixture_sha256,
            capture_mode=event.capture_mode,
            educational_only=True,
        ),
    )


def persist_raw_event(
    session: Session,
    event: SyntheticModbusEvent,
    *,
    fixture_bytes: bytes | None = None,
    receipt_timestamp: datetime | None = None,
) -> EvidenceIngestionReceipt:
    content = (
        fixture_bytes if fixture_bytes is not None else event.model_dump_json().encode("utf-8")
    )
    envelope = protocol_event_to_evidence(event, fixture_sha256=sha256_hex(content))
    return ingest_internal_evidence(
        session,
        envelope,
        receipt_timestamp=receipt_timestamp,
    )


def persist_semantic_evidence(
    session: Session,
    raw_evidence_id: uuid.UUID,
    loaded_profile: LoadedProfile,
    *,
    expected_source_sha256: str | None = None,
    receipt_timestamp: datetime | None = None,
) -> tuple[EvidenceIngestionReceipt, ProtocolSemanticEvent]:
    if loaded_profile.sha256 != EXPECTED_PROFILE_SHA256:
        raise ProtocolEvidenceError("The semantic profile digest is not approved.")
    raw_record = session.scalar(
        select(EvidenceRecord)
        .options(joinedload(EvidenceRecord.source))
        .where(EvidenceRecord.evidence_id == raw_evidence_id)
    )
    if raw_record is None or raw_record.evidence_type != "synthetic_protocol_event":
        raise ProtocolEvidenceError("The verified raw protocol evidence record was not found.")
    if not verify_record_integrity(raw_record):
        raise ProtocolEvidenceError("The raw protocol evidence integrity check failed.")
    if expected_source_sha256 is not None and raw_record.integrity_sha256 != expected_source_sha256:
        raise ProtocolEvidenceError(
            "The supplied source evidence digest does not match the record."
        )
    try:
        event = SyntheticModbusEvent.model_validate(raw_record.payload)
    except ValidationError as exc:
        raise ProtocolEvidenceError("The stored raw protocol payload is invalid.") from exc

    semantic_source_event_id = deterministic_semantic_source_event_id(
        source_evidence_id=raw_record.evidence_id,
        profile_id=loaded_profile.profile.profile_id,
        profile_version=loaded_profile.profile.profile_version,
        profile_sha256=loaded_profile.sha256,
        decoder_version=DECODER_VERSION,
        semantic_schema_version="1.0.0",
    )
    semantic_evidence_id = deterministic_evidence_id_from_fields(
        source_id=SEMANTIC_SOURCE_ID,
        source_event_id=str(semantic_source_event_id),
        evidence_type="protocol_semantic_event",
        payload_schema_version="1.0.0",
    )
    semantic_event = decode_event(
        event,
        loaded_profile,
        semantic_event_id=semantic_evidence_id,
        source_evidence_id=raw_record.evidence_id,
        source_evidence_integrity_sha256=raw_record.integrity_sha256,
        created_at=raw_record.received_at,
        expected_profile_sha256=EXPECTED_PROFILE_SHA256,
        source_evidence_verified=True,
    )
    provenance = SemanticDerivationProvenance(
        derivation_kind="SEMANTIC_INTERPRETATION",
        source_evidence_id=raw_record.evidence_id,
        source_evidence_integrity_sha256=raw_record.integrity_sha256,
        profile_id=loaded_profile.profile.profile_id,
        profile_version=loaded_profile.profile.profile_version,
        profile_sha256=loaded_profile.sha256,
        decoder_name=DECODER_NAME,
        decoder_version=DECODER_VERSION,
        canonicalization_version="otsoc-canonical-json-1",
        educational_only=True,
    )
    envelope = SemanticEvidenceEnvelope(
        source_key=SEMANTIC_SOURCE_KEY,
        source_event_id=str(semantic_source_event_id),
        evidence_type="protocol_semantic_event",
        observed_at=raw_record.observed_at,
        sequence_number=raw_record.sequence_number or 0,
        payload_schema="otsoc.protocol.semantic_event",
        payload_schema_version="1.0.0",
        payload=semantic_event,
        provenance=provenance,
    )
    receipt = ingest_internal_evidence(
        session,
        envelope,
        receipt_timestamp=receipt_timestamp,
    )
    if receipt.evidence_id != semantic_event.semantic_event_id:
        raise ProtocolEvidenceError("The semantic evidence identity is inconsistent.")
    return receipt, semantic_event


def persist_raw_and_semantic(
    session: Session,
    event: SyntheticModbusEvent,
    loaded_profile: LoadedProfile,
    *,
    fixture_bytes: bytes | None = None,
    receipt_timestamp: datetime | None = None,
) -> ProtocolEvidenceWorkflowResult:
    raw_receipt = persist_raw_event(
        session,
        event,
        fixture_bytes=fixture_bytes,
        receipt_timestamp=receipt_timestamp,
    )
    semantic_receipt, semantic_event = persist_semantic_evidence(
        session,
        raw_receipt.evidence_id,
        loaded_profile,
        receipt_timestamp=receipt_timestamp,
    )
    return ProtocolEvidenceWorkflowResult(
        raw_receipt=raw_receipt,
        semantic_receipt=semantic_receipt,
        semantic_event=semantic_event,
    )
