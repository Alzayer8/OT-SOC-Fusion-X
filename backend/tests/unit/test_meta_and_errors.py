from __future__ import annotations

from typing import Any, cast

from fastapi.testclient import TestClient

from app.api.meta import metadata
from app.core.config import Settings


def test_metadata_is_authenticated_and_contains_only_approved_fields(
    client: TestClient, unit_settings: Settings
) -> None:
    response = client.get("/api/v1/meta")

    assert response.status_code == 401

    payload = metadata(unit_settings, cast(Any, None)).model_dump(mode="json")
    assert {
        key: payload[key]
        for key in ("application_name", "application_version", "environment", "api_version")
    } == {
        "application_name": "OT-SOC Fusion X",
        "application_version": "1.0.0",
        "environment": "test",
        "api_version": "v1",
    }
    assert set(payload) == {
        "application_name",
        "application_version",
        "environment",
        "api_version",
        "operating_mode",
        "domain",
        "active_profiles",
        "active_schemas",
    }
    assert payload["operating_mode"] == "SYNTHETIC_OFFLINE"
    assert payload["domain"] == "oil_gas_transfer"
    assert [item["profile_id"] for item in payload["active_profiles"]] == [
        "otsoc.synthetic_modbus.oil_gas_transfer",
        "otsoc.asset_inventory.oil_gas_transfer",
        "otsoc.communication_policy.oil_gas_transfer",
        "otsoc.correlation.oil_gas_transfer",
        "otsoc.incident.oil_gas_transfer",
    ]
    assert len(payload["active_schemas"]) == 7
    assert all(item["version"] for item in payload["active_schemas"])
    assert all(len(item["sha256"]) == 64 for item in payload["active_profiles"])


def test_invalid_route_returns_controlled_response(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["request_id"]
    assert "traceback" not in response.text.lower()


def test_secret_values_do_not_appear_in_responses_or_logs(
    client: TestClient, caplog: object
) -> None:
    secret = "redacted"

    for path in ("/health/live", "/health/ready", "/api/v1/meta", "/invalid"):
        assert secret not in client.get(path).text
    assert secret not in caplog.text
