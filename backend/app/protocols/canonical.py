from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from pydantic import BaseModel

SEMANTIC_ID_NAMESPACE = uuid.UUID("e58444eb-b836-52c4-8544-a86edcb25a38")
CANONICALIZATION_VERSION = "otsoc-canonical-json-1"


def canonical_model_bytes(model: BaseModel) -> bytes:
    return canonical_document_bytes(model.model_dump(mode="json"))


def canonical_document_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def deterministic_semantic_source_event_id(
    *,
    source_evidence_id: uuid.UUID,
    profile_id: str,
    profile_version: str,
    profile_sha256: str,
    decoder_version: str,
    semantic_schema_version: str,
) -> uuid.UUID:
    identity = "|".join(
        (
            str(source_evidence_id),
            profile_id,
            profile_version,
            profile_sha256,
            decoder_version,
            semantic_schema_version,
        )
    )
    return uuid.uuid5(SEMANTIC_ID_NAMESPACE, identity)
