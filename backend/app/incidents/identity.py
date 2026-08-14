from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.incidents.models import QualifiedIncidentCandidate

INCIDENT_ID_NAMESPACE = uuid.UUID("89b14436-c13d-5f1f-976a-c6dc2240fa7a")


@dataclass(frozen=True)
class IncidentIdentity:
    incident_id: uuid.UUID
    grouping_key_sha256: str
    canonical_name: str


def deterministic_incident_identity(
    candidate: QualifiedIncidentCandidate,
    *,
    profile_id: str,
    profile_version: str,
    profile_sha256: str,
    grouping_epoch: datetime,
) -> IncidentIdentity:
    identity_scope = ",".join(sorted(candidate.identity_asset_scope)) or "NO_IDENTITY_ASSET_SCOPE"
    process_scope = ",".join(sorted(candidate.process_asset_scope)) or "NO_PROCESS_ASSET_SCOPE"
    point_scope = ",".join(sorted(candidate.target_point_scope)) or "NO_TARGET_POINT_SCOPE"
    semantic_scope = (
        str(candidate.s3_semantic_evidence_id)
        if candidate.s3_semantic_evidence_id is not None
        else "NO_S3_SEMANTIC_SCOPE"
    )
    parts = (
        profile_id,
        profile_version,
        profile_sha256,
        candidate.qualification_rule_id,
        candidate.qualification_rule_version,
        candidate.category.value,
        identity_scope,
        process_scope,
        point_scope,
        candidate.run_scope,
        candidate.configuration_scope,
        semantic_scope,
        grouping_epoch.isoformat(),
    )
    canonical_name = "|".join(parts)
    return IncidentIdentity(
        incident_id=uuid.uuid5(INCIDENT_ID_NAMESPACE, canonical_name),
        grouping_key_sha256=hashlib.sha256(canonical_name.encode("utf-8")).hexdigest(),
        canonical_name=canonical_name,
    )
