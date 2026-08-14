from __future__ import annotations

import json
import os

from alembic.config import Config

from alembic import command
from app.core.config import Settings
from app.db.session import engine_for, session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.incidents.service import qualify_stored_evidence
from app.tools.incident_support import persist_correlation_chain


def _settings() -> Settings:
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url is None or "otsoc_test" not in test_url:
        raise SystemExit("TEST_DATABASE_URL must target the isolated otsoc_test database")
    return Settings(
        app_name="OT-SOC Fusion X",
        app_version="1.0.0",
        app_env="development",
        api_version="v1",
        log_level="WARNING",
        cors_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        database_url=test_url,
        database_connect_timeout_seconds=2,
    )


def _migrate() -> None:
    config = Config("alembic.ini")
    command.upgrade(config, "head")


def main() -> int:
    settings = _settings()
    _migrate()
    with engine_for(settings).begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)

    s3_request = persist_correlation_chain(
        settings,
        "p6b-f005.json",
        context_fixture="s3_engineering_denied_valve_command.json",
    )
    with session_scope(settings) as session:
        s3 = qualify_stored_evidence(session, s3_request)
    s4_request = persist_correlation_chain(settings, "p6b-f008.json")
    with session_scope(settings) as session:
        s4 = qualify_stored_evidence(session, s4_request)

    if s3.incident is None or s4.incident is None:
        raise RuntimeError("Phase 8B S3/S4 demo incidents were not created")
    if s3.incident.severity != "HIGH" or s4.incident.severity != "HIGH":
        raise RuntimeError("Phase 8B S3/S4 incident severity drifted")
    if s4.incident.category != "PROCESS_INCONSISTENCY":
        raise RuntimeError("Phase 8B S4 category drifted")

    print(
        json.dumps(
            {
                "s3_incident_id": str(s3.incident.incident_id),
                "s4_incident_id": str(s4.incident.incident_id),
                "s3_category": str(s3.incident.category),
                "s4_category": str(s4.incident.category),
                "seeded": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
