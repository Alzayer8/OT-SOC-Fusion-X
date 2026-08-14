from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from sqlalchemy import func, select

from alembic import command
from app.auth.models import LocalUser, SocAuditEvent
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.incidents.models import Incident
from app.incidents.repository import list_incidents
from app.incidents.schemas import IncidentListFilters
from app.lab.catalog import LabScenarioId
from app.lab.service import (
    list_run_history,
    reset_lab,
    start_scenario,
    startup_baseline,
)
from app.product.service import overview_summary, replay_for_incident
from tests.auth_helpers import TEST_ADMIN_USERNAME, create_test_admin
from tests.integration.test_evidence_persistence import evidence_settings
from tests.integration.test_migrations import alembic_config


@pytest.fixture(scope="module")
def v11_lab_result() -> Generator[dict[str, Any], None, None]:
    command.upgrade(alembic_config(), "head")
    settings = evidence_settings()
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
    create_test_admin(settings)
    with session_scope(settings) as session:
        admin = session.scalar(select(LocalUser).where(LocalUser.username == TEST_ADMIN_USERNAME))
        assert admin is not None
        baseline = startup_baseline(settings, session)
        baseline_overview = overview_summary(session).model_dump(mode="json")
        scenario_results: dict[str, dict[str, Any]] = {}
        for scenario_id in (
            LabScenarioId.S1,
            LabScenarioId.S2,
            LabScenarioId.S3,
            LabScenarioId.S4,
        ):
            result = start_scenario(
                settings,
                session,
                scenario_id,
                actor_user_id=admin.user_id,
                actor_context=admin.display_name,
                request_id=f"v11-scenario-{scenario_id.value.lower()}",
            )
            scenario_results[scenario_id.value] = {
                "run": result.active_run.model_dump(mode="json"),
                "overview": overview_summary(session).model_dump(mode="json"),
            }
        before_reset = tuple(
            session.execute(
                select(EvidenceRecord.evidence_id, EvidenceRecord.integrity_sha256).order_by(
                    EvidenceRecord.evidence_id
                )
            ).all()
        )
        reset_context = reset_lab(
            session,
            actor_user_id=admin.user_id,
            actor_context=admin.display_name,
            request_id="v11-lab-reset",
        )
        after_reset = tuple(
            session.execute(
                select(EvidenceRecord.evidence_id, EvidenceRecord.integrity_sha256).order_by(
                    EvidenceRecord.evidence_id
                )
            ).all()
        )
        restart_context = startup_baseline(settings, session)
        current_incidents = list_incidents(
            session,
            filters=IncidentListFilters(),
            limit=100,
            cursor=None,
            scope="CURRENT",
        )
        historical_incidents = list_incidents(
            session,
            filters=IncidentListFilters(),
            limit=100,
            cursor=None,
            scope="ALL_HISTORY",
        )
        history = list_run_history(session, scenario_id=None, state=None, limit=100, offset=0)
        counts = {
            "evidence": int(session.scalar(select(func.count()).select_from(EvidenceRecord)) or 0),
            "incidents": int(session.scalar(select(func.count()).select_from(Incident)) or 0),
            "audits": int(session.scalar(select(func.count()).select_from(SocAuditEvent)) or 0),
        }
        s3_id = uuid.UUID(scenario_results["S3"]["run"]["incident_ids"][0])
        s4_id = uuid.UUID(scenario_results["S4"]["run"]["incident_ids"][0])
        s3_replay = replay_for_incident(session, s3_id).model_dump(mode="json")
        s4_replay = replay_for_incident(session, s4_id).model_dump(mode="json")
        yield {
            "baseline": baseline.model_dump(mode="json"),
            "baseline_overview": baseline_overview,
            "scenarios": scenario_results,
            "before_reset": before_reset,
            "after_reset": after_reset,
            "reset": reset_context.model_dump(mode="json"),
            "restart": restart_context.model_dump(mode="json"),
            "current_incidents": current_incidents,
            "historical_incidents": historical_incidents,
            "history": history,
            "counts": counts,
            "s3_replay": s3_replay,
            "s4_replay": s4_replay,
        }
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)


