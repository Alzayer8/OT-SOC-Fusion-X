from __future__ import annotations

import json
import socket
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.protocols.canonical import (
    canonical_model_bytes,
    deterministic_semantic_source_event_id,
    sha256_hex,
)
from app.protocols.decoder import DECODER_VERSION, decode_event
from app.protocols.fixtures import FIXTURE_ROOT, load_fixture, verify_fixture_set
from app.protocols.models import (
    InterpretationStatus,
    PointAccessClass,
    ReasonCode,
    SyntheticModbusEvent,
)
from app.protocols.profile import (
    EXPECTED_PROFILE_SHA256,
    PROFILE_ROOT,
    ProfileValidationError,
    load_profile,
    parse_profile_bytes,
)

SOURCE_EVIDENCE_ID = uuid.UUID("d18dff22-2936-530b-a72c-4b048cf9d0e2")
SEMANTIC_EVENT_ID = uuid.UUID("d53ebffc-b486-5667-bf56-b35fc5c339b6")
SOURCE_HASH = "1" * 64
CREATED_AT = datetime(2026, 1, 1, 0, 10, 1, tzinfo=UTC)
PROHIBITED_CLAIMS = {
    "attacker",
    "malicious",
    "unauthorized",
    "unsafe",
    "caused",
    "impact",
    "incident",
    "severity",
}


def fixture_event(name: str) -> SyntheticModbusEvent:
    return load_fixture(f"{name}.json")[0]


def decoded(event: SyntheticModbusEvent):  # type: ignore[no-untyped-def]
    return decode_event(
        event,
        load_profile(),
        semantic_event_id=SEMANTIC_EVENT_ID,
        source_evidence_id=SOURCE_EVIDENCE_ID,
        source_evidence_integrity_sha256=SOURCE_HASH,
        created_at=CREATED_AT,
    )


def event_with(event: SyntheticModbusEvent, **updates: object) -> SyntheticModbusEvent:
    return SyntheticModbusEvent.model_validate(
        event.model_copy(update=updates).model_dump(mode="python")
    )


def test_profile_version_loading() -> None:
    loaded = load_profile()
    assert loaded.sha256 == EXPECTED_PROFILE_SHA256
    assert verify_fixture_set().profile_sha256 == EXPECTED_PROFILE_SHA256
    with pytest.raises(ProfileValidationError):
        load_profile(profile_version="9.0.0")
    with pytest.raises(ProfileValidationError):
        load_profile(expected_sha256="0" * 64)

    document = json.loads((PROFILE_ROOT / "oil_gas_modbus_v1.json").read_text("utf-8"))
    document["unknown"] = True
    with pytest.raises(ProfileValidationError):
        parse_profile_bytes(json.dumps(document).encode())
    del document["unknown"]
    document["points"][1]["point_id"] = document["points"][0]["point_id"]
    with pytest.raises(ProfileValidationError):
        parse_profile_bytes(json.dumps(document).encode())
    duplicate_key = b'{"profile_id":"a","profile_id":"b"}'
    with pytest.raises(ProfileValidationError):
        parse_profile_bytes(duplicate_key)


def test_mapping_is_deterministic() -> None:
    event = fixture_event("p4b-normal-read-flow")
    first = decoded(event)
    second = decoded(event)
    assert canonical_model_bytes(first) == canonical_model_bytes(second)


def test_read_only_point_mapping() -> None:
    result = decoded(fixture_event("p4b-normal-read-flow"))
    assert result.interpretation_status is InterpretationStatus.MAPPED
    assert result.point_id == "pipeline_flow_rate_m3h"
    assert result.fictional_target_component == "PL-101"
    assert result.point_access_class is PointAccessClass.READ_ONLY


def test_commandable_point_mapping() -> None:
    result = decoded(fixture_event("p4b-s3-valve-command-25"))
    assert result.point_id == "control_valve_command_percent"
    assert result.fictional_target_component == "CV-101"
    assert result.point_access_class is PointAccessClass.COMMANDABLE_SYNTHETIC


def test_command_state_separation() -> None:
    valve = decoded(fixture_event("p4b-s3-valve-command-25"))
    pump = decoded(fixture_event("p4b-normal-approved-write-pump"))
    assert valve.point_id != "control_valve_position_percent"
    assert "physically" not in valve.semantic_statement.lower()
    assert pump.point_id != "transfer_pump_running"
    assert "running" not in pump.semantic_statement.lower()
    assert "executed" not in pump.semantic_statement.lower()


