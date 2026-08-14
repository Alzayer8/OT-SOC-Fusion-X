from __future__ import annotations

import os
from collections.abc import Generator

import pytest

os.environ.setdefault("APP_NAME", "OT-SOC Fusion X")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("API_VERSION", "v1")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:5173"]')
os.environ.setdefault(
    "AUTH_SESSION_SECRET",
    "unit-test-session-secret-not-for-runtime-20260811",
)
os.environ.setdefault("SCENARIO_LAB_STARTUP_ENABLED", "false")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://otsoc:CHANGE_ME_TEST_ONLY@127.0.0.1:1/otsoc",
)
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://otsoc:CHANGE_ME_TEST_ONLY@127.0.0.1:5432/otsoc_test",
)

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def unit_settings() -> Settings:
    return Settings(
        app_name="OT-SOC Fusion X",
        app_version="1.0.0",
        app_env="test",
        api_version="v1",
        log_level="WARNING",
        cors_origins=["http://localhost:5173"],
        database_url="postgresql+psycopg://otsoc:redacted@127.0.0.1:1/otsoc",
        test_database_url="postgresql+psycopg://otsoc:redacted@127.0.0.1:5432/otsoc_test",
        database_connect_timeout_seconds=1,
    )


@pytest.fixture
def client(unit_settings: Settings) -> Generator[TestClient, None, None]:
    with TestClient(create_app(unit_settings), raise_server_exceptions=False) as test_client:
        yield test_client
