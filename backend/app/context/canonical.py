from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from pydantic import BaseModel

CANONICALIZATION_VERSION = "otsoc-canonical-json-1"
CONTEXT_ID_NAMESPACE = uuid.UUID("16a29e36-604d-5265-bb5d-75361bdc3195")
FINDING_ID_NAMESPACE = uuid.UUID("48d8c560-e68b-5f7b-931f-a689b4cafbcf")


def canonical_document_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_model_bytes(model: BaseModel) -> bytes:
    return canonical_document_bytes(model.model_dump(mode="json"))


def canonical_inventory_bytes(model: BaseModel) -> bytes:
    document = model.model_dump(mode="json")
    document["zones"] = sorted(document["zones"], key=lambda item: item["zone_id"])
    for zone in document["zones"]:
        zone["allowed_relationship_types"] = sorted(zone["allowed_relationship_types"])
    document["assets"] = sorted(document["assets"], key=lambda item: item["asset_key"])
    for asset in document["assets"]:
        asset["identifiers"] = sorted(
            asset["identifiers"], key=lambda item: (item["identifier_type"], item["value"])
        )
        asset["protocol_capabilities"] = sorted(asset["protocol_capabilities"])
    document["relationships"] = sorted(
        document["relationships"],
        key=lambda item: (
            item["relationship_type"],
            item["source_asset_key"],
            item["target_kind"],
            item["target_ref"],
        ),
    )
    return canonical_document_bytes(document)


def canonical_policy_bytes(model: BaseModel) -> bytes:
    document = model.model_dump(mode="json")
    document["governed_paths"] = sorted(
        document["governed_paths"], key=lambda item: item["path_id"]
    )
    for path in document["governed_paths"]:
        path["approved_protocols"] = sorted(path["approved_protocols"])
    document["rules"] = sorted(document["rules"], key=lambda item: item["rule_id"])
    for rule in document["rules"]:
        for field in (
            "operations",
            "function_semantics",
            "point_ids",
            "point_access_classes",
        ):
            rule[field] = sorted(rule[field])
    return canonical_document_bytes(document)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def deterministic_asset_id(*, inventory_profile_id: str, asset_key: str) -> uuid.UUID:
    name = f"urn:otsoc:asset|{inventory_profile_id}|{asset_key}"
    return uuid.uuid5(uuid.NAMESPACE_URL, name)


def deterministic_context_source_event_id(
    *,
    semantic_event_id: uuid.UUID,
    inventory_profile: str,
    inventory_version: str,
    inventory_sha256: str,
    resolver_version: str,
    context_schema_version: str,
) -> uuid.UUID:
    name = "|".join(
        (
            str(semantic_event_id),
            inventory_profile,
            inventory_version,
            inventory_sha256,
            resolver_version,
            context_schema_version,
        )
    )
    return uuid.uuid5(CONTEXT_ID_NAMESPACE, name)


def deterministic_finding_source_event_id(
    *,
    semantic_event_id: uuid.UUID,
    asset_context_event_id: uuid.UUID,
    inventory_profile: str,
    inventory_version: str,
    inventory_sha256: str,
    policy_profile: str,
    policy_version: str,
    policy_sha256: str,
    evaluator_version: str,
    finding_schema_version: str,
) -> uuid.UUID:
    name = "|".join(
        (
            str(semantic_event_id),
            str(asset_context_event_id),
            inventory_profile,
            inventory_version,
            inventory_sha256,
            policy_profile,
            policy_version,
            policy_sha256,
            evaluator_version,
            finding_schema_version,
        )
    )
    return uuid.uuid5(FINDING_ID_NAMESPACE, name)
