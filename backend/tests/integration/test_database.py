from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from app.core.config import Settings
from app.db.health import database_is_ready
from app.db.session import engine_for


def integration_settings() -> Settings:
    test_database_url = os.environ["TEST_DATABASE_URL"]
    return Settings(
        app_name="OT-SOC Fusion X",
        app_version="1.0.0",
        app_env="development",
        api_version="v1",
        log_level="WARNING",
        cors_origins=["http://localhost:5173"],
        database_url=test_database_url,
        database_connect_timeout_seconds=2,
    )


@pytest.mark.integration
def test_database_connectivity_and_readiness() -> None:
    settings = integration_settings()

    assert database_is_ready(settings) is True
    with engine_for(settings).connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1


@pytest.mark.integration
def test_integration_database_is_not_application_database() -> None:
    assert os.environ["TEST_DATABASE_URL"] != os.environ["DATABASE_URL"]
    assert "otsoc_test" in os.environ["TEST_DATABASE_URL"]
