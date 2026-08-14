from __future__ import annotations

from decimal import Decimal

from app.protocols.models import ReasonCode
from app.protocols.profile import PointDefinition


def mapped_statement(
    point: PointDefinition,
    *,
    function_code: int,
    decoded_value: Decimal | bool,
) -> tuple[str, str]:
    if isinstance(decoded_value, bool):
        state = "running" if decoded_value else "stopped"
        return (
            "STATE_OBSERVED",
            f"{point.component} {point.display_label} was observed as {state}.",
        )
    rendered = _format_decimal(decoded_value, point.decimal_places)
    if function_code == 6:
        return (
            "COMMAND_CHANGED_TO",
            f"{point.component} {point.display_label} changed to {rendered}{point.unit}.",
        )
    if point.access_class.value == "COMMANDABLE_SYNTHETIC":
        return (
            "COMMAND_VALUE_READ",
            f"{point.component} {point.display_label} was read as {rendered}{point.unit}.",
        )
    return (
        "PROCESS_VALUE_OBSERVED",
        f"{point.component} {point.display_label} was observed at {rendered} {point.unit}.",
    )


def unmapped_statement(table_type: str | None, address_offset: int | None) -> tuple[str, str]:
    return (
        "ADDRESS_UNMAPPED",
        f"No mapping exists for synthetic address {table_type}:{address_offset} in profile 1.0.0.",
    )


def unsupported_statement(function_code: int) -> tuple[str, str]:
    return (
        "FUNCTION_UNSUPPORTED",
        f"Function code {function_code} is unsupported by profile 1.0.0.",
    )


def malformed_statement(reason_code: ReasonCode) -> tuple[str, str]:
    return (
        "VALUE_MALFORMED",
        f"The synthetic event value could not be interpreted: {reason_code.value}.",
    )


def not_commandable_statement(point: PointDefinition) -> tuple[str, str]:
    return (
        "POINT_NOT_COMMANDABLE",
        f"{point.component} {point.display_label} is read-only; "
        "the synthetic write was not interpreted as a command.",
    )


def _format_decimal(value: Decimal, decimal_places: int) -> str:
    quantum = Decimal(1).scaleb(-decimal_places)
    return format(value.quantize(quantum), f".{decimal_places}f")
