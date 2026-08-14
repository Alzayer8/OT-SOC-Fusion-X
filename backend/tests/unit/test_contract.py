from __future__ import annotations

import json

from app.tools.openapi import rendered_contract


def test_openapi_contract_is_deterministic_and_contains_only_approved_paths() -> None:
    first = rendered_contract()
    second = rendered_contract()
    schema = json.loads(first)

    assert first == second
    assert list(schema["paths"]) == [
        "/api/v1/assets",
        "/api/v1/assets/{asset_key}",
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/session",
        "/api/v1/evidence",
        "/api/v1/evidence/{evidence_id}",
        "/api/v1/incident-assignees",
        "/api/v1/incidents",
        "/api/v1/incidents/{incident_id}",
        "/api/v1/incidents/{incident_id}/assignment",
        "/api/v1/incidents/{incident_id}/audit",
        "/api/v1/incidents/{incident_id}/disposition",
        "/api/v1/incidents/{incident_id}/notes",
        "/api/v1/incidents/{incident_id}/report",
        "/api/v1/incidents/{incident_id}/status",
        "/api/v1/lab/baseline",
        "/api/v1/lab/catalog",
        "/api/v1/lab/context",
        "/api/v1/lab/reset",
        "/api/v1/lab/runs",
        "/api/v1/lab/runs/{run_id}",
        "/api/v1/lab/start",
        "/api/v1/meta",
        "/api/v1/overview/summary",
        "/api/v1/replay",
        "/api/v1/users",
        "/api/v1/users/{user_id}",
        "/api/v1/users/{user_id}/password-reset",
        "/health/live",
        "/health/ready",
    ]


def test_openapi_contract_contains_only_approved_domain_schemas() -> None:
    rendered = rendered_contract()
    contract = rendered.lower()
    schema = json.loads(rendered)
    paths = schema["paths"]

    assert "oil_gas_transfer" in contract
    assert "2.0.0" in contract
    assert "heat_exchanger" not in contract
    assert "nuclear" not in contract

    for prohibited in ("execute playbook", "target_ip", "raw_packet", "custom_payload"):
        assert prohibited not in contract

    lab_start = schema["components"]["schemas"]["LabRunStartRequest"]
    assert set(lab_start["properties"]) == {"scenario_id"}
    assert lab_start["additionalProperties"] is False
    scenario_schema = schema["components"]["schemas"]["LabScenarioId"]
    assert scenario_schema["enum"] == ["BASELINE", "S1", "S2", "S3", "S4"]
    assert "x-otsoc-actor-id" not in contract
    assert "x-otsoc-permissions" not in contract

    assert "syntheticmodbusevent" in contract
    assert "protocolsemanticevent" in contract
    assert "assetcontextevent" in contract
    assert "communicationpolicyfinding" in contract
    assert "incidentrecordresponse" in contract
    assert '"ground_truth_used"' in contract
    assert '"const": false' in contract
    for prohibited_path in (
        "/api/v1/policy",
        "/api/v1/protocol",
        "/api/v1/modbus",
        "/api/v1/decode",
        "/api/v1/packet",
        "/api/v1/network",
        "/api/v1/topology",
    ):
        assert all(prohibited_path not in path for path in paths)
