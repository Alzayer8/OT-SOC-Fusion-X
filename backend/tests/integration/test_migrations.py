from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from app.core.config import Settings
from app.db.session import session_scope
from app.db.test_cleanup import TEST_DATA_TRUNCATE
from app.evidence.models import EvidenceRecord
from app.evidence.service import ingest_evidence
from tests.evidence_helpers import sample_evidence_request

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(BACKEND_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", os.environ["TEST_DATABASE_URL"])
    return config


@pytest.mark.integration
def test_alembic_upgrade_downgrade_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])

    config = alembic_config()
    command.upgrade(config, "head")
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.current(config, check_heads=True)
    engine.dispose()


@pytest.mark.integration
def test_phase4b_migration_upgrade_downgrade_reupgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = alembic_config()
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
        source_types = (
            connection.execute(
                text("SELECT source_type FROM evidence_sources ORDER BY source_type")
            )
            .scalars()
            .all()
        )
        assert source_types == [
            "asset_context_event",
            "communication_policy_finding",
            "correlation_finding",
            "protocol_semantic_event",
            "simulator_telemetry",
            "synthetic_protocol_event",
        ]
    command.downgrade(config, "0003_phase_3_6_oil_gas")
    with engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM evidence_sources")).scalar_one() == 1
        source_type = connection.execute(
            text("SELECT source_type FROM evidence_sources")
        ).scalar_one()
        assert source_type == "simulator_telemetry"
    command.upgrade(config, "head")
    command.current(config, check_heads=True)
    with engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM evidence_sources")).scalar_one() == 6
    engine.dispose()


@pytest.mark.integration
def test_phase5b_migration_upgrade_downgrade_reupgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = alembic_config()
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
        assert connection.execute(text("SELECT count(*) FROM evidence_sources")).scalar_one() == 6
    command.downgrade(config, "0004_phase_4b_protocol_semantics")
    with engine.begin() as connection:
        source_types = (
            connection.execute(
                text("SELECT source_type FROM evidence_sources ORDER BY source_type")
            )
            .scalars()
            .all()
        )
        assert source_types == [
            "protocol_semantic_event",
            "simulator_telemetry",
            "synthetic_protocol_event",
        ]
    command.upgrade(config, "head")
    command.current(config, check_heads=True)
    with engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM evidence_sources")).scalar_one() == 6
    engine.dispose()


@pytest.mark.integration
def test_phase6b_migration_upgrade_downgrade_reupgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = alembic_config()
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
        assert connection.execute(text("SELECT count(*) FROM evidence_sources")).scalar_one() == 6
    command.downgrade(config, "0005_phase_5b_asset_policy")
    with engine.begin() as connection:
        source_types = (
            connection.execute(
                text("SELECT source_type FROM evidence_sources ORDER BY source_type")
            )
            .scalars()
            .all()
        )
        assert source_types == [
            "asset_context_event",
            "communication_policy_finding",
            "protocol_semantic_event",
            "simulator_telemetry",
            "synthetic_protocol_event",
        ]
    command.upgrade(config, "head")
    command.current(config, check_heads=True)
    with engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM evidence_sources")).scalar_one() == 6
    engine.dispose()


@pytest.mark.integration
def test_phase7b_migration_upgrade_downgrade_reupgrade_preserves_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    database_url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = alembic_config()
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(TEST_DATA_TRUNCATE)
    settings = Settings(
        app_name="OT-SOC Fusion X",
        app_version="1.0.0",
        app_env="development",
        api_version="v1",
        log_level="WARNING",
        cors_origins=["http://localhost:5173"],
        database_url=database_url,
        database_connect_timeout_seconds=2,
    )
    with session_scope(settings) as session:
        receipt = ingest_evidence(
            session,
            sample_evidence_request(source_event_id="phase7b-migration-evidence"),
        )
        stored = session.get(EvidenceRecord, receipt.evidence_id)
        assert stored is not None
        before = (stored.evidence_id, stored.integrity_sha256, dict(stored.payload))
    command.downgrade(config, "0006_phase_6b_correlation")
    with engine.begin() as connection:
        assert connection.execute(text("SELECT to_regclass('incidents')")).scalar_one() is None
        row = connection.execute(
            text(
                "SELECT evidence_id, integrity_sha256, payload "
                "FROM evidence_records WHERE evidence_id=:evidence_id"
            ),
            {"evidence_id": str(before[0])},
        ).one()
        assert (uuid.UUID(str(row[0])), row[1], row[2]) == before
    command.upgrade(config, "head")
    command.current(config, check_heads=True)
    with engine.begin() as connection:
        tables = (
            connection.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename LIKE 'incident%' ORDER BY tablename"
                )
            )
            .scalars()
            .all()
        )
        assert tables == [
            "incident_audit_events",
            "incident_evidence_memberships",
            "incident_notes",
            "incident_report_revisions",
            "incident_reports",
            "incident_severity_history",
            "incident_status_history",
            "incident_timeline_entries",
            "incidents",
        ]
        row = connection.execute(
            text(
                "SELECT evidence_id, integrity_sha256, payload "
                "FROM evidence_records WHERE evidence_id=:evidence_id"
            ),
            {"evidence_id": str(before[0])},
        ).one()
        assert (uuid.UUID(str(row[0])), row[1], row[2]) == before
    engine.dispose()
