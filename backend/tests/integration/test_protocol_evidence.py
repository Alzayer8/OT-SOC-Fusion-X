from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.evidence.service import get_evidence, verify_record_integrity
from app.protocols.adapters import (
    ProtocolEvidenceError,
    persist_raw_event,
    persist_semantic_evidence,
)
from app.protocols.fixtures import load_fixture
from app.protocols.profile import LoadedProfile, load_profile
from tests.integration.test_evidence_persistence import evidence_settings
from tests.integration.test_migrations import alembic_config


@pytest.fixture(autouse=True)
def migrated_clean_protocol_database() -> None:
    command.upgrade(alembic_config(), "head")
    with engine_for(evidence_settings()).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)


@pytest.mark.integration
def test_source_evidence_linkage() -> None:
    event, fixture_bytes = load_fixture("p4b-s3-valve-command-25.json")
    with session_scope(evidence_settings()) as session:
        raw = persist_raw_event(session, event, fixture_bytes=fixture_bytes)
    with session_scope(evidence_settings()) as session:
        semantic, payload = persist_semantic_evidence(session, raw.evidence_id, load_profile())
        raw_record = session.get(EvidenceRecord, raw.evidence_id)
        assert raw_record is not None
        assert payload.source_evidence_id == raw.evidence_id
        assert payload.source_evidence_integrity_sha256 == raw_record.integrity_sha256
        assert payload.observed_at == raw_record.observed_at
        semantic_record = session.get(EvidenceRecord, semantic.evidence_id)
        assert semantic_record is not None
        assert semantic_record.sequence_number == raw_record.sequence_number

    with pytest.raises(ProtocolEvidenceError), session_scope(evidence_settings()) as session:
        persist_semantic_evidence(
            session,
            raw.evidence_id,
            load_profile(),
            expected_source_sha256="0" * 64,
        )
    approved = load_profile()
    tampered = LoadedProfile(profile=approved.profile, sha256="0" * 64)
    with pytest.raises(ProtocolEvidenceError), session_scope(evidence_settings()) as session:
        persist_semantic_evidence(session, raw.evidence_id, tampered)


@pytest.mark.integration
def test_raw_evidence_preservation() -> None:
    event, fixture_bytes = load_fixture("p4b-s3-valve-command-25.json")
    with session_scope(evidence_settings()) as session:
        raw = persist_raw_event(session, event, fixture_bytes=fixture_bytes)
    with session_scope(evidence_settings()) as session:
        before = session.get(EvidenceRecord, raw.evidence_id)
        assert before is not None
        snapshot = (
            dict(before.payload),
            dict(before.provenance),
            before.integrity_sha256,
            before.canonical_byte_length,
            before.received_at,
        )
    with session_scope(evidence_settings()) as session:
        persist_semantic_evidence(session, raw.evidence_id, load_profile())
    with session_scope(evidence_settings()) as session:
        after = session.get(EvidenceRecord, raw.evidence_id)
        assert after is not None
        assert (
            dict(after.payload),
            dict(after.provenance),
            after.integrity_sha256,
            after.canonical_byte_length,
            after.received_at,
        ) == snapshot
        assert verify_record_integrity(after) is True


@pytest.mark.integration
def test_semantic_integrity_hashing() -> None:
    event, fixture_bytes = load_fixture("p4b-s3-valve-command-25.json")
    with session_scope(evidence_settings()) as session:
        raw = persist_raw_event(session, event, fixture_bytes=fixture_bytes)
    with session_scope(evidence_settings()) as session:
        semantic, _ = persist_semantic_evidence(session, raw.evidence_id, load_profile())
    with session_scope(evidence_settings()) as session:
        record = session.get(EvidenceRecord, semantic.evidence_id)
        assert record is not None
        assert verify_record_integrity(record) is True
        record.payload["semantic_statement"] = "mutated"
        assert verify_record_integrity(record) is False
        source = session.get(EvidenceRecord, raw.evidence_id)
        assert source is not None
        assert verify_record_integrity(source) is True


@pytest.mark.integration
def test_duplicate_decoding_idempotency() -> None:
    event, fixture_bytes = load_fixture("p4b-s3-valve-command-25.json")
    with session_scope(evidence_settings()) as session:
        raw = persist_raw_event(session, event, fixture_bytes=fixture_bytes)

    def submit() -> str:
        with session_scope(evidence_settings()) as session:
            receipt, _ = persist_semantic_evidence(session, raw.evidence_id, load_profile())
            return receipt.status

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(lambda _: submit(), range(8)))
    assert statuses.count("accepted") == 1
    assert statuses.count("duplicate_existing") == 7
    with session_scope(evidence_settings()) as session:
        count = session.scalar(
            select(func.count())
            .select_from(EvidenceRecord)
            .where(EvidenceRecord.evidence_type == "protocol_semantic_event")
        )
        assert count == 1


@pytest.mark.integration
def test_protocol_evidence_read_types_and_append_only() -> None:
    event, fixture_bytes = load_fixture("p4b-normal-read-flow.json")
    with session_scope(evidence_settings()) as session:
        raw = persist_raw_event(session, event, fixture_bytes=fixture_bytes)
    with session_scope(evidence_settings()) as session:
        semantic, _ = persist_semantic_evidence(session, raw.evidence_id, load_profile())
    with session_scope(evidence_settings()) as session:
        raw_read = get_evidence(session, raw.evidence_id)
        semantic_read = get_evidence(session, semantic.evidence_id)
        assert raw_read is not None and raw_read.evidence_type == "synthetic_protocol_event"
        assert semantic_read is not None
        assert semantic_read.evidence_type == "protocol_semantic_event"
        serialized = semantic_read.model_dump_json().lower()
        assert "scenario_id" not in serialized
        assert 'ground_truth_used":false' in serialized

    for evidence_id in (raw.evidence_id, semantic.evidence_id):
        with pytest.raises(DBAPIError), session_scope(evidence_settings()) as session:
            session.execute(
                text("UPDATE evidence_records SET source_event_id='changed' WHERE evidence_id=:id"),
                {"id": evidence_id},
            )
