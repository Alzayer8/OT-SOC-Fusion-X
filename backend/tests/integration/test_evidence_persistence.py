from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from alembic import command
from app.core.config import Settings
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.canonical import (
    canonical_evidence_bytes,
    deterministic_evidence_id,
    integrity_sha256,
)
from app.evidence.models import EvidenceRecord, EvidenceSource
from app.evidence.schemas import HistoricalEvidenceEnvelopeV1
from app.evidence.service import (
    EvidenceIdentityConflictError,
    EvidenceSourceNotFoundError,
    get_evidence,
    ingest_evidence,
    list_evidence,
    verify_record_integrity,
)
from tests.evidence_helpers import sample_evidence_request
from tests.integration.test_migrations import alembic_config


def evidence_settings() -> Settings:
    return Settings(
        app_name="OT-SOC Fusion X",
        app_version="1.0.0",
        app_env="development",
        api_version="v1",
        log_level="WARNING",
        cors_origins=["http://localhost:5173"],
        database_url=os.environ["TEST_DATABASE_URL"],
        database_connect_timeout_seconds=2,
    )


@pytest.fixture(autouse=True)
def migrated_clean_evidence_database() -> None:
    command.upgrade(alembic_config(), "head")
    engine = engine_for(evidence_settings())
    with engine.begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)


@pytest.mark.integration
def test_seeded_source_and_valid_evidence_persist_with_utc_and_integrity() -> None:
    settings = evidence_settings()
    request = sample_evidence_request()
    with session_scope(settings) as session:
        source = session.scalar(
            select(EvidenceSource).where(EvidenceSource.source_key == "simulator-primary")
        )
        assert source is not None
        assert source.source_type == "simulator_telemetry"
        assert source.schema_version == "2.0.0"
        assert source.display_name == "Primary Synthetic Oil and Gas Transfer Simulator"
        receipt = ingest_evidence(session, request)
        assert receipt.status == "accepted"

    with session_scope(settings) as session:
        record = session.scalar(select(EvidenceRecord))
        assert record is not None
        assert record.observed_at.tzinfo is not None
        assert record.received_at.tzinfo is not None
        assert verify_record_integrity(record) is True


@pytest.mark.integration
def test_retry_is_idempotent_and_conflicting_content_fails_without_partial_row() -> None:
    settings = evidence_settings()
    request = sample_evidence_request(source_event_id="retry-1")
    with session_scope(settings) as session:
        accepted = ingest_evidence(session, request)
    with session_scope(settings) as session:
        duplicate = ingest_evidence(session, request)
        assert duplicate.status == "duplicate_existing"
        assert duplicate.evidence_id == accepted.evidence_id

    conflicting_payload = request.payload.model_copy(
        update={"pipeline_pressure_bar": request.payload.pipeline_pressure_bar + 0.5}
    )
    conflict = request.model_copy(update={"payload": conflicting_payload})
    with pytest.raises(EvidenceIdentityConflictError), session_scope(settings) as session:
        ingest_evidence(session, conflict)
    with session_scope(settings) as session:
        assert session.scalar(select(func.count()).select_from(EvidenceRecord)) == 1


@pytest.mark.integration
def test_concurrent_duplicate_submission_creates_one_record() -> None:
    settings = evidence_settings()
    request = sample_evidence_request(source_event_id="concurrent-1")

    def submit() -> str:
        with session_scope(settings) as session:
            return ingest_evidence(session, request).status

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(lambda _: submit(), range(8)))

    assert statuses.count("accepted") == 1
    assert statuses.count("duplicate_existing") == 7
    with session_scope(settings) as session:
        assert session.scalar(select(func.count()).select_from(EvidenceRecord)) == 1


@pytest.mark.integration
def test_unknown_source_rejects_without_partial_state() -> None:
    settings = evidence_settings()
    request = sample_evidence_request().model_copy(update={"source_key": "unknown-source"})
    with pytest.raises(EvidenceSourceNotFoundError), session_scope(settings) as session:
        ingest_evidence(session, request)
    with session_scope(settings) as session:
        assert session.scalar(select(func.count()).select_from(EvidenceRecord)) == 0


@pytest.mark.integration
def test_database_prevents_mutation_and_source_deletion() -> None:
    settings = evidence_settings()
    with session_scope(settings) as session:
        receipt = ingest_evidence(session, sample_evidence_request())

    with pytest.raises(DBAPIError), session_scope(settings) as session:
        session.execute(
            text("UPDATE evidence_records SET source_event_id='changed' WHERE evidence_id=:id"),
            {"id": receipt.evidence_id},
        )
    with pytest.raises(IntegrityError), session_scope(settings) as session:
        session.execute(text("DELETE FROM evidence_sources WHERE source_key='simulator-primary'"))


