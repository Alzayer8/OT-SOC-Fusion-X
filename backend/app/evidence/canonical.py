from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from app.evidence.schemas import VerifiableEvidenceEnvelope

EVIDENCE_ID_NAMESPACE = uuid.UUID("9db53f17-8ea1-4c0e-9f47-9359724bc8d8")


def canonical_evidence_bytes(source_id: uuid.UUID, request: VerifiableEvidenceEnvelope) -> bytes:
    document: dict[str, Any] = request.model_dump(mode="json")
    document["source_id"] = str(source_id)
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def integrity_sha256(canonical_bytes: bytes) -> str:
    return hashlib.sha256(canonical_bytes).hexdigest()


def deterministic_evidence_id(
    source_id: uuid.UUID, request: VerifiableEvidenceEnvelope
) -> uuid.UUID:
    return deterministic_evidence_id_from_fields(
        source_id=source_id,
        source_event_id=request.source_event_id,
        evidence_type=request.evidence_type,
        payload_schema_version=request.payload_schema_version,
    )


def deterministic_evidence_id_from_fields(
    *,
    source_id: uuid.UUID,
    source_event_id: str,
    evidence_type: str,
    payload_schema_version: str,
) -> uuid.UUID:
    stable_identity = "|".join(
        (str(source_id), source_event_id, evidence_type, payload_schema_version)
    )
    return uuid.uuid5(EVIDENCE_ID_NAMESPACE, stable_identity)
