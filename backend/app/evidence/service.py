from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import UTC, datetime

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Select, false, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.context.models import AssetContextEvidenceEnvelope, PolicyFindingEvidenceEnvelope
from app.correlation.models import CorrelationEvidenceEnvelope
from app.evidence.canonical import (
    canonical_evidence_bytes,
    deterministic_evidence_id,
    integrity_sha256,
)
from app.evidence.models import EvidenceRecord, EvidenceSource
from app.evidence.schemas import (
    MAX_CANONICAL_EVIDENCE_BYTES,
    EvidenceIngestionReceipt,
    EvidenceIngestRequest,
    EvidenceListResponse,
    EvidenceRecordResponse,
    HistoricalEvidenceEnvelopeV1,
    InternalEvidenceEnvelope,
    SemanticEvidenceEnvelope,
    SyntheticProtocolEvidenceEnvelope,
    VerifiableEvidenceEnvelope,
)
from app.lab.models import LabActiveContext, LabRun, LabRunEvidence

logger = logging.getLogger("otsoc.evidence")


class EvidenceSourceNotFoundError(ValueError):
    pass


class EvidenceIdentityConflictError(ValueError):
    pass


class EvidencePayloadTooLargeError(ValueError):
    pass


class EvidenceCursorError(ValueError):
    pass


def ingest_evidence(
    session: Session,
    request: EvidenceIngestRequest,
    *,
    receipt_timestamp: datetime | None = None,
    request_id: str = "unavailable",
) -> EvidenceIngestionReceipt:
    return _ingest_validated_evidence(
        session,
        request,
        receipt_timestamp=receipt_timestamp,
        request_id=request_id,
    )


def ingest_internal_evidence(
    session: Session,
    request: InternalEvidenceEnvelope,
    *,
    receipt_timestamp: datetime | None = None,
    request_id: str = "offline-protocol-workflow",
) -> EvidenceIngestionReceipt:
    return _ingest_validated_evidence(
        session,
        request,
        receipt_timestamp=receipt_timestamp,
        request_id=request_id,
    )


def _ingest_validated_evidence(
    session: Session,
    request: EvidenceIngestRequest | InternalEvidenceEnvelope,
    *,
    receipt_timestamp: datetime | None,
    request_id: str,
) -> EvidenceIngestionReceipt:
    now = receipt_timestamp or datetime.now(UTC)
    source = session.scalar(
        select(EvidenceSource).where(
            EvidenceSource.source_key == request.source_key,
            EvidenceSource.enabled.is_(True),
        )
    )
    if source is None:
        raise EvidenceSourceNotFoundError("The evidence source is unknown or disabled.")
    if source.source_type != request.evidence_type:
        raise EvidenceSourceNotFoundError("The evidence source does not accept this evidence type.")
    if source.schema_version != request.payload_schema_version:
        raise EvidenceSourceNotFoundError(
            "The evidence source is not registered for the current payload schema version."
        )

    canonical = canonical_evidence_bytes(source.id, request)
    maximum_bytes = (
        65_536 if isinstance(request, CorrelationEvidenceEnvelope) else MAX_CANONICAL_EVIDENCE_BYTES
    )
    if len(canonical) > maximum_bytes:
        raise EvidencePayloadTooLargeError("The canonical evidence payload exceeds the size limit.")
    digest = integrity_sha256(canonical)
    evidence_id = deterministic_evidence_id(source.id, request)

    statement = (
        insert(EvidenceRecord)
        .values(
            evidence_id=evidence_id,
            evidence_version=1,
            source_id=source.id,
            source_event_id=request.source_event_id,
            evidence_type=request.evidence_type,
            observed_at=request.observed_at,
            received_at=now,
            sequence_number=request.sequence_number,
            payload_schema=request.payload_schema,
            payload_schema_version=request.payload_schema_version,
            payload=request.payload.model_dump(mode="json"),
            provenance=request.provenance.model_dump(mode="json"),
            integrity_sha256=digest,
            canonical_byte_length=len(canonical),
        )
        .on_conflict_do_nothing(
            constraint="uq_evidence_source_event_identity",
        )
        .returning(EvidenceRecord.evidence_id)
    )
    inserted_id = session.execute(statement).scalar_one_or_none()
    status = "accepted"
    if inserted_id is None:
        existing = session.scalar(_identity_query(source.id, request))
        if existing is None:
            raise RuntimeError("evidence uniqueness conflict could not be resolved")
        if existing.integrity_sha256 != digest or existing.evidence_id != evidence_id:
            raise EvidenceIdentityConflictError(
                "The source event identity already exists with different immutable content."
            )
        evidence_id = existing.evidence_id
        status = "duplicate_existing"

    logger.info(
        "evidence_ingestion_completed",
        extra={
            "request_id": request_id,
            "source_key": request.source_key,
            "evidence_type": request.evidence_type,
            "evidence_id": str(evidence_id),
            "result": status,
        },
    )
    return EvidenceIngestionReceipt(
        status=status,
        evidence_id=evidence_id,
        source_key=request.source_key,
        receipt_timestamp=now,
    )


