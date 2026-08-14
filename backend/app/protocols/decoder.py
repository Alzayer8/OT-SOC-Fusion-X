from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from app.protocols.models import (
    CanonicalAddress,
    FunctionSemantic,
    InterpretationStatus,
    LogicalType,
    OperationCategory,
    OperationCompatibility,
    PointAccessClass,
    ProtocolSemanticEvent,
    ReasonCode,
    SyntheticModbusEvent,
    TableType,
)
from app.protocols.profile import LoadedProfile, PointDefinition
from app.protocols.semantics import (
    malformed_statement,
    mapped_statement,
    not_commandable_statement,
    unmapped_statement,
    unsupported_statement,
)

DECODER_NAME = "otsoc_offline_modbus_semantics"
DECODER_VERSION = "1.0.0"


def decode_event(
    event: SyntheticModbusEvent,
    loaded_profile: LoadedProfile,
    *,
    semantic_event_id: uuid.UUID,
    source_evidence_id: uuid.UUID,
    source_evidence_integrity_sha256: str,
    created_at: datetime,
    expected_profile_sha256: str | None = None,
    source_evidence_verified: bool = True,
) -> ProtocolSemanticEvent:
    function = loaded_profile.functions.get(event.function_code)
    operation_category = function.category if function else OperationCategory.UNSUPPORTED
    function_semantic = function.semantic if function else None

    if not source_evidence_verified:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.MALFORMED,
            reason=ReasonCode.SOURCE_EVIDENCE_NOT_VERIFIED,
            operation_category=operation_category,
            function_semantic=function_semantic,
        )
    if expected_profile_sha256 is not None and expected_profile_sha256 != loaded_profile.sha256:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.MALFORMED,
            reason=ReasonCode.PROFILE_DIGEST_MISMATCH,
            operation_category=operation_category,
            function_semantic=function_semantic,
        )
    if event.protocol_id != 0:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.MALFORMED,
            reason=ReasonCode.PROTOCOL_ID_INVALID,
            operation_category=operation_category,
            function_semantic=function_semantic,
        )
    if function is None:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.UNSUPPORTED,
            reason=ReasonCode.FUNCTION_NOT_SUPPORTED,
            operation_category=OperationCategory.UNSUPPORTED,
            function_semantic=None,
        )
    try:
        table_type = TableType(event.table_type) if event.table_type is not None else None
    except ValueError:
        table_type = None
    if table_type is None:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.UNSUPPORTED,
            reason=ReasonCode.FUNCTION_TABLE_MISMATCH,
            operation_category=operation_category,
            function_semantic=function.semantic,
        )
    if event.address_offset is None or event.address_offset < 0 or event.address_offset > 65_535:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.MALFORMED,
            reason=ReasonCode.ADDRESS_INVALID,
            operation_category=operation_category,
            function_semantic=function.semantic,
        )

    point = loaded_profile.mapping.get((event.unit_id, table_type, event.address_offset))
    if (
        point is not None
        and function.category is OperationCategory.WRITE
        and point.access_class is PointAccessClass.READ_ONLY
    ):
        template_id, statement = not_commandable_statement(point)
        return _build_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            operation_category=function.category,
            function_semantic=function.semantic,
            compatibility=OperationCompatibility.INCOMPATIBLE,
            status=InterpretationStatus.MAPPED,
            reason=ReasonCode.POINT_NOT_COMMANDABLE,
            point=point,
            decoded_value=None,
            template_id=template_id,
            statement=statement,
        )
    if function.allowed_table is not table_type:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.UNSUPPORTED,
            reason=ReasonCode.FUNCTION_TABLE_MISMATCH,
            operation_category=operation_category,
            function_semantic=function.semantic,
        )
    if point is None:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.UNMAPPED,
            reason=ReasonCode.ADDRESS_NOT_IN_PROFILE,
            operation_category=operation_category,
            function_semantic=function.semantic,
        )
    if event.function_code not in point.compatible_functions:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.UNSUPPORTED,
            reason=ReasonCode.FUNCTION_TABLE_MISMATCH,
            operation_category=operation_category,
            function_semantic=function.semantic,
        )
    decoded_value, value_reason = _decode_value(event.raw_value, point)
    if value_reason is not ReasonCode.NONE or decoded_value is None:
        return _neutral_result(
            event,
            loaded_profile,
            semantic_event_id=semantic_event_id,
            source_evidence_id=source_evidence_id,
            source_evidence_integrity_sha256=source_evidence_integrity_sha256,
            created_at=created_at,
            status=InterpretationStatus.MALFORMED,
            reason=value_reason,
            operation_category=operation_category,
            function_semantic=function.semantic,
        )
    template_id, statement = mapped_statement(
        point, function_code=event.function_code, decoded_value=decoded_value
    )
    return _build_result(
        event,
        loaded_profile,
        semantic_event_id=semantic_event_id,
        source_evidence_id=source_evidence_id,
        source_evidence_integrity_sha256=source_evidence_integrity_sha256,
        created_at=created_at,
        operation_category=operation_category,
        function_semantic=function.semantic,
        compatibility=OperationCompatibility.COMPATIBLE,
        status=InterpretationStatus.MAPPED,
        reason=ReasonCode.NONE,
        point=point,
        decoded_value=decoded_value,
        template_id=template_id,
        statement=statement,
    )


