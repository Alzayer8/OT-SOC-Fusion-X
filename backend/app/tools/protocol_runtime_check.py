from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from sqlalchemy import func, select

from app.core.config import Settings
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.evidence.service import get_evidence
from app.protocols.adapters import persist_raw_event, persist_semantic_evidence
from app.protocols.fixtures import load_fixture
from app.protocols.profile import load_profile


@dataclass(frozen=True, slots=True)
class RuntimeCheckResult:
    raw_accepted: bool
    raw_duplicate: bool
    s3_raw_persisted: bool
    semantic_generated: bool
    semantic_persisted: bool
    semantic_duplicate: bool
    raw_unchanged: bool
    source_linkage_correct: bool
    read_types_distinct: bool
    ground_truth_absent: bool


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

    event, fixture_bytes = load_fixture("p4b-s3-valve-command-25.json")
    with session_scope(settings) as session:
        raw_first = persist_raw_event(session, event, fixture_bytes=fixture_bytes)
    with session_scope(settings) as session:
        raw_second = persist_raw_event(session, event, fixture_bytes=fixture_bytes)
        raw_record = session.get(EvidenceRecord, raw_first.evidence_id)
        if raw_record is None:
            raise RuntimeError("S3 raw evidence was not persisted")
        raw_snapshot = (
            dict(raw_record.payload),
            dict(raw_record.provenance),
            raw_record.integrity_sha256,
            raw_record.received_at,
        )
    with session_scope(settings) as session:
        semantic_first, semantic_event = persist_semantic_evidence(
            session, raw_first.evidence_id, load_profile()
        )
    with session_scope(settings) as session:
        semantic_second, _ = persist_semantic_evidence(
            session, raw_first.evidence_id, load_profile()
        )
        raw_after = session.get(EvidenceRecord, raw_first.evidence_id)
        if raw_after is None:
            raise RuntimeError("S3 raw evidence disappeared")
        raw_after_snapshot = (
            dict(raw_after.payload),
            dict(raw_after.provenance),
            raw_after.integrity_sha256,
            raw_after.received_at,
        )
        raw_read = get_evidence(session, raw_first.evidence_id)
        semantic_read = get_evidence(session, semantic_first.evidence_id)
        raw_count = session.scalar(
            select(func.count())
            .select_from(EvidenceRecord)
            .where(EvidenceRecord.evidence_type == "synthetic_protocol_event")
        )
        semantic_count = session.scalar(
            select(func.count())
            .select_from(EvidenceRecord)
            .where(EvidenceRecord.evidence_type == "protocol_semantic_event")
        )

    serialized = semantic_event.model_dump_json().lower()
    result = RuntimeCheckResult(
        raw_accepted=raw_first.status == "accepted",
        raw_duplicate=raw_second.status == "duplicate_existing",
        s3_raw_persisted=raw_count == 1,
        semantic_generated=semantic_event.interpretation_status.value == "MAPPED",
        semantic_persisted=semantic_count == 1,
        semantic_duplicate=semantic_second.status == "duplicate_existing",
        raw_unchanged=raw_snapshot == raw_after_snapshot,
        source_linkage_correct=semantic_event.source_evidence_id == raw_first.evidence_id,
        read_types_distinct=(
            raw_read is not None
            and semantic_read is not None
            and raw_read.evidence_type == "synthetic_protocol_event"
            and semantic_read.evidence_type == "protocol_semantic_event"
        ),
        ground_truth_absent=(
            "scenario_id" not in serialized
            and 'ground_truth"' not in serialized
            and semantic_event.ground_truth_used is False
        ),
    )
    if not all(asdict(result).values()):
        raise RuntimeError("one or more offline runtime checks failed")
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