def get_evidence(session: Session, evidence_id: uuid.UUID) -> EvidenceRecordResponse | None:
    record = session.scalar(
        select(EvidenceRecord)
        .join(EvidenceRecord.source)
        .where(EvidenceRecord.evidence_id == evidence_id)
    )
    return evidence_record_response(record) if record is not None else None


def list_evidence(
    session: Session,
    *,
    limit: int,
    offset: int,
    cursor: str | None = None,
    evidence_type: str | None = None,
    source_key: str | None = None,
    observed_from: datetime | None = None,
    observed_to: datetime | None = None,
    scope: str = "ALL_HISTORY",
    run_id: uuid.UUID | None = None,
) -> EvidenceListResponse:
    statement = select(EvidenceRecord).join(EvidenceRecord.source)
    if scope not in {"CURRENT", "ALL_HISTORY", "RUN"}:
        raise EvidenceCursorError("Evidence scope is invalid.")
    if scope == "CURRENT":
        context = session.get(LabActiveContext, 1)
        if context is None:
            statement = statement.where(false())
        else:
            statement = statement.join(
                LabRunEvidence, LabRunEvidence.evidence_id == EvidenceRecord.evidence_id
            ).where(LabRunEvidence.run_id == context.active_run_id)
    elif scope == "RUN":
        if run_id is None or session.get(LabRun, run_id) is None:
            raise EvidenceCursorError("A valid run_id is required for RUN evidence scope.")
        statement = statement.join(
            LabRunEvidence, LabRunEvidence.evidence_id == EvidenceRecord.evidence_id
        ).where(LabRunEvidence.run_id == run_id)
    elif run_id is not None:
        raise EvidenceCursorError("run_id may only be used with RUN evidence scope.")
    if evidence_type is not None:
        statement = statement.where(EvidenceRecord.evidence_type == evidence_type)
    if source_key is not None:
        statement = statement.where(EvidenceSource.source_key == source_key)
    if observed_from is not None and observed_to is not None:
        statement = statement.where(
            EvidenceRecord.observed_at >= observed_from,
            EvidenceRecord.observed_at <= observed_to,
        )
    if cursor is not None:
        cursor_time, cursor_id = decode_evidence_cursor(cursor)
        statement = statement.where(
            or_(
                EvidenceRecord.observed_at > cursor_time,
                (
                    (EvidenceRecord.observed_at == cursor_time)
                    & (EvidenceRecord.evidence_id > cursor_id)
                ),
            )
        )
    records = session.scalars(
        statement.order_by(EvidenceRecord.observed_at, EvidenceRecord.evidence_id)
        .limit(limit + 1)
        .offset(offset if cursor is None else 0)
    ).all()
    has_more = len(records) > limit
    page = records[:limit]
    return EvidenceListResponse(
        items=[evidence_record_response(record) for record in page],
        limit=limit,
        offset=offset,
        next_cursor=encode_evidence_cursor(page[-1]) if has_more and page else None,
        evidence_type=evidence_type,
        source_key=source_key,
        observed_from=observed_from,
        observed_to=observed_to,
    )


