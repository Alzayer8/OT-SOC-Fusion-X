from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.incidents.grouping import grouping_epoch_start
from app.incidents.identity import deterministic_incident_identity
from app.incidents.memberships import verify_qualification_evidence
from app.incidents.models import IncidentQualificationRequest
from app.incidents.profile import load_incident_profile
from app.incidents.qualification import qualify_incident
from app.incidents.service import qualify_stored_evidence
from app.tools.incident_runtime_check import _settings
from app.tools.incident_support import persist_policy_chain


@dataclass(frozen=True, slots=True)
class IncidentBenchmarkResult:
    development_only: bool
    qualification_operations: int
    qualification_seconds: float
    qualification_per_second: float
    grouping_operations: int
    grouping_seconds: float
    grouping_per_second: float
    serialization_operations: int
    serialization_seconds: float
    serialization_per_second: float


def main() -> int:
    settings = _settings()
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
    request = IncidentQualificationRequest(
        policy_finding=persist_policy_chain(settings, "s1_unknown_source_asset.json")
    )
    profile = load_incident_profile()
    with session_scope(settings) as session:
        bundle = verify_qualification_evidence(session, request)
        candidate = qualify_incident(bundle, profile)
        if candidate is None:
            raise RuntimeError("benchmark evidence did not qualify")
    started = time.perf_counter()
    for _ in range(1_000):
        if qualify_incident(bundle, profile) is None:
            raise RuntimeError("qualification became non-deterministic")
    qualification_seconds = time.perf_counter() - started
    epoch = grouping_epoch_start(candidate.grouping_anchor)
    started = time.perf_counter()
    for _ in range(1_000):
        deterministic_incident_identity(
            candidate,
            profile_id=profile.profile.profile_id,
            profile_version=profile.profile.profile_version,
            profile_sha256=profile.sha256,
            grouping_epoch=epoch,
        )
    grouping_seconds = time.perf_counter() - started
    with session_scope(settings) as session:
        receipt = qualify_stored_evidence(session, request)
        if receipt.incident is None:
            raise RuntimeError("benchmark incident was not created")
        response = receipt.incident
    started = time.perf_counter()
    for _ in range(1_000):
        response.model_dump_json()
    serialization_seconds = time.perf_counter() - started
    result = IncidentBenchmarkResult(
        development_only=True,
        qualification_operations=1_000,
        qualification_seconds=qualification_seconds,
        qualification_per_second=1_000 / qualification_seconds,
        grouping_operations=1_000,
        grouping_seconds=grouping_seconds,
        grouping_per_second=1_000 / grouping_seconds,
        serialization_operations=1_000,
        serialization_seconds=serialization_seconds,
        serialization_per_second=1_000 / serialization_seconds,
    )
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
