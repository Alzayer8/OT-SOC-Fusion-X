from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.integration.test_database import integration_settings


@pytest.mark.integration
def test_readiness_succeeds_when_postgres_is_available() -> None:
    with TestClient(create_app(integration_settings())) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "available"}
