from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import Settings
from app.db.session import session_scope
from app.evidence.models import EvidenceRecord
from app.incidents.models import (
    EvidenceSelection,
    Incident,
    IncidentQualificationReceipt,
    IncidentQualificationRequest,
)
from app.incidents.repository import get_incident_detail
from app.incidents.service import qualify_stored_evidence
from app.product.service import replay_for_incident
from app.tools.incident_support import persist_correlation_chain, persist_policy_chain
from app.tools.phase9_dataset import (
    DATASET_ID,
    DATASET_SEED,
    DATASET_VERSION,
    DatasetCase,
    LoadedDataset,
    load_dataset,
)


class DemoSeedError(ValueError):
    pass


DETERMINISTIC_RECEIPT_TIME = datetime(2026, 8, 11, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class DatasetCaseEvidenceRoot:
    """Verified immutable root produced by one frozen Phase 9 dataset case."""

    role: Literal["POLICY_FINDING", "CORRELATION_FINDING"]
    selection: EvidenceSelection


@dataclass(frozen=True, slots=True)
class DatasetCaseExecution:
    """Typed single-case result used by the CLI seed and the Scenario Lab."""

    case_id: str
    case_kind: Literal["BACKGROUND", "S1", "S2", "S3", "S4"]
    evidence_roots: tuple[DatasetCaseEvidenceRoot, ...]
    incident_ids: tuple[uuid.UUID, ...]
    receipt: dict[str, Any]


def _settings() -> Settings:
    settings = Settings()
    parsed = make_url(settings.database_url_string)
    if parsed.host not in {"db", "localhost", "127.0.0.1"}:
        raise DemoSeedError("the demo seed accepts only the local Compose database")
    if parsed.database not in {"otsoc", "otsoc_demo", "otsoc_test"}:
        raise DemoSeedError("the demo seed database name is not approved")
    return settings


def _migrate() -> None:
    config = Config("alembic.ini")
    command.upgrade(config, "head")


def _record(settings: Settings, evidence_id: uuid.UUID) -> EvidenceRecord:
    with session_scope(settings) as session:
        record = session.get(EvidenceRecord, evidence_id)
        if record is None:
            raise DemoSeedError("seeded evidence could not be reloaded")
        session.expunge(record)
        return record


def _policy_result(settings: Settings, fixture: str) -> tuple[EvidenceSelection, dict[str, Any]]:
    selection = persist_policy_chain(
        settings,
        fixture,
        receipt_timestamp=DETERMINISTIC_RECEIPT_TIME,
    )
    record = _record(settings, selection.evidence_id)
    return selection, {
        "evidence_id": str(record.evidence_id),
        "integrity_sha256": record.integrity_sha256,
        "status": record.payload["policy_status"],
        "reason": record.payload["reason_code"],
    }


def _correlation_result(
    settings: Settings, selection: EvidenceSelection | None
) -> dict[str, Any] | None:
    if selection is None:
        return None
    record = _record(settings, selection.evidence_id)
    return {
        "evidence_id": str(record.evidence_id),
        "integrity_sha256": record.integrity_sha256,
        "status": record.payload["correlation_status"],
        "reason": record.payload["reason_code"],
        "cyber_parent_count": sum(
            record.payload.get(key) is not None
            for key in (
                "primary_cyber_evidence_id",
                "semantic_evidence_id",
                "asset_context_evidence_id",
                "policy_finding_evidence_id",
            )
        ),
    }


def _incident_result(
    settings: Settings, receipt: IncidentQualificationReceipt
) -> dict[str, Any] | None:
    incident = receipt.incident
    if incident is None:
        return None
    incident_id = incident.incident_id
    with session_scope(settings) as session:
        detail = get_incident_detail(session, incident_id)
        replay = replay_for_incident(session, incident_id)
    if detail is None:
        raise DemoSeedError("seeded incident could not be reloaded")
    replay_keys = [
        (item.observed_at.isoformat(), item.sort_rank, str(item.event_id)) for item in replay.events
    ]
    return {
        "incident_id": str(incident_id),
        "category": _value(incident.category),
        "severity": _value(incident.severity),
        "status": _value(incident.status),
        "lineage_evidence_types": sorted(
            {item.evidence.evidence_type for item in replay.events if item.evidence is not None}
        ),
        "lineage_relationships": sorted({item.relationship for item in detail.lineage_references}),
        "replay_completeness": replay.completeness,
        "replay_event_count": len(replay.events),
        "replay_ordering_correct": replay_keys == sorted(replay_keys),
        "replay_order_sha256": hashlib.sha256(
            json.dumps(replay_keys, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }


def _value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _database_counts(settings: Settings) -> dict[str, int]:
    with session_scope(settings) as session:
        evidence = session.scalar(select(func.count()).select_from(EvidenceRecord))
        incidents = session.scalar(select(func.count()).select_from(Incident))
    return {
        "evidence_records": int(evidence or 0),
        "incidents": int(incidents or 0),
    }


def _qualify_policy(
    settings: Settings, selection: EvidenceSelection
) -> IncidentQualificationReceipt:
    with session_scope(settings) as session:
        return qualify_stored_evidence(
            session,
            IncidentQualificationRequest(policy_finding=selection),
            request_id="phase9b-final-seed",
        )


def _qualify_request(
    settings: Settings, request: IncidentQualificationRequest
) -> IncidentQualificationReceipt:
    with session_scope(settings) as session:
        return qualify_stored_evidence(
            session,
            request,
            request_id="phase9b-final-seed",
        )


def _seed_background_execution(settings: Settings, case: DatasetCase) -> DatasetCaseExecution:
    roots: list[DatasetCaseEvidenceRoot] = []
    incident_ids: list[uuid.UUID] = []
    policies: list[dict[str, Any]] = []
    for fixture in case.context_fixtures:
        selection, result = _policy_result(settings, fixture.file)
        policy_receipt = _qualify_policy(settings, selection)
        incident_ids.extend(_incident_ids(policy_receipt))
        roots.append(DatasetCaseEvidenceRoot(role="POLICY_FINDING", selection=selection))
        policies.append(result)
    assert case.correlation_fixture is not None
    request = persist_correlation_chain(
        settings,
        case.correlation_fixture.file,
        simulation_id=case.run_id,
        configuration_hash=case.configuration_hash,
        seed=DATASET_SEED,
        receipt_timestamp=DETERMINISTIC_RECEIPT_TIME,
    )
    receipt = _qualify_request(settings, request)
    if request.correlation_finding is None:
        raise DemoSeedError("the background case did not produce correlation evidence")
    roots.append(
        DatasetCaseEvidenceRoot(
            role="CORRELATION_FINDING",
            selection=request.correlation_finding,
        )
    )
    result = _case_result(settings, case, policies, request, receipt)
    return DatasetCaseExecution(
        case_id=case.case_id,
        case_kind=case.case_kind,
        evidence_roots=tuple(roots),
        incident_ids=tuple(dict.fromkeys((*incident_ids, *_incident_ids(receipt)))),
        receipt=result,
    )


def _seed_background(settings: Settings, case: DatasetCase) -> dict[str, Any]:
    return _seed_background_execution(settings, case).receipt


def _seed_policy_case_execution(settings: Settings, case: DatasetCase) -> DatasetCaseExecution:
    selection, result = _policy_result(settings, case.context_fixtures[0].file)
    receipt = _qualify_policy(settings, selection)
    case_result = _case_result(settings, case, [result], None, receipt)
    return DatasetCaseExecution(
        case_id=case.case_id,
        case_kind=case.case_kind,
        evidence_roots=(DatasetCaseEvidenceRoot(role="POLICY_FINDING", selection=selection),),
        incident_ids=_incident_ids(receipt),
        receipt=case_result,
    )


def _seed_policy_case(settings: Settings, case: DatasetCase) -> dict[str, Any]:
    return _seed_policy_case_execution(settings, case).receipt


def _seed_correlation_case_execution(settings: Settings, case: DatasetCase) -> DatasetCaseExecution:
    assert case.correlation_fixture is not None
    context = case.context_fixtures[0].file if case.context_fixtures else None
    request = persist_correlation_chain(
        settings,
        case.correlation_fixture.file,
        context_fixture=context,
        simulation_id=case.run_id,
        configuration_hash=case.configuration_hash,
        seed=DATASET_SEED,
        receipt_timestamp=DETERMINISTIC_RECEIPT_TIME,
    )
    policies: list[dict[str, Any]] = []
    if request.policy_finding is not None:
        record = _record(settings, request.policy_finding.evidence_id)
        policies.append(
            {
                "evidence_id": str(record.evidence_id),
                "integrity_sha256": record.integrity_sha256,
                "status": record.payload["policy_status"],
                "reason": record.payload["reason_code"],
            }
        )
    receipt = _qualify_request(settings, request)
    if request.correlation_finding is None:
        raise DemoSeedError("the correlation case did not produce correlation evidence")
    roots: list[DatasetCaseEvidenceRoot] = []
    if request.policy_finding is not None:
        roots.append(
            DatasetCaseEvidenceRoot(
                role="POLICY_FINDING",
                selection=request.policy_finding,
            )
        )
    roots.append(
        DatasetCaseEvidenceRoot(
            role="CORRELATION_FINDING",
            selection=request.correlation_finding,
        )
    )
    result = _case_result(settings, case, policies, request, receipt)
    return DatasetCaseExecution(
        case_id=case.case_id,
        case_kind=case.case_kind,
        evidence_roots=tuple(roots),
        incident_ids=_incident_ids(receipt),
        receipt=result,
    )


def _seed_correlation_case(settings: Settings, case: DatasetCase) -> dict[str, Any]:
    return _seed_correlation_case_execution(settings, case).receipt


def _incident_ids(receipt: IncidentQualificationReceipt) -> tuple[uuid.UUID, ...]:
    return (receipt.incident_id,) if receipt.incident_id is not None else ()


def execute_dataset_case(settings: Settings, case: DatasetCase) -> DatasetCaseExecution:
    """Execute exactly one allowlisted frozen case through the accepted pipeline."""

    try:
        approved = load_dataset().manifest.case(case.case_id)
    except StopIteration as exc:
        raise DemoSeedError("the requested final dataset case is not allowlisted") from exc
    if case != approved:
        raise DemoSeedError("the requested final dataset case differs from the frozen manifest")
    if case.case_kind == "BACKGROUND":
        return _seed_background_execution(settings, case)
    if case.case_kind in {"S1", "S2"}:
        return _seed_policy_case_execution(settings, case)
    if case.case_kind in {"S3", "S4"}:
        return _seed_correlation_case_execution(settings, case)
    raise DemoSeedError("the requested final dataset case is unsupported")


def _case_result(
    settings: Settings,
    case: DatasetCase,
    policies: list[dict[str, Any]],
    request: IncidentQualificationRequest | None,
    receipt: IncidentQualificationReceipt,
) -> dict[str, Any]:
    correlation_selection = request.correlation_finding if request is not None else None
    correlation = _correlation_result(settings, correlation_selection)
    incident = _incident_result(settings, receipt)
    return {
        "case_kind": case.case_kind,
        "run_id": case.run_id,
        "configuration_id": (
            case.configuration.configuration_id if case.configuration is not None else None
        ),
        "configuration_hash": case.configuration_hash,
        "policy_statuses": [item["status"] for item in policies],
        "policy_reasons": [item["reason"] for item in policies],
        "policy_evidence": policies,
        "correlation_status": correlation["status"] if correlation is not None else None,
        "correlation_reason": correlation["reason"] if correlation is not None else None,
        "correlation_evidence": correlation,
        "incident": (
            {
                "category": incident["category"],
                "severity": incident["severity"],
                "status": incident["status"],
            }
            if incident is not None
            else None
        ),
        **(
            incident
            if incident is not None
            else {
                "lineage_evidence_types": [],
                "lineage_relationships": [],
                "replay_completeness": None,
                "replay_event_count": 0,
                "replay_ordering_correct": None,
                "replay_order_sha256": None,
            }
        ),
    }


def seed_final_dataset(settings: Settings) -> dict[str, Any]:
    loaded: LoadedDataset = load_dataset()
    cases: dict[str, Any] = {}
    for case in loaded.manifest.cases:
        cases[case.case_id] = execute_dataset_case(settings, case).receipt
    stable = {
        "status": "complete",
        "dataset_id": loaded.manifest.dataset_id,
        "dataset_version": loaded.manifest.dataset_version,
        "dataset_sha256": loaded.sha256,
        "seed": loaded.manifest.seed,
        "environment_classification": loaded.manifest.environment_classification,
        "profiles": {
            key: getattr(loaded.manifest.profiles, key).model_dump(mode="json")
            for key in ("protocol", "inventory", "policy", "correlation", "incident")
        },
        "counts": _database_counts(settings),
        "cases": cases,
    }
    identity = hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**stable, "receipt_identity": identity}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the final synthetic OT-SOC dataset.")
    parser.add_argument("command", choices=("seed",))
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--seed", required=True, type=int)
    arguments = parser.parse_args()
    if (
        arguments.dataset != DATASET_ID
        or arguments.version != DATASET_VERSION
        or arguments.seed != DATASET_SEED
    ):
        raise DemoSeedError("only the frozen Phase 9B dataset/version/seed is accepted")
    settings = _settings()
    _migrate()
    receipt = seed_final_dataset(settings)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
