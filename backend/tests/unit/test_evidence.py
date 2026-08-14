from __future__ import annotations

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.evidence.adapter import telemetry_to_evidence_request
from app.evidence.canonical import (
    canonical_evidence_bytes,
    deterministic_evidence_id,
    integrity_sha256,
)
from app.evidence.schemas import EvidenceIngestRequest, HistoricalEvidenceEnvelopeV1
from app.simulation import OilGasTransferSimulator, SimulationConfig
from tests.evidence_helpers import sample_evidence_request

SOURCE_ID = "143c438b-ca4d-5094-ae31-7794ca91d8f9"


def test_canonical_serialization_digest_and_identity_are_stable() -> None:
    import uuid

    source_id = uuid.UUID(SOURCE_ID)
    request = sample_evidence_request()
    first = canonical_evidence_bytes(source_id, request)
    second = canonical_evidence_bytes(source_id, request)

    assert first == second
    assert integrity_sha256(first) == integrity_sha256(second)
    assert deterministic_evidence_id(source_id, request) == deterministic_evidence_id(
        source_id, request
    )
    assert json.loads(first)["payload_schema_version"] == "2.0.0"


def test_simulator_adapter_contains_public_telemetry_but_no_ground_truth() -> None:
    config = SimulationConfig(duration_seconds=2)
    step = OilGasTransferSimulator(config).step()
    request = telemetry_to_evidence_request(step.telemetry, seed=config.seed)
    serialized = request.model_dump_json().lower()

    assert request.payload.simulation_id == step.telemetry.simulation_id
    assert request.payload.domain == "oil_gas_transfer"
    assert request.payload_schema_version == "2.0.0"
    assert "ground_truth" not in serialized
    assert "scenario_id" not in serialized
    assert "category" not in serialized


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_type", "modbus_packet"),
        ("payload_schema_version", "1.0.0"),
        ("source_key", "../unsafe"),
        ("observed_at", datetime(2026, 1, 1)),
    ],
)
def test_unsupported_or_unsafe_envelope_values_are_rejected(field: str, value: object) -> None:
    document = sample_evidence_request().model_dump(mode="json")
    document[field] = value
    with pytest.raises(ValidationError):
        EvidenceIngestRequest.model_validate(document)


def test_envelope_payload_mismatch_is_rejected() -> None:
    document = sample_evidence_request().model_dump(mode="json")
    document["sequence_number"] = 999
    with pytest.raises(ValidationError, match="payload sequence"):
        EvidenceIngestRequest.model_validate(document)


def test_invalid_numeric_payload_is_rejected() -> None:
    document = sample_evidence_request().model_dump(mode="json")
    document["payload"]["pipeline_pressure_bar"] = -1
    with pytest.raises(ValidationError):
        EvidenceIngestRequest.model_validate(document)


def test_historical_v1_is_explicitly_read_only_not_silently_reinterpreted() -> None:
    document = sample_evidence_request().model_dump(mode="json")
    document["payload_schema_version"] = "1.0.0"
    with pytest.raises(ValidationError):
        EvidenceIngestRequest.model_validate(document)

    historical = {
        "source_key": "simulator-primary",
        "source_event_id": "historical-v1-1",
        "evidence_type": "simulator_telemetry",
        "observed_at": "2026-01-01T00:00:01Z",
        "sequence_number": 1,
        "payload_schema": "otsoc.simulator.telemetry",
        "payload_schema_version": "1.0.0",
        "payload": {
            "simulation_id": "sim-historical-v1",
            "sequence_number": 1,
            "timestamp": "2026-01-01T00:00:01Z",
            "simulator_version": "2.0.0",
            "configuration_hash": "1" * 64,
            "simulation_time_seconds": 1,
            "tank_level_percent": 50.0,
            "pump_command_percent": 55.0,
            "pump_running": True,
            "flow_rate_m3h": 1.0,
            "inlet_temperature_c": 28.0,
            "outlet_temperature_c": 25.0,
            "pressure_bar": 0.5,
        },
        "provenance": {
            "producer": "otsoc_simulator",
            "producer_version": "2.0.0",
            "simulation_id": "sim-historical-v1",
            "configuration_hash": "1" * 64,
        },
    }
    assert HistoricalEvidenceEnvelopeV1.model_validate(historical).payload_schema_version == "1.0.0"
