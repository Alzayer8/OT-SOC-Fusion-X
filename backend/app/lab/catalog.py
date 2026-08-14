from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Literal

from app.tools.phase9_dataset import DatasetCase, LoadedDataset, load_dataset


class LabScenarioId(StrEnum):
    BASELINE = "BASELINE"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"


LAB_SCENARIO_ORDER = (
    LabScenarioId.BASELINE,
    LabScenarioId.S1,
    LabScenarioId.S2,
    LabScenarioId.S3,
    LabScenarioId.S4,
)


@dataclass(frozen=True, slots=True)
class LabScenarioDefinition:
    scenario_id: LabScenarioId
    title: str
    description: str
    dataset_case_id: str
    definition_version: Literal["1.0.0"] = "1.0.0"
    synthetic: Literal[True] = True
    execution_mode: Literal["FROZEN_DETERMINISTIC_PIPELINE"] = "FROZEN_DETERMINISTIC_PIPELINE"


_CATALOG = (
    LabScenarioDefinition(
        scenario_id=LabScenarioId.BASELINE,
        title="Baseline / Normal Synthetic Operation",
        description=(
            "Approved normal communication and stable synthetic transfer-process evidence; "
            "no qualifying incident is expected."
        ),
        dataset_case_id="OTSOC-EVAL-V1-BG-001",
    ),
    LabScenarioDefinition(
        scenario_id=LabScenarioId.S1,
        title="Unknown OT Asset / Source Review",
        description=(
            "Review an unknown synthetic source identity without guessing an asset or asserting "
            "compromise."
        ),
        dataset_case_id="OTSOC-EVAL-V1-S1-001",
    ),
    LabScenarioDefinition(
        scenario_id=LabScenarioId.S2,
        title="Unexpected IT-to-PLC Communication",
        description=(
            "Review the frozen IT-WS-01 to PLC-01 communication-policy condition without "
            "inferring malicious intent."
        ),
        dataset_case_id="OTSOC-EVAL-V1-S2-001",
    ),
    LabScenarioDefinition(
        scenario_id=LabScenarioId.S3,
        title="Control Command Investigation",
        description=(
            "Follow the approved raw 250 to CV-101 25.0% command investigation and its "
            "temporally correlated process context."
        ),
        dataset_case_id="OTSOC-EVAL-V1-S3-001",
    ),
    LabScenarioDefinition(
        scenario_id=LabScenarioId.S4,
        title="Pump / Flow Process Inconsistency",
        description=(
            "Review P-101 running with low flow, pressure behavior, and transfer stagnation "
            "without inventing a cyber cause."
        ),
        dataset_case_id="OTSOC-EVAL-V1-S4-001",
    ),
)


def scenario_catalog() -> tuple[LabScenarioDefinition, ...]:
    return _CATALOG


def scenario_definition(scenario_id: LabScenarioId) -> LabScenarioDefinition:
    return next(item for item in _CATALOG if item.scenario_id is scenario_id)


@lru_cache(maxsize=1)
def loaded_lab_dataset() -> LoadedDataset:
    """Load and digest-verify the exact runtime dataset used by the lab."""

    return load_dataset()


def dataset_case(scenario_id: LabScenarioId) -> DatasetCase:
    definition = scenario_definition(scenario_id)
    return loaded_lab_dataset().manifest.case(definition.dataset_case_id)
