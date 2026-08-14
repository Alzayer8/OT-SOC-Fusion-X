from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.protocols.canonical import canonical_model_bytes, sha256_hex
from app.protocols.models import (
    FICTIONAL_ENDPOINT_ID,
    PROFILE_ID,
    PROFILE_VERSION,
    FunctionSemantic,
    LogicalType,
    OperationCategory,
    PointAccessClass,
    TableType,
)

MAX_PROFILE_BYTES = 65_536
MAX_PROFILE_POINTS = 64
PROFILE_ROOT = Path(__file__).resolve().parent / "profiles"
PROFILE_FILENAME = "oil_gas_modbus_v1.json"
EXPECTED_PROFILE_SHA256 = "b3ade7b3ae5dd7e5955c54b5a3345dc6f79b5bfa7bf78a2f1a82df3a5f4016ff"


class ProfileValidationError(ValueError):
    pass


class StrictProfileModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
        frozen=True,
    )


class FictionalEndpoint(StrictProfileModel):
    endpoint_id: Literal["OTSOC-MB-UNIT-01"]
    description: Literal["Synthetic Oil & Gas transfer semantic unit"]
    unit_id: Literal[1]
    network_address: None
    tcp_port: None
    real_device_equivalence: None


class CanonicalAddressing(StrictProfileModel):
    identity_fields: tuple[Literal["unit_id", "table_type", "address_offset"], ...]
    address_offset_base: Literal[0]
    discrete_input_display_base: Literal[10001]
    input_register_display_base: Literal[30001]
    holding_register_display_base: Literal[40001]

    @model_validator(mode="after")
    def validate_identity_fields(self) -> CanonicalAddressing:
        if self.identity_fields != ("unit_id", "table_type", "address_offset"):
            raise ValueError("canonical identity fields must use the approved order")
        return self


class SupportedFunction(StrictProfileModel):
    function_code: int = Field(ge=0, le=255)
    semantic: FunctionSemantic
    category: OperationCategory
    allowed_table: TableType


class StatementTemplateCatalog(StrictProfileModel):
    command_changed_to: Literal["COMMAND_CHANGED_TO"]
    command_value_read: Literal["COMMAND_VALUE_READ"]
    process_value_observed: Literal["PROCESS_VALUE_OBSERVED"]
    state_observed: Literal["STATE_OBSERVED"]
    address_unmapped: Literal["ADDRESS_UNMAPPED"]
    function_unsupported: Literal["FUNCTION_UNSUPPORTED"]
    value_malformed: Literal["VALUE_MALFORMED"]
    point_not_commandable: Literal["POINT_NOT_COMMANDABLE"]

    def values(self) -> set[str]:
        return set(self.model_dump().values())


class PointDefinition(StrictProfileModel):
    point_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    component: str = Field(min_length=1, max_length=16, pattern=r"^[A-Z]{1,2}-[0-9]{3}$")
    display_label: str = Field(min_length=1, max_length=80)
    access_class: PointAccessClass
    table_type: TableType
    address_offset: int = Field(ge=0, le=65_535)
    display_reference: int = Field(ge=10_001, le=49_999)
    logical_type: LogicalType
    protocol_representation: Literal["uint16", "single_bit"]
    width: Literal[1]
    signed: Literal[False]
    byte_order: Literal["big_endian", "not_applicable"]
    scale: Decimal | None
    unit: str = Field(min_length=1, max_length=32)
    engineering_min: Decimal
    engineering_max: Decimal
    raw_min: int
    raw_max: int
    compatible_functions: tuple[int, ...] = Field(min_length=1, max_length=4)
    template_id: str = Field(min_length=1, max_length=40)
    decimal_places: int = Field(ge=0, le=3)

    @model_validator(mode="after")
    def validate_representation(self) -> PointDefinition:
        if self.engineering_min > self.engineering_max or self.raw_min > self.raw_max:
            raise ValueError("point limits are reversed")
        if self.raw_min < 0 or self.raw_max > 65_535:
            raise ValueError("raw bounds must fit uint16")
        if self.logical_type is LogicalType.BOOLEAN:
            if (
                self.protocol_representation != "single_bit"
                or self.scale is not None
                or self.byte_order != "not_applicable"
                or (self.raw_min, self.raw_max) != (0, 1)
                or self.decimal_places != 0
            ):
                raise ValueError("Boolean point representation is invalid")
        elif (
            self.protocol_representation != "uint16"
            or self.scale is None
            or self.scale <= 0
            or self.byte_order != "big_endian"
        ):
            raise ValueError("decimal point representation or scale is invalid")
        if self.access_class is PointAccessClass.COMMANDABLE_SYNTHETIC:
            if (
                self.table_type is not TableType.HOLDING_REGISTER
                or 6 not in self.compatible_functions
            ):
                raise ValueError("commandable points must be approved FC06 holding registers")
        elif 6 in self.compatible_functions:
            raise ValueError("read-only points cannot declare a write function")
        return self


