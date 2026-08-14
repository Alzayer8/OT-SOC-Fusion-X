from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.protocols.decoder import decode_event
from app.protocols.fixtures import FixtureValidationError, load_fixture
from app.protocols.models import (
    InterpretationStatus,
    OperationCompatibility,
    ReasonCode,
    SyntheticModbusEvent,
)
from app.protocols.profile import (
    PROFILE_ROOT,
    ProfileValidationError,
    load_profile,
    parse_profile_bytes,
)

SOURCE_ID = uuid.UUID("d18dff22-2936-530b-a72c-4b048cf9d0e2")
SEMANTIC_ID = uuid.UUID("d53ebffc-b486-5667-bf56-b35fc5c339b6")
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def base_event() -> SyntheticModbusEvent:
    return load_fixture("p4b-s3-valve-command-25.json")[0]


def result_for(**updates: object):  # type: ignore[no-untyped-def]
    event = SyntheticModbusEvent.model_validate(
        base_event().model_copy(update=updates).model_dump(mode="python")
    )
    return decode_event(
        event,
        load_profile(),
        semantic_event_id=SEMANTIC_ID,
        source_evidence_id=SOURCE_ID,
        source_evidence_integrity_sha256="1" * 64,
        created_at=NOW,
    )


@pytest.mark.parametrize(
    ("function_code", "table_type", "address_offset"),
    [(2, "discrete_input", 0), (3, "holding_register", 0), (4, "input_register", 2)],
)
def test_supported_function_table_combinations(
    function_code: int, table_type: str, address_offset: int
) -> None:
    result = result_for(
        function_code=function_code,
        table_type=table_type,
        address_offset=address_offset,
        raw_value=1,
    )
    assert result.interpretation_status is InterpretationStatus.MAPPED


def test_function_table_mismatch_and_invalid_table_fail_neutrally() -> None:
    mismatch = result_for(function_code=4, table_type="holding_register", address_offset=0)
    invalid = result_for(function_code=4, table_type="coil", address_offset=0)
    for result in (mismatch, invalid):
        assert result.interpretation_status is InterpretationStatus.UNSUPPORTED
        assert result.reason_code is ReasonCode.FUNCTION_TABLE_MISMATCH
        assert result.decoded_value is None


@pytest.mark.parametrize(
    ("table_type", "address_offset"),
    [
        ("input_register", 0),
        ("input_register", 1),
        ("input_register", 2),
        ("input_register", 3),
        ("input_register", 4),
        ("input_register", 5),
        ("discrete_input", 0),
    ],
)
def test_write_to_each_read_only_point_is_incompatible(
    table_type: str, address_offset: int
) -> None:
    result = result_for(
        function_code=6,
        table_type=table_type,
        address_offset=address_offset,
        raw_value=1,
    )
    assert result.interpretation_status is InterpretationStatus.MAPPED
    assert result.operation_compatibility is OperationCompatibility.INCOMPATIBLE
    assert result.reason_code is ReasonCode.POINT_NOT_COMMANDABLE
    assert result.decoded_value is None


def test_wrong_unit_protocol_address_and_uint16_bounds_fail_closed() -> None:
    assert result_for(unit_id=2).interpretation_status is InterpretationStatus.UNMAPPED
    assert result_for(protocol_id=1).reason_code is ReasonCode.PROTOCOL_ID_INVALID
    assert result_for(address_offset=-1).reason_code is ReasonCode.ADDRESS_INVALID
    assert result_for(raw_value=-1).reason_code is ReasonCode.RAW_VALUE_OUT_OF_UINT16_RANGE
    assert result_for(raw_value=65_536).reason_code is ReasonCode.RAW_VALUE_OUT_OF_UINT16_RANGE


@pytest.mark.parametrize(("raw", "status"), [(0, "MAPPED"), (1, "MAPPED"), (2, "MALFORMED")])
def test_boolean_discrete_input_bounds(raw: int, status: str) -> None:
    result = result_for(
        function_code=2,
        table_type="discrete_input",
        address_offset=0,
        raw_value=raw,
    )
    assert result.interpretation_status.value == status


def test_profile_scale_address_access_and_digest_tampering_rejected() -> None:
    path = PROFILE_ROOT / "oil_gas_modbus_v1.json"
    original = json.loads(path.read_text("utf-8"))
    mutations = []
    invalid_scale = json.loads(json.dumps(original))
    invalid_scale["points"][0]["scale"] = "0"
    mutations.append(invalid_scale)
    duplicate_address = json.loads(json.dumps(original))
    duplicate_address["points"][1]["address_offset"] = 0
    duplicate_address["points"][1]["display_reference"] = 40001
    mutations.append(duplicate_address)
    invalid_access = json.loads(json.dumps(original))
    invalid_access["points"][2]["access_class"] = "COMMANDABLE_SYNTHETIC"
    mutations.append(invalid_access)
    for document in mutations:
        with pytest.raises(ProfileValidationError):
            parse_profile_bytes(json.dumps(document).encode())
    with pytest.raises(ProfileValidationError):
        load_profile(expected_sha256="f" * 64)


def test_fixture_traversal_oversize_and_executable_shapes_rejected() -> None:
    with pytest.raises(FixtureValidationError):
        load_fixture("../p4b-s3-valve-command-25.json")
    document = base_event().model_dump(mode="json")
    document["raw_value"] = "x" * 65
    with pytest.raises(ValidationError):
        SyntheticModbusEvent.model_validate(document)
    document = base_event().model_dump(mode="json")
    document["raw_value"] = {"__reduce__": "run"}
    with pytest.raises(ValidationError):
        SyntheticModbusEvent.model_validate(document)


def test_semantic_string_and_log_injection_fields_are_rejected() -> None:
    for field in ("source_identity", "fixture_id"):
        document = base_event().model_dump(mode="json")
        document[field] = "safe\r\nforged"
        with pytest.raises(ValidationError):
            SyntheticModbusEvent.model_validate(document)
    result = result_for()
    assert "OTSOC-LAB-SOURCE-03" not in result.semantic_statement
    assert "p4b-s3-valve-command-25" not in result.semantic_statement


def test_no_protocol_endpoint_or_remote_control_route() -> None:
    paths = set(create_app().openapi()["paths"])
    assert "/api/v1/lab/start" in paths
    assert "/api/v1/incidents/{incident_id}/report" in paths
    for prohibited in (
        "/protocol",
        "/modbus",
        "/decode",
        "/packet",
        "/control",
        "/scan",
        "/capture",
        "/execute",
    ):
        assert all(prohibited not in path for path in paths)


def test_protocol_package_has_no_network_or_simulator_control_import() -> None:
    root = Path(__file__).parents[2] / "app" / "protocols"
    source = "\n".join(path.read_text("utf-8") for path in root.glob("*.py"))
    for prohibited in (
        "import socket",
        "import scapy",
        "import pymodbus",
        "import requests",
        "import subprocess",
        "app.simulation",
    ):
        assert prohibited not in source