@pytest.mark.integration
def test_reads_are_bounded_stably_ordered_and_detect_in_memory_mutation() -> None:
    settings = evidence_settings()
    for event_id in ("ordered-2", "ordered-1"):
        with session_scope(settings) as session:
            ingest_evidence(session, sample_evidence_request(source_event_id=event_id))
    with session_scope(settings) as session:
        response = list_evidence(session, limit=1, offset=0)
        assert len(response.items) == 1
        found = get_evidence(session, response.items[0].evidence_id)
        assert found is not None
        record = session.get(EvidenceRecord, found.evidence_id)
        assert record is not None
        record.payload["pipeline_pressure_bar"] = 2.9
        assert verify_record_integrity(record) is False


@pytest.mark.integration
def test_historical_v1_record_remains_readable_and_integrity_verifiable() -> None:
    settings = evidence_settings()
    historical = HistoricalEvidenceEnvelopeV1.model_validate(
        {
            "source_key": "simulator-primary",
            "source_event_id": "historical-v1-persisted",
            "evidence_type": "simulator_telemetry",
            "observed_at": "2026-01-01T00:00:01Z",
            "sequence_number": 1,
            "payload_schema": "otsoc.simulator.telemetry",
            "payload_schema_version": "1.0.0",
            "payload": {
                "simulation_id": "sim-historical-v1",
                "sequence_number": 1,
                "timestamp": "2026-01-01T00:00:01Z",
                "simulator_version": "2.0.0",
                "configuration_hash": "1" * 64,
                "simulation_time_seconds": 1,
                "tank_level_percent": 50.0,
                "pump_command_percent": 55.0,
                "pump_running": True,
                "flow_rate_m3h": 1.0,
                "inlet_temperature_c": 28.0,
                "outlet_temperature_c": 25.0,
                "pressure_bar": 0.5,
            },
            "provenance": {
                "producer": "otsoc_simulator",
                "producer_version": "2.0.0",
                "simulation_id": "sim-historical-v1",
                "configuration_hash": "1" * 64,
            },
        }
    )
    with session_scope(settings) as session:
        source = session.scalar(
            select(EvidenceSource).where(EvidenceSource.source_key == "simulator-primary")
        )
        assert source is not None
        canonical = canonical_evidence_bytes(source.id, historical)
        evidence_id = deterministic_evidence_id(source.id, historical)
        session.add(
            EvidenceRecord(
                evidence_id=evidence_id,
                evidence_version=1,
                source_id=source.id,
                source_event_id=historical.source_event_id,
                evidence_type=historical.evidence_type,
                observed_at=historical.observed_at,
                received_at=datetime.now(UTC),
                sequence_number=historical.sequence_number,
                payload_schema=historical.payload_schema,
                payload_schema_version=historical.payload_schema_version,
                payload=historical.payload.model_dump(mode="json"),
                provenance=historical.provenance.model_dump(mode="json"),
                integrity_sha256=integrity_sha256(canonical),
                canonical_byte_length=len(canonical),
            )
        )

    with session_scope(settings) as session:
        record = session.get(EvidenceRecord, evidence_id)
        assert record is not None
        assert verify_record_integrity(record) is True
        response = get_evidence(session, evidence_id)
        assert response is not None
        assert response.payload_schema_version == "1.0.0"
        assert "tank_level_percent" in response.payload.model_dump()


@pytest.mark.integration
def test_database_foreign_key_is_enforced() -> None:
    settings = evidence_settings()
    with pytest.raises(IntegrityError), session_scope(settings) as session:
        session.execute(
            text(
                """
                    INSERT INTO evidence_records
                        (evidence_id, evidence_version, source_id, source_event_id, evidence_type,
                         observed_at, received_at, sequence_number, payload_schema,
                         payload_schema_version, payload, provenance, integrity_sha256,
                         canonical_byte_length)
                    VALUES
                        (gen_random_uuid(), 1, gen_random_uuid(), 'bad-fk', 'simulator_telemetry',
                         :now, :now, 1, 'otsoc.simulator.telemetry', '2.0.0', '{}'::jsonb,
                         '{}'::jsonb, :digest, 2)
                    """
            ),
            {"now": datetime.now(UTC), "digest": "0" * 64},
        )
