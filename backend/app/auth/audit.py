from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.auth.models import SocAuditAction, SocAuditEvent, SocAuditResult

MAX_AUDIT_DETAILS_BYTES = 4_096
_SENSITIVE_KEY_PARTS = ("password", "token", "cookie", "csrf", "secret", "credential")


class AuditPayloadError(ValueError):
    pass


def append_soc_audit_event(
    session: Session,
    *,
    action: SocAuditAction,
    result: SocAuditResult,
    request_id: str,
    actor_user_id: uuid.UUID | None = None,
    subject_user_id: uuid.UUID | None = None,
    subject_label: str | None = None,
    incident_id: uuid.UUID | None = None,
    scenario_run_id: uuid.UUID | None = None,
    safe_reason: str | None = None,
    details: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> SocAuditEvent:
    safe_details = _validated_details(details or {})
    if not 8 <= len(request_id) <= 64:
        raise AuditPayloadError("Audit request ID is invalid.")
    if subject_label is not None and not 1 <= len(subject_label) <= 80:
        raise AuditPayloadError("Audit subject label is invalid.")
    if safe_reason is not None and not 1 <= len(safe_reason) <= 300:
        raise AuditPayloadError("Audit reason is invalid.")
    event = SocAuditEvent(
        audit_event_id=uuid.uuid4(),
        action=action.value,
        result=result.value,
        occurred_at=occurred_at or datetime.now(UTC),
        actor_user_id=actor_user_id,
        subject_user_id=subject_user_id,
        subject_label=subject_label,
        incident_id=incident_id,
        scenario_run_id=scenario_run_id,
        request_id=request_id,
        safe_reason=safe_reason,
        details=safe_details,
    )
    session.add(event)
    return event


def _validated_details(details: dict[str, Any]) -> dict[str, Any]:
    _reject_sensitive_keys(details)
    try:
        encoded = json.dumps(details, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise AuditPayloadError("Audit details must be JSON serializable.") from exc
    if len(encoded.encode("utf-8")) > MAX_AUDIT_DETAILS_BYTES:
        raise AuditPayloadError("Audit details exceed the size limit.")
    copied = json.loads(encoded)
    if not isinstance(copied, dict):  # pragma: no cover - the input is already a dictionary
        raise AuditPayloadError("Audit details must be a JSON object.")
    return copied


def _reject_sensitive_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).casefold()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                raise AuditPayloadError("Sensitive values are prohibited in audit details.")
            _reject_sensitive_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_sensitive_keys(child)