def test_zero_based_addressing() -> None:
    pump = decoded(fixture_event("p4b-normal-approved-write-pump"))
    valve = decoded(fixture_event("p4b-s3-valve-command-25"))
    assert pump.canonical_address.address_offset == 0
    assert pump.canonical_address.display_reference == 40001
    assert valve.canonical_address.address_offset == 1
    assert valve.canonical_address.display_reference == 40002
    display_as_offset = event_with(valve_event(), address_offset=40002)
    assert decoded(display_as_offset).interpretation_status is InterpretationStatus.UNMAPPED


def valve_event() -> SyntheticModbusEvent:
    return fixture_event("p4b-s3-valve-command-25")


def test_scale_decode() -> None:
    flow = decoded(fixture_event("p4b-normal-read-flow"))
    pressure_event = event_with(
        fixture_event("p4b-normal-read-flow"), address_offset=3, raw_value=1250
    )
    pressure = decoded(pressure_event)
    assert flow.decoded_value == Decimal("5.50")
    assert pressure.decoded_value == Decimal("1.250")


def test_min_max_decode() -> None:
    loaded = load_profile()
    base = fixture_event("p4b-normal-read-flow")
    for point in loaded.profile.points:
        function = point.compatible_functions[0]
        for raw in (point.raw_min, point.raw_max):
            candidate = event_with(
                base,
                function_code=function,
                table_type=point.table_type.value,
                address_offset=point.address_offset,
                raw_value=raw,
            )
            assert decoded(candidate).interpretation_status is InterpretationStatus.MAPPED
        invalid = event_with(
            base,
            function_code=function,
            table_type=point.table_type.value,
            address_offset=point.address_offset,
            raw_value=point.raw_max + 1,
        )
        invalid_result = decoded(invalid)
        assert invalid_result.interpretation_status is InterpretationStatus.MALFORMED
        assert invalid_result.decoded_value is None


def test_unknown_address() -> None:
    result = decoded(fixture_event("p4b-unknown-address"))
    assert result.interpretation_status is InterpretationStatus.UNMAPPED
    assert result.reason_code is ReasonCode.ADDRESS_NOT_IN_PROFILE
    assert result.point_id is None
    assert result.decoded_value is None
    assert result.fictional_target_component is None


def test_unsupported_operation() -> None:
    result = decoded(fixture_event("p4b-unsupported-operation"))
    assert result.interpretation_status is InterpretationStatus.UNSUPPORTED
    assert result.reason_code is ReasonCode.FUNCTION_NOT_SUPPORTED
    assert result.point_id is None
    assert result.decoded_value is None


def test_malformed_raw_value() -> None:
    result = decoded(fixture_event("p4b-malformed-value"))
    assert result.interpretation_status is InterpretationStatus.MALFORMED
    assert result.reason_code is ReasonCode.RAW_VALUE_TYPE_INVALID
    assert result.decoded_value is None
    for invalid in (True, 250.0, [250], {"value": 250}):
        document = valve_event().model_dump(mode="python")
        document["raw_value"] = invalid
        if invalid is True:
            result = decoded(SyntheticModbusEvent.model_validate(document))
            assert result.reason_code is ReasonCode.RAW_VALUE_TYPE_INVALID
        else:
            with pytest.raises(ValidationError):
                SyntheticModbusEvent.model_validate(document)


def test_out_of_range_engineering_value() -> None:
    result = decoded(fixture_event("p4b-out-of-range-value"))
    assert result.interpretation_status is InterpretationStatus.MALFORMED
    assert result.reason_code is ReasonCode.ENGINEERING_VALUE_OUT_OF_RANGE
    assert result.decoded_value is None
    assert "120.0" not in result.semantic_statement


def test_semantic_statement_generation() -> None:
    result = decoded(valve_event())
    assert result.statement_template_id == "COMMAND_CHANGED_TO"
    assert result.semantic_statement == "CV-101 valve-position command changed to 25.0% open."


def test_no_malicious_intent_inference() -> None:
    manifest = verify_fixture_set()
    for item in manifest.fixtures:
        statement = decoded(load_fixture(item.file)[0]).semantic_statement.lower()
        words = {word.strip(".,:;!?()[]") for word in statement.split()}
        assert not words & PROHIBITED_CLAIMS