def encode_evidence_cursor(record: EvidenceRecord) -> str:
    document = json.dumps(
        {"observed_at": record.observed_at.isoformat(), "evidence_id": str(record.evidence_id)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(document).decode("ascii").rstrip("=")


def decode_evidence_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    if not 1 <= len(cursor) <= 512:
        raise EvidenceCursorError("Evidence cursor is invalid.")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.b64decode(padded, altchars=b"-_", validate=True)
        document = json.loads(raw.decode("utf-8"))
        if set(document) != {"observed_at", "evidence_id"}:
            raise ValueError
        observed_at = TypeAdapter(datetime).validate_python(document["observed_at"])
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError
        return observed_at, uuid.UUID(document["evidence_id"])
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise EvidenceCursorError("Evidence cursor is invalid.") from exc


def verify_record_integrity(record: EvidenceRecord) -> bool:
    envelope = {
        "source_key": record.source.source_key,
        "source_event_id": record.source_event_id,
        "evidence_type": record.evidence_type,
        "observed_at": record.observed_at,
        "sequence_number": record.sequence_number,
        "payload_schema": record.payload_schema,
        "payload_schema_version": record.payload_schema_version,
        "payload": record.payload,
        "provenance": record.provenance,
    }
    request: VerifiableEvidenceEnvelope
    try:
        if (
            record.evidence_type == "simulator_telemetry"
            and record.payload_schema_version == "1.0.0"
        ):
            request = HistoricalEvidenceEnvelopeV1.model_validate(envelope)
        elif (
            record.evidence_type == "simulator_telemetry"
            and record.payload_schema_version == "2.0.0"
        ):
            request = EvidenceIngestRequest.model_validate(envelope)
        elif record.evidence_type == "synthetic_protocol_event":
            request = SyntheticProtocolEvidenceEnvelope.model_validate(envelope)
        elif record.evidence_type == "protocol_semantic_event":
            request = SemanticEvidenceEnvelope.model_validate(envelope)
        elif record.evidence_type == "asset_context_event":
            request = AssetContextEvidenceEnvelope.model_validate(envelope)
        elif record.evidence_type == "communication_policy_finding":
            request = PolicyFindingEvidenceEnvelope.model_validate(envelope)
        elif record.evidence_type == "correlation_finding":
            request = CorrelationEvidenceEnvelope.model_validate(envelope)
        else:
            return False
    except ValidationError:
        return False
    canonical = canonical_evidence_bytes(record.source_id, request)
    return integrity_sha256(canonical) == record.integrity_sha256


def _identity_query(
    source_id: uuid.UUID, request: EvidenceIngestRequest | InternalEvidenceEnvelope
) -> Select[tuple[EvidenceRecord]]:
    return select(EvidenceRecord).where(
        EvidenceRecord.source_id == source_id,
        EvidenceRecord.source_event_id == request.source_event_id,
        EvidenceRecord.evidence_type == request.evidence_type,
        EvidenceRecord.payload_schema_version == request.payload_schema_version,
    )


def evidence_record_response(record: EvidenceRecord) -> EvidenceRecordResponse:
    return EvidenceRecordResponse(
        evidence_id=record.evidence_id,
        evidence_version=record.evidence_version,
        source_key=record.source.source_key,
        source_event_id=record.source_event_id,
        evidence_type=record.evidence_type,
        observed_at=record.observed_at,
        received_at=record.received_at,
        sequence_number=record.sequence_number,
        payload_schema=record.payload_schema,
        payload_schema_version=record.payload_schema_version,
        payload=record.payload,
        provenance=record.provenance,
        integrity_sha256=record.integrity_sha256,
        canonical_byte_length=record.canonical_byte_length,
    )
