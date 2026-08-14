from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from app.context.adapters import persist_asset_context_and_finding
from app.context.fixtures import load_fixture
from app.context.inventory import load_inventory_profile
from app.context.models import PolicyStatus, ResolutionStatus, ZoneId
from app.context.policy import load_policy_profile
from app.core.config import Settings
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.protocols.adapters import persist_raw_event, persist_semantic_evidence
from app.protocols.profile import load_profile


@dataclass(frozen=True, slots=True)
class ContextRuntimeCheckResult:
    semantic_evidence_exists: bool
    exact_source_identity_resolved: bool
    exact_destination_identity_resolved: bool
    zones_resolved: bool
    asset_context_persisted: bool
    policy_evaluated: bool
    policy_finding_persisted: bool
    retry_is_duplicate: bool
    s1_unknown: bool
    s2_denied: bool
    s3_approved: bool
    s3_unapproved_denied: bool
    semantic_evidence_unchanged: bool
    raw_evidence_unchanged: bool
    ground_truth_absent: bool


def _settings() -> Settings:
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url is None or "otsoc_test" not in test_url:
        raise SystemExit("TEST_DATABASE_URL must target the isolated otsoc_test database")
    return Settings(
        app_name="OT-SOC Fusion X",
        app_version="1.0.0",
        app_env="development",
        api_version="v1",
        log_level="WARNING",
        cors_origins=["http://localhost:5173"],
        database_url=test_url,
        database_connect_timeout_seconds=2,
    )


def main() -> int:
    settings = _settings()
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
    inventory = load_inventory_profile()
    protocol = load_profile()
    policy = load_policy_profile(inventory=inventory, protocol_profile=protocol)

    results = {}
    snapshots = None
    retry = None
    for file_name in (
        "s1_unknown_source_asset.json",
        "s2_it_to_controller.json",
        "s3_hmi_approved_valve_command.json",
        "s3_engineering_denied_valve_command.json",
    ):
        fixture, fixture_bytes = load_fixture(file_name)
        with session_scope(settings) as session:
            raw = persist_raw_event(session, fixture.event, fixture_bytes=fixture_bytes)
        with session_scope(settings) as session:
            semantic, _ = persist_semantic_evidence(session, raw.evidence_id, protocol)
        with session_scope(settings) as session:
            raw_record = session.get(EvidenceRecord, raw.evidence_id)
            semantic_record = session.get(EvidenceRecord, semantic.evidence_id)
            if raw_record is None or semantic_record is None:
                raise RuntimeError("raw or semantic parent evidence is unavailable")
            if file_name == "s3_hmi_approved_valve_command.json":
                snapshots = (
                    (dict(raw_record.payload), raw_record.integrity_sha256),
                    (dict(semantic_record.payload), semantic_record.integrity_sha256),
                )
            workflow = persist_asset_context_and_finding(
                session,
                semantic.evidence_id,
                inventory,
                policy,
                source_claims=fixture.source_identity_claims,
                destination_claims=fixture.destination_identity_claims,
            )
            results[file_name] = workflow
        if file_name == "s3_hmi_approved_valve_command.json":
            with session_scope(settings) as session:
                retry = persist_asset_context_and_finding(
                    session,
                    semantic.evidence_id,
                    inventory,
                    policy,
                    source_claims=fixture.source_identity_claims,
                    destination_claims=fixture.destination_identity_claims,
                )
            with session_scope(settings) as session:
                raw_after = session.get(EvidenceRecord, raw.evidence_id)
                semantic_after = session.get(EvidenceRecord, semantic.evidence_id)
                if raw_after is None or semantic_after is None:
                    raise RuntimeError("parent evidence disappeared")
                after = (
                    (dict(raw_after.payload), raw_after.integrity_sha256),
                    (dict(semantic_after.payload), semantic_after.integrity_sha256),
                )

    approved = results["s3_hmi_approved_valve_command.json"]
    s1 = results["s1_unknown_source_asset.json"]
    s2 = results["s2_it_to_controller.json"]
    s3_denied = results["s3_engineering_denied_valve_command.json"]
    serialized = "".join(
        item.context_event.model_dump_json() + item.policy_finding.model_dump_json()
        for item in results.values()
    ).lower()
    result = ContextRuntimeCheckResult(
        semantic_evidence_exists=all(
            item.context_event.semantic_event_id for item in results.values()
        ),
        exact_source_identity_resolved=(
            approved.context_event.source_resolution.status is ResolutionStatus.RESOLVED
            and approved.context_event.source_resolution.asset_key == "HMI-01"
        ),
        exact_destination_identity_resolved=(
            approved.context_event.destination_resolution.status is ResolutionStatus.RESOLVED
            and approved.context_event.destination_resolution.asset_key == "PLC-01"
        ),
        zones_resolved=(
            approved.context_event.source_resolution.zone_id is ZoneId.OT_CONTROL_ZONE
            and approved.context_event.destination_resolution.zone_id is ZoneId.OT_CONTROL_ZONE
        ),
        asset_context_persisted=all(
            item.context_receipt.status == "accepted" for item in results.values()
        ),
        policy_evaluated=all(item.policy_finding.reason_code for item in results.values()),
        policy_finding_persisted=all(
            item.finding_receipt.status == "accepted" for item in results.values()
        ),
        retry_is_duplicate=(
            retry is not None
            and retry.context_receipt.status == "duplicate_existing"
            and retry.finding_receipt.status == "duplicate_existing"
        ),
        s1_unknown=s1.policy_finding.policy_status is PolicyStatus.UNKNOWN,
        s2_denied=s2.policy_finding.policy_status is PolicyStatus.DENIED,
        s3_approved=approved.policy_finding.policy_status is PolicyStatus.APPROVED,
        s3_unapproved_denied=s3_denied.policy_finding.policy_status is PolicyStatus.DENIED,
        semantic_evidence_unchanged=snapshots is not None and snapshots[1] == after[1],
        raw_evidence_unchanged=snapshots is not None and snapshots[0] == after[0],
        ground_truth_absent=(
            "scenario_id" not in serialized
            and '"ground_truth"' not in serialized
            and all(not item.context_event.ground_truth_used for item in results.values())
            and all(not item.policy_finding.ground_truth_used for item in results.values())
        ),
    )
    if not all(asdict(result).values()):
        raise RuntimeError("one or more Phase 5B offline runtime checks failed")
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