def test_derived_evidence_identity() -> None:
    loaded = load_profile()
    values = {
        "source_evidence_id": SOURCE_EVIDENCE_ID,
        "profile_id": loaded.profile.profile_id,
        "profile_version": loaded.profile.profile_version,
        "profile_sha256": loaded.sha256,
        "decoder_version": DECODER_VERSION,
        "semantic_schema_version": "1.0.0",
    }
    first = deterministic_semantic_source_event_id(**values)
    assert first == deterministic_semantic_source_event_id(**values)
    changed = dict(values)
    changed["profile_sha256"] = "0" * 64
    assert first != deterministic_semantic_source_event_id(**changed)  # type: ignore[arg-type]


def test_semantic_canonicalization() -> None:
    result = decoded(valve_event())
    canonical = canonical_model_bytes(result)
    independently = json.dumps(
        result.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    assert canonical == independently
    assert sha256_hex(canonical) == sha256_hex(independently)
    assert sha256_hex(canonical) == sha256_hex(canonical)


def test_mapping_version_isolation() -> None:
    original = decoded(valve_event())
    loaded = load_profile()
    other_identity = deterministic_semantic_source_event_id(
        source_evidence_id=SOURCE_EVIDENCE_ID,
        profile_id=loaded.profile.profile_id,
        profile_version=loaded.profile.profile_version,
        profile_sha256="0" * 64,
        decoder_version=DECODER_VERSION,
        semantic_schema_version="1.0.0",
    )
    assert original.profile_sha256 == loaded.sha256
    assert other_identity != deterministic_semantic_source_event_id(
        source_evidence_id=SOURCE_EVIDENCE_ID,
        profile_id=loaded.profile.profile_id,
        profile_version=loaded.profile.profile_version,
        profile_sha256=loaded.sha256,
        decoder_version=DECODER_VERSION,
        semantic_schema_version="1.0.0",
    )
    assert decoded(valve_event()) == original


def test_s3_semantic_fixture() -> None:
    result = decoded(valve_event())
    assert result.function_code == 6
    assert result.canonical_address.table_type == "holding_register"
    assert result.canonical_address.address_offset == 1
    assert result.raw_value == 250
    assert result.point_id == "control_valve_command_percent"
    assert result.decoded_value == Decimal("25.0")
    assert result.semantic_statement == "CV-101 valve-position command changed to 25.0% open."
    assert result.ground_truth_used is False


def test_ground_truth_non_leakage() -> None:
    document = valve_event().model_dump(mode="json")
    for field in ("ground_truth", "scenario_id", "category"):
        candidate = dict(document)
        candidate[field] = "S3"
        with pytest.raises(ValidationError):
            SyntheticModbusEvent.model_validate(candidate)
    result = decoded(valve_event())
    assert result.ground_truth_used is False
    protocol_sources = "\n".join(
        path.read_text("utf-8")
        for path in (Path(__file__).parents[2] / "app" / "protocols").glob("*.py")
    )
    assert "GroundTruthEvent" not in protocol_sources


def test_simulator_protocol_independence() -> None:
    simulation_root = Path(__file__).parents[2] / "app" / "simulation"
    sources = "\n".join(path.read_text("utf-8") for path in simulation_root.glob("*.py"))
    assert "app.protocols" not in sources
    assert "modbus" not in sources.lower()


def test_no_network_socket_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def blocked_socket(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("protocol semantics attempted to create a socket")

    monkeypatch.setattr(socket, "socket", blocked_socket)
    assert load_profile().sha256 == EXPECTED_PROFILE_SHA256
    assert decoded(valve_event()).interpretation_status is InterpretationStatus.MAPPED
    assert verify_fixture_set().fixtures
    assert calls == 0
    protocol_root = Path(__file__).parents[2] / "app" / "protocols"
    imports = "\n".join(path.read_text("utf-8") for path in protocol_root.glob("*.py"))
    prohibited_imports = (
        "import socket",
        "import scapy",
        "import pymodbus",
        "import requests",
        "import subprocess",
    )
    for prohibited in prohibited_imports:
        assert prohibited not in imports
    assert not list(FIXTURE_ROOT.glob("*.pcap"))