def _decode_value(
    raw_value: int | str | bool | None, point: PointDefinition
) -> tuple[Decimal | bool | None, ReasonCode]:
    if raw_value is None:
        return None, ReasonCode.RAW_VALUE_REQUIRED
    if not isinstance(raw_value, int) or isinstance(raw_value, bool):
        return None, ReasonCode.RAW_VALUE_TYPE_INVALID
    if raw_value < 0 or raw_value > 65_535:
        return None, ReasonCode.RAW_VALUE_OUT_OF_UINT16_RANGE
    if point.logical_type is LogicalType.BOOLEAN:
        if raw_value not in (0, 1):
            return None, ReasonCode.ENGINEERING_VALUE_OUT_OF_RANGE
        return bool(raw_value), ReasonCode.NONE
    if point.scale is None:
        return None, ReasonCode.RAW_VALUE_TYPE_INVALID
    decoded = Decimal(raw_value) * point.scale
    if decoded < point.engineering_min or decoded > point.engineering_max:
        return None, ReasonCode.ENGINEERING_VALUE_OUT_OF_RANGE
    return decoded, ReasonCode.NONE


def _neutral_result(
    event: SyntheticModbusEvent,
    loaded_profile: LoadedProfile,
    *,
    semantic_event_id: uuid.UUID,
    source_evidence_id: uuid.UUID,
    source_evidence_integrity_sha256: str,
    created_at: datetime,
    status: InterpretationStatus,
    reason: ReasonCode,
    operation_category: OperationCategory,
    function_semantic: FunctionSemantic | None,
) -> ProtocolSemanticEvent:
    if status is InterpretationStatus.UNMAPPED:
        template_id, statement = unmapped_statement(event.table_type, event.address_offset)
    elif status is InterpretationStatus.UNSUPPORTED:
        template_id, statement = unsupported_statement(event.function_code)
    else:
        template_id, statement = malformed_statement(reason)
    return _build_result(
        event,
        loaded_profile,
        semantic_event_id=semantic_event_id,
        source_evidence_id=source_evidence_id,
        source_evidence_integrity_sha256=source_evidence_integrity_sha256,
        created_at=created_at,
        operation_category=operation_category,
        function_semantic=function_semantic,
        compatibility=OperationCompatibility.NOT_APPLICABLE,
        status=status,
        reason=reason,
        point=None,
        decoded_value=None,
        template_id=template_id,
        statement=statement,
    )


def _build_result(
    event: SyntheticModbusEvent,
    loaded_profile: LoadedProfile,
    *,
    semantic_event_id: uuid.UUID,
    source_evidence_id: uuid.UUID,
    source_evidence_integrity_sha256: str,
    created_at: datetime,
    operation_category: OperationCategory,
    function_semantic: FunctionSemantic | None,
    compatibility: OperationCompatibility,
    status: InterpretationStatus,
    reason: ReasonCode,
    point: PointDefinition | None,
    decoded_value: Decimal | bool | None,
    template_id: str,
    statement: str,
) -> ProtocolSemanticEvent:
    display_reference = point.display_reference if point is not None else None
    return ProtocolSemanticEvent(
        semantic_event_id=semantic_event_id,
        semantic_schema="otsoc.protocol.semantic_event",
        semantic_schema_version="1.0.0",
        protocol="modbus_tcp",
        profile_id=loaded_profile.profile.profile_id,
        profile_version=loaded_profile.profile.profile_version,
        profile_sha256=loaded_profile.sha256,
        decoder_name=DECODER_NAME,
        decoder_version=DECODER_VERSION,
        observed_at=event.observed_at,
        source_evidence_id=source_evidence_id,
        source_evidence_integrity_sha256=source_evidence_integrity_sha256,
        source_identity=event.source_identity,
        destination_identity=event.destination_identity,
        transaction_id=event.transaction_id,
        unit_id=event.unit_id,
        operation_category=operation_category,
        function_code=event.function_code,
        function_semantic=function_semantic,
        message_role=event.message_role,
        canonical_address=CanonicalAddress(
            unit_id=event.unit_id,
            table_type=event.table_type,
            address_offset=event.address_offset,
            display_reference=display_reference,
        ),
        operation_compatibility=compatibility,
        point_id=point.point_id if point is not None else None,
        point_access_class=point.access_class if point is not None else None,
        logical_type=point.logical_type if point is not None else None,
        raw_value=event.raw_value,
        decoded_value=decoded_value,
        unit=point.unit if point is not None and decoded_value is not None else None,
        fictional_target_component=point.component if point is not None else None,
        statement_template_id=template_id,
        semantic_statement=statement,
        interpretation_status=status,
        reason_code=reason,
        derivation_kind="SEMANTIC_INTERPRETATION",
        derived_from=source_evidence_id,
        created_at=created_at,
        canonicalization_version="otsoc-canonical-json-1",
        ground_truth_used=False,
    )
