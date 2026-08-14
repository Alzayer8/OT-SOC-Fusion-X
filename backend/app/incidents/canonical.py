from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


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
    for field in (
        "categories",
        "severities",
        "statuses",
        "evidence_roles",
        "timeline_entry_types",
    ):
        document[field] = sorted(document[field])
    document["evidence_schemas"] = sorted(
        document["evidence_schemas"],
        key=lambda item: (item["evidence_type"], item["schema_id"], item["schema_version"]),
    )
    document["rules"] = sorted(document["rules"], key=lambda item: item["rule_id"])
    for rule in document["rules"]:
        rule["required_evidence_types"] = sorted(rule["required_evidence_types"])
    return canonical_document_bytes(document)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
