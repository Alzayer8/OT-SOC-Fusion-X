from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass

from app.core.config import Settings
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.adapter import telemetry_to_evidence_request
from app.evidence.service import get_evidence, ingest_evidence
from app.simulation import OilGasTransferSimulator, SimulationConfig


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    accepted_events: int
    accepted_seconds: float
    accepted_per_second: float
    duplicate_retries: int
    duplicate_seconds: float
    duplicate_per_second: float
    read_operations: int
    read_seconds: float
    mean_read_milliseconds: float


def main() -> int:
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url is None or "otsoc_test" not in test_url:
        raise SystemExit("TEST_DATABASE_URL must target the isolated otsoc_test database")
    settings = Settings(
        app_name="OT-SOC Fusion X",
        app_version="1.0.0",
        app_env="development",
        api_version="v1",
        log_level="WARNING",
        cors_origins=["http://localhost:5173"],
        database_url=test_url,
        database_connect_timeout_seconds=2,
    )
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)

    config = SimulationConfig(duration_seconds=1_000)
    simulator = OilGasTransferSimulator(config)
    requests = [
        telemetry_to_evidence_request(step.telemetry, seed=config.seed)
        for step in simulator.run_steps(1_000)
    ]
    evidence_ids = []
    accepted_start = time.perf_counter()
    for request in requests:
        with session_scope(settings) as session:
            evidence_ids.append(ingest_evidence(session, request).evidence_id)
    accepted_seconds = time.perf_counter() - accepted_start

    duplicate_start = time.perf_counter()
    for request in requests:
        with session_scope(settings) as session:
            receipt = ingest_evidence(session, request)
            if receipt.status != "duplicate_existing":
                raise RuntimeError("benchmark duplicate retry was unexpectedly accepted")
    duplicate_seconds = time.perf_counter() - duplicate_start

    read_ids = evidence_ids[:100]
    read_start = time.perf_counter()
    for evidence_id in read_ids:
        with session_scope(settings) as session:
            if get_evidence(session, evidence_id) is None:
                raise RuntimeError("benchmark evidence record was not readable")
    read_seconds = time.perf_counter() - read_start

    result = BenchmarkResult(
        accepted_events=len(requests),
        accepted_seconds=accepted_seconds,
        accepted_per_second=len(requests) / accepted_seconds,
        duplicate_retries=len(requests),
        duplicate_seconds=duplicate_seconds,
        duplicate_per_second=len(requests) / duplicate_seconds,
        read_operations=len(read_ids),
        read_seconds=read_seconds,
        mean_read_milliseconds=(read_seconds / len(read_ids)) * 1_000,
    )
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
