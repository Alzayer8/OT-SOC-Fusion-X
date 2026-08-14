from __future__ import annotations

import hashlib
from datetime import UTC, datetime

GROUPING_WINDOW_SECONDS = 300


def grouping_epoch_start(anchor: datetime) -> datetime:
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        raise ValueError("grouping anchor must be timezone-aware")
    unix_seconds = int(anchor.astimezone(UTC).timestamp())
    epoch_seconds = (unix_seconds // GROUPING_WINDOW_SECONDS) * GROUPING_WINDOW_SECONDS
    return datetime.fromtimestamp(epoch_seconds, tz=UTC)


def unresolved_source_scope(source_identity: str) -> str:
    if not 1 <= len(source_identity) <= 80:
        raise ValueError("unresolved source identity is outside the approved bound")
    digest = hashlib.sha256(source_identity.encode("utf-8")).hexdigest()
    return f"UNRESOLVED:{digest}"
