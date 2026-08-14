from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from pydantic import BaseModel

from app.correlation.models import EvidenceParentReference

CORRELATION_ID_NAMESPACE = uuid.UUID("0f531efe-4f8b-5af7-9c17-a3b603ed90bd")


def canonical_document_bytes(document: dict[str, Any] | list[Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_model_bytes(model: BaseModel) -> bytes:
    return canonical_document_bytes(model.model_dump(mode="json"))


def canonical_profile_bytes(model: BaseModel) -> bytes:
    document = model.model_dump(mode="json")
    document["statuses"] = sorted(document["statuses"])
    document["rules"] = sorted(document["rules"], key=lambda item: item["rule_id"])
    for rule in document["rules"]:
        for field in ("process_asset_keys", "point_ids"):
            rule[field] = sorted(rule[field])
        rule["relationships"] = sorted(
            rule["relationships"],
            key=lambda item: (
                item["relationship_type"],
                item["source_asset_key"],
                item["target_asset_key"],
            ),
        )
    return canonical_document_bytes(document)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_parent_references(
    references: tuple[EvidenceParentReference, ...],
) -> tuple[EvidenceParentReference, ...]:
    unique: dict[uuid.UUID, EvidenceParentReference] = {}
    for reference in references:
        existing = unique.get(reference.evidence_id)
        if existing is not None and existing != reference:
            raise ValueError("one evidence ID has conflicting parent-reference content")
        unique[reference.evidence_id] = reference
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (item.evidence_type, item.observed_at, str(item.evidence_id)),
        )
    )


def parent_set_sha256(references: tuple[EvidenceParentReference, ...]) -> str:
    ordered = canonical_parent_references(references)
    return sha256_hex(canonical_document_bytes([item.model_dump(mode="json") for item in ordered]))


def deterministic_correlation_source_event_id(
    *,
    profile_id: str,
    profile_version: str,
    profile_sha256: str,
    rule_id: str,
    rule_version: str,
    evaluator_version: str,
    simulation_id: str | None,
    configuration_hash: str | None,
    anchor_time: str | None,
    parent_digest: str,
    finding_schema_version: str,
) -> uuid.UUID:
    name = "|".join(
        (
            profile_id,
            profile_version,
            profile_sha256,
            rule_id,
            rule_version,
            evaluator_version,
            simulation_id or "",
            configuration_hash or "",
            anchor_time or "",
            parent_digest,
            finding_schema_version,
        )
    )
    return uuid.uuid5(CORRELATION_ID_NAMESPACE, name)
