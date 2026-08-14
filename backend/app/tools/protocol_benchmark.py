from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from app.protocols.decoder import decode_event
from app.protocols.fixtures import load_fixture
from app.protocols.models import SyntheticModbusEvent
from app.protocols.profile import load_profile

BENCHMARK_EVENTS = 1_000


@dataclass(frozen=True, slots=True)
class ProtocolBenchmarkResult:
    events: int
    validation_seconds: float
    validation_per_second: float
    decode_seconds: float
    decode_per_second: float
    scope: str = "bounded local offline benchmark; not production capacity"


def main() -> int:
    source_event, _ = load_fixture("p4b-s3-valve-command-25.json")
    document = source_event.model_dump(mode="json")

    validation_start = time.perf_counter()
    events = [SyntheticModbusEvent.model_validate(document) for _ in range(BENCHMARK_EVENTS)]
    validation_seconds = time.perf_counter() - validation_start

    profile = load_profile()
    source_evidence_id = uuid.UUID("d18dff22-2936-530b-a72c-4b048cf9d0e2")
    semantic_event_id = uuid.UUID("d53ebffc-b486-5667-bf56-b35fc5c339b6")
    created_at = datetime(2026, 1, 1, 0, 10, 1, tzinfo=UTC)
    decode_start = time.perf_counter()
    for event in events:
        decode_event(
            event,
            profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256="1" * 64,
            created_at=created_at,
        )
    decode_seconds = time.perf_counter() - decode_start

    result = ProtocolBenchmarkResult(
        events=BENCHMARK_EVENTS,
        validation_seconds=validation_seconds,
        validation_per_second=BENCHMARK_EVENTS / validation_seconds,
        decode_seconds=decode_seconds,
        decode_per_second=BENCHMARK_EVENTS / decode_seconds,
    )
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