class ModbusProfile(StrictProfileModel):
    profile_id: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    profile_version: Literal["1.0.0"]
    protocol: Literal["modbus_tcp"]
    educational_only: Literal[True]
    disclaimer: Literal[
        "Fictional academic synthetic profile; non-plant-derived and not for real equipment."
    ]
    fictional_endpoint: FictionalEndpoint
    canonical_addressing: CanonicalAddressing
    supported_functions: tuple[SupportedFunction, ...]
    statement_templates: StatementTemplateCatalog
    points: tuple[PointDefinition, ...] = Field(min_length=1, max_length=MAX_PROFILE_POINTS)

    @model_validator(mode="after")
    def validate_profile_uniqueness_and_contract(self) -> ModbusProfile:
        if self.profile_id != PROFILE_ID or self.profile_version != PROFILE_VERSION:
            raise ValueError("unsupported profile identity or version")
        if self.fictional_endpoint.endpoint_id != FICTIONAL_ENDPOINT_ID:
            raise ValueError("fictional endpoint identity mismatch")
        function_codes = [item.function_code for item in self.supported_functions]
        if len(function_codes) != len(set(function_codes)):
            raise ValueError("duplicate supported function code")
        if set(function_codes) != {2, 3, 4, 6}:
            raise ValueError("supported function set differs from the approved profile")
        point_ids = [point.point_id for point in self.points]
        addresses = [
            (self.fictional_endpoint.unit_id, point.table_type, point.address_offset)
            for point in self.points
        ]
        if len(point_ids) != len(set(point_ids)):
            raise ValueError("duplicate point ID")
        if len(addresses) != len(set(addresses)):
            raise ValueError("duplicate canonical address")
        if len(self.points) != 9:
            raise ValueError("profile 1.0.0 requires exactly nine points")
        if (
            sum(
                point.access_class is PointAccessClass.COMMANDABLE_SYNTHETIC
                for point in self.points
            )
            != 2
        ):
            raise ValueError("profile must contain exactly two commandable synthetic points")
        if sum(point.access_class is PointAccessClass.READ_ONLY for point in self.points) != 7:
            raise ValueError("profile must contain exactly seven read-only points")
        templates = self.statement_templates.values()
        for point in self.points:
            if point.template_id not in templates:
                raise ValueError("point references an unknown statement template")
            expected_display = self.display_reference(point.table_type, point.address_offset)
            if point.display_reference != expected_display:
                raise ValueError("display reference does not match zero-based address")
        return self

    def display_reference(self, table_type: TableType, address_offset: int) -> int:
        bases = {
            TableType.DISCRETE_INPUT: self.canonical_addressing.discrete_input_display_base,
            TableType.INPUT_REGISTER: self.canonical_addressing.input_register_display_base,
            TableType.HOLDING_REGISTER: self.canonical_addressing.holding_register_display_base,
        }
        return bases[table_type] + address_offset


@dataclass(frozen=True)
class LoadedProfile:
    profile: ModbusProfile
    sha256: str

    @property
    def mapping(self) -> dict[tuple[int, TableType, int], PointDefinition]:
        unit_id = self.profile.fictional_endpoint.unit_id
        return {
            (unit_id, point.table_type, point.address_offset): point
            for point in self.profile.points
        }

    @property
    def functions(self) -> dict[int, SupportedFunction]:
        return {item.function_code: item for item in self.profile.supported_functions}


def load_profile(
    profile_id: str = PROFILE_ID,
    profile_version: str = PROFILE_VERSION,
    *,
    expected_sha256: str | None = None,
) -> LoadedProfile:
    if (profile_id, profile_version) != (PROFILE_ID, PROFILE_VERSION):
        raise ProfileValidationError("The requested profile ID/version is not available.")
    path = PROFILE_ROOT / PROFILE_FILENAME
    if path.is_symlink() or path.resolve().parent != PROFILE_ROOT.resolve():
        raise ProfileValidationError("The approved profile path is unsafe.")
    loaded = parse_profile_bytes(path.read_bytes())
    required_digest = expected_sha256 or EXPECTED_PROFILE_SHA256
    if required_digest == "PENDING" or loaded.sha256 != required_digest:
        raise ProfileValidationError("The profile digest does not match the approved digest.")
    return loaded


def parse_profile_bytes(content: bytes) -> LoadedProfile:
    if not content or len(content) > MAX_PROFILE_BYTES:
        raise ProfileValidationError("The profile file exceeds the approved size bound.")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_object)
        profile = ModbusProfile.model_validate(document)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ProfileValidationError("The profile configuration is invalid.") from exc
    return LoadedProfile(profile=profile, sha256=sha256_hex(canonical_model_bytes(profile)))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProfileValidationError("The profile contains a duplicate JSON key.")
        result[key] = value
    return result
