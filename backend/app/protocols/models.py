from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
)

RAW_EVENT_SCHEMA = "otsoc.synthetic_modbus.event"
RAW_EVENT_SCHEMA_VERSION = "1.0.0"
SEMANTIC_SCHEMA = "otsoc.protocol.semantic_event"
SEMANTIC_SCHEMA_VERSION = "1.0.0"
PROFILE_ID = "otsoc.synthetic_modbus.oil_gas_transfer"
PROFILE_VERSION = "1.0.0"
FICTIONAL_ENDPOINT_ID = "OTSOC-MB-UNIT-01"


class StrictProtocolModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
        frozen=True,
    )


class CaptureMode(StrEnum):
    OFFLINE_FIXTURE = "OFFLINE_FIXTURE"
    IN_MEMORY_TEST = "IN_MEMORY_TEST"


class MessageRole(StrEnum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    OPERATION = "OPERATION"


class TableType(StrEnum):
    DISCRETE_INPUT = "discrete_input"
    INPUT_REGISTER = "input_register"
    HOLDING_REGISTER = "holding_register"


class OperationCategory(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    UNSUPPORTED = "UNSUPPORTED"


class FunctionSemantic(StrEnum):
    READ_DISCRETE_INPUTS = "READ_DISCRETE_INPUTS"
    READ_HOLDING_REGISTERS = "READ_HOLDING_REGISTERS"
    READ_INPUT_REGISTERS = "READ_INPUT_REGISTERS"
    WRITE_SINGLE_REGISTER = "WRITE_SINGLE_REGISTER"


class PointAccessClass(StrEnum):
    READ_ONLY = "READ_ONLY"
    COMMANDABLE_SYNTHETIC = "COMMANDABLE_SYNTHETIC"


class LogicalType(StrEnum):
    DECIMAL = "decimal"
    BOOLEAN = "boolean"


class OperationCompatibility(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class InterpretationStatus(StrEnum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"
    UNSUPPORTED = "UNSUPPORTED"
    MALFORMED = "MALFORMED"


class ReasonCode(StrEnum):
    NONE = "NONE"
    ADDRESS_NOT_IN_PROFILE = "ADDRESS_NOT_IN_PROFILE"
    ADDRESS_INVALID = "ADDRESS_INVALID"
    FUNCTION_NOT_SUPPORTED = "FUNCTION_NOT_SUPPORTED"
    FUNCTION_TABLE_MISMATCH = "FUNCTION_TABLE_MISMATCH"
    POINT_NOT_COMMANDABLE = "POINT_NOT_COMMANDABLE"
    RAW_VALUE_REQUIRED = "RAW_VALUE_REQUIRED"
    RAW_VALUE_TYPE_INVALID = "RAW_VALUE_TYPE_INVALID"
    RAW_VALUE_OUT_OF_UINT16_RANGE = "RAW_VALUE_OUT_OF_UINT16_RANGE"
    ENGINEERING_VALUE_OUT_OF_RANGE = "ENGINEERING_VALUE_OUT_OF_RANGE"
    PROTOCOL_ID_INVALID = "PROTOCOL_ID_INVALID"
    SOURCE_EVIDENCE_NOT_VERIFIED = "SOURCE_EVIDENCE_NOT_VERIFIED"
    PROFILE_DIGEST_MISMATCH = "PROFILE_DIGEST_MISMATCH"


RawScalar = StrictInt | StrictStr | StrictBool | None
BoundedIdentity = Annotated[
    str,
    Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:-]*$"),
]


class SyntheticModbusEvent(StrictProtocolModel):
    event_version: Literal["1.0.0"]
    capture_mode: CaptureMode
    observed_at: AwareDatetime
    source_identity: BoundedIdentity
    destination_identity: BoundedIdentity
    transaction_id: Annotated[StrictInt, Field(ge=0, le=65_535)]
    protocol_id: Annotated[StrictInt, Field(ge=0, le=65_535)]
    unit_id: Annotated[StrictInt, Field(ge=0, le=255)]
    message_role: MessageRole
    function_code: Annotated[StrictInt, Field(ge=0, le=255)]
    table_type: Annotated[
        StrictStr | None,
        Field(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_]*$"),
    ]
    address_offset: StrictInt | None
    raw_value: RawScalar
    fixture_id: BoundedIdentity

    @field_validator("address_offset")
    @classmethod
    def validate_address_integer_bound(cls, value: int | None) -> int | None:
        if value is not None and not -(2**63) <= value <= 2**63 - 1:
            raise ValueError("address_offset is outside the signed 64-bit bound")
        return value

    @field_validator("raw_value")
    @classmethod
    def validate_raw_scalar_bound(cls, value: RawScalar) -> RawScalar:
        if isinstance(value, str) and len(value) > 64:
            raise ValueError("raw_value string exceeds 64 characters")
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and not -(2**63) <= value <= 2**63 - 1
        ):
            raise ValueError("raw_value integer is outside the signed 64-bit bound")
        return value


class CanonicalAddress(StrictProtocolModel):
    unit_id: int
    table_type: str | None
    address_offset: int | None
    display_reference: int | None


class ProtocolSemanticEvent(StrictProtocolModel):
    semantic_event_id: uuid.UUID
    semantic_schema: Literal["otsoc.protocol.semantic_event"]
    semantic_schema_version: Literal["1.0.0"]
    protocol: Literal["modbus_tcp"]
    profile_id: Literal["otsoc.synthetic_modbus.oil_gas_transfer"]
    profile_version: Literal["1.0.0"]
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decoder_name: Literal["otsoc_offline_modbus_semantics"]
    decoder_version: str = Field(min_length=1, max_length=24)
    observed_at: AwareDatetime
    source_evidence_id: uuid.UUID
    source_evidence_integrity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_identity: BoundedIdentity
    destination_identity: BoundedIdentity
    transaction_id: int
    unit_id: int
    operation_category: OperationCategory
    function_code: int
    function_semantic: FunctionSemantic | None
    message_role: MessageRole
    canonical_address: CanonicalAddress
    operation_compatibility: OperationCompatibility
    point_id: str | None
    point_access_class: PointAccessClass | None
    logical_type: LogicalType | None
    raw_value: RawScalar
    decoded_value: Decimal | bool | None
    unit: str | None
    fictional_target_component: str | None
    statement_template_id: str
    semantic_statement: str
    interpretation_status: InterpretationStatus
    reason_code: ReasonCode
    derivation_kind: Literal["SEMANTIC_INTERPRETATION"]
    derived_from: uuid.UUID
    created_at: AwareDatetime
    canonicalization_version: Literal["otsoc-canonical-json-1"]
    ground_truth_used: Literal[False]

    @field_validator("semantic_statement")
    @classmethod
    def forbid_policy_or_intent_claims(cls, value: str) -> str:
        prohibited = {
            "attacker",
            "malicious",
            "unauthorized",
            "unsafe",
            "caused",
            "impact",
            "incident",
            "severity",
        }
        words = {word.strip(".,:;!?()[]").lower() for word in value.split()}
        if words & prohibited:
            raise ValueError("semantic statement contains a prohibited policy or intent term")
        return value


def aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value
