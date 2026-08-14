from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.evidence.service import verify_record_integrity
from app.incidents.models import Incident
from app.tools.phase9_demo_seed import seed_final_dataset
from tests.integration.test_evidence_persistence import evidence_settings


def _clear() -> None:
    settings = evidence_settings()
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)


def _counts() -> tuple[int, int]:
    with session_scope(evidence_settings()) as session:
        evidence = session.scalar(select(func.count()).select_from(EvidenceRecord))
        incidents = session.scalar(select(func.count()).select_from(Incident))
    return int(evidence or 0), int(incidents or 0)


def test_final_seed_is_complete_integrity_verified_and_idempotent() -> None:
    _clear()
    settings = evidence_settings()

    first = seed_final_dataset(settings)
    counts_after_first = _counts()
    second = seed_final_dataset(settings)
    counts_after_second = _counts()

    assert first == second
    assert first["receipt_identity"] == second["receipt_identity"]
    assert first["status"] == "complete"
    assert first["counts"] == {
        "evidence_records": counts_after_first[0],
        "incidents": counts_after_first[1],
    }
    assert counts_after_first == counts_after_second
    assert len(first["cases"]) == 5
    assert first["cases"]["OTSOC-EVAL-V1-BG-001"]["incident"] is None
    assert first["cases"]["OTSOC-EVAL-V1-S1-001"]["incident"] == {
        "category": "ASSET_IDENTITY_ANOMALY",
        "severity": "LOW",
        "status": "OPEN",
    }
    assert first["cases"]["OTSOC-EVAL-V1-S2-001"]["incident"] == {
        "category": "COMMUNICATION_POLICY_VIOLATION",
        "severity": "MEDIUM",
        "status": "OPEN",
    }
    assert first["cases"]["OTSOC-EVAL-V1-S3-001"]["incident"] == {
        "category": "CONTROL_COMMAND_INVESTIGATION",
        "severity": "HIGH",
        "status": "OPEN",
    }
    assert first["cases"]["OTSOC-EVAL-V1-S4-001"]["incident"] == {
        "category": "PROCESS_INCONSISTENCY",
        "severity": "HIGH",
        "status": "OPEN",
    }
    assert first["cases"]["OTSOC-EVAL-V1-S4-001"]["correlation_evidence"]["cyber_parent_count"] == 0
    with session_scope(settings) as session:
        records = session.scalars(select(EvidenceRecord)).all()
        assert records
        assert all(verify_record_integrity(record) for record in records)


def test_final_dataset_reproduces_all_five_cases_three_times() -> None:
    identities: list[str] = []
    case_results: list[dict[str, object]] = []
    for _ in range(3):
        _clear()
        receipt = seed_final_dataset(evidence_settings())
        identities.append(receipt["receipt_identity"])
        case_results.extend(receipt["cases"].values())

    assert len(set(identities)) == 1
    assert len(case_results) == 15
    assert all(item["replay_ordering_correct"] is not False for item in case_results)