@pytest.mark.integration
def test_v11_clean_baseline_is_normal_current_context(v11_lab_result: dict[str, Any]) -> None:
    baseline = v11_lab_result["baseline"]["active_run"]
    overview = v11_lab_result["baseline_overview"]
    assert baseline["scenario_id"] == "BASELINE"
    assert baseline["status"] == "COMPLETED"
    assert baseline["evidence_count"] == 80
    assert baseline["incident_count"] == 0
    assert overview["active_run"]["scenario_id"] == "BASELINE"
    assert overview["incidents"]["total"] == 0
    assert overview["incidents"]["high"] == 0
    assert overview["policy_findings"]["denied"] == 0
    assert overview["correlations"]["correlated"] == 0
    assert overview["process_snapshot_status"] == "COMPLETE"
    assert overview["process_snapshot_scope"] == "ACTIVE_RUN"
    assert overview["as_of"] != overview["generated_at"]


@pytest.mark.integration
def test_v11_s1_s4_runs_have_exact_deterministic_deltas(
    v11_lab_result: dict[str, Any],
) -> None:
    scenarios = v11_lab_result["scenarios"]
    assert {
        key: (value["run"]["evidence_count"], value["run"]["incident_count"])
        for key, value in scenarios.items()
    } == {"S1": (4, 1), "S2": (4, 1), "S3": (46, 1), "S4": (72, 1)}
    for scenario_id, value in scenarios.items():
        assert value["run"]["status"] == "COMPLETED"
        assert value["overview"]["active_run"]["scenario_id"] == scenario_id
        assert value["overview"]["incidents"]["total"] == 1
    assert scenarios["S1"]["overview"]["process_snapshot_scope"] == "BASELINE_REFERENCE"
    assert scenarios["S2"]["overview"]["process_snapshot_scope"] == "BASELINE_REFERENCE"


@pytest.mark.integration
def test_v11_s3_and_s4_preserve_golden_semantic_boundaries(
    v11_lab_result: dict[str, Any],
) -> None:
    s3_evidence = [
        event["evidence"]
        for event in v11_lab_result["s3_replay"]["events"]
        if event["evidence"] is not None
    ]
    raw = next(item for item in s3_evidence if item["evidence_type"] == "synthetic_protocol_event")
    semantic = next(
        item for item in s3_evidence if item["evidence_type"] == "protocol_semantic_event"
    )
    assert raw["payload"]["function_code"] == 6
    assert raw["payload"]["address_offset"] == 1
    assert raw["payload"]["raw_value"] == 250
    assert semantic["payload"]["point_id"] == "control_valve_command_percent"
    assert semantic["payload"]["fictional_target_component"] == "CV-101"
    assert semantic["payload"]["decoded_value"] == "25.0"

    s4_evidence = [
        event["evidence"]
        for event in v11_lab_result["s4_replay"]["events"]
        if event["evidence"] is not None
    ]
    assert {item["evidence_type"] for item in s4_evidence} == {
        "simulator_telemetry",
        "correlation_finding",
    }
    correlation = next(
        item for item in s4_evidence if item["evidence_type"] == "correlation_finding"
    )
    assert correlation["payload"]["primary_cyber_evidence_id"] is None
    assert correlation["payload"]["causality_inferred"] is False
    assert correlation["payload"]["malicious_intent_inferred"] is False


@pytest.mark.integration
def test_v11_reset_and_restart_preserve_history_but_activate_baseline(
    v11_lab_result: dict[str, Any],
) -> None:
    assert v11_lab_result["before_reset"] == v11_lab_result["after_reset"]
    assert v11_lab_result["reset"]["active_run"]["scenario_id"] == "BASELINE"
    assert v11_lab_result["restart"]["active_run"]["scenario_id"] == "BASELINE"
    assert len(v11_lab_result["current_incidents"].items) == 0
    assert len(v11_lab_result["historical_incidents"].items) == 4
    assert v11_lab_result["history"].total == 5
    assert v11_lab_result["counts"] == {"evidence": 206, "incidents": 4, "audits": 10}
