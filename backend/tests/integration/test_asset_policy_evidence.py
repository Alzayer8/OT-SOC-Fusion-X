from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from app.context.adapters import (
    AssetPolicyEvidenceError,
    persist_asset_context,
    persist_asset_context_and_finding,
    persist_policy_finding,
)
from app.context.canonical import canonical_policy_bytes, sha256_hex
from app.context.fixtures import load_fixture
from app.context.inventory import load_inventory_profile
from app.context.models import CommunicationPolicyProfile
from app.context.policy import LoadedPolicy, load_policy_profile
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.evidence.service import get_evidence, verify_record_integrity
from app.protocols.adapters import persist_raw_event, persist_semantic_evidence
from app.protocols.profile import load_profile
from tests.integration.test_evidence_persistence import evidence_settings
from tests.integration.test_migrations import alembic_config


@pytest.fixture(autouse=True)
def migrated_clean_asset_policy_database() -> None:
    command.upgrade(alembic_config(), "head")
    with engine_for(evidence_settings()).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)


def _persist_semantic(file_name: str):  # type: ignore[no-untyped-def]
    fixture, fixture_bytes = load_fixture(file_name)
    with session_scope(evidence_settings()) as session:
        raw = persist_raw_event(session, fixture.event, fixture_bytes=fixture_bytes)
    with session_scope(evidence_settings()) as session:
        semantic, payload = persist_semantic_evidence(session, raw.evidence_id, load_profile())
    return fixture, raw, semantic, payload


@pytest.mark.integration
def test_asset_policy_derivatives_persist_link_read_and_preserve_parents() -> None:
    fixture, raw, semantic, _ = _persist_semantic("known_hmi_approved_read.json")
    inventory = load_inventory_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=load_profile())
    with session_scope(evidence_settings()) as session:
        raw_record = session.get(EvidenceRecord, raw.evidence_id)
        semantic_record = session.get(EvidenceRecord, semantic.evidence_id)
        assert raw_record is not None and semantic_record is not None
        snapshots = {
            raw.evidence_id: (dict(raw_record.payload), raw_record.integrity_sha256),
            semantic.evidence_id: (dict(semantic_record.payload), semantic_record.integrity_sha256),
        }
        workflow = persist_asset_context_and_finding(
            session,
            semantic.evidence_id,
            inventory,
            policy,
            source_claims=fixture.source_identity_claims,
            destination_claims=fixture.destination_identity_claims,
        )
        context_record = session.get(EvidenceRecord, workflow.context_receipt.evidence_id)
        finding_record = session.get(EvidenceRecord, workflow.finding_receipt.evidence_id)
        assert context_record is not None and finding_record is not None
        assert verify_record_integrity(context_record) is True
        assert verify_record_integrity(finding_record) is True
        assert workflow.context_event.semantic_event_id == semantic.evidence_id
        assert (
            workflow.context_event.semantic_evidence_integrity_sha256
            == semantic_record.integrity_sha256
        )
        assert workflow.policy_finding.asset_context_event_id == context_record.evidence_id
        assert (
            workflow.policy_finding.semantic_evidence_integrity_sha256
            == semantic_record.integrity_sha256
        )
        assert workflow.context_event.ground_truth_used is False
        assert workflow.policy_finding.ground_truth_used is False
        context_read = get_evidence(session, context_record.evidence_id)
        finding_read = get_evidence(session, finding_record.evidence_id)
        assert context_read is not None and context_read.evidence_type == "asset_context_event"
        assert finding_read is not None
        assert finding_read.evidence_type == "communication_policy_finding"
        for evidence_id, snapshot in snapshots.items():
            record = session.get(EvidenceRecord, evidence_id)
            assert record is not None
            assert (dict(record.payload), record.integrity_sha256) == snapshot


@pytest.mark.integration
def test_asset_policy_parent_hash_substitution_fails_closed() -> None:
    fixture, _, semantic, _ = _persist_semantic("known_hmi_approved_read.json")
    inventory = load_inventory_profile()
    policy = load_policy_profile()
    with pytest.raises(AssetPolicyEvidenceError), session_scope(evidence_settings()) as session:
        persist_asset_context(
            session,
            semantic.evidence_id,
            inventory,
            source_claims=fixture.source_identity_claims,
            destination_claims=fixture.destination_identity_claims,
            expected_semantic_sha256="0" * 64,
        )
    with session_scope(evidence_settings()) as session:
        context, _ = persist_asset_context(
            session,
            semantic.evidence_id,
            inventory,
            source_claims=fixture.source_identity_claims,
            destination_claims=fixture.destination_identity_claims,
        )
    with pytest.raises(AssetPolicyEvidenceError), session_scope(evidence_settings()) as session:
        persist_policy_finding(
            session,
            semantic.evidence_id,
            context.evidence_id,
            inventory,
            policy,
            expected_context_sha256="0" * 64,
        )


