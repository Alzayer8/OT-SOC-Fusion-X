from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass

from app.context.findings import authorization_input_from_semantic, build_asset_context_event
from app.context.fixtures import load_fixture
from app.context.identity import resolve_identity
from app.context.inventory import load_inventory_profile
from app.context.models import IdentifierType, IdentityClaim
from app.context.policy import evaluate_policy, load_policy_profile
from app.protocols.decoder import decode_event
from app.protocols.profile import load_profile

BENCHMARK_OPERATIONS = 1_000


@dataclass(frozen=True, slots=True)
class ContextBenchmarkResult:
    operations_per_measurement: int
    identity_resolution_seconds: float
    identity_resolutions_per_second: float
    asset_context_seconds: float
    asset_contexts_per_second: float
    policy_evaluation_seconds: float
    policy_evaluations_per_second: float
    scope: str = "bounded local offline development measurement; not production capacity"


def main() -> int:
    fixture, _ = load_fixture("known_hmi_approved_read.json")
    inventory = load_inventory_profile()
    protocol = load_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=protocol)
    semantic = decode_event(
        fixture.event,
        protocol,
        semantic_event_id=uuid.UUID("40804c9a-5f2c-5bd1-86ba-b196eed518dc"),
        source_evidence_id=uuid.UUID("9d73db91-741f-5e02-8295-90aa0329c25f"),
        source_evidence_integrity_sha256="1" * 64,
        created_at=fixture.event.observed_at,
    )
    claim = (IdentityClaim(identifier_type=IdentifierType.LOGICAL_ID, value="HMI-01"),)

    identity_start = time.perf_counter()
    for _ in range(BENCHMARK_OPERATIONS):
        resolve_identity(claim, inventory)
    identity_seconds = time.perf_counter() - identity_start

    context_start = time.perf_counter()
    contexts = [
        build_asset_context_event(
            context_event_id=uuid.UUID("3301a8dc-a119-5de4-aede-c79360ce811b"),
            semantic=semantic,
            semantic_integrity_sha256="2" * 64,
            inventory=inventory,
            source_claims=fixture.source_identity_claims,
            destination_claims=fixture.destination_identity_claims,
        )
        for _ in range(BENCHMARK_OPERATIONS)
    ]
    context_seconds = time.perf_counter() - context_start

    auth = authorization_input_from_semantic(semantic, semantic_integrity_sha256="2" * 64)
    policy_start = time.perf_counter()
    for context in contexts:
        evaluate_policy(auth, context, policy)
    policy_seconds = time.perf_counter() - policy_start

    result = ContextBenchmarkResult(
        operations_per_measurement=BENCHMARK_OPERATIONS,
        identity_resolution_seconds=identity_seconds,
        identity_resolutions_per_second=BENCHMARK_OPERATIONS / identity_seconds,
        asset_context_seconds=context_seconds,
        asset_contexts_per_second=BENCHMARK_OPERATIONS / context_seconds,
        policy_evaluation_seconds=policy_seconds,
        policy_evaluations_per_second=BENCHMARK_OPERATIONS / policy_seconds,
    )
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
