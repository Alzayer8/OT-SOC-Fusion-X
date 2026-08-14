from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.api.lab import router
from app.core.config import Settings
from app.lab.catalog import LabScenarioId, dataset_case, scenario_catalog
from app.lab.models import LabActiveContext, LabRun, LabRunEvidence, LabRunIncident
from app.lab.schemas import LabNoFieldsRequest, LabRunStartRequest
from app.lab.service import _baseline_run_id, _new_run, read_catalog
from app.tools.phase9_demo_seed import DemoSeedError, execute_dataset_case


def test_scenario_catalog_is_exact_and_bound_to_the_frozen_phase9_cases() -> None:
    definitions = scenario_catalog()

    assert [item.scenario_id for item in definitions] == [
        LabScenarioId.BASELINE,
        LabScenarioId.S1,
        LabScenarioId.S2,
        LabScenarioId.S3,
        LabScenarioId.S4,
    ]
    assert [item.dataset_case_id for item in definitions] == [
        "OTSOC-EVAL-V1-BG-001",
        "OTSOC-EVAL-V1-S1-001",
        "OTSOC-EVAL-V1-S2-001",
        "OTSOC-EVAL-V1-S3-001",
        "OTSOC-EVAL-V1-S4-001",
    ]
    assert [dataset_case(item.scenario_id).case_kind for item in definitions] == [
        "BACKGROUND",
        "S1",
        "S2",
        "S3",
        "S4",
    ]
    catalog = read_catalog()
    assert [item.scenario_id for item in catalog.items] == [
        item.scenario_id for item in definitions
    ]
    assert len(catalog.dataset_sha256) == 64


def test_lab_mutation_contracts_reject_arbitrary_controls() -> None:
    assert LabRunStartRequest.model_validate({"scenario_id": "S3"}).scenario_id is LabScenarioId.S3
    assert LabNoFieldsRequest.model_validate({}) == LabNoFieldsRequest()

    with pytest.raises(ValidationError):
        LabRunStartRequest.model_validate(
            {"scenario_id": "S3", "target": "PLC-01", "payload": {"register": 1}}
        )
    with pytest.raises(ValidationError):
        LabRunStartRequest.model_validate({"scenario_id": "S5"})
    with pytest.raises(ValidationError):
        LabNoFieldsRequest.model_validate({"target": "PLC-01"})


def test_single_case_executor_rejects_a_forged_case(unit_settings: Settings) -> None:
    forged = dataset_case(LabScenarioId.S3).model_copy(update={"run_id": "forged-simulation-run"})

    with pytest.raises(DemoSeedError, match="differs from the frozen manifest"):
        execute_dataset_case(unit_settings, forged)


def test_lab_api_surface_is_bounded_to_catalog_context_history_and_mutations() -> None:
    observed = {
        (route.path, method) for route in router.routes for method in (route.methods or set())
    }

    assert observed == {
        ("/api/v1/lab/catalog", "GET"),
        ("/api/v1/lab/context", "GET"),
        ("/api/v1/lab/runs", "GET"),
        ("/api/v1/lab/runs/{run_id}", "GET"),
        ("/api/v1/lab/start", "POST"),
        ("/api/v1/lab/baseline", "POST"),
        ("/api/v1/lab/reset", "POST"),
    }


def test_lab_identity_fields_and_associations_are_restrict_only() -> None:
    run_user_fk = next(iter(LabRun.__table__.c.started_by_user_id.foreign_keys))
    context_user_fk = next(iter(LabActiveContext.__table__.c.changed_by_user_id.foreign_keys))

    assert run_user_fk.target_fullname == "local_users.user_id"
    assert run_user_fk.ondelete == "RESTRICT"
    assert context_user_fk.target_fullname == "local_users.user_id"
    assert context_user_fk.ondelete == "RESTRICT"
    for column in (
        LabRunEvidence.__table__.c.run_id,
        LabRunEvidence.__table__.c.evidence_id,
        LabRunIncident.__table__.c.run_id,
        LabRunIncident.__table__.c.incident_id,
        LabActiveContext.__table__.c.active_run_id,
    ):
        foreign_key = next(iter(column.foreign_keys))
        assert foreign_key.ondelete == "RESTRICT"


def test_baseline_identity_and_run_snapshot_are_deterministic() -> None:
    actor_user_id = uuid.UUID("1888f38a-b93c-46c0-baa4-ad5a891c6e56")
    baseline_id = _baseline_run_id()
    run = _new_run(
        LabScenarioId.S3,
        actor_user_id=actor_user_id,
        actor_context="Lab Administrator",
        started_at=datetime(2026, 8, 11, tzinfo=UTC),
    )

    assert baseline_id == _baseline_run_id()
    assert run.scenario_id == "S3"
    assert run.dataset_case_id == "OTSOC-EVAL-V1-S3-001"
    assert run.started_by_user_id == actor_user_id
    assert run.configuration_hash == dataset_case(LabScenarioId.S3).configuration_hash
    assert run.failure_code is None
