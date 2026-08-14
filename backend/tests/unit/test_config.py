from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_REQUIRED_ENV_KEYS = (
    "APP_NAME",
    "APP_VERSION",
    "APP_ENV",
    "API_VERSION",
    "CORS_ORIGINS",
    "DATABASE_URL",
    "TEST_DATABASE_URL",
)


def test_configuration_rejects_missing_required_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in _REQUIRED_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_test_configuration_requires_a_separate_database() -> None:
    database_url = "postgresql+psycopg://user:CHANGE_ME_TEST_ONLY@localhost:5432/otsoc"
    with pytest.raises(ValidationError, match="must be different"):
        Settings(
            app_name="OT-SOC Fusion X",
            app_version="1.0.0",
            app_env="test",
            api_version="v1",
            cors_origins=["http://localhost:5173"],
            database_url=database_url,
            test_database_url=database_url,
        )


def test_configuration_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_name="OT-SOC Fusion X",
            app_version="1.0.0",
            app_env="development",
            api_version="v1",
            cors_origins=["*"],
            database_url="postgresql+psycopg://user:CHANGE_ME_TEST_ONLY@localhost:5432/otsoc",
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://otsoc:otsoc_dev_only_change_me@localhost:5432/otsoc",
        "postgresql+psycopg://otsoc:CHANGE_ME_PHASE9B_LOCAL_ONLY@localhost:5432/otsoc",
    ],
)
def test_configuration_rejects_documented_demo_password_placeholders(
    database_url: str,
) -> None:
    with pytest.raises(ValidationError, match="placeholder must be replaced"):
        Settings(
            app_name="OT-SOC Fusion X",
            app_version="1.0.0",
            app_env="development",
            api_version="v1",
            cors_origins=["http://localhost:5173"],
            database_url=database_url,
        )


@pytest.mark.parametrize(
    ("version", "database_url"),
    [
        ("v1", "postgresql+psycopg://user:CHANGE_ME_TEST_ONLY@localhost:5432/otsoc"),
        ("1.0.0", "not-a-postgresql-url"),
    ],
)
def test_configuration_rejects_malformed_version_or_database_url(
    version: str,
    database_url: str,
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_name="OT-SOC Fusion X",
            app_version=version,
            app_env="development",
            api_version="v1",
            cors_origins=["http://localhost:5173"],
            database_url=database_url,
        )
