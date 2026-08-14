from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.evidence.service import decode_evidence_cursor, encode_evidence_cursor
from app.product.schemas import ReplayEvent, ReplayWindowRequest
from app.product.service import asset_catalog, asset_detail


def test_phase8b_asset_catalog_is_exact_and_static() -> None:
    catalog = asset_catalog()

    assert [item.definition.asset_key for item in catalog.assets] == [
        "PLC-01",
        "HMI-01",
        "ENG-WS-01",
        "IT-WS-01",
        "MON-01",
        "SOC-01",
        "TK-101",
        "P-101",
        "PL-101",
        "CV-101",
        "TK-102",
    ]
    assert len(catalog.zones) == 5
    assert len(catalog.relationships) == 9
    assert sum(item.definition.asset_kind == "CYBER" for item in catalog.assets) == 6
    assert sum(item.definition.asset_kind == "PROCESS" for item in catalog.assets) == 5
    assert all(item.definition.enabled for item in catalog.assets)


def test_phase8b_asset_detail_uses_catalog_identity_and_relationships() -> None:
    catalog = asset_catalog()
    detail = asset_detail("CV-101")
    expected = next(item for item in catalog.assets if item.definition.asset_key == "CV-101")

    assert detail.asset == expected
    assert detail.zone.zone_id == expected.definition.zone_id
    assert detail.asset.process_point_ids
    assert detail.inbound_relationships or detail.outbound_relationships


def test_phase8b_evidence_cursor_is_opaque_and_round_trips() -> None:
    observed_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    evidence_id = uuid.UUID("00000000-0000-4000-8000-000000000123")

    cursor = encode_evidence_cursor(
        SimpleNamespace(observed_at=observed_at, evidence_id=evidence_id)  # type: ignore[arg-type]
    )

    assert ":" not in cursor
    assert decode_evidence_cursor(cursor) == (observed_at, evidence_id)
    with pytest.raises(ValueError):
        decode_evidence_cursor("not-a-valid-cursor")


def test_phase8b_replay_window_is_bounded_and_requires_unique_types() -> None:
    start = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    valid = {
        "simulation_id": "sim-phase8b",
        "configuration_hash": "a" * 64,
        "observed_from": start,
        "observed_to": start + timedelta(minutes=15),
        "evidence_types": ["simulator_telemetry", "correlation_finding"],
    }

    assert ReplayWindowRequest.model_validate(valid).observed_to == start + timedelta(minutes=15)
    with pytest.raises(ValidationError):
        ReplayWindowRequest.model_validate({**valid, "observed_to": start + timedelta(minutes=16)})
    with pytest.raises(ValidationError):
        ReplayWindowRequest.model_validate(
            {**valid, "evidence_types": ["simulator_telemetry", "simulator_telemetry"]}
        )


def test_phase8b_replay_event_requires_exactly_one_payload() -> None:
    base = {
        "event_id": "00000000-0000-4000-8000-000000000124",
        "event_class": "TELEMETRY",
        "sort_rank": 50,
        "observed_at": "2026-08-11T12:00:00Z",
        "summary": "Stored telemetry",
        "integrity_verified": True,
    }

    with pytest.raises(ValidationError):
        ReplayEvent.model_validate(base)
