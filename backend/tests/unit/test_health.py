from __future__ import annotations

from fastapi.testclient import TestClient


def test_liveness_returns_typed_response(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "OT-SOC Fusion X",
        "version": "1.0.0",
    }
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Request-ID"]


def test_readiness_fails_safely_when_postgres_is_unavailable(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
    assert "traceback" not in response.text.lower()
    assert "postgresql" not in response.text.lower()