@pytest.mark.integration
def test_asset_policy_concurrent_derivative_idempotency() -> None:
    fixture, _, semantic, _ = _persist_semantic("duplicate_policy_evaluation.json")
    inventory = load_inventory_profile()
    policy = load_policy_profile()

    def submit_context() -> str:
        with session_scope(evidence_settings()) as session:
            receipt, _ = persist_asset_context(
                session,
                semantic.evidence_id,
                inventory,
                source_claims=fixture.source_identity_claims,
                destination_claims=fixture.destination_identity_claims,
            )
            return receipt.status

    with ThreadPoolExecutor(max_workers=8) as executor:
        context_statuses = list(executor.map(lambda _: submit_context(), range(8)))
    assert context_statuses.count("accepted") == 1
    assert context_statuses.count("duplicate_existing") == 7
    with session_scope(evidence_settings()) as session:
        context_id = session.scalar(
            select(EvidenceRecord.evidence_id).where(
                EvidenceRecord.evidence_type == "asset_context_event"
            )
        )
    assert context_id is not None

    def submit_finding() -> str:
        with session_scope(evidence_settings()) as session:
            receipt, _ = persist_policy_finding(
                session, semantic.evidence_id, context_id, inventory, policy
            )
            return receipt.status

    with ThreadPoolExecutor(max_workers=8) as executor:
        finding_statuses = list(executor.map(lambda _: submit_finding(), range(8)))
    assert finding_statuses.count("accepted") == 1
    assert finding_statuses.count("duplicate_existing") == 7
    with session_scope(evidence_settings()) as session:
        assert session.scalar(select(func.count()).select_from(EvidenceRecord)) == 4


@pytest.mark.integration
def test_policy_version_re_evaluation_preserves_historical_finding() -> None:
    fixture, _, semantic, _ = _persist_semantic("known_hmi_approved_read.json")
    inventory = load_inventory_profile()
    policy = load_policy_profile()
    with session_scope(evidence_settings()) as session:
        context, _ = persist_asset_context(
            session,
            semantic.evidence_id,
            inventory,
            source_claims=fixture.source_identity_claims,
            destination_claims=fixture.destination_identity_claims,
        )
    with session_scope(evidence_settings()) as session:
        old, _ = persist_policy_finding(
            session, semantic.evidence_id, context.evidence_id, inventory, policy
        )
    document = policy.profile.model_dump(mode="python")
    document["profile_version"] = "1.0.1"
    profile = CommunicationPolicyProfile.model_validate(document)
    revised = LoadedPolicy(profile=profile, sha256=sha256_hex(canonical_policy_bytes(profile)))
    with session_scope(evidence_settings()) as session:
        new, finding = persist_policy_finding(
            session, semantic.evidence_id, context.evidence_id, inventory, revised
        )
        assert new.evidence_id != old.evidence_id
        assert finding.policy_version == "1.0.1"
        assert get_evidence(session, old.evidence_id) is not None
        assert get_evidence(session, new.evidence_id) is not None


@pytest.mark.integration
def test_asset_policy_derivatives_are_append_only() -> None:
    fixture, _, semantic, _ = _persist_semantic("known_hmi_approved_read.json")
    inventory = load_inventory_profile()
    policy = load_policy_profile()
    with session_scope(evidence_settings()) as session:
        workflow = persist_asset_context_and_finding(
            session,
            semantic.evidence_id,
            inventory,
            policy,
            source_claims=fixture.source_identity_claims,
            destination_claims=fixture.destination_identity_claims,
        )
    for evidence_id in (
        workflow.context_receipt.evidence_id,
        workflow.finding_receipt.evidence_id,
    ):
        with pytest.raises(DBAPIError), session_scope(evidence_settings()) as session:
            session.execute(
                text("UPDATE evidence_records SET source_event_id='changed' WHERE evidence_id=:id"),
                {"id": evidence_id},
            )
