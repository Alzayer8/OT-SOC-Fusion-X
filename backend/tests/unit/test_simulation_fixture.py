from __future__ import annotations

import json
import os
from pathlib import Path

from app.tools.simulation_fixture import fixture_document

FIXTURE_PATH = (
    Path(os.environ.get("OTSOC_REPOSITORY_ROOT", Path(__file__).resolve().parents[3]))
    / "scenarios"
    / "fixtures"
    / "phase-3.6-oil-gas-canonical.json"
)


def test_active_fixture_is_generated_from_canonical_simulator() -> None:
    stored = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    generated = fixture_document()
    assert stored == generated
    assert stored["domain"] == "oil_gas_transfer"
    assert stored["simulator_version"] == "3.0.0"
    assert stored["seed"] == 20260809
    assert set(stored["scenario_versions"]) == {"S1", "S2", "S3", "S4"}
