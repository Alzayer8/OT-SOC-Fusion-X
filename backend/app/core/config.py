from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_UNSAFE_DEMO_PASSWORDS = frozenset({"otsoc_dev_only_change_me", "CHANGE_ME_PHASE9B_LOCAL_ONLY"})
_UNSAFE_SESSION_SECRETS = frozenset(
    {
        "CHANGE_ME",
        "CHANGE_ME_V1_1_LOCAL_ONLY",
        "otsoc_dev_only_change_me",
    }
)


class Settings(BaseSettings):
    """Validated settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=_REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(min_length=1, max_length=80)
    app_version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
    app_env: Literal["development", "test", "contract"]
    api_version: Literal["v1"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: list[AnyHttpUrl] = Field(min_length=1, max_length=10)
    database_url: PostgresDsn
    test_database_url: PostgresDsn | None = None
    database_connect_timeout_seconds: int = Field(default=2, ge=1, le=10)
    auth_session_secret: SecretStr = Field(min_length=32, max_length=512)
    auth_session_ttl_minutes: int = Field(default=480, ge=5, le=1_440)
    auth_cookie_secure: bool = False
    auth_session_cookie_name: str = Field(
        default="otsoc_session", pattern=r"^[a-z][a-z0-9_]{2,31}$"
    )
    auth_csrf_cookie_name: str = Field(default="otsoc_csrf", pattern=r"^[a-z][a-z0-9_]{2,31}$")
    scenario_lab_startup_enabled: bool = True

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_origins(cls, origins: list[AnyHttpUrl]) -> list[AnyHttpUrl]:
        if any(str(origin).rstrip("/") == "*" for origin in origins):
            raise ValueError("CORS wildcard origins are prohibited")
        return origins

    @model_validator(mode="after")
    def validate_test_database_separation(self) -> Settings:
        database_passwords = [urlsplit(str(self.database_url)).password]
        if self.test_database_url is not None:
            database_passwords.append(urlsplit(str(self.test_database_url)).password)
        if any(password in _UNSAFE_DEMO_PASSWORDS for password in database_passwords):
            raise ValueError("The documented demo database password placeholder must be replaced")
        if self.auth_session_secret.get_secret_value() in _UNSAFE_SESSION_SECRETS:
            raise ValueError("The documented session-secret placeholder must be replaced")
        if self.auth_session_cookie_name == self.auth_csrf_cookie_name:
            raise ValueError("Session and CSRF cookie names must be distinct")
        if self.app_env == "test":
            if self.test_database_url is None:
                raise ValueError("TEST_DATABASE_URL is required when APP_ENV=test")
            if str(self.database_url) == str(self.test_database_url):
                raise ValueError("Test and application database URLs must be different")
        return self

    @property
    def database_url_string(self) -> str:
        return str(self.database_url)

    @property
    def cors_origin_strings(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.cors_origins]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
